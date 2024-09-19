#!/bin/bash

# Kill any previously running scripts
echo "Killing any previously running scripts"
pkill -f "launch_"

# Wait for processes to terminate
sleep 2

set -e

echo "Launching core"
python ./launch_core.py &
sleep 2

echo "Launching workflow"
python ./launch_workflow.py &
sleep 2

echo "Running client tests"
python ./test_run_client.py
sleep 2
