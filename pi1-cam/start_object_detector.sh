#!/bin/bash

CONTAINER_NAME="yolo11-detector"
IMAGE="ultralytics/ultralytics:latest-arm64"
LOKI_URL="http://loki.home:3100"
STREAM_URL="rtsp://localhost:8554/picam0"

# Stop existing
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

echo "Launching YOLO11 object detection..."

docker run -d \
  --name $CONTAINER_NAME \
  --network host \
  --restart always \
  -e LOKI_URL=$LOKI_URL \
  -e STREAM_URL=$STREAM_URL \
  -v "./object_detection.py:/usr/src/app/object_detection.py" \
  $IMAGE \
  python3 /usr/src/app/object_detection.py

echo "YOLO11 Container started."
