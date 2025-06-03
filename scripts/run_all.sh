#!/bin/bash

echo "Starting generate.py..."
python3 generate.py &
PID1=$!

echo "Starting generate2.py..."
python3 generate2.py &
PID2=$!

# Wait for both to finish
wait $PID1
wait $PID2

echo "Both scripts finished."
