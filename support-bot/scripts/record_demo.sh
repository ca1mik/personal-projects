#!/bin/bash
# record_demo.sh – script to record a demo video of the bot flow using ffmpeg
# Prerequisites: Docker Compose up, ffmpeg installed, DISPLAY or virtual screen for Xvfb

set -e

# Start services in the background
docker compose up -d

# Wait for the app to be ready (poll health endpoint)
while true; do
  if curl -s http://localhost:${APP_PORT:-8000}/health | grep -q "\"status\": \"ok\""; then
    echo "App is up"
    break
  fi
  echo "Waiting for app..."
  sleep 2
done

# Use Xvfb to provide a virtual display (needed for UI interactions if any)
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Run a demo client that simulates a user interaction via the Telegram Bot API
# (Replace with actual test script if available)
python - <<'PY'
import time, requests
# Replace with real bot token if needed
token = "${TELEGRAM_BOT_TOKEN:-}"  # empty for mock mode
# Simulate /start command
url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {"chat_id": "123456", "text": "/start"}
requests.post(url, json=payload)
# Wait for bot to respond and follow flow (demo script can be expanded)
time.sleep(5)
PY

# Record the screen for 30 seconds
ffmpeg -y -video_size 1280x720 -framerate 25 -f x11grab -i :99 -t 30 artifacts/demo_mock.mp4

# Shut down services
docker compose down

echo "Demo video saved to artifacts/demo_mock.mp4"
