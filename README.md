# PromoForge AI — Intelligent Promotional Moment Discovery & Ranking System
**Kuku Technologies – AI Generalist Recruitment Assignment (Problem 1: Find the Promos)**

PromoForge AI is a modular, hybrid neuro-symbolic pipeline that ingests timestamped microdrama screenplays and automatically discovers, validates, scores, and ranks **20 to 60-second vertical promotional clips** for Instagram Reels, TikTok, and YouTube Shorts.

## Key Capabilities
1. **Stage 1 — Fault-Tolerant Screenplay Ingestion:** Multi-pass regex parser handling case variations, encoding artifacts, character alias resolution across 50 episodes, and simultaneous camera/action/dialogue layers.
2. **Stages 2–4 — Hybrid Candidate Discovery & Exact Timestamp Snapping:** Discovers both continuous single-segment promos and stitched multi-segment cross-episode trailers, snapping every proposed timestamp to true screenplay beat boundaries.
3. **Stages 5–7 — Explainable 6-Criterion Scoring, MMR Diversity Ranking & 12-Point QA Gate:** Evaluates Opening Hook (25%), Cliffhanger (25%), Standalone Clarity (20%), Emotional Intensity (10%), Narrative Coherence (10%), and Promotional Curiosity (10%), while automatically rejecting duration violations and separating overlapping A/B variants via Temporal IoU.
4. **Live Interview Ready:** Upload any new .txt or .zip screenplay pack directly in the Streamlit sidebar to run live discovery on unseen shows.

## How to Run Locally or on Streamlit Community Cloud
    pip install -r requirements.txt
    streamlit run app/app.py

> **Confidentiality Note:** In compliance with Kuku's assignment guidelines, raw screenplay .txt files are excluded via .gitignore from public repositories. Precomputed outputs (outputs/) are included so the dashboard runs immediately out-of-the-box, and new screenplay files can be uploaded live via the sidebar.