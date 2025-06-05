#!/bin/bash

# --------------------------------------------
# run_all.sh
# Launch multiple instances of generate.py,
# each with a different --obu-id argument.
# --------------------------------------------

echo "Starting generate.py for OBU 1..."
python3 generate.py --obu-id 1 &
PID1=$!

echo "Starting generate.py for OBU 2..."
python3 generate.py --obu-id 2 &
PID2=$!

# If you want to launch a third OBU, uncomment and adjust:
echo "Starting generate.py for OBU 3..."
python3 generate.py --obu-id 3 &
PID3=$!

# Wait for both (or all) to finish:
wait $PID1
wait $PID2
# If you uncommented OBU 3 above, also add:
wait $PID3

echo "All generate.py instances have finished."
