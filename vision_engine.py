import cv2
import pytesseract
import numpy as np
import re

class VCTVisionEngine:
    def __init__(self):
        # ---------------------------------------------------------
        # VCT BROADCAST LAYOUT (1920x1080 Reference)
        # ---------------------------------------------------------
        
        # 1. SCORE & TIMER (Top Center)
        self.roi_score_left = (20, 90, 830, 890)   # Team A Score
        self.roi_score_right = (20, 90, 1030, 1090) # Team B Score
        self.roi_timer = (20, 100, 930, 990)       # Round Timer

        # 2. PLAYER SIDEBARS (Left & Right)
        # We define the "Start Y" and "Step Y" to generate slots for 5 players
        self.left_sidebar_x = 100   # Approx X for Left Health Bars
        self.right_sidebar_x = 1820 # Approx X for Right Health Bars
        
        self.sidebar_start_y = 550  # Start lower down (approx middle of screen)
        self.sidebar_step_y = 85    # Vertical distance between players
        
        # Specific offsets for Credits (relative to player slot)
        # In VCT, credits are usually small text under the name or next to weapon
        self.credits_offset_x = 50 
        self.credits_offset_y = 10

    def preprocess_image(self, img, invert=True):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # High contrast thresholding for white text on dark background
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        if invert:
            thresh = cv2.bitwise_not(thresh)
        return thresh

    def read_number(self, image_crop):
        """Reads integers from an image crop using Tesseract."""
        if image_crop.size == 0: return 0
        
        processed = self.preprocess_image(image_crop)
        # config: assume single block of digits
        config = r'--oem 3 --psm 6 outputbase digits'
        text = pytesseract.image_to_string(processed, config=config)
        
        # Clean up non-digits (handle commas like "1,550")
        digits = re.sub(r"[^0-9]", "", text)
        return int(digits) if digits else 0

    def check_alive_status(self, frame, side='left'):
        """
        Counts alive players by checking if their health bar area is colored vs gray.
        """
        alive_count = 0
        alive_indices = []
        
        # Define X coordinate based on side
        # Left bars grow Right; Right bars grow Left. 
        # We sample a pixel that should be colored if full HP.
        sample_x = 260 if side == 'left' else 1660 
        
        # Iterate through 5 player slots
        # Note: In VCT, the player list is usually vertically centered or bottom-aligned
        # We'll scan 5 zones. You might need to tweak 'start_y' based on exact UI.
        start_y = 540 
        gap = 95 # approximate gap between player cards
        
        for i in range(5):
            y = start_y + (i * gap)
            
            # Safety check for frame bounds
            if y >= frame.shape[0]: break

            # Crop a tiny sample of the health bar
            # Region: 10x10 pixel box
            sample = frame[y:y+10, sample_x:sample_x+10]
            
            # Check if it has color (Saturation > threshold)
            hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
            saturation = np.mean(hsv[:, :, 1])
            value = np.mean(hsv[:, :, 2])
            
            # Active health bars are bright and saturated. Dead/Gray is low sat.
            if saturation > 40 and value > 50:
                alive_count += 1
                alive_indices.append(i)
        
        return alive_count

    def get_economy(self, frame, side='left'):
        """
        Attempts to read credit counts for all players on a side and sum them.
        """
        total_credits = 0
        
        # Coordinates for Credit Text (This is tricky and varies by specific VCT overlay version)
        # Based on your image: Credits are small, white text, e.g., "1,550"
        # They appear below the name or near the weapon icon.
        
        base_x = 180 if side == 'left' else 1600
        start_y = 565 # Slightly below the health bar/name
        gap = 95
        
        for i in range(5):
            y = start_y + (i * gap)
            
            # Crop the credit text area
            # ROI: y:y+20, x:x+60
            credit_roi = frame[y:y+25, base_x:base_x+70]
            
            # OCR
            credits = self.read_number(credit_roi)
            
            # Sanity check: Credits rarely exceed 9000 or are < 0
            if 0 <= credits <= 9000:
                total_credits += credits
                
        return total_credits

    def analyze_vct_frame(self, frame):
        """
        Master function to get all VCT stats.
        """
        stats = {}
        
        # 1. Scores (Top Bar)
        score_l_img = frame[self.roi_score_left[0]:self.roi_score_left[1], 
                            self.roi_score_left[2]:self.roi_score_left[3]]
        score_r_img = frame[self.roi_score_right[0]:self.roi_score_right[1], 
                            self.roi_score_right[2]:self.roi_score_right[3]]
                            
        stats['score_left'] = self.read_number(score_l_img)
        stats['score_right'] = self.read_number(score_r_img)
        
        # 2. Alive Players (Sidebars)
        stats['alive_left'] = self.check_alive_status(frame, side='left')
        stats['alive_right'] = self.check_alive_status(frame, side='right')
        
        # 3. Economy (OCR)
        # Note: Economy is often hidden during combat. 
        # You might want to cache the last valid value seen during Buy Phase.
        stats['eco_left'] = self.get_economy(frame, side='left')
        stats['eco_right'] = self.get_economy(frame, side='right')
        
        return stats