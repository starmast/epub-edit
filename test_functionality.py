#!/usr/bin/env python3
"""
Comprehensive test script for ePub Editor functionality.
Tests everything except actual LLM API calls.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.database import init_db, async_session_maker
from app.models.models import Project, Chapter, ProcessingJob
from app.services.epub_service import EPubService
from app.services.token_service import TokenService
from app.services.edit_parser import EditParser
from app.utils.file_manager import FileManager
from app.utils.encryption import encrypt_api_key, decrypt_api_key


class TestRunner:
    def __init__(self):
        self.results = []
        self.test_epub_path = Path("epub_test.epub")
        self.project_id = None

    def log(self, message: str, level: str = "INFO"):
        """Log test messages."""
        color_codes = {
            "INFO": "\033[94m",  # Blue
            "SUCCESS": "\033[92m",  # Green
            "ERROR": "\033[91m",  # Red
            "WARNING": "\033[93m",  # Yellow
        }
        reset = "\033[0m"
        print(f"{color_codes.get(level, '')}{level}: {message}{reset}")

    def test_result(self, test_name: str, passed: bool, details: str = ""):
        """Record test result."""
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.log(f"✓ {test_name}", "SUCCESS")
            if details:
                self.log(f"  {details}", "INFO")
        else:
            self.log(f"✗ {test_name}", "ERROR")
            if details:
                self.log(f"  {details}", "ERROR")

    async def test_1_database_initialization(self):
        """Test 1: Database initialization."""
        self.log("\n=== Test 1: Database Initialization ===", "INFO")
        try:
            await init_db()
            self.test_result("Database initialization", True, "Database initialized successfully")
        except Exception as e:
            self.test_result("Database initialization", False, str(e))
            raise

    async def test_2_epub_validation(self):
        """Test 2: ePub file validation."""
        self.log("\n=== Test 2: ePub File Validation ===", "INFO")
        try:
            if not self.test_epub_path.exists():
                raise FileNotFoundError(f"Test ePub not found: {self.test_epub_path}")

            size_mb = self.test_epub_path.stat().st_size / (1024 * 1024)
            self.test_result("ePub file exists", True, f"File size: {size_mb:.2f} MB")

            # Validate it's a valid ePub
            epub_service = EPubService()
            metadata = epub_service.extract_metadata(str(self.test_epub_path))

            self.test_result("ePub metadata extraction", True,
                           f"Title: {metadata.get('title', 'N/A')}, "
                           f"Author: {metadata.get('author', 'N/A')}")

            return metadata

        except Exception as e:
            self.test_result("ePub file validation", False, str(e))
            raise

    async def test_3_project_creation(self, metadata: Dict[str, Any]):
        """Test 3: Project creation in database."""
        self.log("\n=== Test 3: Project Creation ===", "INFO")
        try:
            async with async_session_maker() as db:
                # Create project
                project = Project(
                    name=metadata.get('title', 'Test Book'),
                    original_file_path=str(self.test_epub_path),
                    metadata=json.dumps(metadata),
                    processing_status="idle",
                    llm_settings=json.dumps({
                        "endpoint": "https://api.openai.com/v1",
                        "model": "gpt-4",
                        "max_tokens": 4096,
                        "editing_style": "moderate"
                    })
                )
                db.add(project)
                await db.commit()
                await db.refresh(project)

                self.project_id = project.id
                self.test_result("Project creation", True, f"Project ID: {project.id}")

                return project

        except Exception as e:
            self.test_result("Project creation", False, str(e))
            raise

    async def test_4_chapter_extraction(self):
        """Test 4: Extract chapters from ePub."""
        self.log("\n=== Test 4: Chapter Extraction ===", "INFO")
        try:
            epub_service = EPubService()
            file_manager = FileManager()

            # Extract chapters
            chapters = epub_service.extract_chapters(str(self.test_epub_path))

            self.test_result("Chapter extraction", True,
                           f"Extracted {len(chapters)} chapters")

            # Save chapters to filesystem and database
            async with async_session_maker() as db:
                for chapter_data in chapters:
                    # Save chapter content to filesystem
                    chapter_path = file_manager.save_chapter_content(
                        self.project_id,
                        chapter_data['chapter_number'],
                        chapter_data['html_content']
                    )

                    # Create database entry
                    chapter = Chapter(
                        project_id=self.project_id,
                        chapter_number=chapter_data['chapter_number'],
                        title=chapter_data.get('title', f'Chapter {chapter_data["chapter_number"]}'),
                        original_content_path=str(chapter_path),
                        processing_status='not_started',
                        token_count=0  # Will be calculated in next test
                    )
                    db.add(chapter)

                await db.commit()

                self.test_result("Chapter database storage", True,
                               f"Stored {len(chapters)} chapters in database")

            return chapters

        except Exception as e:
            self.test_result("Chapter extraction", False, str(e))
            raise

    async def test_5_token_counting(self, chapters):
        """Test 5: Token counting for chapters."""
        self.log("\n=== Test 5: Token Counting ===", "INFO")
        try:
            # Try to use tiktoken, fallback to word-based approximation
            try:
                token_service = TokenService()
                use_tiktoken = True
            except Exception as e:
                self.log(f"  Tiktoken unavailable ({str(e)[:50]}), using word approximation", "WARNING")
                use_tiktoken = False

            total_tokens = 0
            for chapter_data in chapters:
                # Use text content directly from extraction
                content = chapter_data.get('text_content', '')

                # Count tokens
                if use_tiktoken:
                    tokens = token_service.count_tokens(content)
                else:
                    # Rough approximation: 1 token ≈ 0.75 words
                    words = len(content.split())
                    tokens = int(words / 0.75)

                total_tokens += tokens

                self.log(f"  Chapter {chapter_data.get('title', 'N/A')}: {tokens} tokens", "INFO")

            method = "tiktoken" if use_tiktoken else "word approximation"
            self.test_result("Token counting", True,
                           f"Total tokens: {total_tokens} (using {method})")

            return total_tokens

        except Exception as e:
            self.test_result("Token counting", False, str(e))
            raise

    async def test_6_edit_parser(self):
        """Test 6: Edit parser with mock LLM responses."""
        self.log("\n=== Test 6: Edit Parser ===", "INFO")
        try:
            edit_parser = EditParser()

            # Test sample text
            original_text = """Line 1: The quick brown fox jumps over the lazy dog.
Line 2: She sells sea shells by the sea shore.
Line 3: How much wood would a woodchuck chuck?
Line 4: Peter Piper picked a peck of pickled peppers.
Line 5: A simple sentence."""

            # Test various edit commands
            test_cases = [
                {
                    "name": "Replace edit",
                    "edit": "R∆1∆brown⟹red",
                    "expected_changes": 1
                },
                {
                    "name": "Delete edit",
                    "edit": "D∆5",
                    "expected_changes": 1
                },
                {
                    "name": "Insert edit",
                    "edit": "I∆3∆This is an inserted line.",
                    "expected_changes": 1
                },
                {
                    "name": "Multiple edits",
                    "edit": "R∆1∆quick⟹slow◊R∆2∆sea shells⟹seashells◊D∆5",
                    "expected_changes": 3
                },
                {
                    "name": "Merge edit",
                    "edit": "M∆2-3∆She sells seashells by the seashore.",
                    "expected_changes": 1
                }
            ]

            for test_case in test_cases:
                try:
                    edits = edit_parser.parse_edits(test_case["edit"])
                    if len(edits) == test_case["expected_changes"]:
                        self.test_result(f"Edit parser - {test_case['name']}", True,
                                       f"Parsed {len(edits)} edit(s)")
                    else:
                        self.test_result(f"Edit parser - {test_case['name']}", False,
                                       f"Expected {test_case['expected_changes']}, got {len(edits)}")
                except Exception as e:
                    self.test_result(f"Edit parser - {test_case['name']}", False, str(e))

        except Exception as e:
            self.test_result("Edit parser", False, str(e))
            raise

    async def test_7_apply_edits(self):
        """Test 7: Apply parsed edits to text."""
        self.log("\n=== Test 7: Apply Edits ===", "INFO")
        try:
            edit_parser = EditParser()

            original_text = """The quick brown fox jumps over the lazy dog.
She sells sea shells by the sea shore.
How much wood would a woodchuck chuck?
Peter Piper picked a peck of pickled peppers.
A simple sentence."""

            # Test replace
            edit = "R∆1∆brown⟹red"
            edits = edit_parser.parse_edits(edit)
            result_text, stats = edit_parser.apply_edits(original_text, edits)

            if "red fox" in result_text and "brown" not in result_text:
                self.test_result("Apply replace edit", True, f"Replaced 1 occurrence")
            else:
                self.test_result("Apply replace edit", False, f"Result doesn't contain expected text")

            # Test delete
            edit = "D∆5"
            edits = edit_parser.parse_edits(edit)
            result_text, stats = edit_parser.apply_edits(original_text, edits)
            result_lines = [line for line in result_text.split("\n") if line.strip()]

            if len(result_lines) == 4:
                self.test_result("Apply delete edit", True, f"Deleted 1 line, {stats['deletions']} deletion(s)")
            else:
                self.test_result("Apply delete edit", False, f"Expected 4 lines, got {len(result_lines)}")

            # Test insert
            edit = "I∆2∆Inserted line here."
            edits = edit_parser.parse_edits(edit)
            result_text, stats = edit_parser.apply_edits(original_text, edits)
            result_lines = result_text.split("\n")

            if "Inserted line here" in result_text and stats['insertions'] == 1:
                self.test_result("Apply insert edit", True, f"Inserted 1 line")
            else:
                self.test_result("Apply insert edit", False, f"Insert failed")

        except Exception as e:
            self.test_result("Apply edits", False, str(e))
            raise

    async def test_8_diff_generation(self):
        """Test 8: Generate diff between original and edited text."""
        self.log("\n=== Test 8: Diff Generation ===", "INFO")
        try:
            import difflib

            original = [
                "The quick brown fox",
                "jumps over the lazy dog.",
                "This is a test."
            ]

            edited = [
                "The quick red fox",
                "jumps over the lazy cat.",
                "This is a test."
            ]

            # Generate diff
            differ = difflib.Differ()
            diff = list(differ.compare(original, edited))

            changes_found = any(line.startswith('-') or line.startswith('+')
                              for line in diff)

            if changes_found:
                self.test_result("Diff generation", True,
                               f"Generated diff with {len(diff)} lines")
            else:
                self.test_result("Diff generation", False, "No changes detected in diff")

        except Exception as e:
            self.test_result("Diff generation", False, str(e))
            raise

    async def test_9_encryption(self):
        """Test 9: API key encryption/decryption."""
        self.log("\n=== Test 9: API Key Encryption ===", "INFO")
        try:
            test_key = "sk-test-api-key-12345"

            # Encrypt
            encrypted = encrypt_api_key(test_key)
            self.test_result("API key encryption", True,
                           f"Encrypted length: {len(encrypted)}")

            # Decrypt
            decrypted = decrypt_api_key(encrypted)

            if decrypted == test_key:
                self.test_result("API key decryption", True, "Key decrypted correctly")
            else:
                self.test_result("API key decryption", False,
                               f"Expected '{test_key}', got '{decrypted}'")

        except Exception as e:
            self.test_result("API key encryption", False, str(e))
            raise

    async def test_10_file_manager(self):
        """Test 10: File manager operations."""
        self.log("\n=== Test 10: File Manager ===", "INFO")
        try:
            file_manager = FileManager()

            # Test project directory creation
            project_dir = file_manager.get_project_dir(999)
            if project_dir.exists():
                self.test_result("Project directory creation", True,
                               f"Directory: {project_dir}")
            else:
                self.test_result("Project directory creation", False,
                               "Directory not created")

            # Test chapter content saving
            test_content = "<html><body><p>Test chapter content</p></body></html>"
            chapter_path_str = file_manager.save_chapter_content(999, 1, test_content)
            chapter_path = Path(chapter_path_str)

            if chapter_path.exists():
                with open(chapter_path, 'r', encoding='utf-8') as f:
                    saved_content = f.read()
                if saved_content == test_content:
                    self.test_result("Chapter content saving", True,
                                   f"Saved to: {chapter_path}")
                else:
                    self.test_result("Chapter content saving", False,
                                   "Content mismatch")
            else:
                self.test_result("Chapter content saving", False,
                               "File not created")

            # Test edits saving
            test_edits = {"edits": ["R∆1∆test⟹example"], "applied": False}
            edits_path_str = file_manager.save_chapter_edits(999, 1, test_edits)
            edits_path = Path(edits_path_str)

            if edits_path.exists():
                with open(edits_path, 'r', encoding='utf-8') as f:
                    saved_edits = json.load(f)
                if saved_edits == test_edits:
                    self.test_result("Chapter edits saving", True,
                                   f"Saved to: {edits_path}")
                else:
                    self.test_result("Chapter edits saving", False,
                                   "Edits mismatch")
            else:
                self.test_result("Chapter edits saving", False,
                               "File not created")

        except Exception as e:
            self.test_result("File manager operations", False, str(e))
            raise

    async def test_11_epub_export_preparation(self):
        """Test 11: ePub export preparation (without actual LLM edits)."""
        self.log("\n=== Test 11: ePub Export Preparation ===", "INFO")
        try:
            if not self.project_id:
                self.test_result("Export preparation", False,
                               "No project ID available")
                return

            epub_service = EPubService()
            file_manager = FileManager()

            # Get project and chapters from database
            async with async_session_maker() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(Project).where(Project.id == self.project_id)
                )
                project = result.scalar_one_or_none()

                if not project:
                    self.test_result("Export preparation", False,
                                   "Project not found in database")
                    return

                result = await db.execute(
                    select(Chapter).where(Chapter.project_id == self.project_id)
                    .order_by(Chapter.chapter_number)
                )
                chapters = result.scalars().all()

                self.test_result("Export data retrieval", True,
                               f"Retrieved project and {len(chapters)} chapters")

            # Verify original chapter files exist
            missing_files = []
            for chapter in chapters:
                if chapter.original_content_path:
                    path = Path(chapter.original_content_path)
                    if not path.exists():
                        missing_files.append(chapter.original_content_path)

            if missing_files:
                self.test_result("Chapter files verification", False,
                               f"Missing {len(missing_files)} files")
            else:
                self.test_result("Chapter files verification", True,
                               f"All {len(chapters)} chapter files exist")

        except Exception as e:
            self.test_result("Export preparation", False, str(e))
            raise

    def print_summary(self):
        """Print test summary."""
        self.log("\n" + "="*60, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("="*60, "INFO")

        passed = sum(1 for r in self.results if r['passed'])
        total = len(self.results)
        percentage = (passed / total * 100) if total > 0 else 0

        self.log(f"\nTotal Tests: {total}", "INFO")
        self.log(f"Passed: {passed}", "SUCCESS")
        self.log(f"Failed: {total - passed}", "ERROR" if passed < total else "INFO")
        self.log(f"Success Rate: {percentage:.1f}%",
                "SUCCESS" if percentage == 100 else "WARNING")

        if passed < total:
            self.log("\nFailed Tests:", "ERROR")
            for result in self.results:
                if not result['passed']:
                    self.log(f"  - {result['test']}: {result['details']}", "ERROR")

        self.log("\n" + "="*60 + "\n", "INFO")

        return passed == total

    async def run_all_tests(self):
        """Run all tests in sequence."""
        try:
            # Database and file system tests
            await self.test_1_database_initialization()
            metadata = await self.test_2_epub_validation()
            project = await self.test_3_project_creation(metadata)
            chapters = await self.test_4_chapter_extraction()
            await self.test_5_token_counting(chapters)

            # Parsing and editing tests
            await self.test_6_edit_parser()
            await self.test_7_apply_edits()
            await self.test_8_diff_generation()

            # Utility tests
            await self.test_9_encryption()
            await self.test_10_file_manager()

            # Export tests
            await self.test_11_epub_export_preparation()

            # Print summary
            all_passed = self.print_summary()

            return 0 if all_passed else 1

        except Exception as e:
            self.log(f"\nCritical error during testing: {e}", "ERROR")
            self.print_summary()
            return 1


async def main():
    """Main test runner."""
    runner = TestRunner()
    exit_code = await runner.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
