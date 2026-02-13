import cv2
import numpy as np
import pytesseract
import streamlink
import time
import json
import config

# Setup Tesseract
if config.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

class GameWatcher:
    def __init__(self, stream_url, output_file="game_state.json"):
        self.stream_url = stream_url
        self.output_file = output_file
        self.cap = None

    def connect_stream(self):
        print(f"Connecting to {self.stream_url}...")
        streams = streamlink.streams(self.stream_url)
        if not streams:
            print("No streams found.")
            return False
        
        # Get best quality stream URL
        stream_url = streams['best'].url
        self.cap = cv2.VideoCapture(stream_url)
        return True

    def process_frame(self, frame):
        # 1. Get Timer
        timer_img = frame[config.ROI_TIMER['y'][0]:config.ROI_TIMER['y'][1], 
                          config.ROI_TIMER['x'][0]:config.ROI_TIMER['x'][1]]
        
        # Pre-process for OCR (Grayscale -> Invert -> Threshold)
        gray = cv2.cvtColor(timer_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        timer_text = pytesseract.image_to_string(thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789:')
        
        # 2. Check Spike Status (Detect Red Color in Spike Area)
        spike_img = frame[config.ROI_SPIKE['y'][0]:config.ROI_SPIKE['y'][1], 
                          config.ROI_SPIKE['x'][0]:config.ROI_SPIKE['x'][1]]
        hsv_spike = cv2.cvtColor(spike_img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_spike, config.SPIKE_RED_LOWER, config.SPIKE_RED_UPPER)
        spike_planted = cv2.countNonZero(mask) > 50 # Threshold of red pixels

        # 3. Count Alive Players (Check brightness of avatar region)
        team_a_alive = 0
        for (x, y) in config.TEAM_A_AVATARS:
            # Check if pixel is bright (Alive) or dark (Dead)
            # Safe check to ensure we are within bounds
            if y < frame.shape[0] and x < frame.shape[1]:
                pixel_brightness = np.mean(frame[y-5:y+5, x-5:x+5])
                if pixel_brightness > 50: # Threshold for "Alive"
                    team_a_alive += 1

        team_b_alive = 0
        for (x, y) in config.TEAM_B_AVATARS:
            if y < frame.shape[0] and x < frame.shape[1]:
                pixel_brightness = np.mean(frame[y-5:y+5, x-5:x+5])
                if pixel_brightness > 50:
                    team_b_alive += 1

        return {
            "timestamp": time.time(),
            "timer": timer_text.strip(),
            "spike_planted": spike_planted,
            "team_a_alive": team_a_alive,
            "team_b_alive": team_b_alive
        }

    def run(self):
        if not self.connect_stream():
            return

        frame_count = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Stream ended or buffered. Reconnecting...")
                self.connect_stream()
                continue

            # Optimize: Process only every 10th frame (6 times per second is enough)
            frame_count += 1
            if frame_count % 10 != 0:
                continue

            try:
                state = self.process_frame(frame)
                
                # Write to JSON file atomically
                with open(self.output_file, 'w') as f:
                    json.dump(state, f)
                
                print(f"Update: {state}")
                
            except Exception as e:
                print(f"Error processing frame: {e}")

if __name__ == "__main__":
    # Replace with a real live VCT stream URL when available
    # For testing, use a VOD URL from YouTube or Twitch
    URL = "https://www.youtube.com/watch?t=5&v=GoLVlVZAk6E&feature=youtu.be" 
    bot = GameWatcher(URL)
    bot.run()