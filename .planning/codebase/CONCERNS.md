# Codebase Concerns

**Analysis Date:** 2026-02-12

## Tech Debt

**Hardcoded Coordinates and Resolution Assumptions:**
- Issue: ROI coordinates are hardcoded for 1920x1080 resolution with no scaling or adaptation mechanism
- Files: `d:\Git\Val-Prediciton-Model\config.py`, `d:\Git\Val-Prediciton-Model\vision_engine.py`, `d:\Git\Val-Prediciton-Model\dashboard.py`
- Impact: System completely breaks with different broadcast resolutions, aspect ratios, or UI layout changes. Any VCT UI refresh requires manual recalibration of ~20+ coordinate values
- Fix approach: Implement dynamic ROI detection using template matching or UI element detection; create resolution-agnostic coordinate mapping system; add calibration wizard to visually select regions

**Duplicate Vision Engine Implementation:**
- Issue: VCTVisionEngine class exists in both `d:\Git\Val-Prediciton-Model\vision_engine.py` and `d:\Git\Val-Prediciton-Model\dashboard.py` with slightly different coordinate values
- Files: `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 6-146), `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 18-112)
- Impact: Bug fixes must be applied to two places; inconsistent behavior between backend and dashboard; increased maintenance burden; vision_engine.py is unused by backend.py
- Fix approach: Remove duplicate from dashboard.py; refactor backend.py to use shared vision_engine module; consolidate all ROI definitions to config.py

**Backend Never Uses Shared Vision Engine:**
- Issue: `d:\Git\Val-Prediciton-Model\backend.py` implements its own frame processing logic (lines 31-71) instead of using VCTVisionEngine
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 31-71), `d:\Git\Val-Prediciton-Model\vision_engine.py`
- Impact: Code duplication, inconsistent feature extraction between backend and dashboard, backend lacks economy calculation and other vision features
- Fix approach: Refactor backend.py to instantiate and use VCTVisionEngine for all frame analysis

**Synthetic Training Data Doesn't Match Real Game Dynamics:**
- Issue: Model trained on random synthetic data with arbitrary probability formula (line 133 in dashboard.py) rather than actual VCT match data
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 118-141)
- Impact: Model predictions are unreliable; no correlation to actual team strength, economy impact, positioning, or map knowledge; model accuracy unknown; serves primarily as placeholder
- Fix approach: Collect real match data from VODs with ground truth outcomes; implement cross-validation with historical match statistics; track prediction accuracy against real results

**Magic Numbers Throughout Vision Processing:**
- Issue: Color thresholds, brightness thresholds, pixel offsets hardcoded without explanation or documentation
- Files: `d:\Git\Val-Prediciton-Model\config.py` (lines 26-27), `d:\Git\Val-Prediciton-Model\backend.py` (lines 46, 55, 62), `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 75, 86), `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 85-87)
- Examples: Brightness threshold 50 (line 55 backend.py), Spike pixel count threshold 50 (line 46 backend.py), Saturation threshold 40 (line 85 vision_engine.py)
- Impact: No way to understand why values were chosen; thresholds may fail on different lighting conditions, stream quality, or broadcast graphics
- Fix approach: Extract all thresholds to config.py with descriptive names; add comments explaining purpose and calibration method; create threshold tuning utility

**No Dependency Version Pinning:**
- Issue: `d:\Git\Val-Prediciton-Model\requirements.txt` lists dependencies without version constraints
- Files: `d:\Git\Val-Prediciton-Model\requirements.txt`
- Impact: Different installations may use incompatible library versions; pytesseract API changes could break OCR; numpy/OpenCV behavior may differ; reproducibility impossible
- Fix approach: Run `pip freeze > requirements.txt` to pin all versions; create requirements-dev.txt for development tools; implement CI/CD to test against multiple Python/library versions

## Known Bugs

**Stream Reconnection Infinite Loop Risk:**
- Symptoms: If stream consistently fails or ends, backend.py reconnects indefinitely without backoff or eventual shutdown
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 78-88)
- Trigger: Launch backend against dead/invalid stream URL; stream ends but doesn't EOF properly
- Workaround: Manually kill process; add timeout to stream.read()
- Root cause: No max retry limit, no exponential backoff, no detection of permanent failures
- Fix: Add retry counter with max limit (e.g., 5 reconnects); implement exponential backoff (2s → 4s → 8s); detect permanent failures

**OCR Empty Image Fallback Returns 0, Not Error:**
- Symptoms: When image crop fails, function silently returns 0 instead of indicating failure or trying fallback methods
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (line 50), `d:\Git\Val-Prediciton-Model\vision_engine.py` (line 40)
- Trigger: Score region OCR fails due to reflection, overlay, or broadcast graphics; returns 0 instead of preserving previous score
- Impact: Game state jumps from 13-12 to 0-0, creating false data spikes in predictions
- Fix: Cache last valid score; return None + log warning; implement multi-level fallback (larger ROI, different preprocessing, manual entry)

**No Handling for Incomplete Player Avatars:**
- Symptoms: If only 4 players visible (late-game elimination), alive count reading continues trying to sample slot 5
- Files: `d:\Git\Val-Prediciton-Model\config.py` (lines 17-22), `d:\Git\Val-Prediciton-Model\backend.py` (lines 50-63)
- Trigger: Queue breaks, one player eliminated off-screen before frame capture
- Impact: Reads garbage pixels, returns incorrect alive counts, makes prediction invalid
- Fix: Detect empty avatar slots using brightness variation; stop iteration early; validate alive count against previous frame

**Spike Detection Threshold Too Strict for Lighting Variations:**
- Symptoms: Spike planted indicator sometimes misdetected as unplanted or vice versa under different broadcast lighting
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (line 46), `d:\Git\Val-Prediciton-Model\dashboard.py` (line 90)
- Trigger: Mid-round lighting change, spike icon dimmer or brighter than expected
- Cause: Fixed red pixel count threshold (>50) doesn't adapt to lighting; HSV ranges too restrictive
- Fix: Implement adaptive thresholding; normalize by ROI brightness; track spike state changes rather than absolute value

## Security Considerations

**Unsanitized File Upload Path Vulnerability:**
- Risk: Dashboard accepts file uploads (line 169, dashboard.py) and directly opens with cv2.VideoCapture without validation
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 169, 181-184)
- Current mitigation: File type limited to mp4/jpg/png in uploader; tempfile.NamedTemporaryFile creates in system temp directory
- Recommendations:
  - Validate file MIME type before reading (magic bytes, not extension)
  - Scan uploaded files with antivirus/malware detector
  - Enforce maximum file size limit (e.g., 500MB for videos)
  - Store uploads outside web-accessible directory
  - Implement rate limiting on uploads per IP/user

**Hardcoded Windows Tesseract Path:**
- Risk: Config suggests Windows-only deployment with hardcoded path assumption
- Files: `d:\Git\Val-Prediciton-Model\config.py` (lines 4-5), `d:\Git\Val-Prediciton-Model\dashboard.py` (line 154)
- Impact: Fails on macOS/Linux without modification; path may not exist; no error message if Tesseract absent
- Current mitigation: Path is optional (can be None); dashboard allows override via text input
- Recommendations:
  - Detect Tesseract location automatically (cross-platform check)
  - Use poetry/conda for system dependency management
  - Provide clear setup documentation per OS
  - Fail gracefully with actionable error message if Tesseract unavailable

**No Authentication on Backend Stream Watcher:**
- Risk: backend.py runs continuously, consuming resources, with no access control
- Files: `d:\Git\Val-Prediciton-Model\backend.py`
- Impact: Anyone with access to server can launch unlimited stream monitoring processes; no audit trail
- Fix: Add process authentication; implement resource quotas; add logging of start/stop events with timestamps

**Streamlink URL Injection Risk:**
- Risk: stream_url is passed directly to streamlink.streams() without validation
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (line 21)
- Impact: Malicious stream URL could potentially execute code via streamlink's processing
- Fix: Whitelist allowed domains (youtube.com, twitch.tv, etc.); validate URL format before passing to streamlink

## Performance Bottlenecks

**OCR on Every Frame is CPU-Intensive:**
- Problem: Score/timer OCR performed even on frames where text hasn't changed, wasting CPU
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 39, 91), `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 99-100)
- Cause: No frame differencing; every frame processed equally; pytesseract is inherently slow
- Current state: Backend downsamples to 6fps (every 10th frame) which helps, but still excessive
- Improvement path: Implement frame hashing to detect score change; OCR only when diff detected; cache OCR output for N frames; use hardware acceleration for image preprocessing

**Live Stream Connection and Buffering:**
- Problem: No stream quality selection or adaptive bitrate; may cause buffering on lower bandwidth connections
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (line 27)
- Cause: Always selects 'best' stream quality which may be 1080p60 (high bandwidth requirement)
- Improvement path: Allow quality selection in config; implement adaptive quality based on available bandwidth; add buffer underrun detection

**Whole Frame Capture When Small ROIs Needed:**
- Problem: Backend captures full 1920x1080 frames from stream just to extract small ROI regions (~200x200 pixels total)
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 31-71)
- Cause: cv2.VideoCapture doesn't support hardware ROI cropping; entire frame must be decoded
- Improvement path: Use codec-level ROI extraction if available; implement frame region-of-interest at codec level; use ffmpeg crop filter

**Model Prediction Called Even With Invalid Game State:**
- Problem: Model.predict_proba() called even when vision confidence low (e.g., score OCR failed)
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 236, 261)
- Impact: Garbage predictions displayed with high confidence; users can't distinguish valid from invalid
- Fix: Compute vision confidence score; skip prediction if confidence < threshold; display "Unable to analyze frame" instead

## Fragile Areas

**Vision Engine ROI Coordinate Tuning:**
- Files: `d:\Git\Val-Prediciton-Model\config.py` (lines 11-22), `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 13-38), `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 25-38)
- Why fragile: ROIs are pixel-perfect coordinates; ±5 pixel error causes feature detection to completely fail (empty crops, wrong regions); no visual feedback during tuning
- Safe modification:
  1. Add debug mode that overlays ROI boxes on frame
  2. Create tuning script that shows real-time ROI extraction
  3. Accept ROI region definitions interactively with visual feedback
  4. Test all ROI changes against known sample frames before deployment
- Test coverage: Zero automated tests for vision coordinate correctness; manual visual verification only

**Alive Player Detection Brightness Sampling:**
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 50-63), `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 51-89)
- Why fragile: Detects alive status by checking if 10x10 pixel sample is bright (>50 threshold); extremely susceptible to:
  - Broadcast graphics overlays covering the sample point
  - Lighting changes during stream
  - Different map lighting conditions affecting baseline brightness
  - Player model colors and weapon visibility
- Safe modification:
  1. Sample multiple points per player, not single pixel location
  2. Use color-based detection (alive bars are colored, dead are grayscale) instead of brightness
  3. Compare to known dead state as baseline
  4. Add smoothing: only change alive status if consistent across 5+ frames
- Test coverage: No unit tests; integration tests only with real VOD samples

**Tesseract OCR Dependency:**
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 9-11), `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 19-21)
- Why fragile: Tesseract is separate binary; code fails silently if missing; OCR accuracy varies with:
  - Image quality and compression artifacts
  - Font rendering in different broadcast versions
  - Overlapping UI elements
  - Motion blur on captured frames
- Safe modification:
  1. Check Tesseract exists at startup; fail with clear error message if missing
  2. Implement fallback to EasyOCR or PaddleOCR as backup
  3. Validate OCR output format before use (regex for "MM:SS" timer format)
  4. Cache successful OCR results to detect anomalies
- Test coverage: No unit tests for OCR; dashboard has manual testing only

**Streamlink Stream Resolution:**
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 20-28)
- Why fragile: Assumes 'best' stream quality always matches expected 1920x1080; actual resolution varies by:
  - Stream source (YouTube/Twitch encoding differences)
  - User's internet bandwidth available
  - Broadcaster's streaming setup
  - VOD vs live stream resolution differences
- Safe modification:
  1. Query actual stream resolution after connection
  2. Dynamically adjust ROI coordinates based on detected resolution
  3. Or enforce minimum resolution requirement and fail if unavailable
  4. Log actual resolution for debugging
- Test coverage: Only tested against specific YouTube VOD; untested with Twitch streams

## Scaling Limits

**Single-Thread Frame Processing:**
- Current capacity: 6 fps processing (every 10th frame at 60fps capture), single CPU core
- Limit: CPU saturated at moderate resolution; 4K resolution would require aggressive downsampling or parallel processing
- Scaling path: Implement multi-threading for vision processing; use process pool for OCR (CPU-bound); stream frame queue between capture and analysis threads

**JSON File State Serialization:**
- Current capacity: Backend writes game_state.json atomically every ~167ms (6 fps)
- Limit: File I/O becomes bottleneck if dashboard polls continuously; no queue if writes block
- Scaling path: Switch to message queue (Redis, RabbitMQ) or WebSocket connection; implement frame skip if write falls behind

**In-Memory Model Persistence:**
- Current capacity: Single LogisticRegression model cached via @st.cache_resource for entire session
- Limit: Model retrains on every dashboard restart; no version management or A/B testing capability
- Scaling path: Persist model to disk (pickle/joblib); implement model versioning; load correct version based on config

**Streamlink Network Connection:**
- Current capacity: Single stream connection with infinite reconnect retry
- Limit: If stream repeatedly fails, connection loop consumes bandwidth and CPU trying to reconnect
- Scaling path: Implement exponential backoff; add max retry limit; monitor connection health metrics

## Dependencies at Risk

**Tesseract-OCR System Binary:**
- Risk: Project depends on Tesseract as separate system dependency with no automatic installation
- Impact: Setup failure on clean environment; unclear error messages if missing; upgrade incompatibilities
- Current state: Only documented in config comments; no setup script or dependency checker
- Migration plan:
  1. Replace with pure-Python OCR library (EasyOCR, PaddleOCR, or KerasOCR)
  2. Or use poetry + conda to manage system dependencies
  3. Or implement Docker image with Tesseract pre-installed
  4. Fallback option: API-based OCR (Google Vision, Azure Computer Vision) with caching

**streamlink Library:**
- Risk: Depends on external streaming library for Twitch/YouTube URL resolution; subject to API changes if streamlink abandons Twitch/YouTube support
- Impact: Cannot access streams if streamlink stops supporting platforms
- Current state: streamlink maintained by community but could be unmaintained in future
- Migration plan:
  1. Implement direct YouTube/Twitch API integration (requires API keys and authentication)
  2. Fall back to yt-dlp for YouTube-only support
  3. For production, negotiate direct stream access with VCT broadcasts

**pytesseract Version Incompatibilities:**
- Risk: Tesseract and pytesseract must match versions; OCR API may change
- Impact: Upgrade one without other causes silent failures or crashes
- Current state: No version pinning, testing in requirements.txt
- Fix: Pin both pytesseract and system Tesseract versions together; test compatibility matrix

**scikit-learn Model Serialization:**
- Risk: Model saved as pickle; unsafe to unpickle untrusted data; format incompatible across versions
- Impact: Cannot safely load model from untrusted source; model breaks with sklearn version upgrade
- Current state: Model retrained on startup, not persisted
- Fix: Use joblib for serialization; implement model versioning; validate model signature before loading

## Missing Critical Features

**No Confidence Scoring for Predictions:**
- Problem: Model outputs win probability (e.g., 67%) but provides no indication of whether this is high-confidence or just a guess
- Blocks: Cannot distinguish between "team clearly favored" and "50-50 coin flip"
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 236-237)
- Solution: Calculate prediction confidence via model uncertainty; indicate low-confidence predictions to user

**No Historical State Tracking:**
- Problem: Each frame analyzed in isolation; no memory of previous game state changes
- Blocks: Cannot detect momentum swings, economy efficiency, or sustained advantages
- Files: All vision processing layers
- Solution: Implement sliding window of past N frames; calculate deltas and trends; feed temporal features to model

**No Manual Calibration Tool:**
- Problem: ROI coordinates hardcoded; when broadcast UI changes, must edit config.py manually
- Blocks: Cannot adapt to new VCT seasons with different graphics layouts
- Solution: Create GUI tool to click regions on sample frame; automatically saves coordinates to config

**No Error Recovery or User Feedback:**
- Problem: When vision fails (OCR error, spike detection fails, etc.), user gets silent 0 values
- Blocks: Cannot debug why predictions are wrong; no visibility into failure modes
- Solution: Implement vision health check; display confidence metrics; show which features failed

**No Batch Processing for Historical Data:**
- Problem: Can only analyze current frame at a time; cannot process VOD files to build training dataset
- Blocks: Cannot improve model with historical match outcomes
- Solution: Add batch processing mode; process entire VOD and output frame-by-frame statistics

## Test Coverage Gaps

**Vision Coordinate Correctness Untested:**
- What's not tested: Whether ROI coordinates actually capture the intended game UI elements
- Files: `d:\Git\Val-Prediciton-Model\config.py`, `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 13-38)
- Risk: Silent failures where coordinates are off by pixels; features return 0 instead of correct values
- Priority: High - coordinates are fragile and frequently break
- Test approach: Create automated tests with known sample frames; assert OCR output matches expected values; store expected output as golden frames

**OCR Accuracy Not Measured:**
- What's not tested: Whether pytesseract correctly reads score/timer text under various conditions
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 48-55), `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 38-49)
- Risk: OCR fails silently returning 0; no way to detect errors
- Priority: High - OCR is critical path and known to be fragile
- Test approach: Create test set of score/timer crops from real VODs with ground truth; measure accuracy; set minimum threshold

**Alive Player Detection Accuracy:**
- What's not tested: Whether brightness-based detection correctly identifies alive vs dead players
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 50-63), `d:\Git\Val-Prediciton-Model\vision_engine.py` (lines 51-89)
- Risk: False positives/negatives make win predictions invalid; no way to detect
- Priority: High - directly impacts prediction accuracy
- Test approach: Sample frames with known player states (5v5, 4v5, etc.); validate alive count correctness; test against various lighting/maps

**Model Predictions Not Validated Against Real Outcomes:**
- What's not tested: Whether predicted win probabilities correlate with actual match results
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 117-141)
- Risk: Model is trained on synthetic data with no real-world validation; predictions may be completely wrong
- Priority: Critical - core business logic is untested
- Test approach: Collect 100+ real VCT match samples; run prediction on each; compare against actual winner; calculate accuracy/calibration

**Stream Connection Resilience:**
- What's not tested: Whether backend.py correctly handles stream drops, reconnects, network errors
- Files: `d:\Git\Val-Prediciton-Model\backend.py` (lines 19-28, 73-88)
- Risk: Infinite reconnect loops, data corruption on disconnect, unclear state
- Priority: High - affects production reliability
- Test approach: Mock streamlink with intentional failures; verify exponential backoff; verify eventual shutdown after max retries

**Dashboard UI Error Handling:**
- What's not tested: What happens when user uploads corrupted video, OCR fails, or vision processing crashes
- Files: `d:\Git\Val-Prediciton-Model\dashboard.py` (lines 176-213)
- Risk: App crashes or shows confusing 0 values instead of error message
- Priority: Medium - affects user experience but not data integrity
- Test approach: Create test videos (corrupted, wrong resolution, unplayable); ensure graceful error messages

---

*Concerns audit: 2026-02-12*
