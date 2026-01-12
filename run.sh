#!/bin/bash

echo "🚀 Starting MockStar AI Interview Platform..."

# Navigate to project directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Running setup first..."
    ./setup.sh
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Navigate to app directory
cd app

# Check if all dependencies are installed
echo "🔍 Checking dependencies..."
python -c "
import flask, flask_session, pymongo, redis, dotenv, requests, google.generativeai
print('✅ All dependencies are installed')
" 2>/dev/null || {
    echo "❌ Some dependencies are missing. Installing..."
    cd ..
    pip install -r requirements.txt
    cd app
}

echo "🌟 Starting the application..."
echo "🌐 Open your browser and go to: http://localhost:5001"
echo "📱 Press Ctrl+C to stop the server"
echo ""

# Run the Flask application
python main.py
