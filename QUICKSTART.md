# Quick Start Guide

Get the ePub Editor up and running in minutes!

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

## Installation & Setup

### Option 1: Using the Start Script (Recommended)

```bash
# Make the script executable (if not already)
chmod +x start.sh

# Run the start script
./start.sh
```

The script will:
- Create a virtual environment if needed
- Install all dependencies
- Start the application

### Option 2: Manual Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create data directory
mkdir -p data/projects

# 4. Start the application
python app/main.py
```

## Access the Application

Open your browser and navigate to:
```
http://localhost:8000
```

## First Time Usage

### 1. Upload an ePub File
- Drag and drop an `.epub` file onto the upload area, or click to browse
- The app will extract chapters and metadata automatically

### 2. Configure LLM
- Click on your project to open the dashboard
- Click "Configure" in the LLM Configuration section
- Enter your API details:
  - **API Endpoint**: e.g., `https://api.openai.com/v1`
  - **API Key**: Your OpenAI (or compatible) API key
  - **Model**: Choose from GPT-4, GPT-4 Turbo, etc.
  - **Editing Style**: Light, Moderate, or Heavy
- Click "Test Connection" to verify
- Click "Save Configuration"

### 3. Start Processing
- Click "Start Processing"
- Configure:
  - **Chapter Range**: Which chapters to process
  - **Parallel Workers**: How many chapters to process simultaneously (1-10)
- Click "Start Processing"
- Watch real-time progress updates

### 4. Review Changes
- Once chapters are processed, click "View Diff" on any chapter
- See original vs. edited content side-by-side
- Review the statistics on edits made

### 5. Export
- Click "Export ePub" to download your edited book
- The file maintains the original structure with all edits applied

## Supported LLM APIs

The application works with any OpenAI-compatible API:

### OpenAI
```
Endpoint: https://api.openai.com/v1
Models: gpt-4, gpt-4-turbo, gpt-4o, gpt-3.5-turbo
```

### OpenRouter
```
Endpoint: https://openrouter.ai/api/v1
Models: Various (check OpenRouter docs)
```

### Local Models (Ollama)
```
Endpoint: http://localhost:11434/v1
Models: llama3, mistral, etc. (any installed model)
```

### LM Studio
```
Endpoint: http://localhost:1234/v1
Models: Whatever model you load in LM Studio
```

## Configuration Options

### Environment Variables (.env)

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/epub_editor.db

# Security (Change in production!)
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# Application
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Processing
MAX_WORKERS=5
DEFAULT_MAX_TOKENS=4096
```

### Editing Styles

- **Light**: Minimal changes, only fix obvious errors
- **Moderate**: Balanced approach, fix errors and improve readability
- **Heavy**: Comprehensive editing, significant improvements to style and flow

## Tips for Best Results

1. **Start Small**: Process a few chapters first to verify settings
2. **Monitor Token Usage**: Keep an eye on costs if using paid APIs
3. **Adjust Worker Count**: More workers = faster processing, but watch rate limits
4. **Temperature Setting**: Lower (0.1-0.3) for consistent, conservative edits
5. **Test Connection**: Always test before processing to avoid wasted time

## Troubleshooting

### Upload Fails
- Ensure file is a valid `.epub` format
- Check file size (default limit: 100MB)

### Processing Stuck
- Verify LLM API key and endpoint
- Check internet connection
- Review logs for errors

### WebSocket Disconnects
- This is normal, it will auto-reconnect
- Refresh the page if progress stops updating

### Can't Install Dependencies
- Ensure Python 3.9+ is installed
- Try: `pip install --upgrade pip`
- Some packages may need system dependencies (build tools)

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [plan.md](plan.md) for the complete feature spec
- Explore the API endpoints at `/docs` (FastAPI auto-documentation)

## Need Help?

- Check the [README](README.md) for more detailed information
- Open an issue on GitHub for bugs or feature requests
- Review the API documentation at `http://localhost:8000/docs`

## Stopping the Application

Press `Ctrl+C` in the terminal where the app is running.

---

**Happy Editing! 📚✨**
