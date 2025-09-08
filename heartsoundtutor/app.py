from flask import Flask, render_template, send_from_directory, request, jsonify
from dotenv import load_dotenv
import os

# Load .env and override stale shell values
load_dotenv(override=True)

# Masked confirmation
k = os.getenv("OPENAI_API_KEY", "")
print("OPENAI key:", ("sk-****" + k[-4:]) if k else "MISSING")

app = Flask(__name__, template_folder="templates", static_folder="static")

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
    return {"ai_mode": "live", "key_loaded": bool(os.getenv("OPENAI_API_KEY"))}

# --------- Mock fallback (never reveals unless asked) ----------
def mock_reply(state, item, user_msg, force_wrap=False):
    title = item.get("title","")
    buzz  = item.get("buzz",[])
    teach = item.get("teach","")
    audio = item.get("file","")

    if force_wrap:
        state = "wrap"

    if state == "probe":
        text = "\n".join([
            "**Probe (mock)**",
            "- Focus on where it’s loudest and radiation.",
            "- Which **maneuver** changes intensity/timing?"
        ])
        return {"text": text, "audio": None, "next_state": "maneuvers"}

    if state == "maneuvers":
        text = "\n".join([
            "**Maneuvers (mock)**",
            "- Good — synthesize in 1 line (name + 2 features) when you want the reveal.",
            "Say **'reveal'** anytime to see the answer."
        ])
        # stay in maneuvers until the learner explicitly asks to reveal
        return {"text": text, "audio": None, "next_state": "maneuvers"}

    # wrap (explicit reveal only)
    text = "\n".join([
        f"**Answer — {title}**",
        f"- Buzzwords: " + (" • ".join(buzz) if buzz else "—"),
        f"- Pearl: " + (teach.split('.')[0] + '.' if teach else "Focus on location, radiation, and maneuvers."),
        "- Diff: list 2–3 mimics."
    ])
    return {"text": text, "audio": f"/{audio}" if audio else None, "next_state": "wrap"}

# ---------- Guided Case Flow (LIVE; no reveal until explicitly asked) ----------
@app.route("/case_api", methods=["POST"])
def case_api():
    try:
        data = request.get_json(force=True) or {}
        state = data.get("state")
        item = data.get("item") or {}
        user_msg = (data.get("user_msg") or "").strip()

        title = item.get("title","")
        buzz  = item.get("buzz",[])
        teach = item.get("teach","")
        audio = item.get("file","")  # e.g., static/sounds/Adult-Case-X.mp3

        # 1) Intro = AUDIO ONLY (no text bubble)
        if state == "intro":
            return jsonify({"text": "", "audio": f"/{audio}", "next_state": "probe"})

        lowered = user_msg.lower()
        reveal_now = any(kw in lowered for kw in [
            "reveal", "answer", "final", "tell me the diagnosis", "what is it?"
        ])

        # 2) If the user explicitly asks: reveal (wrap)
        if reveal_now:
            return jsonify(mock_reply("wrap", item, user_msg, force_wrap=True))

        # 3) Otherwise we NEVER reveal before explicit request.
        #    Stay in 'maneuvers' after probe; keep coaching, one question at a time.
        next_state = "maneuvers" if state in ("probe", "maneuvers") else "maneuvers"

        # LIVE call with strict guardrails
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            hint_mode = any(kw in lowered for kw in ["hint", "clue", "another hint", "give me a hint"])

            system_instructions = (
                "You are a concise cardiology tutor for heart sounds (NBME/boards style).\n"
                "Global rules:\n"
                "• Do NOT state or imply the specific diagnosis OR list canonical buzzwords "
                "  unless the learner explicitly asked to 'reveal' (then server sets wrap).\n"
                "• If the learner asks for a hint, give ONE short, non-diagnostic hint "
                "  (location OR timing OR a maneuver effect). No murmur name. One sentence.\n"
                "• Otherwise (before reveal), keep <=3 bullets and ask exactly ONE follow-up question.\n"
                "• When the server sets wrap (explicit reveal only), provide: murmur name, 3 hallmark buzzwords, "
                "  one pitfall, and a one-line differential. No further questions."
            )

            phase_instruction = {
                "probe": (
                    "If hint_mode: one-sentence non-diagnostic hint. "
                    "Else: evaluate their description concisely (<=3 bullets), then ask exactly ONE maneuver question. "
                    "Do NOT reveal diagnosis or buzzwords."
                ),
                "maneuvers": (
                    "If hint_mode: one-sentence non-diagnostic hint about a maneuver. "
                    "Else: confirm/correct in <=3 bullets, end with exactly ONE synthesis or next-step question. "
                    "Do NOT reveal diagnosis or buzzwords."
                ),
                # 'wrap' is only set by server on explicit reveal.
            }

            user_blob = (
                f"Selected Item (internal only; do NOT reveal unless explicit reveal):\n"
                f"Title: {title}\n"
                f"Buzz: {', '.join(buzz)}\n"
                f"Teach: {teach}\n\n"
                f"Phase now: {state}\n"
                f"Hint mode: {'yes' if hint_mode else 'no'}\n"
                f"Reveal requested: no\n"
                f"Learner said: {user_msg or '(first turn)'}\n\n"
                f"Your task this turn:\n{phase_instruction.get(state, phase_instruction['maneuvers'])}\n"
                f"Format: max 3 bullets + exactly 1 question (unless hint_mode, then one sentence only)."
            )

            resp = client.responses.create(
                model="gpt-4o-mini",
                instructions=system_instructions,
                input=[{"role":"user","content": user_blob}]
            )
            answer = getattr(resp, "output_text", None) or str(resp)
            return jsonify({
                "text": answer,
                "audio": None,               # no extra audio until explicit reveal/wrap
                "next_state": next_state     # keep coaching; reveal only when asked
            })

        except Exception as e:
            msg = str(e)
            if ("insufficient_quota" in msg or
                "You exceeded your current quota" in msg or
                "invalid_api_key" in msg):
                print("LIVE error, falling back to mock:", e)
                fb = mock_reply(state, item, user_msg, force_wrap=False)
                return jsonify(fb)
            print("LIVE error (no fallback match):", e)
            return jsonify({"error": "Tutor is temporarily unavailable."}), 500

    except Exception as e:
        print("CASE error:", e)
        return jsonify({"error": "Tutor is unavailable right now."}), 500

if __name__ == "__main__":
    app.run(debug=True)
