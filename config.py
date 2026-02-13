# config.py

# Point to your Tesseract executable if not in PATH
# TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
TESSERACT_CMD = None 

# 1920x1080 Coordinates [y1:y2, x1:x2]
# These are estimates for the standard VCT HUD. 
# You may need to tweak these by 5-10 pixels.

ROI_TIMER = {'y': [35, 85], 'x': [910, 1010]} # Top center clock
ROI_SPIKE = {'y': [15, 60], 'x': [940, 980]}  # Spike icon area

# Agent Avatars (Top Left - Defenders / Top Right - Attackers)
# We check a specific pixel in the avatar box to see if it's "lit up" (alive) or dark (dead)
# Simplified approach: Check 5 specific points on each side
TEAM_A_AVATARS = [
    (550, 70), (620, 70), (690, 70), (760, 70), (830, 70) # x, y coordinates
]
TEAM_B_AVATARS = [
    (1090, 70), (1160, 70), (1230, 70), (1300, 70), (1370, 70)
]

# Color Thresholds (HSV)
# Red Spike Planted Indicator
SPIKE_RED_LOWER = (0, 100, 100)
SPIKE_RED_UPPER = (10, 255, 255)