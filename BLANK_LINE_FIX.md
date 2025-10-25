# Fix: Blank Line Filtering for Accurate Diff Comparison

## Problem

When storing `original_lines` and `edited_lines` for diff viewing, blank lines in the original caused misalignment:

```json
"original_lines": [
  "Information",
  "",                    // ← Empty line
  "Table of Contents URL:",
  "..."
]

"edited_lines": [
  "Information",
  "Table of Contents URL:",  // ← No empty line, shifted
  "..."
]
```

This made line 2 in original (empty) compare to line 2 in edited (actual content), showing false differences.

## Solution

**Filter blank lines BEFORE sending to LLM** instead of after applying edits.

### Implementation

Updated `_extract_body_content()` in `app/services/processing_service.py`:

```python
# Old: Kept single blank lines between paragraphs
consecutive_blank = 0
if stripped:
    cleaned_lines.append(stripped)
    consecutive_blank = 0
else:
    consecutive_blank += 1
    if consecutive_blank == 1:
        cleaned_lines.append('')  # Keep one blank

# New: Remove ALL blank lines
cleaned_lines = [line.strip() for line in lines if line.strip()]
```

### Flow

1. **Extract** plain text from XHTML → filters out ALL blank lines
2. **Send** to LLM with numbered lines (no blanks)
3. **LLM returns** edit commands with line numbers matching no-blank content
4. **Apply edits** with matching line numbers ✅
5. **Save** `original_lines` and `edited_lines` (both without blanks)
6. **Diff viewer** compares line-by-line perfectly ✅

### Files Modified

- `app/services/processing_service.py:527-553` - Updated `_extract_body_content()`
- `app/services/processing_service.py:455-460` - Removed post-edit filtering
- `app/routers/chapters.py:183-188` - Removed post-extraction filtering
- `test_text_extraction.py:21-41` - Updated test function
- `test_text_extraction_detailed.py:16-28` - Updated test function

## Result

✅ Line numbers in edit commands match the content  
✅ `original_lines` and `edited_lines` align perfectly  
✅ Diff viewer shows accurate line-by-line comparison  
✅ Blank lines preserved in `original_xhtml` for proper export reconstruction

## Example

**Before (broken):**
```
Line 1 (original): "Information"     → Line 1 (edited): "Information"      ✅
Line 2 (original): ""                → Line 2 (edited): "Table of..."     ❌ FALSE DIFF
Line 3 (original): "Table of..."    → Line 3 (edited): "https://..."     ❌ FALSE DIFF
```

**After (fixed):**
```
Line 1 (original): "Information"     → Line 1 (edited): "Information"      ✅
Line 2 (original): "Table of..."    → Line 2 (edited): "Table of..."     ✅
Line 3 (original): "https://..."    → Line 3 (edited): "https://..."     ✅
```
