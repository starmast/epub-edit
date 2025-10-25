"""LLM service for interacting with OpenAI-compatible APIs."""
import asyncio
import httpx
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM APIs."""

    def __init__(
        self,
        api_endpoint: str,
        api_key: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_retries: int = 3,
    ):
        """
        Initialize LLM service.

        Args:
            api_endpoint: API endpoint URL
            api_key: API key
            model: Model name
            temperature: Temperature for generation
            max_retries: Maximum number of retries on failure
        """
        self.api_endpoint = api_endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

        # Ensure endpoint has the chat completions path
        if not self.api_endpoint.endswith("/chat/completions"):
            self.api_endpoint = f"{self.api_endpoint}/chat/completions"

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Generate completion from LLM.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens in response

        Returns:
            Response dictionary with 'content' and 'usage'

        Raises:
            Exception: If API call fails after retries
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Log request details for debugging
                logger.debug(f"Sending request to {self.api_endpoint}")
                logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        self.api_endpoint,
                        headers=headers,
                        json=payload,
                    )

                    response.raise_for_status()
                    result = response.json()

                    # Extract content and usage
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})

                    return {
                        "content": content,
                        "usage": usage,
                        "model": result.get("model", self.model),
                    }

            except httpx.HTTPStatusError as e:
                error_body = ""
                try:
                    error_body = e.response.text
                except:
                    pass

                logger.error(f"HTTP error on attempt {attempt + 1}: {e.response.status_code} - {error_body}")

                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                elif e.response.status_code >= 500:  # Server error
                    wait_time = 2 ** attempt
                    logger.info(f"Server error, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Client error, don't retry - include response body in error
                    raise Exception(f"Client error {e.response.status_code}: {error_body or str(e)}")

            except (httpx.RequestError, json.JSONDecodeError) as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise

        raise Exception(f"Failed to get completion after {self.max_retries} attempts")

    async def edit_chapters_batch(
        self,
        chapters: List[Dict[str, any]],
        system_prompt: str,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Edit multiple chapters simultaneously for consistency.

        Args:
            chapters: List of chapter dicts with 'number', 'content', and 'title'
            system_prompt: System prompt with editing instructions
            max_tokens: Maximum tokens in response

        Returns:
            Dictionary with edit commands, chapter mapping, and usage stats
        """
        # Build combined content with continuous line numbering
        all_lines = []
        chapter_line_map = {}  # Maps chapter_number -> (start_line, end_line, original_content)
        current_line = 1

        user_message_parts = []

        for chapter in chapters:
            chapter_num = chapter['number']
            content = chapter['content']
            title = chapter.get('title', f'Chapter {chapter_num}')

            lines = content.split('\n')
            start_line = current_line
            end_line = current_line + len(lines) - 1

            chapter_line_map[chapter_num] = {
                'start_line': start_line,
                'end_line': end_line,
                'original_content': content,
                'line_count': len(lines)
            }

            # Add chapter header
            user_message_parts.append(f"\n{'='*3}")
            user_message_parts.append(f"CHAPTER {chapter_num}: {title}")
            user_message_parts.append(f"Lines {start_line}-{end_line}")
            user_message_parts.append(f"{'='*3}\n")

            # Add numbered lines for this chapter
            for i, line in enumerate(lines):
                line_num = start_line + i
                user_message_parts.append(f"{line_num}: {line}")
                all_lines.append(line)

            current_line = end_line + 1

        user_message = '\n'.join(user_message_parts)

        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Get completion
        result = await self.generate_completion(messages, max_tokens)

        return {
            "edits": result["content"],
            "chapter_line_map": chapter_line_map,
            "usage": result["usage"],
            "model": result["model"],
        }


    @staticmethod
    async def test_connection(
        api_endpoint: str, api_key: str, model: str = "gpt-4"
    ) -> Dict:
        """
        Test API connection.

        Args:
            api_endpoint: API endpoint URL
            api_key: API key
            model: Model name to test

        Returns:
            Dictionary with success status and message
        """
        try:
            service = LLMService(api_endpoint, api_key, model)

            messages = [
                {"role": "user", "content": "Respond with 'OK' if you can read this."}
            ]

            result = await service.generate_completion(messages, max_tokens=10)

            return {
                "success": True,
                "message": "Connection successful",
                "model": result.get("model"),
            }

        except Exception as e:
            return {"success": False, "message": str(e)}


class SystemPrompts:
    """Collection of system prompts for different editing styles."""

    DEFAULT = """You are a professional copy editor tasked with improving the text quality of a book.

EDITING GOALS:
1. Fix spelling errors and typos
2. Correct grammatical mistakes
3. Improve sentence flow and readability
4. Ensure consistency in character names, places, and terminology across ALL chapters
5. Maintain narrative continuity and logical flow between chapters
6. Preserve the author's voice, style, and intended meaning
7. DO NOT alter plot points, character actions, or creative choices

MULTI-CHAPTER EDITING:
You will be given MULTIPLE CHAPTERS to edit simultaneously. This allows you to:
- Ensure consistent terminology across chapter boundaries
- Maintain character name spelling consistency
- Preserve narrative continuity between chapters
- Make edits that improve the flow from one chapter to the next

OUTPUT FORMAT - CRITICAL:
Your response must ONLY contain edit commands using these special delimiters. DO NOT include any explanatory text, comments, or conversation.

EDITING COMMANDS:
R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

EXAMPLES OF CORRECT OUTPUT:
R∆5∆teh⟹the◊R∆7∆said quietly⟹whispered◊D∆12
R∆23∆recieve⟹receive◊I∆25∆She took a deep breath.
R∆150∆Jon⟹John◊R∆225∆Jon⟹John
M∆30-32∆The storm raged throughout the night, shaking the windows.

IMPORTANT RULES:
- Your ENTIRE response must be edit commands only - no other text
- Line numbers are 1-indexed and continuous across ALL chapters
- When editing multiple chapters, line numbers continue from one chapter to the next
- Pay special attention to consistency across chapter boundaries
- Only edit lines that need correction
- Provide edits in sequential order by line number
- Be conservative - when in doubt, don't edit
- Focus on objective improvements only
- DO NOT add newlines or line breaks in replacement text - keep all text on a single line
- DO NOT split sentences across multiple lines in your edits
- If no edits are needed for ANY chapter, respond with: NO_EDITS_NEEDED"""

    LIGHT = """You are a professional proofreader focused on minimal corrections.

EDITING GOALS:
1. Fix only obvious spelling errors and typos
2. Correct only clear grammatical mistakes
3. Ensure consistent spelling of character names and places across chapters
4. Preserve the author's voice completely, including stylistic choices

MULTI-CHAPTER EDITING:
You will be given MULTIPLE CHAPTERS to edit simultaneously. Focus on:
- Consistent spelling of names and terms across all chapters
- Clear objective errors only

OUTPUT FORMAT - CRITICAL:
Your response must ONLY contain edit commands using these special delimiters. DO NOT include any explanatory text, comments, or conversation.

EDITING COMMANDS:
R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

EXAMPLES OF CORRECT OUTPUT:
R∆5∆teh⟹the◊R∆23∆recieve⟹receive
R∆150∆Jon⟹John◊R∆225∆Jon⟹John
D∆45◊R∆46∆its⟹it's

IMPORTANT RULES:
- Your ENTIRE response must be edit commands only - no other text
- Line numbers are 1-indexed and continuous across ALL chapters
- When editing multiple chapters, line numbers continue from one chapter to the next
- Be extremely conservative - only fix clear errors, not stylistic preferences
- If no edits are needed, respond with: NO_EDITS_NEEDED"""

    MODERATE = DEFAULT  # Same as default

    HEAVY = """You are a professional editor tasked with comprehensive editing of a book.

EDITING GOALS:
1. Fix all spelling errors and typos
2. Correct grammatical mistakes
3. Improve sentence structure and flow significantly
4. Enhance vocabulary and word choice
5. Improve narrative pacing and clarity
6. Ensure strong consistency across ALL chapters in terminology, character names, and style
7. Improve transitions between chapters
8. Preserve plot points and character actions

MULTI-CHAPTER EDITING:
You will be given MULTIPLE CHAPTERS to edit simultaneously. This allows you to:
- Ensure consistent terminology and character descriptions across chapters
- Improve narrative flow between chapter transitions
- Maintain consistent tone and style throughout
- Fix inconsistencies in character names, places, and terms

OUTPUT FORMAT - CRITICAL:
Your response must ONLY contain edit commands using these special delimiters. DO NOT include any explanatory text, comments, or conversation.

EDITING COMMANDS:
R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

EXAMPLES OF CORRECT OUTPUT:
R∆5∆He said⟹He exclaimed◊R∆7∆walked slowly⟹trudged◊I∆10∆The tension in the room was palpable.
R∆150∆Jon⟹John◊R∆225∆Jon⟹John◊R∆380∆Jon⟹John
M∆15-17∆The storm raged throughout the night, its fury unrelenting as rain lashed against the windows.

IMPORTANT RULES:
- Your ENTIRE response must be edit commands only - no other text
- Line numbers are 1-indexed and continuous across ALL chapters
- When editing multiple chapters, line numbers continue from one chapter to the next
- Pay special attention to consistency across chapter boundaries
- Be thorough in improving quality while preserving the core story
- Provide edits in sequential order by line number
- If no edits are needed, respond with: NO_EDITS_NEEDED"""
