# ePub Editor - LLM-Powered Book Editor

A powerful web application that leverages Large Language Models (LLMs) to automatically edit ePub books, focusing on improving spelling, grammar, and narrative continuity while preserving the original meaning and author's voice.

## Features

### Core Features
- **ePub Processing**: Upload and extract chapters from ePub files with metadata preservation
- **LLM Integration**: Support for OpenAI-compatible APIs (OpenAI, OpenRouter, local models)
- **Parallel Processing**: Process multiple chapters concurrently with configurable worker pools
- **Real-time Updates**: WebSocket-based live progress tracking
- **Diff Viewer**: Side-by-side comparison of original vs edited content
- **Smart Token Management**: Automatic token counting and batch optimization
- **Export**: Generate edited ePub files with all changes applied

### Advanced Features
- **Multiple Editing Styles**: Choose from light, moderate, or heavy editing approaches
- **Progress Persistence**: Resume processing after interruptions
- **Error Handling**: Automatic retry with exponential backoff
- **Secure API Keys**: Encrypted storage of LLM API credentials
- **Cost Estimation**: Track token usage and estimate API costs

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for Python
- **SQLAlchemy**: Async ORM for database operations
- **SQLite**: Lightweight database for metadata and settings
- **ebooklib**: ePub file processing
- **tiktoken**: Accurate token counting
- **httpx**: Async HTTP client for LLM APIs

### Frontend
- **Vanilla JavaScript**: No build tools required
- **Tailwind CSS**: Utility-first CSS framework (via CDN)
- **WebSockets**: Real-time communication

## Installation

### Prerequisites
- Python 3.9+
- pip

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd epub-edit
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create environment file**
   ```bash
   cp .env.example .env
   ```

5. **Generate secure keys**
   ```python
   # In Python shell
   import secrets
   print(f"SECRET_KEY={secrets.token_urlsafe(32)}")
   print(f"ENCRYPTION_KEY={secrets.token_urlsafe(32)}")
   ```
   Add these to your `.env` file

6. **Create data directory**
   ```bash
   mkdir -p data/projects
   ```

## Usage

### Starting the Server

```bash
# Development mode (with auto-reload)
python app/main.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`

### Using the Application

1. **Upload an ePub**
   - Drag and drop an ePub file or click to browse
   - The app will extract chapters and metadata

2. **Configure LLM**
   - Open the project dashboard
   - Click "Configure" in the LLM Configuration section
   - Enter your API endpoint and key
   - Select model and editing style
   - Test the connection

3. **Start Processing**
   - Click "Start Processing"
   - Configure chapter range and worker count
   - Monitor progress in real-time

4. **Review Changes**
   - Click "View Diff" on completed chapters
   - Compare original vs edited content
   - See statistics on edits made

5. **Export**
   - Click "Export ePub" to download the edited book
   - The ePub maintains the original structure and metadata

## API Endpoints

### Projects
- `POST /api/projects` - Create project and upload ePub
- `GET /api/projects` - List all projects
- `GET /api/projects/{id}` - Get project details
- `DELETE /api/projects/{id}` - Delete project

### Chapters
- `GET /api/projects/{id}/chapters` - List chapters
- `GET /api/chapters/{id}/content` - Get chapter content
- `GET /api/chapters/{id}/diff` - Get diff view
- `PATCH /api/chapters/{id}/edits` - Update edits
- `POST /api/chapters/{id}/retry` - Retry failed chapter

### Processing
- `POST /api/projects/{id}/process` - Start processing
- `POST /api/projects/{id}/pause` - Pause processing
- `POST /api/projects/{id}/resume` - Resume processing
- `POST /api/projects/{id}/stop` - Stop processing
- `POST /api/test-llm-connection` - Test LLM connection
- `GET /api/projects/{id}/export` - Export edited ePub

### WebSocket
- `WS /ws/projects/{id}` - Real-time updates

## Configuration

### Environment Variables

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/epub_editor.db

# Security
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# Application
DEBUG=True
HOST=0.0.0.0
PORT=8000

# File Upload
MAX_UPLOAD_SIZE=100000000  # 100MB
ALLOWED_EXTENSIONS=epub

# Processing
MAX_WORKERS=5
DEFAULT_MAX_TOKENS=4096
SAFETY_BUFFER=500

# CORS
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### LLM Configuration

The application supports any OpenAI-compatible API:

- **OpenAI**: `https://api.openai.com/v1`
- **OpenRouter**: `https://openrouter.ai/api/v1`
- **Local (Ollama)**: `http://localhost:11434/v1`
- **LM Studio**: `http://localhost:1234/v1`

## Architecture

### Data Flow

1. **Upload**: ePub → Extract chapters → Store in filesystem + database
2. **Configure**: LLM settings → Encrypted storage
3. **Process**: Queue chapters → Worker pool → LLM API → Parse edits → Apply changes
4. **Export**: Load edited chapters → Reassemble ePub → Download

### File Structure

```
epub-edit/
├── app/
│   ├── models/          # SQLAlchemy models
│   ├── routers/         # API endpoints
│   ├── services/        # Business logic
│   ├── utils/           # Utilities
│   ├── config.py        # Configuration
│   └── main.py          # FastAPI application
├── data/
│   └── projects/        # Project files
│       └── {id}/
│           ├── original/
│           ├── edits/
│           └── output/
├── static/
│   ├── css/
│   └── js/
│       └── app.js       # Frontend application
├── templates/
│   └── index.html       # Main HTML
└── requirements.txt
```

## Edit Command Format

The LLM uses special delimiters to specify edits:

- `R∆line∆pattern⟹replacement` - Replace text on a specific line
- `D∆line` - Delete an entire line
- `I∆line∆text` - Insert new text after a line
- `M∆start-end∆text` - Merge/replace a range of lines

Multiple edits are separated by `◊`

Example:
```
R∆5∆said⟹exclaimed◊D∆7◊I∆10∆He paused, gathering his thoughts.
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app/
```

### Adding New Features

1. Backend: Add service in `app/services/`
2. API: Add router in `app/routers/`
3. Frontend: Update `static/js/app.js`

## Troubleshooting

### Common Issues

**Upload fails**
- Check file size limits in `.env`
- Ensure ePub is valid

**Processing stuck**
- Check LLM API connectivity
- Review logs for errors
- Verify API key and quota

**WebSocket disconnects**
- Check CORS settings
- Ensure stable network connection

**Database errors**
- Delete `data/epub_editor.db` to reset
- Check file permissions

## Security Considerations

- API keys are encrypted at rest
- Input validation on all endpoints
- HTML sanitization to prevent XSS
- Rate limiting recommended for production
- Use HTTPS/WSS in production

## Performance Tips

- Adjust `MAX_WORKERS` based on API rate limits
- Use smaller `MAX_TOKENS` for faster processing
- Process shorter chapters first for quick results
- Monitor token usage to control costs

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions

## Acknowledgments

- Built with FastAPI and modern web technologies
- Uses OpenAI-compatible APIs for LLM integration
- Designed for professional book editing workflows
