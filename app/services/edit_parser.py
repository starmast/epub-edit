"""Parser for LLM edit commands."""
import re
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class EditCommand:
    """Base class for edit commands."""

    def __init__(self, line_num: int):
        self.line_num = line_num

    def apply(self, lines: List[str]) -> List[str]:
        """Apply this edit to a list of lines."""
        raise NotImplementedError


class ReplaceCommand(EditCommand):
    """Replace command: R∆line∆pattern⟹replacement"""

    def __init__(self, line_num: int, pattern: str, replacement: str):
        super().__init__(line_num)
        self.pattern = pattern
        self.replacement = replacement

    def apply(self, lines: List[str]) -> List[str]:
        if 0 < self.line_num <= len(lines):
            idx = self.line_num - 1
            lines[idx] = lines[idx].replace(self.pattern, self.replacement)
        else:
            logger.warning(f"Line number {self.line_num} out of range")
        return lines

    def __repr__(self):
        return f"Replace(line={self.line_num}, pattern='{self.pattern[:20]}...', replacement='{self.replacement[:20]}...')"


class DeleteCommand(EditCommand):
    """Delete command: D∆line"""

    def apply(self, lines: List[str]) -> List[str]:
        if 0 < self.line_num <= len(lines):
            idx = self.line_num - 1
            lines[idx] = ""  # Mark for deletion
        else:
            logger.warning(f"Line number {self.line_num} out of range")
        return lines

    def __repr__(self):
        return f"Delete(line={self.line_num})"


class InsertCommand(EditCommand):
    """Insert command: I∆line∆text"""

    def __init__(self, line_num: int, text: str):
        super().__init__(line_num)
        self.text = text

    def apply(self, lines: List[str]) -> List[str]:
        if 0 < self.line_num <= len(lines):
            idx = self.line_num - 1
            # Insert after the specified line
            lines.insert(idx + 1, self.text)
        else:
            logger.warning(f"Line number {self.line_num} out of range")
        return lines

    def __repr__(self):
        return f"Insert(line={self.line_num}, text='{self.text[:20]}...')"


class MergeCommand(EditCommand):
    """Merge command: M∆start-end∆text"""

    def __init__(self, start_line: int, end_line: int, text: str):
        super().__init__(start_line)
        self.start_line = start_line
        self.end_line = end_line
        self.text = text

    def apply(self, lines: List[str]) -> List[str]:
        if 0 < self.start_line <= len(lines) and 0 < self.end_line <= len(lines):
            start_idx = self.start_line - 1
            end_idx = self.end_line - 1

            # Replace range with single line
            lines[start_idx] = self.text
            # Mark other lines for deletion
            for i in range(start_idx + 1, end_idx + 1):
                if i < len(lines):
                    lines[i] = ""
        else:
            logger.warning(
                f"Line range {self.start_line}-{self.end_line} out of range"
            )
        return lines

    def __repr__(self):
        return f"Merge(lines={self.start_line}-{self.end_line}, text='{self.text[:20]}...')"


class EditParser:
    """Parser for edit commands from LLM responses."""

    @staticmethod
    def parse_edits(edit_string: str) -> List[EditCommand]:
        """
        Parse edit commands from LLM response.

        Args:
            edit_string: String containing edit commands

        Returns:
            List of EditCommand objects
        """
        commands = []

        # Check for NO_EDITS_NEEDED response
        if "NO_EDITS_NEEDED" in edit_string.strip():
            logger.info("LLM indicated no edits needed")
            return commands

        # Split by ◊ separator
        edit_parts = edit_string.split("◊")

        for part in edit_parts:
            part = part.strip()
            if not part:
                continue

            try:
                # Replace command: R∆line∆pattern⟹replacement
                if part.startswith("R∆"):
                    match = re.match(r"R∆(\d+)∆(.+?)⟹(.+)", part, re.DOTALL)
                    if match:
                        line_num = int(match.group(1))
                        pattern = match.group(2).strip()
                        replacement = match.group(3).strip()
                        commands.append(ReplaceCommand(line_num, pattern, replacement))
                    else:
                        logger.warning(f"Could not parse replace command: {part}")

                # Delete command: D∆line
                elif part.startswith("D∆"):
                    match = re.match(r"D∆(\d+)", part)
                    if match:
                        line_num = int(match.group(1))
                        commands.append(DeleteCommand(line_num))
                    else:
                        logger.warning(f"Could not parse delete command: {part}")

                # Insert command: I∆line∆text
                elif part.startswith("I∆"):
                    match = re.match(r"I∆(\d+)∆(.+)", part, re.DOTALL)
                    if match:
                        line_num = int(match.group(1))
                        text = match.group(2).strip()
                        commands.append(InsertCommand(line_num, text))
                    else:
                        logger.warning(f"Could not parse insert command: {part}")

                # Merge command: M∆start-end∆text
                elif part.startswith("M∆"):
                    match = re.match(r"M∆(\d+)-(\d+)∆(.+)", part, re.DOTALL)
                    if match:
                        start_line = int(match.group(1))
                        end_line = int(match.group(2))
                        text = match.group(3).strip()
                        commands.append(MergeCommand(start_line, end_line, text))
                    else:
                        logger.warning(f"Could not parse merge command: {part}")

                else:
                    logger.warning(f"Unknown command format: {part}")

            except Exception as e:
                logger.error(f"Error parsing edit command '{part}': {e}")

        return commands

    @staticmethod
    def apply_edits(content: str, commands: List[EditCommand]) -> Tuple[str, Dict]:
        """
        Apply edit commands to content.

        Args:
            content: Original content
            commands: List of edit commands

        Returns:
            Tuple of (edited_content, stats_dict)
        """
        # Split content into lines
        lines = content.split("\n")
        original_line_count = len(lines)

        # Sort commands by line number (descending for inserts/deletes)
        # Actually, we need to be careful with the order
        # For now, apply in the order given

        stats = {
            "total_edits": len(commands),
            "replacements": 0,
            "deletions": 0,
            "insertions": 0,
            "merges": 0,
        }

        # Apply commands
        for command in commands:
            lines = command.apply(lines)

            # Update stats
            if isinstance(command, ReplaceCommand):
                stats["replacements"] += 1
            elif isinstance(command, DeleteCommand):
                stats["deletions"] += 1
            elif isinstance(command, InsertCommand):
                stats["insertions"] += 1
            elif isinstance(command, MergeCommand):
                stats["merges"] += 1

        # Remove empty lines that were marked for deletion
        lines = [line for line in lines if line != "" or line.strip()]

        # Join back
        edited_content = "\n".join(lines)

        stats["original_line_count"] = original_line_count
        stats["edited_line_count"] = len(lines)

        return edited_content, stats

    @staticmethod
    def generate_diff(original: str, edited: str) -> List[Dict]:
        """
        Generate a diff between original and edited content.

        Args:
            original: Original content
            edited: Edited content

        Returns:
            List of diff chunks
        """
        import difflib

        original_lines = original.split("\n")
        edited_lines = edited.split("\n")

        diff = difflib.unified_diff(
            original_lines,
            edited_lines,
            lineterm="",
            n=3,  # Context lines
        )

        # Parse diff into structured format
        diff_chunks = []
        current_chunk = None

        for line in diff:
            if line.startswith("---") or line.startswith("+++"):
                continue
            elif line.startswith("@@"):
                # New chunk
                if current_chunk:
                    diff_chunks.append(current_chunk)
                current_chunk = {"header": line, "changes": []}
            elif current_chunk:
                change_type = "context"
                if line.startswith("-"):
                    change_type = "deletion"
                elif line.startswith("+"):
                    change_type = "addition"

                current_chunk["changes"].append({"type": change_type, "content": line})

        if current_chunk:
            diff_chunks.append(current_chunk)

        return diff_chunks
