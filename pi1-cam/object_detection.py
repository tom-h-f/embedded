import os
import time
import requests
from ultralytics import YOLO

# --- CONFIGURATION ---
# Use IP address if pi0.local fails inside Docker
LOKI_BASE_URL = os.getenv("LOKI_URL")
STREAM_URL = os.getenv("STREAM_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "yolo11n.pt")
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.6"))

class LokiReporter:
    def __init__(self, base_url):
        self.url = f"{base_url.rstrip('/')}/loki/api/v1/push"
        self.session = requests.Session()
        self.hostname = os.uname()[1]
        # Unique session ID to prevent stream collision with old/stale data
        self.session_id = str(int(time.time()))
        self.last_ts = 0

    def get_unique_ts(self):
        """Ensures timestamps are strictly increasing for Loki."""
        ts = int(time.time() * 1e9)
        if ts <= self.last_ts:
            ts = self.last_ts + 1
        self.last_ts = ts
        return str(ts)

    def send_batch(self, detections):
        """
        Sends multiple detections in a single push request.
        detections: list of tuples (label, confidence)
        """
        ts = self.get_unique_ts()
        
        # We group by object label to maintain clean streams
        streams = []
        for label, conf in detections:
            streams.append({
                "stream": {
                    "job": "yolo11_inference",
                    "host": self.hostname,
                    "object": label,
                    "session": self.session_id
                },
                "values": [
                    [ts, f"YOLO11 Detection: {label} (conf: {conf:.2f})"]
                ]
            })

        payload = {"streams": streams}
        
        try:
            resp = self.session.post(self.url, json=payload, timeout=2)
            if resp.status_code != 204:
                print(f"Loki Error {resp.status_code}: {resp.text}")
            else:
                print(f"Sent {len(detections)} objects to Loki.")
        except Exception as e:
            print(f"Loki Connection Failed: {e}")

def main():
    print(f"Initializing YOLO11 with model: {MODEL_NAME}")
    model = YOLO(MODEL_NAME)
    loki = LokiReporter(LOKI_BASE_URL)

    print(f"Connecting to: {STREAM_URL}")
    
    # Predict with stream=True for memory efficiency
    results = model.predict(
        source=STREAM_URL,
        stream=True,
        conf=CONF_THRESHOLD,
        imgsz=720,      # Optimization for Pi 4
        vid_stride=12,   # Process every 5th frame to save CPU/Battery
        verbose=False
    )

    last_logged_objects = set()

    for r in results:
        current_frame_objects = set()
        to_log = []

        for box in r.boxes:
            label = model.names[int(box.cls[0])]
            conf = float(box.conf[0])
            current_frame_objects.add(label)

            # Deduplication: Only log if object is new in this frame sequence
            if label not in last_logged_objects:
                to_log.append((label, conf))

        if to_log:
            loki.send_batch(to_log)

        last_logged_objects = current_frame_objects

if __name__ == "__main__":
    main()
