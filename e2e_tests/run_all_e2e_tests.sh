#!/bin/bash

set -e

for test_dir in */; do
    echo "Running tests in $test_dir"

    cd $test_dir
    sh ./run.sh
    cd ..
done
