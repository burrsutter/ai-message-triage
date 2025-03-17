#!/bin/bash
# The retry logic came from ChatGPT
clear

if [ -z "$1" ]; then
    echo "Usage: $0 <topic>"
    exit 1
fi

TOPIC=$1
BROKER="localhost:9092"
RETRY_INTERVAL=5  # Wait time before retrying

# Function to check if topic exists
topic_exists() {
    kafka-topics --bootstrap-server $BROKER --list | grep -q "^$TOPIC$"
}

echo "Checking for topic: $TOPIC"

while ! topic_exists; do
    echo "Topic '$TOPIC' not found. Retrying in $RETRY_INTERVAL seconds..."
    sleep $RETRY_INTERVAL
done

echo "Topic '$TOPIC' found. Connecting with kcat..."

while true; do
    # Start kcat in unbuffered mode (-u) and suppress extra info (-q)
    kcat -C -b $BROKER -t $TOPIC -o beginning -u -q 2>&1 | tee /dev/tty | while read -r line; do
        if echo "$line" | grep -q "Local: Unknown partition"; then
            echo "Partition error detected. Retrying in $RETRY_INTERVAL seconds..."
            sleep $RETRY_INTERVAL
            break
        fi
    done
    
    echo "Rechecking topic existence..."
    while ! topic_exists; do
        echo "Waiting for topic '$TOPIC' to be available again..."
        sleep $RETRY_INTERVAL
    done

    echo "Reconnecting to topic '$TOPIC'..."
done