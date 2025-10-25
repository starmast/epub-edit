#!/bin/bash
# ePub Editor - Startup Script

echo "🚀 Starting ePub Editor..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if [ ! -f ".dependencies_installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    touch .dependencies_installed
fi

# Create data directory if it doesn't exist
mkdir -p data/projects

# Start the server
echo "✅ Starting server on http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python app/main.py
