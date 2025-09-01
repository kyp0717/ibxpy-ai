#!/bin/bash

# Interactive Brokers API Installation Script
# This script helps install the ibapi Python package

echo "=========================================="
echo "Interactive Brokers API Installation Guide"
echo "=========================================="
echo ""
echo "The ibapi package must be downloaded from Interactive Brokers directly."
echo ""
echo "Steps to install ibapi:"
echo ""
echo "1. Download the TWS API from:"
echo "   https://www.interactivebrokers.com/en/index.php?f=5041"
echo ""
echo "2. Select 'TWS API Stable' (or Latest)"
echo ""
echo "3. After downloading, extract the zip file"
echo ""
echo "4. Navigate to the extracted folder and find:"
echo "   TWS_API/source/pythonclient/"
echo ""
echo "5. Install using uv:"
echo "   uv pip install /path/to/TWS_API/source/pythonclient/"
echo ""
echo "Example installation command:"
echo "   uv pip install ~/Downloads/TWS_API/source/pythonclient/"
echo ""
echo "=========================================="
echo ""
read -p "Have you downloaded the TWS API? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    read -p "Enter the path to TWS_API folder (e.g., ~/Downloads/TWS_API): " tws_path
    
    # Expand tilde and check if path exists
    tws_path="${tws_path/#\~/$HOME}"
    
    if [ -d "$tws_path/source/pythonclient" ]; then
        echo "Found pythonclient at: $tws_path/source/pythonclient"
        echo "Installing ibapi..."
        uv pip install "$tws_path/source/pythonclient/"
        
        # Verify installation
        if python -c "import ibapi" 2>/dev/null; then
            echo ""
            echo "✅ ibapi installed successfully!"
            python -c "import ibapi; print(f'ibapi version: {ibapi.VERSION}')" 2>/dev/null || echo "Version info not available"
        else
            echo "❌ Installation failed. Please check the path and try again."
        fi
    else
        echo "❌ Cannot find $tws_path/source/pythonclient/"
        echo "Please check the path and ensure you've extracted the TWS API zip file."
    fi
else
    echo "Please download the TWS API first from:"
    echo "https://www.interactivebrokers.com/en/index.php?f=5041"
fi