#!/bin/bash

echo "🚀 Setting up Promo Alerts..."

# Create data directory if it doesn't exist
mkdir -p data

# Initialize git if not already done
if [ ! -d ".git" ]; then
    echo "📁 Initializing git repository..."
    git init
    git add .
    git commit -m "🎯 Initial commit: Promo Alerts setup"
fi

# Test the Python script
echo "🧪 Testing the monitoring script..."
cd app

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Test run
echo "🔍 Running test to verify everything works..."
python3 main.py

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Push this repository to GitHub"
echo "2. Go to Settings > Actions > General"
echo "3. Enable 'Read and write permissions' for workflows"
echo "4. The workflow will run automatically every 2 hours"
echo "5. Check the Actions tab to see execution results"
echo ""
echo "🎯 Happy promo hunting! ✈️"
