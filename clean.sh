#!/bin/bash

# Directories to delete
directories=("data" "processed" "output" "logs" "summaries" "questions" "meeting_context")

# Loop through each directory and delete it
for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Deleting directory: $dir"
    rm -rf "$dir"
  else
    echo "Directory $dir does not exist."
  fi
done

# Recreate the logs directory
mkdir -p logs
echo "Logs directory recreated."

# Confirm the operation
echo "Directories deleted and logs directory recreated."