#!/usr/bin/env python3
"""Debug script to inspect epub structure."""
import sys
from ebooklib import epub

def inspect_epub(epub_path):
    """Inspect the structure of an epub file."""
    print(f"\n{'='*60}")
    print(f"Inspecting: {epub_path}")
    print(f"{'='*60}\n")

    book = epub.read_epub(epub_path)

    print("METADATA:")
    print(f"  Title: {book.get_metadata('DC', 'title')}")
    print(f"  Author: {book.get_metadata('DC', 'creator')}")
    print()

    print("ALL ITEMS:")
    for i, item in enumerate(book.get_items(), 1):
        print(f"  {i}. Type: {item.get_type()}, File: {item.file_name}, ID: {getattr(item, 'id', 'N/A')}")
    print()

    print("SPINE:")
    print(f"  Length: {len(book.spine)}")
    for i, spine_item in enumerate(book.spine, 1):
        if isinstance(spine_item, tuple):
            item, linear = spine_item
            print(f"  {i}. Item: {item}, Linear: {linear}")
            if hasattr(item, 'file_name'):
                print(f"      File: {item.file_name}")
        else:
            print(f"  {i}. Item: {spine_item}")
            if hasattr(spine_item, 'file_name'):
                print(f"      File: {spine_item.file_name}")
    print()

    print("TABLE OF CONTENTS:")
    print(f"  {book.toc}")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_epub.py <epub_file>")
        sys.exit(1)

    for epub_file in sys.argv[1:]:
        inspect_epub(epub_file)
