# Domain Pitfalls: CV-Based Valorant Esports Event Detection

**Domain:** Computer vision event extraction from VCT broadcast streams
**Researched:** 2026-02-12
**Confidence:** HIGH (based on existing codebase analysis and domain expertise)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or complete system failure.

### Pitfall 1: Replay Footage Creating Phantom Events
**What goes wrong:** Broadcast replays show kills/rounds that already happened. Without replay detection, you log duplicate events with wrong timestamps, corrupting your event log. A single 30-second replay can inject 5-10 false kill events.

**Why it happens:**
- VCT broadcasts frequently show replays during tactical timeouts, between rounds, or after clutch plays
- Replay overlays are subtle (small "REPLAY" text in corner, different camera angles)
- State extraction (scores, alive counts) works identically on replay footage
- Timer may continue running or reset during replays

**Consequences:**
- Event logs contain duplicate kills/rounds with incorrect timestamps
- Prediction model trains on corrupted data (same events counted 2-3x)
- Economy calculations become impossible (phantom kills reset economy state)
- No way to retroactively clean data without manual review of VODs

**Prevention:**
1. **OCR-based replay detection:** Add ROI for "REPLAY" text overlay (typically top-left or top-right corner)
2. **State coherence validation:** Alive counts should only decrease, never increase (except round reset). If alive_count increases without score change, likely replay
3. **Timer regression detection:** If timer increases between frames (without round end), flag as replay
4. **Score change validation:** Score can only increase, never decrease. Score regression = replay or broadcast transition
5. **Pause state detection:** Suppress event detection during tactical timeouts (different overlay state)

**Detection:**
- Event logs show more kills than mathematically possible (e.g., 8 kills in a 5v5 round)
- Alive count increases mid-round
- Timestamp order violations (events appear out of sequence)
- Economy spikes don't match round outcomes

**Phase mapping:** Phase 1 (event detection) must include replay detection before processing any events. This is not a "nice to have" — it's foundational to data quality.

---

### Pitfall 2: Hardcoded ROI Coordinates Breaking on Overlay Updates
**What goes wrong:** VCT updates broadcast overlay between seasons/events (2024 vs 2025 overlays differ). Your hardcoded ROI coordinates suddenly extract nothing or wrong data. All existing frame processing fails silently or returns garbage.

**Why it happens:**
- Riot updates VCT broadcast graphics every few months (Champions vs Masters vs Kickoff overlays vary)
- Stream providers (Valorant_Esports_EN vs regional channels) may use slightly different layouts
- UI scales differently at different stream qualities (1080p source vs re-encoded 720p)
- Your codebase has two conflicting ROI systems (config.py vs vision_engine.py with different coordinates)

**Consequences:**
- OCR reads wrong screen regions, returns gibberish or empty strings
- Alive count detection samples wrong pixels, always returns 0 or 5
- Spike status detection fails, always returns false
- System appears to work (no crashes) but logs completely invalid data
- Historical data becomes incomparable across overlay versions

**Prevention:**
1. **Overlay version detection:** OCR a known constant element (e.g., "VALORANT" logo position/text) to fingerprint overlay version
2. **Multi-version ROI configs:** Store ROI sets per overlay version (VCT_2024_CHAMPIONS, VCT_2025_KICKOFF, etc.)
3. **Automated ROI calibration:** On startup, show reference frame, let user click key points to auto-adjust ROIs
4. **Validation tests:** Before processing match, test OCR on known static elements (round counter should read "0-0" at start)
5. **Runtime sanity checks:** If score OCR fails >10 consecutive frames, alert that ROI is likely wrong
6. **Single source of truth:** Consolidate config.py and vision_engine.py ROI definitions (currently duplicated and conflicting)

**Detection:**
- OCR consistently returns empty strings or single characters
- Score never changes despite round progression
- Alive counts stay at 0 or 5 all match
- Economy values are always 0 or nonsensical (9999999)
- Timer reads random characters instead of MM:SS

**Phase mapping:** Phase 1 needs ROI validation. Phase 2 (multi-match reliability) needs overlay version detection and multi-version support.

---

### Pitfall 3: State Debouncing Failures Creating Event Storms
**What goes wrong:** OCR flickers between correct/incorrect values across consecutive frames (timer reads "1:30", "1", "1:30", "1:3C", "1:30"). Without debouncing, each flicker triggers a state change event. A single kill generates 5-10 "kill" events as alive_count oscillates (4, 5, 4, 4, 5, 4).

**Why it happens:**
- pytesseract OCR is non-deterministic on marginal inputs (compression artifacts, motion blur)
- Alive status detection uses brightness thresholds — small lighting changes cause flicker
- Stream buffering causes duplicate frames or skipped frames
- HSV color detection for spike status is sensitive to compression artifacts
- You process at 6fps but events happen between frames (kill occurs between frame N and N+1)

**Consequences:**
- Event logs contain 10x-100x more events than actually occurred
- Impossible to determine "true" event timestamp (which of 10 flickers is real?)
- Prediction model sees massive noise-to-signal ratio
- Event log file size explodes (MB instead of KB per match)
- Downstream analysis becomes impossible (can't calculate kill rate when kills are duplicated)

**Prevention:**
1. **Temporal debouncing:** State must persist for N consecutive frames (N=3-5) before emitting event
2. **Confidence thresholds:** OCR should return confidence scores — ignore low-confidence reads
3. **State history window:** Track last 10 states, use median/mode instead of last value
4. **Hysteresis on thresholds:** Use different thresholds for state transitions (e.g., alive if brightness >60, dead if <40, keep previous state if 40-60)
5. **Event deduplication:** Before logging event, check if identical event occurred in last 2 seconds
6. **OCR preprocessing improvements:**
   - Upscale ROI before OCR (2x bilinear)
   - Denoise with Gaussian blur
   - Adaptive thresholding instead of fixed threshold
   - Whitelist allowed characters (timer = "0-9:", score = "0-9")

**Detection:**
- Event log shows 50+ events per round (should be 5-15)
- Multiple identical events within 1-2 seconds
- Alive count changes every frame instead of step changes
- Log file size >1MB for single map (should be ~50-200KB)
- Kill events when alive_count didn't actually change

**Phase mapping:** Phase 1 (event detection) requires debouncing logic before any events are logged. This is the difference between usable and unusable data.

---

### Pitfall 4: Buy Phase vs Combat Phase State Conflation
**What goes wrong:** Economy data is only visible during buy phase (first 30s of round). During combat, economy UI is hidden. Your code reads economy ROI during combat, gets 0 or random noise, and logs "team economy dropped to 0" events. You can't distinguish between "actual eco round" and "UI not visible."

**Why it happens:**
- VCT overlay shows economy only during buy phase, hides during combat to reduce clutter
- Your current code (vision_engine.py get_economy) doesn't check game phase before OCR
- Round timer alone doesn't indicate phase (spike plant extends timer)
- No state machine tracking round phase transitions

**Consequences:**
- Economy event logs are 90% false "economy dropped to 0" during combat
- Can't determine actual buy type (eco/force/full buy) from logs
- Prediction model trained on garbage economy features
- Manual data cleaning requires watching every round to classify buy types

**Prevention:**
1. **Phase detection state machine:**
   - Buy phase: timer 1:40-1:10, economy visible
   - Combat phase: timer <1:10 or spike planted, economy hidden
   - Post-round: all dead or timer 0:00, transition state
2. **Cache last valid economy:** During combat, use cached buy-phase economy values
3. **Event timing restrictions:** Only emit "buy_type" event during buy phase (once per round)
4. **UI element presence detection:** Check for economy UI visibility (is background box present?) before OCR
5. **Round phase in event schema:** Tag events with round_phase context (buy/combat/post)

**Detection:**
- Economy oscillates between valid values and 0 throughout round
- Economy events trigger mid-combat
- Team economy shows as 0 when they're clearly on full buy (rifles + abilities)
- Event logs missing buy_type classification

**Phase mapping:** Phase 2 (economy events) requires phase detection state machine. Attempting economy extraction without phase awareness produces unusable data.

---

### Pitfall 5: Frame-Level vs Event-Level Timestamp Precision Confusion
**What goes wrong:** You timestamp events with frame capture time, but frames are captured at 6fps (every ~166ms). Actual game events happen at 60fps game time. Two kills 50ms apart appear simultaneous in your log. You can't distinguish "trade kill" (50ms apart) from "double kill" (1000ms apart).

**Why it happens:**
- Stream is 60fps, you process every 10th frame (6fps optimization)
- Multiple game events can occur between processed frames
- time.time() gives you "when frame was processed" not "when event occurred in game"
- VCT broadcasts are already delayed 5-10 seconds from actual game time
- No access to game server timestamps — only broadcast timestamps

**Consequences:**
- Event sequence order is ambiguous (which kill happened first?)
- Can't calculate reaction times or trade kill timing
- Prediction model can't use fine-grained timing features
- Round timer from OCR doesn't align with event timestamps (timer is game time, timestamp is wall clock time)
- Replay analysis shows timestamp errors of 2-3 seconds

**Prevention:**
1. **Use round timer as event timestamp:** OCR'd timer (1:23) is game time — convert to seconds remaining and use as event timestamp
2. **Event ordering within frame:** When multiple state changes detected in one frame, assign sub-frame ordering based on logic (score change implies round end, which implies all deaths occurred before)
3. **Timestamp normalization:** Store both wall_clock_time (frame capture) and game_time (timer OCR) for each event
4. **Accept precision limits:** Document that events within same frame have ~166ms timestamp uncertainty
5. **Frame number as event ID:** Include frame_number in event schema for exact ordering

**Detection:**
- Event timestamps don't align with round timer values
- Multiple events have identical timestamps when they should be sequential
- Events appear out of logical order (round end before all kills)
- Timer shows 1:30 but event timestamp is wall clock time

**Phase mapping:** Phase 1 must decide on timestamp strategy upfront — changing timestamp schema after data collection requires reprocessing all matches.

---

## Moderate Pitfalls

Mistakes that cause delays, data quality issues, or technical debt.

### Pitfall 6: Stream Quality Variations Breaking Detection Thresholds
**What goes wrong:** Your brightness threshold for alive detection (brightness > 50) works on 1080p source stream but fails on 720p re-encoded stream. Stream buffering drops quality mid-match. Detection accuracy drops from 95% to 60%.

**Why it happens:**
- Streamlink "best" quality varies (sometimes 1080p60, sometimes 720p30)
- Network issues cause adaptive bitrate changes mid-match
- Different stream sources (Twitch vs YouTube) use different encoders (compression artifacts vary)
- Stream provider may switch encoder settings between maps

**Prevention:**
1. **Adaptive thresholds:** Calibrate thresholds on first round (sample alive players at round start when all are alive)
2. **Quality validation:** Check resolution on each frame, warn if != 1920x1080
3. **Fallback detection methods:** If brightness detection fails, try edge detection or template matching
4. **Log stream metadata:** Record resolution, bitrate, source for each match to correlate with accuracy

**Detection:**
- Alive count accuracy drops suddenly mid-match
- Accuracy varies between matches with same ROI settings
- OCR confidence scores decrease

**Phase mapping:** Phase 2 (multi-match reliability) should add stream quality monitoring and adaptive thresholding.

---

### Pitfall 7: Team/Map Auto-Detection Without Validation
**What goes wrong:** OCR misreads team name "LOUD" as "L0UD" or map name "Ascent" as "Ascerit". You auto-create match records with wrong team names. Historical data has 5 variations of same team name ("LOUD", "L0UD", "LODD", etc.). Cross-match analysis impossible.

**Why it happens:**
- Team name text is stylized/custom fonts (not OCR-friendly)
- Map names appear briefly (2-3 seconds at round start)
- No validation against known team/map lists
- Typos propagate through entire match

**Prevention:**
1. **Fuzzy matching against whitelist:** Maintain list of known VCT teams, find closest match (Levenshtein distance)
2. **Multi-frame consensus:** Read team name from 5-10 frames, use majority vote
3. **Manual confirmation:** Show detected team/map, require user confirmation before starting match
4. **Regex patterns:** Team names follow patterns (all caps, 2-6 chars) — reject invalid formats
5. **Metadata API fallback:** Use VCT API (vlr.gg, rib.gg) to fetch current matches, match against detected names

**Detection:**
- Multiple variations of same team in database
- Map names that don't exist in Valorant
- Team names with numbers/symbols (L0UD instead of LOUD)

**Phase mapping:** Phase 1 (auto-detect teams/map) should include fuzzy matching and validation from day one.

---

### Pitfall 8: Round Transition Detection Failures
**What goes wrong:** Can't reliably detect when round ends and new round begins. Miss the state reset point. Carry over state from previous round (alive counts, spike status). Log shows "spike planted" in new round that just started.

**Why it happens:**
- Multiple transition indicators: score change, timer reset, all players alive, tactical timeout
- Transition timing varies (instant vs 5-second break vs tactical timeout)
- Replay footage shown during transition
- Score change detection requires 2-frame history (previous score, current score)

**Prevention:**
1. **Multi-signal transition detection:**
   - Score changed AND timer >1:30 (reset) AND all players alive = new round
   - Use all three signals, not just one
2. **State reset on transition:** Clear spike_planted, reset alive counts, invalidate economy cache
3. **Transition cooldown:** After detecting round end, ignore events for 5 seconds (transition period)
4. **Pre-round validation:** First frame of new round should have timer ~1:40, alive counts = 5, spike unplanted

**Detection:**
- Events logged during round transitions (e.g., kill events when all players alive)
- Spike status carries over to new round
- Round event counts don't reset (shows 10 kills in a single round across multiple actual rounds)

**Phase mapping:** Phase 1 (event detection) requires robust round boundary detection — events without correct round context are useless.

---

### Pitfall 9: OCR Character Confusion on Stylized Overlays
**What goes wrong:** VCT overlay uses custom fonts. pytesseract confuses "0" vs "O", "1" vs "I", "5" vs "S". Score reads "1O" instead of "10". Timer reads "I:30" instead of "1:30". Economy reads "S00" instead of "500".

**Why it happens:**
- Tesseract trained on standard fonts, VCT uses custom esports fonts
- White text on colored/gradient backgrounds reduces contrast
- Small text sizes (economy numbers are ~12px height)
- Italicized or bold styling breaks OCR assumptions

**Prevention:**
1. **Character whitelisting:** Configure Tesseract to only output expected chars
   - Timer: `tessedit_char_whitelist=0123456789:`
   - Score: `tessedit_char_whitelist=0123456789`
   - Economy: `tessedit_char_whitelist=0123456789,`
2. **Image preprocessing:**
   - Upscale 2x before OCR (larger text = better accuracy)
   - Convert to pure black text on white background (aggressive thresholding)
   - Denoise with morphological operations
3. **Post-OCR validation:**
   - Timer format: `\d:\d\d` or `\d\d:\d\d`
   - Score format: `\d+` where value 0-13
   - Economy format: `\d{3,5}` where value 0-9000
4. **Template matching fallback:** For digits 0-9, create templates from known-good frames, use cv2.matchTemplate if OCR fails

**Detection:**
- OCR output contains letters when expecting only numbers
- Invalid timer formats ("1O:3C" instead of "10:30")
- Score values >13 (impossible in Valorant)
- Economy values with letters or symbols

**Phase mapping:** Phase 1 should implement character whitelisting and validation immediately — this is basic OCR hygiene.

---

### Pitfall 10: Agent/Ultimate Detection Via CV Is Extremely Fragile
**What goes wrong:** Agent portraits are small (~30x30px), vary by skin, partially occluded by UI. Ultimate status is a tiny colored dot. Detection accuracy <70%. You need 10 correct detections per round (5 agents * 2 teams). 70%^10 = 2.8% chance of perfect round detection.

**Why it happens:**
- Agent portraits use varied skins/cosmetics (not canonical images)
- Ultimate dot is 3-5 pixels, easily lost in compression
- Lighting/effects vary by map and in-game time
- Templates don't account for all skin variations

**Consequences:**
- Agent composition logs are mostly wrong
- Ultimate tracking is random noise
- Model trained on garbage agent features

**Prevention:**
1. **Defer to Phase 3:** Mark agent/ultimate extraction as "research needed" — don't attempt in Phase 1
2. **Focus on deterministic extraction first:** Score, alive count, timer, spike status are reliable — build on those
3. **Consider alternative data sources:**
   - VCT API often publishes agent comps before match
   - Manual entry of agent comp (one-time per map)
   - Extract from pre-game agent select screen (larger, clearer images)
4. **If attempting CV detection:**
   - Use multiple template matching (5-10 templates per agent for different skins)
   - Require multi-frame consensus (same agent detected 10+ frames)
   - Allow manual override/correction

**Detection:**
- Agent composition changes mid-round (impossible)
- Duplicate agents on same team
- Agents that don't exist in Valorant
- Ultimate status flickers every frame

**Phase mapping:** Phase 1 should explicitly SKIP agent/ultimate detection. Mark as Phase 3 with deep research flag. Focus on reliable state extraction first.

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable.

### Pitfall 11: Overwriting game_state.json Loses Historical Data
**What goes wrong:** Current code overwrites game_state.json every frame. No event history. Can't replay or analyze past events.

**Prevention:** Append events to log file (JSONL or SQLite), don't overwrite.

**Phase mapping:** Phase 1 fixes this immediately — persistent event log is core requirement.

---

### Pitfall 12: No Match Session Management
**What goes wrong:** Can't distinguish between maps in a BO3 series. Event log conflates all maps into single stream.

**Prevention:** Implement match_id, map_number metadata. Detect map transitions (loading screen, score reset to 0-0).

**Phase mapping:** Phase 2 (multi-match support) adds session management.

---

### Pitfall 13: Stream Buffering Causes Frame Duplicates or Skips
**What goes wrong:** Network issues cause streamlink to return duplicate frames or skip frames. Event detection sees same frame twice or misses transition.

**Prevention:**
- Hash frames, skip if identical to previous
- Track frame timestamps, warn if gap >500ms

**Phase mapping:** Phase 2 adds stream health monitoring.

---

### Pitfall 14: No Graceful Degradation When OCR Fails
**What goes wrong:** If timer OCR fails (returns empty string), entire frame processing throws exception. Miss events during OCR failures.

**Prevention:**
- Return None for failed OCR, keep processing other elements
- Use last known valid value with confidence decay
- Log OCR failures for monitoring

**Phase mapping:** Phase 1 adds error handling to all OCR operations.

---

### Pitfall 15: Config.py vs Vision_Engine.py ROI Duplication
**What goes wrong:** Two different ROI coordinate systems in codebase. config.py defines one set, vision_engine.py defines another. They conflict (different coordinates for same elements). Unclear which is "correct."

**Prevention:**
- Consolidate to single source of truth (config.py)
- vision_engine.py should import from config.py
- Delete duplicate definitions

**Phase mapping:** Phase 1 cleanup — fix before building on this foundation.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Event Detection | Replay footage creating phantom events | Implement replay detection from day one |
| Phase 1: Event Detection | State debouncing failures | Require 3-frame consensus for state changes |
| Phase 1: Event Detection | Round transition detection | Multi-signal detection (score + timer + alive) |
| Phase 2: Economy Events | Buy phase vs combat phase conflation | Build phase detection state machine first |
| Phase 2: Multi-Match | Hardcoded ROI coordinates breaking | Add overlay version detection before running multiple matches |
| Phase 2: Team/Map Auto-Detect | OCR typos propagating | Fuzzy match against whitelist, require confirmation |
| Phase 3: Agent/Ultimate Detection | CV detection too fragile | Deep research required — may need alternative approach |
| Phase 3: Agent/Ultimate Detection | Template matching with skin variations | Consider manual entry or API fallback |

---

## Sources

**HIGH confidence:** Based on analysis of existing codebase at d:\Git\Val-Prediciton-Model
- config.py ROI definitions and thresholds
- vision_engine.py extraction methods
- backend.py processing loop and state handling

**MEDIUM confidence:** Domain expertise in CV-based esports analysis
- Replay detection is a known critical issue in all esports CV projects
- OCR reliability on stylized game overlays is well-documented challenge
- State debouncing is standard requirement for any CV state machine

**Research gaps:**
- Exact VCT overlay update schedule (requires monitoring VCT production over multiple events)
- Optimal debouncing parameters (requires empirical testing on real match footage)
- Agent/ultimate detection feasibility (flagged for Phase 3 deep research)

---

## Implementation Priority

**Must address in Phase 1 (foundational):**
1. Replay detection
2. State debouncing (3-frame consensus)
3. Round transition detection
4. Persistent event logging (replace game_state.json overwriting)
5. OCR character whitelisting and validation
6. Consolidate config.py vs vision_engine.py ROI definitions

**Must address in Phase 2 (before multi-match):**
1. Overlay version detection
2. Buy phase vs combat phase state machine
3. Team/map auto-detection with fuzzy matching
4. Stream quality monitoring

**Defer to Phase 3 (requires research):**
1. Agent composition extraction
2. Ultimate status tracking

**Continuous monitoring:**
- OCR accuracy rates per element type
- Event detection precision/recall (requires ground truth from manual annotation)
- False positive rate (especially from replays)
- Stream quality correlation with accuracy
