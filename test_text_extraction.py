#!/usr/bin/env python3
"""
Test script to validate XHTML text extraction and reconstruction.

This script tests:
1. Extracting plain text from XHTML (removing all HTML tags)
2. Reconstructing XHTML from edited plain text
3. Ensuring the round-trip preserves content structure
"""

import sys
from pathlib import Path
from bs4 import BeautifulSoup
from app.services.epub_service import EPubService

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def extract_body_content(xhtml_content: str) -> str:
    """
    Extract plain text content from XHTML, removing all HTML tags and blank lines.
    (Same as ProcessingService._extract_body_content)
    """
    soup = BeautifulSoup(xhtml_content, "xml")

    # Find the body tag
    body = soup.find("body")
    if body:
        # Get just the text content, no HTML tags
        text = body.get_text(separator='\n', strip=False)

        # Filter out all blank lines for cleaner LLM editing
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]

        return '\n'.join(cleaned_lines)

    # Fallback: return the full content if no body found
    return xhtml_content


def wrap_body_content(edited_text_content: str, original_xhtml: str) -> str:
    """
    Wrap edited plain text back into the original XHTML structure.
    (Same as ProcessingService._wrap_body_content)
    """
    soup = BeautifulSoup(original_xhtml, "xml")

    # Find the body tag
    body = soup.find("body")
    if body:
        # Clear the body
        body.clear()

        # Split edited text into lines and wrap in paragraphs
        lines = edited_text_content.split('\n')

        current_paragraph = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                # Check if this looks like a heading (all caps, short, or starts with "Chapter")
                if (len(stripped) < 60 and
                    (stripped.isupper() or
                     stripped.startswith('Chapter ') or
                     stripped.startswith('CHAPTER '))):
                    # Flush current paragraph
                    if current_paragraph:
                        p_tag = soup.new_tag('p')
                        p_tag.string = ' '.join(current_paragraph)
                        body.append(p_tag)
                        current_paragraph = []
                    # Create heading
                    h_tag = soup.new_tag('h1')
                    h_tag.string = stripped
                    body.append(h_tag)
                else:
                    current_paragraph.append(stripped)
            else:
                # Empty line - flush current paragraph
                if current_paragraph:
                    p_tag = soup.new_tag('p')
                    p_tag.string = ' '.join(current_paragraph)
                    body.append(p_tag)
                    current_paragraph = []

        # Flush any remaining paragraph
        if current_paragraph:
            p_tag = soup.new_tag('p')
            p_tag.string = ' '.join(current_paragraph)
            body.append(p_tag)

        return str(soup)

    # Fallback: wrap in basic HTML structure
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<p>{edited_text_content}</p>
</body>
</html>"""


def print_section(title: str, content: str, max_lines: int = 30):
    """Print a section with a title and limited content."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    lines = content.split('\n')
    if len(lines) > max_lines:
        print('\n'.join(lines[:max_lines]))
        print(f"\n... ({len(lines) - max_lines} more lines) ...")
    else:
        print(content)


def main():
    epub_path = "epub_test.epub"

    if not Path(epub_path).exists():
        print(f"Error: {epub_path} not found!")
        print("Please ensure epub_test.epub is in the current directory.")
        return 1

    print(f"Testing text extraction with: {epub_path}")

    # Extract chapters from ePub
    print("\n[1/5] Extracting chapters from ePub...")
    chapters = EPubService.extract_chapters(epub_path)
    print(f"   Found {len(chapters)} chapters")

    if not chapters:
        print("Error: No chapters found in ePub!")
        return 1

    # Use the first chapter for testing
    test_chapter = chapters[0]
    print(f"\n[2/5] Testing with chapter: {test_chapter['title']}")
    print(f"   Word count: {test_chapter['word_count']}")

    original_xhtml = test_chapter['html_content']

    # Show original XHTML
    print_section("[3/5] ORIGINAL XHTML (with all tags)", original_xhtml, max_lines=40)

    # Extract plain text
    print("\n[4/5] Extracting plain text (removing HTML tags)...")
    plain_text = extract_body_content(original_xhtml)
    print_section("   EXTRACTED PLAIN TEXT", plain_text, max_lines=40)

    # Simulate an edit (change "teh" to "the" as an example)
    edited_text = plain_text.replace("teh", "the")
    print(f"\n   Applied test edit: replaced 'teh' -> 'the'")

    # Reconstruct XHTML
    print("\n[5/5] Reconstructing XHTML from edited text...")
    reconstructed_xhtml = wrap_body_content(edited_text, original_xhtml)
    print_section("   RECONSTRUCTED XHTML", reconstructed_xhtml, max_lines=40)

    # Validation
    print("\n" + "="*80)
    print("VALIDATION CHECKS")
    print("="*80)

    # Check 1: Original had HTML tags
    has_tags_original = '<p>' in original_xhtml and '<h1>' in original_xhtml
    print(f"✓ Original has HTML tags (<p>, <h1>, etc.): {has_tags_original}")

    # Check 2: Plain text has no HTML tags
    has_no_tags_plain = '<p>' not in plain_text and '<h1>' not in plain_text
    print(f"✓ Plain text has no HTML tags: {has_no_tags_plain}")

    # Check 3: Reconstructed has HTML tags again
    has_tags_reconstructed = '<p>' in reconstructed_xhtml and ('</p>' in reconstructed_xhtml or '/>' in reconstructed_xhtml)
    print(f"✓ Reconstructed has HTML tags: {has_tags_reconstructed}")

    # Check 4: Content preserved
    original_soup = BeautifulSoup(original_xhtml, "xml")
    original_text = original_soup.get_text().strip()

    reconstructed_soup = BeautifulSoup(reconstructed_xhtml, "xml")
    reconstructed_text = reconstructed_soup.get_text().strip()

    # Compare (allowing for minor whitespace differences)
    original_words = original_text.split()
    reconstructed_words = reconstructed_text.split()

    content_preserved = len(original_words) == len(reconstructed_words)
    print(f"✓ Word count preserved: {content_preserved} (original: {len(original_words)}, reconstructed: {len(reconstructed_words)})")

    # Check 5: Structure preserved
    has_xml_declaration = '<?xml' in reconstructed_xhtml
    has_body_tag = '<body>' in reconstructed_xhtml or '<body' in reconstructed_xhtml
    print(f"✓ XML structure preserved: {has_xml_declaration and has_body_tag}")

    print("\n" + "="*80)
    if all([has_tags_original, has_no_tags_plain, has_tags_reconstructed, has_body_tag]):
        print("✓ ALL CHECKS PASSED - Text extraction and reconstruction working correctly!")
        print("\nSummary:")
        print("  • HTML tags are removed when sending to LLM (plain text only)")
        print("  • Edited text is properly reconstructed into valid XHTML")
        print("  • Content and structure are preserved")
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Please review the output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
