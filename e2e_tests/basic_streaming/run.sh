#!/bin/bash

# Kill any previously running scripts
echo "Killing any previously running scripts"
pkill -f "launch_"

# Wait for processes to terminate
sleep 2

set -e

echo "Launching core"
poetry run python ./launch_core.py &
sleep 2

echo "Launching workflow"
poetry run python ./launch_workflow.py &
sleep 2

echo "Running client tests"
poetry run python ./test_run_client.py
sleep 2
