---
description: Git add, commit, and push for parent repo and submodule
---

#!/bin/bash
set -e

echo "🔄 Starting git operations for parent repo and submodule..."

# Handle submodule first (ctx-ai)
if [ -d "ctx-ai" ]; then
    echo "📦 Processing submodule: ctx-ai"
    cd ctx-ai
    
    # Check if there are changes
    if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo "Adding and committing changes in ctx-ai..."
        git add -A
        git commit -m "Test push from slash command" || echo "No changes to commit in ctx-ai"
        git push || echo "Nothing to push in ctx-ai"
    else
        echo "No changes in ctx-ai submodule"
    fi
    
    cd ..
fi

# Handle parent repository
echo "📦 Processing parent repository..."

# Check if there are changes
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "Adding and committing changes in parent repo..."
    git add -A
    git commit -m "Test push from slash command" || echo "No changes to commit"
    git push || echo "Nothing to push"
else
    echo "No changes in parent repository"
fi

echo "✅ Git operations completed!"