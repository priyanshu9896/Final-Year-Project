#!/bin/bash

echo "🚀 Setting up MockStar AI Interview Platform..."

# Navigate to project directory
cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

echo "✅ Python 3 found"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "To run the project:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Navigate to app directory: cd app"
echo "3. Run the application: python main.py"
echo ""
echo "Or simply run: ./run.sh"
echo ""
echo "🌐 The application will be available at: http://localhost:5001"
