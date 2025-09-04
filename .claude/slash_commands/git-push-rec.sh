#!/bin/bash
set -e

echo "🔄 Starting git operations for ctx-ai and parent repo..."

# Store the original directory
ORIGINAL_DIR=$(pwd)

# Determine if we're in ctx-ai or parent directory
if [[ "$ORIGINAL_DIR" == *"/ctx-ai"* ]]; then
    echo "📍 Currently in ctx-ai directory"
    CTX_AI_DIR="$ORIGINAL_DIR"
    PARENT_DIR="$(dirname "$ORIGINAL_DIR")"
else
    echo "📍 Currently in parent directory"
    CTX_AI_DIR="$ORIGINAL_DIR/ctx-ai"
    PARENT_DIR="$ORIGINAL_DIR"
fi

# Handle ctx-ai repository first
if [ -d "$CTX_AI_DIR" ]; then
    echo "📦 Processing ctx-ai repository..."
    cd "$CTX_AI_DIR"
    
    # Check if there are changes
    if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo "Adding and committing changes in ctx-ai..."
        git add -A
        git commit -m "Update from git-push-rec command" || echo "No changes to commit in ctx-ai"
        git push || echo "Nothing to push in ctx-ai"
        echo "✅ ctx-ai push completed"
    else
        echo "No changes in ctx-ai repository"
    fi
fi

# Handle parent repository
echo "📦 Processing parent repository..."
cd "$PARENT_DIR"

# Check if there are changes
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "Adding and committing changes in parent repo..."
    git add -A
    git commit -m "Update from git-push-rec command (including submodule updates)" || echo "No changes to commit"
    git push || echo "Nothing to push in parent repo"
    echo "✅ Parent repo push completed"
else
    echo "No changes in parent repository"
fi

# Return to original directory
cd "$ORIGINAL_DIR"

echo "✅ All git operations completed!"