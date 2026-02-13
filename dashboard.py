import streamlit as st
import cv2
import pytesseract
import numpy as np
import pandas as pd
import tempfile
import re
from sklearn.linear_model import LogisticRegression

# -----------------------------------------------------------------------------
# 1. CONFIG & SETUP
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Valorant VCT Predictor", layout="wide")

# -----------------------------------------------------------------------------
# 2. VCT VISION ENGINE (The "Eyes")
# -----------------------------------------------------------------------------
class VCTVisionEngine:
    def __init__(self, tesseract_cmd=None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # ROIs for 1080p VCT Layout
        # Format: (y_start, y_end, x_start, x_end)
        self.ROIS = {
            'score_left': (20, 90, 830, 890),
            'score_right': (20, 90, 1030, 1090),
            'timer': (20, 100, 930, 990),
            # Spike icon usually appears top-mid or near timer
            'spike': (80, 120, 940, 980) 
        }
        
        # Player Health Bar Sampling Points (VCT Layout)
        # We check specific pixels to see if a player is "Alive" (Colored) or "Dead" (Gray)
        self.LEFT_SIDEBAR_X = 260   # X-coord to check for Left Team Health
        self.RIGHT_SIDEBAR_X = 1660 # X-coord to check for Right Team Health
        self.SIDEBAR_START_Y = 540  # Y-coord of first player
        self.SIDEBAR_GAP = 95       # Pixels between players

    def preprocess(self, img, invert=True):
        """Prepares image for OCR."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        if invert:
            thresh = cv2.bitwise_not(thresh)
        return thresh

    def read_number(self, img_crop):
        """OCR to read digits."""
        if img_crop.size == 0: return 0
        processed = self.preprocess(img_crop)
        config = r'--oem 3 --psm 6 outputbase digits'
        text = pytesseract.image_to_string(processed, config=config)
        digits = re.sub(r"[^0-9]", "", text)
        return int(digits) if digits else 0

    def count_alive(self, frame, side='left'):
        """Counts alive players based on health bar color intensity."""
        alive = 0
        x = self.LEFT_SIDEBAR_X if side == 'left' else self.RIGHT_SIDEBAR_X
        
        for i in range(5):
            y = self.SIDEBAR_START_Y + (i * self.SIDEBAR_GAP)
            if y >= frame.shape[0]: break
            
            # Sample a 10x10 area of the health bar
            sample = frame[y:y+10, x:x+10]
            hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
            
            # Check Saturation (S) and Value (V). 
            # Dead players are gray (Low S). Alive are Red/Green/Cyan (High S).
            sat = np.mean(hsv[:, :, 1])
            val = np.mean(hsv[:, :, 2])
            
            if sat > 40 and val > 50:
                alive += 1
        return alive

    def detect_spike(self, frame):
        """Checks if spike is planted (Red icon near timer)."""
        roi = self.ROIS['spike']
        crop = frame[roi[0]:roi[1], roi[2]:roi[3]]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        
        # Red range for planted spike indicator
        lower_red1, upper_red1 = np.array([0, 70, 50]), np.array([10, 255, 255])
        lower_red2, upper_red2 = np.array([170, 70, 50]), np.array([180, 255, 255])
        
        mask = cv2.inRange(hsv, lower_red1, upper_red1) + cv2.inRange(hsv, lower_red2, upper_red2)
        return cv2.countNonZero(mask) > 50

    def analyze(self, frame):
        """Extracts full game state from a frame."""
        stats = {}
        
        # 1. Scores
        sl_roi = self.ROIS['score_left']
        sr_roi = self.ROIS['score_right']
        stats['score_left'] = self.read_number(frame[sl_roi[0]:sl_roi[1], sl_roi[2]:sl_roi[3]])
        stats['score_right'] = self.read_number(frame[sr_roi[0]:sr_roi[1], sr_roi[2]:sr_roi[3]])
        
        # 2. Alive Players
        stats['alive_left'] = self.count_alive(frame, 'left')
        stats['alive_right'] = self.count_alive(frame, 'right')
        
        # 3. Spike
        stats['spike_planted'] = self.detect_spike(frame)
        
        # 4. Momentum (Simple Logic based on Score Diff)
        stats['score_diff'] = stats['score_left'] - stats['score_right']
        
        return stats

# -----------------------------------------------------------------------------
# 3. PREDICTION MODEL (The "Brain")
# -----------------------------------------------------------------------------
@st.cache_resource
def load_model():
    """Trains a lightweight Logistic Regression model on dummy data."""
    # Synthetic Data: [Score Diff, Alive Diff, Spike Planted (0/1)]
    # Target: 1 = Left Win, 0 = Right Win
    np.random.seed(42)
    X = []
    y = []
    
    for _ in range(2000):
        s_diff = np.random.randint(-5, 6) # Score difference
        a_diff = np.random.randint(-5, 6) # Alive player difference
        spike = np.random.choice([0, 1])  # Spike planted?
        
        # Simple Logic: More alive players + Score lead = Higher chance to win
        # Spike logic: If planted, heavily favors attackers (assume Left is attacking for sim)
        prob = 0.5 + (s_diff * 0.05) + (a_diff * 0.15) + (spike * 0.1)
        prob = np.clip(prob, 0, 1)
        
        X.append([s_diff, a_diff, spike])
        y.append(1 if np.random.random() < prob else 0)
        
    model = LogisticRegression()
    model.fit(X, y)
    return model

model = load_model()

# -----------------------------------------------------------------------------
# 4. DASHBOARD UI
# -----------------------------------------------------------------------------

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # 1. Tesseract Path
    default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    tess_path = st.text_input("Tesseract Path", value=default_path)
    
    st.markdown("---")
    st.header("Teams")
    team_a = st.text_input("Left Team Name", "G2")
    team_b = st.text_input("Right Team Name", "NRG")
    
    st.markdown("---")
    st.info("Upload a VOD frame to analyze the current game state.")

# --- MAIN PAGE ---
st.title(f"📊 {team_a} vs {team_b} Prediction Dashboard")

# 1. File Uploader for Analysis
uploaded_file = st.file_uploader("Upload VOD or Screenshot (.mp4, .jpg, .png)", type=['mp4', 'jpg', 'png'])

col_vid, col_data = st.columns([2, 1])

vision = VCTVisionEngine(tesseract_cmd=tess_path)
current_stats = None

with col_vid:
    st.subheader("🎥 VOD Analysis")
    
    if uploaded_file:
        # Save temp file
        tfile = tempfile.NamedTemporaryFile(delete=False)
        tfile.write(uploaded_file.read())
        
        cap = cv2.VideoCapture(tfile.name)
        
        if uploaded_file.name.endswith('.mp4'):
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_idx = st.slider("Select Frame to Analyze", 0, total_frames-1, 100)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        
        ret, frame = cap.read()
        
        if ret:
            # RUN VISION ANALYSIS
            current_stats = vision.analyze(frame)
            
            # DRAW DEBUG OVERLAY
            debug_frame = frame.copy()
            # Score Boxes
            cv2.rectangle(debug_frame, (vision.ROIS['score_left'][2], vision.ROIS['score_left'][0]), 
                          (vision.ROIS['score_left'][3], vision.ROIS['score_left'][1]), (0, 255, 0), 2)
            cv2.rectangle(debug_frame, (vision.ROIS['score_right'][2], vision.ROIS['score_right'][0]), 
                          (vision.ROIS['score_right'][3], vision.ROIS['score_right'][1]), (0, 0, 255), 2)
            
            # Alive Dots
            for i in range(5):
                y = vision.SIDEBAR_START_Y + (i * vision.SIDEBAR_GAP)
                cv2.circle(debug_frame, (vision.LEFT_SIDEBAR_X, y+5), 8, (255, 255, 0), -1)
                cv2.circle(debug_frame, (vision.RIGHT_SIDEBAR_X, y+5), 8, (255, 255, 0), -1)
                
            st.image(debug_frame, channels="BGR", caption="Analyzed Frame (Debug View)")
            
        cap.release()

with col_data:
    st.subheader("📈 Live Win Probability")
    
    if current_stats:
        # Display Raw Stats
        s1, s2 = st.columns(2)
        s1.metric(f"{team_a} Score", current_stats['score_left'])
        s2.metric(f"{team_b} Score", current_stats['score_right'])
        
        s3, s4 = st.columns(2)
        s3.metric(f"{team_a} Alive", f"{current_stats['alive_left']}/5")
        s4.metric(f"{team_b} Alive", f"{current_stats['alive_right']}/5")
        
        st.metric("Spike Planted?", "YES" if current_stats['spike_planted'] else "NO")
        
        # PREDICT
        # Prepare Features: [Score Diff, Alive Diff, Spike]
        alive_diff = current_stats['alive_left'] - current_stats['alive_right']
        features = [[current_stats['score_diff'], alive_diff, int(current_stats['spike_planted'])]]
        
        # Get Probability
        probs = model.predict_proba(features)[0]
        win_prob_a = probs[1] * 100
        
        st.divider()
        st.subheader(f"Win Chance: {team_a}")
        st.progress(int(win_prob_a))
        st.markdown(f"## {win_prob_a:.1f}%")
        
        if win_prob_a > 60:
            st.success(f"{team_a} is favored to win this round!")
        elif win_prob_a < 40:
            st.error(f"{team_b} is favored to win this round!")
        else:
            st.warning("Too close to call.")
            
    else:
        st.info("Upload a video or image to see predictions.")

    # Manual Override Section
    with st.expander("Manual Override (If Vision Fails)"):
        m_alive_a = st.number_input(f"{team_a} Alive", 0, 5, 5)
        m_alive_b = st.number_input(f"{team_b} Alive", 0, 5, 5)
        m_spike = st.checkbox("Spike Planted (Manual)")
        
        if st.button("Predict Manually"):
            feat = [[0, m_alive_a - m_alive_b, int(m_spike)]]
            man_prob = model.predict_proba(feat)[0][1] * 100
            st.write(f"Manual Calculation: {man_prob:.1f}%")