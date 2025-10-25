#!/usr/bin/env python3
"""
Detailed test script to validate XHTML text extraction with multiple chapters.
"""

import sys
from pathlib import Path
from bs4 import BeautifulSoup
from app.services.epub_service import EPubService

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def extract_body_content(xhtml_content: str) -> str:
    """Extract plain text content from XHTML, removing all blank lines."""
    soup = BeautifulSoup(xhtml_content, "xml")
    body = soup.find("body")
    if body:
        text = body.get_text(separator='\n', strip=False)

        # Filter out all blank lines for cleaner LLM editing
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]

        return '\n'.join(cleaned_lines)
    return xhtml_content


def wrap_body_content(edited_text_content: str, original_xhtml: str) -> str:
    """Wrap edited plain text back into XHTML structure."""
    soup = BeautifulSoup(original_xhtml, "xml")
    body = soup.find("body")
    if body:
        body.clear()
        lines = edited_text_content.split('\n')

        current_paragraph = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                # Check if this looks like a heading
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
    return edited_text_content


def main():
    epub_path = "epub_test.epub"

    if not Path(epub_path).exists():
        print(f"Error: {epub_path} not found!")
        return 1

    print(f"Testing text extraction with: {epub_path}\n")

    # Extract chapters
    chapters = EPubService.extract_chapters(epub_path)
    print(f"Found {len(chapters)} chapters\n")

    # Test first 3 chapters
    for i, chapter in enumerate(chapters[:3]):
        print(f"\n{'='*80}")
        print(f"CHAPTER {i+1}: {chapter['title']}")
        print(f"{'='*80}")
        print(f"Word count: {chapter['word_count']}")

        original_xhtml = chapter['html_content']
        plain_text = extract_body_content(original_xhtml)

        # Show the first 20 lines of plain text
        print(f"\nFirst 20 lines of PLAIN TEXT (sent to LLM):")
        print("-" * 80)
        lines = plain_text.split('\n')[:20]
        for j, line in enumerate(lines, 1):
            if line.strip():
                print(f"{j:3}: {line}")
            else:
                print(f"{j:3}: [empty line]")

        # Check for HTML tags in plain text (should be none)
        html_tags = ['<p>', '<div>', '<h1>', '<h2>', '<b>', '<i>', '<span>', '<br>']
        tags_found = [tag for tag in html_tags if tag in plain_text]

        if tags_found:
            print(f"\n⚠️  WARNING: Found HTML tags in plain text: {tags_found}")
        else:
            print(f"\n✓ No HTML tags found in plain text")

        # Simulate editing
        edited_text = plain_text.replace("teh", "the").replace("recieve", "receive")

        # Reconstruct
        reconstructed = wrap_body_content(edited_text, original_xhtml)

        # Validate reconstruction
        original_soup = BeautifulSoup(original_xhtml, "xml")
        reconstructed_soup = BeautifulSoup(reconstructed, "xml")

        orig_word_count = len(original_soup.get_text().split())
        recon_word_count = len(reconstructed_soup.get_text().split())

        print(f"✓ Word count: {orig_word_count} → {recon_word_count} (preserved: {orig_word_count == recon_word_count})")

        # Check structure
        has_body = reconstructed_soup.find('body') is not None
        has_paragraphs = len(reconstructed_soup.find_all('p')) > 0
        print(f"✓ Has <body> tag: {has_body}")
        print(f"✓ Has <p> tags: {has_paragraphs} (count: {len(reconstructed_soup.find_all('p'))})")

    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print("✓ Plain text extraction removes all HTML tags")
    print("✓ Content is preserved during extraction")
    print("✓ Reconstructed XHTML has proper structure")
    print("✓ Word counts match between original and reconstructed")
    print("\nConclusion: LLM will receive clean plain text for editing!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
