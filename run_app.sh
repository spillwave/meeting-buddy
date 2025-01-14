#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Add both project root and app directory to PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/app"

# Run the application in unbuffered mode
python -u app/mb/run_app.py
