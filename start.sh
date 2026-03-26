#!/bin/bash
# Start all Engram services
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧠 Starting Engram..."

# Check Docker
if ! docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo "📦 Starting Docker containers (pgvector + Redis)..."
    docker compose up -d
    sleep 2
fi

echo "✓ Docker containers running"

# Start FastAPI backend
echo "🔧 Starting backend (port 8000)..."
uv run engram server &
BACKEND_PID=$!
sleep 2

# Start Next.js frontend
echo "🌐 Starting frontend (port 3001)..."
cd web
npm run dev -- -p 3001 &
FRONTEND_PID=$!
cd ..

echo ""
echo "============================================"
echo "  Engram is running!"
echo ""
echo "  Frontend:  http://localhost:3001"
echo "  Backend:   http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle cleanup
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait for either process to exit
wait
