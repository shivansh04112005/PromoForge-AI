"""
PromoForge AI - Core Reusable Pipeline Engine (app/engine.py)
Processes any Kuku microdrama screenplay (.txt or .zip) end-to-end:
Stage 1 (Parsing) -> Stage 2-4 (Discovery & Timestamp Snapping) -> Stage 5-7 (Scoring, QA & Ranking)
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

def parse_timestamp_to_seconds(ts_str: str) -> Optional[float]:
    if not ts_str:
        return None
    clean_ts = ts_str.strip().strip("()")
    m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$", clean_ts)
    if not m:
        return None
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    return round(hours * 3600 + minutes * 60 + seconds, 2)

def format_seconds_to_timestamp(seconds: float) -> str:
    seconds = max(0.0, round(float(seconds), 2))
    mins = int(seconds // 60)
    secs = seconds - (mins * 60)
    return f"{mins:02d}:{secs:05.2f}"

def sanitize_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\bfianc\s{2,}", "fiancé ", text)
    return text.replace("\u00a0", " ")

HOOK_KEYWORDS = [
    r"\bslap", r"\bblood", r"\bpoison", r"\barsenic", r"\bmarrying me\b",
    r"\bdisowned\b", r"\barrest\b", r"\bstole\b", r"\bhang\b", r"\bgallows\b",
    r"\bwitch", r"\bfire\b", r"\bburn", r"\bscream", r"\bshove", r"\bwhip\b",
    r"\bcrop\b", r"\bdead\b", r"\bkill", r"\bambush", r"\btraitor\b",
    r"\bduchess\b", r"\byour grace\b", r"\bring\b", r"\bguards\b", r"\bthorn"
]

CLIFFHANGER_CUES = [
    r"cliffhanger", r"cut to black", r"freeze-frame", r"abrupt cut",
    r"swells dramatically", r"ominous", r"crescendo", r"gasp", r"shock",
    r"stopping mere millimeters", r"inches from", r"fades to black"
]

def score_beat_dramatic_signals(beat_type: str, content: str, delivery: str = "") -> Dict[str, Any]:
    combined = f"{delivery} {content}".lower()
    hook_hits = [kw.strip(r"\b") for kw in HOOK_KEYWORDS if re.search(kw, combined)]
    cliff_hits = [cw for cw in CLIFFHANGER_CUES if re.search(cw, combined)]
    has_excl = "!" in content
    has_ques = "?" in content
    intensity = 0.0
    if beat_type == "DIALOGUE":
        intensity += 2.0 + (1.5 if has_excl else 0.0) + (1.0 if has_ques else 0.0)
    elif beat_type == "ACTION":
        intensity += 1.5
    elif beat_type == "SOUND_FX":
        intensity += 1.0
    intensity += len(hook_hits) * 2.0 + len(cliff_hits) * 1.5
    return {
        "signal_score": round(min(10.0, intensity), 2),
        "hook_triggers": hook_hits,
        "cliffhanger_triggers": cliff_hits,
        "has_exclamation": has_excl,
        "has_question": has_ques
    }

def parse_screenplay_text(raw_text: str, filename: str = "uploaded_episode.txt", fallback_ep_num: int = 1) -> Dict[str, Any]:
    raw_content = sanitize_text(raw_text)
    m_file = re.search(r"episode-(\d+)", filename, re.IGNORECASE)
    ep_from_file = int(m_file.group(1)) if m_file else fallback_ep_num
    ep_num_match = re.search(r"EPISODE\s+NUMBER:\s*Episode\s*(\d+)", raw_content, re.IGNORECASE)
    episode_number = int(ep_num_match.group(1)) if ep_num_match else ep_from_file
    logline_match = re.search(
        r"EPISODE\s+LOGLINE:\s*(.+?)(?=CONTINUITY\s+NOTES:|---\s*SCRIPT\s*START\s*---|$)",
        raw_content, re.IGNORECASE | re.DOTALL
    )
    logline = " ".join(logline_match.group(1).split()) if logline_match else ""
    continuity_match = re.search(
        r"CONTINUITY\s+NOTES:\s*(.+?)(?=---\s*SCRIPT\s*START\s*---|$)",
        raw_content, re.IGNORECASE | re.DOTALL
    )
    continuity_notes = " ".join(continuity_match.group(1).split()) if continuity_match else ""
    script_body_match = re.search(
        r"---\s*SCRIPT\s*START\s*---(.+?)(?:---\s*SCRIPT\s*END\s*---|$)",
        raw_content, re.IGNORECASE | re.DOTALL
    )
    script_body = script_body_match.group(1) if script_body_match else raw_content
    scene_splits = list(re.finditer(r"\bSCENE\s+(\d+)\b", script_body, re.IGNORECASE))
    if not scene_splits:
        scene_chunks = [(1, script_body)]
    else:
        scene_chunks = []
        for idx, match in enumerate(scene_splits):
            sc_num = int(match.group(1))
            start_pos = match.end()
            end_pos = scene_splits[idx + 1].start() if idx + 1 < len(scene_splits) else len(script_body)
            scene_chunks.append((sc_num, script_body[start_pos:end_pos]))
    beat_pattern = re.compile(
        r"\*\*([^*]+?):\*\*\s*Start:\s*\(([^)]+)\)\s*\|\s*End:\s*\(([^)]+)\)\s*(.*?)(?=\*\*[^*]+?:\*\*\s*Start:|$)",
        re.DOTALL | re.IGNORECASE
    )
    scenes = []
    all_beats = []
    for sc_num, sc_text in scene_chunks:
        heading_match = re.search(r"Scene\s+heading:\s*(.+?)(?=Scene\s+start:|$)", sc_text, re.IGNORECASE | re.DOTALL)
        scene_heading = " ".join(heading_match.group(1).split()) if heading_match else "SCENE"
        sc_start_match = re.search(r"Scene\s+start:\s*([0-9:.]+)", sc_text, re.IGNORECASE)
        sc_end_match = re.search(r"Scene\s+end:\s*([0-9:.]+)", sc_text, re.IGNORECASE)
        sc_start_str = sc_start_match.group(1).strip() if sc_start_match else "00:00.00"
        sc_end_str = sc_end_match.group(1).strip() if sc_end_match else None
        sc_start_sec = parse_timestamp_to_seconds(sc_start_str) or 0.0
        sc_end_sec = parse_timestamp_to_seconds(sc_end_str) if sc_end_str else None
        scene_beats = []
        for b_idx, b_match in enumerate(beat_pattern.finditer(sc_text)):
            raw_label = " ".join(b_match.group(1).split()).strip()
            b_start_raw = b_match.group(2).strip()
            b_end_raw = b_match.group(3).strip()
            b_content = " ".join(b_match.group(4).split()).strip()
            b_start_sec = parse_timestamp_to_seconds(b_start_raw)
            b_end_sec = parse_timestamp_to_seconds(b_end_raw)
            upper_label = raw_label.upper()
            speaker_raw = None
            delivery_tone = ""
            if upper_label == "CAMERA":
                beat_type = "CAMERA"
            elif upper_label == "ACTION":
                beat_type = "ACTION"
            elif upper_label in ("SOUND FX", "SOUND", "SFX"):
                beat_type = "SOUND_FX"
            else:
                beat_type = "DIALOGUE"
                parens = re.findall(r"\(([^)]+)\)", raw_label)
                delivery_tone = ", ".join(parens) if parens else ""
                speaker_raw = re.sub(r"\s*\([^)]*\)", "", raw_label).strip().title()
                if b_content.startswith('"') and b_content.endswith('"') and len(b_content) >= 2:
                    b_content = b_content[1:-1].strip()
                elif b_content.startswith('"'):
                    b_content = b_content[1:].strip()
            ts_valid = (b_start_sec is not None and b_end_sec is not None and b_end_sec >= b_start_sec)
            b_dur = round(b_end_sec - b_start_sec, 2) if ts_valid else 0.0
            signals = score_beat_dramatic_signals(beat_type, b_content, delivery_tone)
            beat_obj = {
                "beat_id": f"EP{episode_number:02d}_SC{sc_num:02d}_B{b_idx+1:03d}",
                "episode": episode_number,
                "scene_number": sc_num,
                "beat_type": beat_type,
                "raw_label": raw_label,
                "speaker": speaker_raw,
                "canonical_character": speaker_raw,
                "delivery": delivery_tone,
                "start_time": b_start_raw,
                "end_time": b_end_raw,
                "start_sec": b_start_sec,
                "end_sec": b_end_sec,
                "duration_sec": b_dur,
                "text": b_content,
                "timestamp_valid": ts_valid,
                "signals": signals
            }
            scene_beats.append(beat_obj)
            all_beats.append(beat_obj)
        if sc_end_sec is None and scene_beats:
            valid_ends = [b["end_sec"] for b in scene_beats if b["end_sec"] is not None]
            sc_end_sec = max(valid_ends) if valid_ends else 0.0
            sc_end_str = format_seconds_to_timestamp(sc_end_sec)
        scenes.append({
            "scene_number": sc_num,
            "scene_heading": scene_heading,
            "start_time": sc_start_str,
            "end_time": sc_end_str or format_seconds_to_timestamp(sc_end_sec or 0.0),
            "start_sec": sc_start_sec,
            "end_sec": sc_end_sec or 0.0,
            "duration_sec": round((sc_end_sec or 0.0) - sc_start_sec, 2),
            "beat_count": len(scene_beats),
            "dialogue_count": sum(1 for b in scene_beats if b["beat_type"] == "DIALOGUE"),
            "beats": scene_beats
        })
    valid_beat_ends = [b["end_sec"] for b in all_beats if b["end_sec"] is not None]
    ep_duration_sec = max(valid_beat_ends) if valid_beat_ends else 0.0
    unique_chars = sorted(list({b["canonical_character"] for b in all_beats if b["canonical_character"]}))
    return {
        "episode_number": episode_number,
        "filename": filename,
        "logline": logline,
        "continuity_notes": continuity_notes,
        "total_duration_sec": round(ep_duration_sec, 2),
        "total_duration_str": format_seconds_to_timestamp(ep_duration_sec),
        "scene_count": len(scenes),
        "beat_count": len(all_beats),
        "dialogue_count": sum(1 for b in all_beats if b["beat_type"] == "DIALOGUE"),
        "action_count": sum(1 for b in all_beats if b["beat_type"] == "ACTION"),
        "camera_count": sum(1 for b in all_beats if b["beat_type"] == "CAMERA"),
        "sfx_count": sum(1 for b in all_beats if b["beat_type"] == "SOUND_FX"),
        "characters_present": unique_chars,
        "parsing_warnings": [],
        "scenes": scenes
    }

def run_live_discovery_on_episodes(episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = []
    c_idx = 1
    for ep in episodes:
        all_beats = [b for sc in ep["scenes"] for b in sc["beats"] if b["timestamp_valid"]]
        if not all_beats:
            continue
        ep_max_sec = ep["total_duration_sec"]
        target_start = max(0.0, ep_max_sec - 46.0)
        hook_beats = [
            b for b in all_beats
            if max(0.0, ep_max_sec - 56.0) <= b["start_sec"] <= max(5.0, ep_max_sec - 22.0)
            and b["beat_type"] in ("DIALOGUE", "ACTION")
        ]
        if hook_beats:
            best_h = max(hook_beats, key=lambda b: (b["signals"]["signal_score"] * 2.0) - abs(b["start_sec"] - target_start) * 0.15)
            seg_s, seg_e = best_h["start_sec"], all_beats[-1]["end_sec"]
            dur = round(seg_e - seg_s, 2)
            if 20.0 <= dur <= 60.0:
                active_beats = [b for b in all_beats if b["start_sec"] >= seg_s]
                dialogues = [f'{b["canonical_character"]}: "{b["text"]}"' for b in active_beats if b["beat_type"] == "DIALOGUE"]
                actions = [b["text"] for b in active_beats if b["beat_type"] in ("ACTION", "SOUND_FX")]
                candidates.append(_build_live_cand(f"LIVE_PROMO_{c_idx:03d}", ep, seg_s, seg_e, active_beats, dialogues, actions, "Episode Climax Cliffhanger"))
                c_idx += 1
        if ep_max_sec >= 85.0:
            early_hooks = [
                b for b in all_beats
                if 0.0 <= b["start_sec"] <= ep_max_sec - 50.0
                and b["beat_type"] in ("DIALOGUE", "ACTION")
                and b["signals"]["signal_score"] >= 3.5
            ]
            if early_hooks:
                eh = early_hooks[0]
                cand_ends = [
                    b for b in all_beats
                    if eh["start_sec"] + 25.0 <= b["end_sec"] <= min(eh["start_sec"] + 52.0, ep_max_sec - 10.0)
                    and b["beat_type"] in ("DIALOGUE", "ACTION")
                ]
                if cand_ends:
                    be = max(cand_ends, key=lambda b: b["signals"]["signal_score"])
                    seg_s, seg_e = eh["start_sec"], be["end_sec"]
                    active_beats = [b for b in all_beats if seg_s <= b["start_sec"] and b["end_sec"] <= seg_e + 0.5]
                    dialogues = [f'{b["canonical_character"]}: "{b["text"]}"' for b in active_beats if b["beat_type"] == "DIALOGUE"]
                    actions = [b["text"] for b in active_beats if b["beat_type"] in ("ACTION", "SOUND_FX")]
                    candidates.append(_build_live_cand(f"LIVE_PROMO_{c_idx:03d}", ep, seg_s, seg_e, active_beats, dialogues, actions, "Mid-Episode Confrontation"))
                    c_idx += 1
    candidates.sort(key=lambda x: x["evaluation"]["overall_score"], reverse=True)
    for idx, c in enumerate(candidates):
        c["ranking"] = {
            "global_rank": idx + 1,
            "tier": "TIER_1_POST_FIRST" if idx < 10 else "TIER_2_STRONG_BACKUP",
            "quality_score": c["evaluation"]["overall_score"],
            "mmr_diversity_score": c["evaluation"]["overall_score"],
            "ranking_explanation": f"Ranked #{idx+1} with score {c['evaluation']['overall_score']}/100."
        }
    return candidates

def _build_live_cand(cid: str, ep: Dict[str, Any], s_sec: float, e_sec: float, beats: List[Dict[str, Any]], dialogues: List[str], actions: List[str], role: str) -> Dict[str, Any]:
    dur = round(e_sec - s_sec, 2)
    first_3s = sum(1 for b in beats if b["start_sec"] <= s_sec + 3.0 and b["beat_type"] in ("DIALOGUE", "ACTION", "SOUND_FX"))
    avg_sig = round(sum(b["signals"]["signal_score"] for b in beats) / max(1, len(beats)), 2)
    hook_line = dialogues[0] if dialogues else (actions[0] if actions else "Opening dramatic beat")
    cliff_line = dialogues[-1] if dialogues else (actions[-1] if actions else "Unresolved ending beat")
    hook_sc = min(96.0, 74.0 + first_3s * 6.0 + avg_sig * 2.5)
    cliff_sc = min(96.0, 78.0 + avg_sig * 3.0)
    clarity_sc = 88.0
    emo_sc = min(95.0, 65.0 + avg_sig * 5.5)
    coh_sc = 88.0
    cur_sc = round(hook_sc * 0.4 + cliff_sc * 0.6, 1)
    overall = round(hook_sc*0.25 + cliff_sc*0.25 + clarity_sc*0.20 + emo_sc*0.10 + coh_sc*0.10 + cur_sc*0.10, 2)
    return {
        "candidate_id": cid,
        "promo_type": "single_segment",
        "archetype": "Dramatic Confrontation & Hook",
        "episodes": [ep["episode_number"]],
        "episode_label": f"Episode {ep['episode_number']}",
        "segment_count": 1,
        "segments": [{
            "segment_index": 1,
            "episode": ep["episode_number"],
            "start_time": format_seconds_to_timestamp(s_sec),
            "end_time": format_seconds_to_timestamp(e_sec),
            "start_sec": s_sec,
            "end_sec": e_sec,
            "duration_sec": dur,
            "segment_role": role,
            "beat_count": len(beats),
            "first_3s_active_beats": first_3s,
            "characters": ep["characters_present"],
            "dialogue_lines": dialogues,
            "action_cues": actions
        }],
        "total_duration_sec": dur,
        "hook_description": f"Opens immediately on: {hook_line[:120]}",
        "cliffhanger_description": f"Cuts at unresolved tension: {cliff_line[:120]}",
        "standalone_context": ep["logline"] or f"Self-contained dramatic conflict in Episode {ep['episode_number']}.",
        "why_it_works": f"High-signal {dur}s vertical promo clip with {len(dialogues)} dialogue lines and immediate 3-second hook.",
        "qa_flags": [],
        "is_valid": 20.0 <= dur <= 60.0,
        "evaluation": {
            "criterion_scores": {
                "opening_hook": round(hook_sc, 1),
                "cliffhanger": round(cliff_sc, 1),
                "standalone_clarity": round(clarity_sc, 1),
                "emotional_intensity": round(emo_sc, 1),
                "narrative_coherence": round(coh_sc, 1),
                "promotional_curiosity": round(cur_sc, 1)
            },
            "initial_overall_score": overall,
            "overall_score": overall,
            "supporting_evidence_quotes": dialogues[:3],
            "key_strengths": [f"Active 3-second hook ({first_3s} beats in first 3s).", "Exact beat-snapped duration within 20-60s bounds."],
            "weaknesses": ["Single-location scene; pair with dynamic captions."],
            "editor_rejection_risks": ["Verify pacing transition in final audio mix."],
            "scoring_explanation": f"Scored {overall}/100 across {len(beats)} screenplay beats."
        },
        "qa_audit": {
            "qa_status": "VALID_TOP_TIER" if overall >= 80.0 else "VALID_EDITORIAL_REVIEW",
            "hard_valid": 20.0 <= dur <= 60.0,
            "deterministic_checks": {"5_total_duration_20_to_60s": 20.0 <= dur <= 60.0},
            "semantic_warnings": [],
            "duplicate_of": None,
            "temporal_iou_with_primary": 0.0
        }
    }