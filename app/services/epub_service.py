"""ePub processing service."""
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import re
from pathlib import Path


class EPubService:
    """Service for extracting and processing ePub files."""

    @staticmethod
    def extract_metadata(epub_path: str) -> Dict:
        """
        Extract metadata from an ePub file.

        Args:
            epub_path: Path to the ePub file

        Returns:
            Dictionary containing metadata
        """
        book = epub.read_epub(epub_path)

        metadata = {
            "title": book.get_metadata("DC", "title")[0][0]
            if book.get_metadata("DC", "title")
            else "Unknown",
            "author": book.get_metadata("DC", "creator")[0][0]
            if book.get_metadata("DC", "creator")
            else "Unknown",
            "language": book.get_metadata("DC", "language")[0][0]
            if book.get_metadata("DC", "language")
            else "en",
            "publisher": book.get_metadata("DC", "publisher")[0][0]
            if book.get_metadata("DC", "publisher")
            else None,
            "publication_date": book.get_metadata("DC", "date")[0][0]
            if book.get_metadata("DC", "date")
            else None,
            "identifier": book.get_metadata("DC", "identifier")[0][0]
            if book.get_metadata("DC", "identifier")
            else None,
        }

        return metadata

    @staticmethod
    def extract_chapters(epub_path: str) -> List[Dict]:
        """
        Extract chapters from an ePub file.

        Args:
            epub_path: Path to the ePub file

        Returns:
            List of dictionaries containing chapter information
        """
        book = epub.read_epub(epub_path)
        chapters = []
        chapter_num = 1

        # Get items that are document type (chapters)
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Extract content
                content = item.get_content()
                soup = BeautifulSoup(content, "xml")

                # Try to extract title from h1, h2, or title tag
                title = None
                for tag in ["h1", "h2", "h3", "title"]:
                    title_tag = soup.find(tag)
                    if title_tag:
                        title = title_tag.get_text().strip()
                        break

                if not title:
                    title = f"Chapter {chapter_num}"

                # Get text content
                text_content = soup.get_text()

                # Clean up whitespace
                text_content = re.sub(r"\n\s*\n", "\n\n", text_content)
                text_content = text_content.strip()

                # Skip if content is too short (probably not a real chapter)
                if len(text_content) < 100:
                    continue

                # Get HTML content (cleaned)
                html_content = str(soup)

                chapters.append(
                    {
                        "chapter_number": chapter_num,
                        "title": title,
                        "html_content": html_content,
                        "text_content": text_content,
                        "word_count": len(text_content.split()),
                    }
                )

                chapter_num += 1

        return chapters

    @staticmethod
    def clean_html(html_content: str) -> str:
        """
        Clean and normalize HTML content.

        Args:
            html_content: Raw HTML content

        Returns:
            Cleaned HTML content
        """
        soup = BeautifulSoup(html_content, "xml")

        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()

        # Get text and preserve basic structure
        return str(soup)

    @staticmethod
    def extract_text_with_line_numbers(html_content: str) -> List[Tuple[int, str]]:
        """
        Extract text from HTML with line numbers.

        Args:
            html_content: HTML content

        Returns:
            List of tuples (line_number, text)
        """
        soup = BeautifulSoup(html_content, "xml")
        text = soup.get_text()

        # Split into lines and add line numbers
        lines = text.split("\n")
        numbered_lines = [
            (i + 1, line.strip()) for i, line in enumerate(lines) if line.strip()
        ]

        return numbered_lines

    @staticmethod
    def reassemble_epub(
        original_epub_path: str,
        output_epub_path: str,
        edited_chapters: Dict[int, str],
    ) -> str:
        """
        Reassemble an ePub with edited chapters.

        Args:
            original_epub_path: Path to original ePub
            output_epub_path: Path for output ePub
            edited_chapters: Dictionary mapping chapter numbers to edited HTML content

        Returns:
            Path to the created ePub file
        """
        # Read original book
        book = epub.read_epub(original_epub_path)

        # Create new book with same metadata
        new_book = epub.EpubBook()

        # Copy metadata
        for meta_type in ["DC", "OPF"]:
            for meta_name, meta_value in book.metadata.get(meta_type, {}).items():
                for value in meta_value:
                    if isinstance(value, tuple):
                        new_book.add_metadata(meta_type, meta_name, value[0], value[1] if len(value) > 1 else {})
                    else:
                        new_book.add_metadata(meta_type, meta_name, value)

        # Process items
        chapter_num = 1
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Check if we have edited content for this chapter
                if chapter_num in edited_chapters:
                    # Create new chapter with edited content
                    new_chapter = epub.EpubHtml(
                        title=item.title or f"Chapter {chapter_num}",
                        file_name=item.file_name,
                        lang=item.lang or "en",
                    )
                    new_chapter.set_content(edited_chapters[chapter_num].encode("utf-8"))
                    new_book.add_item(new_chapter)
                else:
                    # Keep original
                    new_book.add_item(item)

                chapter_num += 1
            else:
                # Copy non-chapter items (CSS, images, etc.)
                new_book.add_item(item)

        # Copy spine
        new_book.spine = book.spine

        # Copy table of contents
        new_book.toc = book.toc

        # Write the ePub
        epub.write_epub(output_epub_path, new_book)

        return output_epub_path
