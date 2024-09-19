#!/bin/bash

set -e

for test_dir in */; do
    echo "Running tests in $test_dir"

    cd $test_dir
    poetry run sh ./run.sh
    cd ..
done
