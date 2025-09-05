#!/bin/bash
# Test runner script for the trading backend

echo "═══════════════════════════════════════════════════════════════"
echo "  Trading Backend Test Suite"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Ensure we're in the backend directory
cd "$(dirname "$0")"

# Install test dependencies if needed
echo "📦 Installing test dependencies..."
uv pip install pytest pytest-asyncio pytest-mock httpx

echo ""
echo "🧪 Running tests..."
echo ""

# Run different test categories
echo "1️⃣ Running Unit Tests..."
uv run pytest tests/test_error_handler.py -v -m "not slow"

echo ""
echo "2️⃣ Running Service Tests..."
uv run pytest tests/test_services.py -v -m "not slow"

echo ""
echo "3️⃣ Running API Endpoint Tests..."
uv run pytest tests/test_api_endpoints.py -v -m "not slow"

echo ""
echo "4️⃣ Running Performance Tests..."
uv run pytest tests/test_performance.py -v -k "not memory" --tb=no

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Test Summary"
echo "═══════════════════════════════════════════════════════════════"

# Run all tests with summary
uv run pytest tests/ --tb=no -q

echo ""
echo "✅ Test suite complete!"