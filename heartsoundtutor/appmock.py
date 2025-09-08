from flask import Flask, render_template, send_from_directory, request, jsonify
import json, os, random

app = Flask(__name__, template_folder="templates", static_folder="static")

# -------- Load your murmur bank once (for distractors & phrasing) --------
DATA_PATH = os.path.join(app.static_folder, "data", "murmurs.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    BANK = json.load(f).get("items", [])

def pick_distractors(correct_id, correct_cat, k=3):
    # Prefer same category, fall back to any
    same = [it for it in BANK if it.get("id") != correct_id and it.get("cat") == correct_cat]
    pool = same if len(same) >= k else [it for it in BANK if it.get("id") != correct_id]
    random.shuffle(pool)
    return pool[:k]

def mcq_for(item):
    """Build a 4-option MCQ (A-D) with one correct answer."""
    correct = item.get("title","")
    correct_id = item.get("id","")
    cat = item.get("cat","")
    distractors = [d.get("title","") for d in pick_distractors(correct_id, cat, k=3)]
    options = [correct] + distractors
    random.shuffle(options)
    # Label A-D and remember which one is correct
    labeled = []
    correct_key = None
    for i, opt in enumerate(options):
        key = chr(ord('A')+i)
        labeled.append({"key": key, "label": opt})
        if opt == correct:
            correct_key = key
    return labeled, correct_key

# ---- NBME-style progressive hints (no diagnosis names) ----
SITE_WORDS = ["apex", "left sternal border", "right sternal border", "LSB", "LLSB", "RUSB", "LUSB", "base"]

def nbme_hint_pack(item):
    """
    Build up to 3 progressive hints:
    1) Timing/site phrasing (systolic/diastolic + NBME site).
    2) Maneuver effect (squatting/handgrip/Valsalva/inspiration).
    3) Radiation/ancillary (carotids, axilla, pulse pressure, extra sounds).
    Avoid naming the diagnosis explicitly.
    """
    buzz = [b.strip() for b in (item.get("buzz") or [])]
    teach = (item.get("teach") or "")
    text = " ".join(buzz + [teach]).lower()

    def first_site():
        for w in SITE_WORDS:
            if w.lower() in text:
                return (w.replace("LSB","left sternal border")
                          .replace("LLSB","left lower sternal border")
                          .replace("RUSB","right upper sternal border")
                          .replace("LUSB","left upper sternal border"))
        return "the characteristic listening area"

    def timing_word():
        if "diastolic" in text: return "diastolic"
        if "systolic" in text: return "systolic"
        return "cardiac-cycle"

    def a_maneuver():
        if "handgrip" in text:   return "Handgrip (↑ afterload) often accentuates regurgitant or L→R shunt murmurs."
        if "squatting" in text:  return "Squatting (↑ preload/afterload) can increase intensity or shift timing."
        if "valsalva" in text:   return "Valsalva (↓ preload) typically softens most murmurs (HCM/MVP exceptions)."
        if "inspiration" in text:return "Inspiration ↑ right-sided sounds; expiration accentuates left-sided."
        return "Try a physiologic maneuver (squatting, handgrip, Valsalva) to test intensity/timing."

    def a_radiation_or_extra():
        if "carotid" in text:    return "Assess for radiation to the carotids."
        if "axilla" in text:     return "Assess for radiation to the axilla."
        if "pulse pressure" in text or "bounding" in text: return "Note pulse pressure/‘bounding’ quality."
        if "opening snap" in text or "click" in text: return "Listen for extra sounds relative to S2 (snap/click)."
        return "Consider radiation and any extra sounds to firm up the impression."

    h1 = f"Think **{timing_word()}**; focus at the **{first_site()}**."
    h2 = a_maneuver()
    h3 = a_radiation_or_extra()
    return [h1, h2, h3]

# ---- NBME-style micro-card + compact 'More info' dropdown (inline styles) ----
def nbme_wrap(item):
    """
    Micro-card (5 lines) + compact 'More info' with inline styles
    so no changes to styles.css are required.
    """
    title = (item.get("title") or "").strip()
    buzzs = [b.strip() for b in (item.get("buzz") or []) if b.strip()]
    teach = (item.get("teach") or "").strip()
    text  = (" ".join(buzzs) + " " + teach).lower()

    # --- helpers ---
    def site():
        if "left lower sternal border" in text or "llsb" in text: return "LLSB"
        if "left sternal border" in text or "lsb"  in text:       return "LSB"
        if "right upper sternal border" in text or "rusb" in text:return "RUSB"
        if "left upper sternal border" in text or "lusb" in text: return "LUSB"
        if "apex" in text:                                        return "apex"
        if "base" in text:                                        return "base"
        return "classic area"

    def timing():
        if "diastolic" in text: return "diastolic"
        if "holosystolic" in text or "pan-systolic" in text: return "holosystolic (systolic)"
        if "systolic" in text: return "systolic"
        if "early diastolic" in text: return "early diastolic"
        return "timing"

    def radiation():
        if "carotid" in text: return "→ carotids"
        if "axilla"  in text: return "→ axilla"
        if "no radiation" in text: return "non-radiating"
        return "typical pattern"

    def maneuver_one():
        if "handgrip" in text:   return "↑ with handgrip (↑ afterload)"
        if "squatting" in text:  return "changes with squatting (↑ preload/afterload)"
        if "valsalva" in text:   return "↓ with Valsalva (↓ preload) in most murmurs"
        if "inspiration" in text:return "Right ↑ with inspiration / Left ↑ with expiration"
        return "characteristic response to standard maneuvers"

    def buzz_line():
        b = buzzs[:3] if len(buzzs) > 3 else buzzs
        return " • ".join(b) if b else "—"

    def dont_miss():
        if "mvp" in text or "click" in text:
            return "MR at **apex** → **axilla** (click if MVP) vs VSD at **LLSB**."
        if "carotid" in text or "crescendo" in text:
            return "AS at **RUSB** → **carotids** vs MR at **apex** → **axilla**."
        if "llsb" in text or "left lower sternal border" in text:
            return "VSD (**LLSB**) vs TR (↑ with inspiration, prominent v waves)."
        return (teach.split(".")[0] + ".") if teach else "Anchor on timing/site + one maneuver."

    # ---------- micro-card (always visible) ----------
    micro = [
        f"**Dx:** {title}",
        f"**Hear it:** {timing()} @ {site()} {radiation()}",
        f"**Maneuver:** {maneuver_one()}",
        f"**Buzz:** {buzz_line()}",
        f"**Don’t miss:** {dont_miss()}",
    ]

    # ---------- build expanded details (compact inline styles) ----------
    # timing/quality list
    tq = []
    if "diastolic" in text: tq.append("Diastolic")
    if "systolic"  in text: tq.append("Systolic")
    if "holosystolic" in text or "pan-systolic" in text: tq.append("Holosystolic")
    if "crescendo" in text or "decrescendo" in text: tq.append("Crescendo–decrescendo")
    if "early diastolic" in text: tq.append("Early diastolic")
    if "mid-diastolic" in text:   tq.append("Mid-diastolic")
    if "late diastolic" in text:  tq.append("Late diastolic")
    if "high-pitched" in text:    tq.append("High-pitched")
    if "low-pitched" in text or "rumble" in text: tq.append("Low-pitched/rumble")
    if "harsh" in text:           tq.append("Harsh")
    if "blowing" in text:         tq.append("Blowing")
    # dedupe
    seen=set(); tq=[x for x in tq if not (x in seen or seen.add(x))]

    # maneuvers expanded
    man = []
    if "handgrip" in text:   man.append("↑ with **handgrip** (↑ afterload) for regurg/shunts")
    if "squatting" in text:  man.append("↑/shift with **squatting** (↑ preload/afterload)")
    if "valsalva" in text:   man.append("↓ with **Valsalva** (↓ preload) in most lesions")
    if "inspiration" in text:man.append("Right-sided ↑ with **inspiration**; left-sided with **expiration**")
    man_expanded = " • ".join(man) if man else "Characteristic response to standard maneuvers"

    # extras
    extras = []
    if "opening snap" in text: extras.append("Opening snap after S2")
    if "click" in text or "mvp" in text: extras.append("Mid-systolic click (MVP)")
    if "wide pulse pressure" in text or "bounding" in text: extras.append("Wide pulse pressure / bounding pulses")
    extras_line = " • ".join(extras)

    # build compact lists with inline styles
    full_buzz = "".join(f"<li style='margin:0'>{b}</li>" for b in buzzs) or "<li style='margin:0'>—</li>"
    diffs = [
        "Mitral regurgitation — holosystolic at **apex**, radiates to **axilla**; click if MVP.",
        "Aortic stenosis — systolic crescendo–decrescendo at **RUSB**, radiates to **carotids**; soft/late **S2**."
    ]
    diff_html = "".join(f"<li style='margin:0'>{d}</li>" for d in diffs)

    pearl = teach.split(".")[0].strip() + "." if teach else ""

    more_info_html = f"""
<details>
  <summary><strong>More info</strong></summary>
  <div style="margin-top:.25rem; line-height:1.25">
    <div style="margin:2px 0"><strong>Site:</strong> {site().upper()}</div>
    <div style="margin:2px 0"><strong>Timing/Quality:</strong> {', '.join(tq) or '—'}</div>
    <div style="margin:2px 0"><strong>Radiation:</strong> {radiation()}</div>
    <div style="margin:2px 0"><strong>Maneuvers:</strong> {man_expanded}</div>
    {f"<div style='margin:2px 0'><strong>Extras:</strong> {extras_line}</div>" if extras_line else ""}
    <div style="margin:2px 0"><strong>Buzzwords (full):</strong></div>
    <ul style="margin:4px 0 4px 1rem; padding-left:1rem">{full_buzz}</ul>
    {f"<div style='margin:2px 0'><strong>Pearl:</strong> {pearl}</div>" if pearl else ""}
    <div style="margin:2px 0"><strong>Differentiate from:</strong></div>
    <ul style="margin:4px 0 0 1rem; padding-left:1rem">{diff_html}</ul>
  </div>
</details>
""".strip()

    return "\n".join(micro) + "\n\n" + more_info_html

# ---------------- Basic pages ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/case/<item_id>")
def case_page(item_id):
    return render_template("case.html")

@app.route("/sounds/<path:filename>")
def sounds(filename):
    return send_from_directory("static/sounds", filename)

@app.route("/health")
def health():
    return {"ai_mode": "mock", "key_loaded": False}

# ---------------- Mock tutor logic (MCQ + progressive hints) ----------------
@app.route("/case_api", methods=["POST"])
def case_api():
    """
    Pure-mock MCQ flow:
      intro      -> audio only + MCQ (A–D); next_state='mcq'
      mcq        -> on choice:
                      - correct  => immediate NBME wrap + replay audio
                      - wrong    => next hint; max 3 tries, then lock & suggest reveal
      hint ask   -> returns next hint without consuming a try (cap 3)
      reveal     -> explicit; returns NBME wrap + audio
    Client sends: attempts (int), hint_level (int), and optionally 'choice_key' (A–D)
    """
    try:
        data = request.get_json(force=True) or {}
        state       = data.get("state")              # 'intro' | 'mcq'
        item        = data.get("item") or {}
        user_msg    = (data.get("user_msg") or "").strip().lower()
        attempts    = int(data.get("attempts") or 0)
        hint_level  = int(data.get("hint_level") or 0)
        choice_key  = (data.get("choice_key") or "").strip().upper()

        # Look up full item from BANK
        full = next((it for it in BANK if (it.get("id")==item.get("id")) or (it.get("title")==item.get("title"))), item)

        # Audio path
        audio = full.get("file","")

        # Build MCQ options deterministically per case
        random.seed(full.get("id") or full.get("title"))
        options, correct_key = mcq_for(full)
        hints = nbme_hint_pack(full)

        # Intro => audio only, then serve MCQ
        if state == "intro":
            return jsonify({
                "text": "",
                "audio": f"/{audio}",
                "choices": options,          # [{key:'A', label:'...'}, ...]
                "next_state": "mcq",
                "hint_level": 0,
                "attempts": 0
            })

        # Explicit reveal at any time
        if any(k in user_msg for k in ["reveal", "answer", "final", "what is it", "tell me the diagnosis"]):
            wrap_text = nbme_wrap(full)
            return jsonify({
                "text": wrap_text,
                "audio": f"/{audio}" if audio else None,
                "choices": None,
                "next_state": "wrap",
                "hint_level": hint_level,
                "attempts": attempts
            })

        # User asked for a hint (does not consume a try)
        if any(k in user_msg for k in ["hint", "clue", "another hint", "give me a hint"]):
            hint_level = min(hint_level + 1, 3)
            hint_text = hints[hint_level-1]
            return jsonify({
                "text": hint_text,
                "audio": None,
                "choices": options,
                "next_state": "mcq",
                "hint_level": hint_level,
                "attempts": attempts
            })

        # MCQ choice handling
        if state == "mcq" and choice_key in ["A","B","C","D"]:
            if choice_key == correct_key:
                # ✅ Correct → immediately show full NBME wrap and replay audio
                wrap_text = nbme_wrap(full)
                return jsonify({
                    "text": "✅ **Correct.**\n\n" + wrap_text,
                    "audio": f"/{audio}" if audio else None,
                    "choices": None,          # hide buttons
                    "next_state": "wrap",
                    "hint_level": hint_level,
                    "attempts": attempts
                })
            else:
                # ❌ Wrong → increment attempts, provide next hint (up to 3 total), keep choices unless locked
                attempts += 1
                if hint_level < 3:
                    hint_level += 1
                hint_text = hints[hint_level-1]
                if attempts >= 3:
                    text = "\n".join([
                        "❌ Not quite.",
                        f"- Hint: {hint_text}",
                        "- You’re out of tries. Click **Reveal answer** for the explanation."
                    ])
                    return jsonify({
                        "text": text,
                        "audio": None,
                        "choices": None,       # lock choices after 3 wrong
                        "next_state": "await-reveal",
                        "hint_level": hint_level,
                        "attempts": attempts
                    })
                else:
                    text = "\n".join([
                        "❌ Not quite.",
                        f"- Hint: {hint_text}",
                        f"- Tries left: {3 - attempts}. Choose A–D or click **Hint**."
                    ])
                    return jsonify({
                        "text": text,
                        "audio": None,
                        "choices": options,
                        "next_state": "mcq",
                        "hint_level": hint_level,
                        "attempts": attempts
                    })

        # Fallback generic coaching
        text = "Choose an option (A–D) or click **Hint**."
        return jsonify({
            "text": text,
            "audio": None,
            "choices": options,
            "next_state": "mcq",
            "hint_level": hint_level,
            "attempts": attempts
        })

    except Exception as e:
        print("MOCK CASE error:", e)
        return jsonify({"error": "Tutor is unavailable right now."}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
