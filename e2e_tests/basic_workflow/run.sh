#!/bin/bash

# Kill any previously running scripts
echo "Killing any previously running scripts"
pkill -f "launch_"

# Wait for processes to terminate
sleep 2

set -e

echo "Launching core"
python ./launch_core.py &
sleep 5

echo "Launching workflow"
python ./launch_workflow.py &
sleep 5

echo "Running client tests"
python ./test_run_client.py

# Kill any previously running scripts
echo "Killing any previously running scripts"
pkill -f "launch_"
