clear

if [ -z "$1" ]; then
    echo "Usage: $0 <topic>"
    exit 1
fi
kcat -C -b localhost:9092 -t $1