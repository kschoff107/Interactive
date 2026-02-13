#!/bin/bash
# Render build script for backend

set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create storage directory
mkdir -p ../storage

# Initialize database
python -m db.init_db

echo "Backend build completed successfully!"
