#!/bin/bash
# Render build script for backend

set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create storage directory
mkdir -p ../storage

# Initialize database
python init_db.py

echo "Backend build completed successfully!"
