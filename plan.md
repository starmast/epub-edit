# Improved Instructions for Building an ePub Book Editor Web Application with LLM Integration

## Project Overview
Build a Python web application that leverages Large Language Models (LLMs) to automatically edit ePub books, focusing on improving spelling, grammar, and narrative continuity while preserving the original meaning and author's voice.

## Technology Stack
- **Backend**: FastAPI (Python)
- **Frontend**: Vanilla HTML, CSS (Tailwind CSS), JavaScript (no NPM/build tools)
- **Database**: SQLite for metadata and settings
- **File Storage**: JSON files for chapter edits
- **Real-time Communication**: WebSockets for processing feedback
- **Token Counting**: tiktoken library
- **ePub Processing**: ebooklib or similar Python library
- **Text Diffing**: difflib or similar for visualization

## Architecture & Data Model

### Database Schema (SQLite)
```sql
-- Projects table
projects:
  - id (INTEGER PRIMARY KEY)
  - name (TEXT)
  - original_file_path (TEXT)
  - metadata (JSON) -- title, author, language, etc.
  - created_at (TIMESTAMP)
  - updated_at (TIMESTAMP)
  - processing_status (TEXT) -- idle, processing, paused, completed
  - llm_settings (JSON) -- endpoint, api_key, model, max_tokens

-- Chapters table
chapters:
  - id (INTEGER PRIMARY KEY)
  - project_id (INTEGER FOREIGN KEY)
  - chapter_number (INTEGER)
  - title (TEXT)
  - original_content_path (TEXT)
  - edited_content_path (TEXT)
  - processing_status (TEXT) -- not_started, queued, in_progress, completed, failed
  - error_message (TEXT)
  - token_count (INTEGER)
  - processed_at (TIMESTAMP)

-- Processing jobs table
processing_jobs:
  - id (INTEGER PRIMARY KEY)
  - project_id (INTEGER FOREIGN KEY)
  - start_chapter (INTEGER)
  - end_chapter (INTEGER)
  - worker_count (INTEGER)
  - started_at (TIMESTAMP)
  - completed_at (TIMESTAMP)
  - status (TEXT)
```

### File Structure
```
/data
  /projects
    /{project_id}
      /original
        - book.epub
        /chapters
          - chapter_001.html
          - chapter_002.html
      /edits
        - chapter_001_edits.json
        - chapter_002_edits.json
      /output
        - edited_book.epub
```

## Detailed Workflow Implementation

### Phase 1: Project Creation & Book Upload
1. **Upload Interface**
   - Single file upload (`.epub` format validation)
   - Create new project with auto-generated UUID
   - Store original ePub in project directory
   - Extract and validate ePub structure

2. **Initial Processing**
   ```python
   # Extract metadata
   - Book title, author(s), publisher
   - Language, publication date
   - Total chapter count
   - Table of contents structure
   
   # Process chapters
   - Extract HTML content from each chapter
   - Clean and normalize HTML (preserve semantic structure)
   - Extract text with line numbers and paragraph grouping
   - Calculate token count per chapter using tiktoken
   - Store processed chapters as individual files
   ```

### Phase 2: Project Dashboard

#### Summary Section
- Display book metadata prominently
- Show total chapters, estimated processing time
- Display overall processing progress (percentage, time elapsed)
- Current processing status with visual indicator

#### LLM Configuration Panel
```
Fields:
- API Endpoint URL (e.g., https://api.openai.com/v1)
- API Key (masked input, stored encrypted)
- Model Selection (dropdown with common models)
- Max Context Tokens (with preset suggestions based on model)
- Temperature (0.0-1.0, default: 0.3 for consistency)
- System Prompt Template (expandable text area with preview)
```

#### Chapter Management Grid
```
Columns:
- Chapter # | Title | Word Count | Token Count | Status | Actions
- Color-coded status indicators:
  - Gray: Not Started
  - Yellow: Queued
  - Blue (animated): In Progress
  - Green: Completed
  - Red: Failed
  - Orange: Needs Review
- Actions: View Original | View Diff | Retry | Skip
```

### Phase 3: Processing Configuration & Execution

#### Processing Settings Dialog
```
Parameters:
- Chapter Range: Start [___] End [___] 
- Parallel Workers: [slider 1-10, default: 3]
- Batch Strategy: 
  □ Maximize context usage (fit multiple chapters)
  □ One chapter per request (simpler)
- Error Handling:
  □ Auto-retry failed chapters (max 3 attempts)
  □ Continue on errors
  □ Pause on errors
- Processing Order:
  ○ Sequential
  ○ Priority (process shorter chapters first)
```

#### Enhanced System Prompt
```python
SYSTEM_PROMPT = """
You are a professional copy editor tasked with improving the text quality of a book chapter.

EDITING GOALS:
1. Fix spelling errors and typos
2. Correct grammatical mistakes
3. Improve sentence flow and readability
4. Ensure consistency in character names, places, and terminology
5. Maintain narrative continuity and logical flow
6. Preserve the author's voice, style, and intended meaning
7. DO NOT alter plot points, character actions, or creative choices

EDITING COMMANDS:
Use these special delimiters to mark your edits:

R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

EXAMPLES:
R∆5∆said⟹exclaimed◊D∆7◊I∆10∆He paused, gathering his thoughts.
M∆12-14∆The storm raged throughout the night.

IMPORTANT RULES:
- Line numbers are 1-indexed
- Only edit lines that need correction
- Provide edits in sequential order
- Be conservative - when in doubt, don't edit
- Focus on objective improvements only
"""
```

### Phase 4: Optimized Batch Processing

#### Token Calculation & Batching Algorithm
```python
def calculate_batch_groups(chapters, max_tokens, system_prompt_tokens):
    """
    Group chapters to maximize token usage while staying under limits
    """
    available_tokens = max_tokens - system_prompt_tokens - SAFETY_BUFFER
    batches = []
    current_batch = []
    current_tokens = 0
    
    for chapter in chapters:
        if current_tokens + chapter.tokens <= available_tokens:
            current_batch.append(chapter)
            current_tokens += chapter.tokens
        else:
            if current_batch:
                batches.append(current_batch)
            current_batch = [chapter]
            current_tokens = chapter.tokens
    
    if current_batch:
        batches.append(current_batch)
    
    return batches
```

#### Worker Pool Management
- Use asyncio with semaphore for concurrent API calls
- Implement exponential backoff for rate limiting
- Queue management with priority support
- Graceful shutdown on pause/stop

### Phase 5: Real-time Updates via WebSocket

#### WebSocket Message Protocol
```javascript
// Client -> Server
{
  "action": "start_processing" | "pause" | "resume" | "stop",
  "project_id": "uuid",
  "params": {...}
}

// Server -> Client
{
  "type": "status_update" | "chapter_complete" | "error" | "progress",
  "project_id": "uuid",
  "data": {
    "chapter_id": 123,
    "status": "in_progress",
    "progress_percentage": 45,
    "estimated_time_remaining": "5m 30s",
    "tokens_used": 15000,
    "message": "Processing chapter 12..."
  }
}
```

### Phase 6: Diff Visualization

#### Chapter Diff View
- Side-by-side comparison (original vs edited)
- Inline diff mode option
- Color coding: additions (green), deletions (red), modifications (yellow)
- Line number references
- Statistics: total edits, words changed, readability score changes
- Accept/Reject individual edits functionality
- Export diff as PDF/HTML for review

### Phase 7: Export & Download

#### Final ePub Generation
1. Apply all accepted edits to chapter files
2. Preserve original ePub structure and metadata
3. Update table of contents if needed
4. Repackage as valid ePub file
5. Validate output with ePub checker
6. Generate editing report (summary of all changes)

## Additional Features & Improvements

### Error Handling & Recovery
- Automatic checkpoint saving every N chapters
- Resume from last checkpoint after crashes
- Detailed error logging with context
- Manual edit override capability
- Validation of LLM responses before applying

### Performance Optimizations
- Cache tokenization results
- Implement request pooling for API efficiency
- Background processing for large books
- Incremental updates to UI (don't reload entire page)
- Lazy loading for chapter content

### User Experience Enhancements
- Drag-and-drop file upload
- Progress persistence (close browser, return later)
- Export processing logs
- Batch project management
- Preset system prompts for different editing styles
- Cost estimation before processing (based on token usage)

### Monitoring & Analytics
- Token usage tracking and cost calculation
- Processing time analytics
- Edit density heatmap (which chapters needed most edits)
- LLM response time tracking
- Success/failure rate statistics

## API Endpoints

```python
# Project Management
POST   /api/projects                 # Create project & upload ePub
GET    /api/projects                 # List all projects
GET    /api/projects/{id}           # Get project details
DELETE /api/projects/{id}           # Delete project

# Chapter Management  
GET    /api/projects/{id}/chapters  # List chapters with status
GET    /api/chapters/{id}/content   # Get original content
GET    /api/chapters/{id}/diff      # Get diff view
PATCH  /api/chapters/{id}/edits     # Update/override edits

# Processing Control
POST   /api/projects/{id}/process   # Start processing
POST   /api/projects/{id}/pause     # Pause processing
POST   /api/projects/{id}/resume    # Resume processing
POST   /api/projects/{id}/stop      # Stop processing

# LLM Configuration
PUT    /api/projects/{id}/llm-config # Update LLM settings
POST   /api/test-llm-connection      # Test API credentials

# Export
GET    /api/projects/{id}/export    # Generate & download edited ePub

# WebSocket
WS     /ws/projects/{id}            # Real-time updates
```

## Security Considerations
- Sanitize HTML content to prevent XSS
- Encrypt API keys in database
- Validate ePub files for malicious content
- Rate limiting on API endpoints
- File size limits for uploads
- Secure WebSocket connections (WSS in production)

## Development Roadmap
1. **Phase 1**: Core upload, extraction, and chapter processing
2. **Phase 2**: LLM integration and basic editing
3. **Phase 3**: WebSocket real-time updates
4. **Phase 4**: Diff visualization and edit management
5. **Phase 5**: Export functionality
6. **Phase 6**: UI polish and optimizations
7. **Phase 7**: Advanced features (batch processing, analytics)

This improved specification provides a more robust, scalable, and user-friendly application design with better error handling, performance optimization, and clearer implementation details.