from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from vachaspeech import VachaSpeech
from vachaspeech.tts import gender_id
from vachaspeech.text_normalizer import normalize_text
import tempfile
import os
import subprocess
import re
import torch
import numpy as np
import soundfile as sf
from pathlib import Path

def trim_trailing_noise(filepath, threshold=0.02, window_ms=10, margin_ms=100):
    """Trim trailing noise from a WAV file using RMS energy analysis.

    Scans from the end to find sustained low-energy regions (noise floor)
    produced by the codec when fed garbage tokens past the end of speech.
    """
    data, sr = sf.read(filepath)
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    window = max(int(sr * window_ms / 1000), 1)
    n = len(data)

    # Compute RMS per window (vectorized)
    n_windows = (n + window - 1) // window
    rms = np.zeros(n_windows)
    for i in range(n_windows):
        start = i * window
        end = min(start + window, n)
        chunk = data[start:end]
        rms[i] = np.sqrt(np.mean(chunk**2))

    peak_rms = np.max(rms)
    if peak_rms < 1e-8:
        return

    rms_norm = rms / peak_rms
    above = np.where(rms_norm > threshold)[0]
    if len(above) == 0:
        return

    # Last window above threshold → cut after margin
    last_idx = above[-1]
    cut = min((last_idx + 1) * window + int(sr * margin_ms / 1000), n)

    if n - cut >= sr * 0.2:
        sf.write(filepath, data[:cut], sr)


app = Flask(__name__)
CORS(app)

tts = VachaSpeech()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
if device.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    tts.model = tts.model.to(device)
    if hasattr(tts, "codec") and hasattr(tts.codec, "model"):
        tts.codec.model = tts.codec.model.to(device)
else:
    print("No GPU detected, falling back to CPU")

def generate_custom(text, gender="female", temperature=0.8, top_p=0.95, top_k=40, repetition_penalty=1.1, max_length_multiplier=5):
    clean_text = normalize_text(text)
    predict_max_len = len(clean_text) * max_length_multiplier

    messages = [
        {"role": "user", "content": gender_id[gender] + " " + clean_text}
    ]

    input_text = tts.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tts.tokenizer(input_text,
                        return_tensors='pt',
                        padding=True,
                        truncation=True,
                        max_length=512).to(device)

    with torch.inference_mode():
        outputs = tts.model.generate(
            **inputs,
            max_new_tokens=predict_max_len,
            min_new_tokens=10,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            do_sample=True,
            pad_token_id=tts.tokenizer.pad_token_id,
            eos_token_id=tts.tokenizer.eos_token_id
        )
    generated = outputs[0][inputs["input_ids"].shape[-1]:]
    result = tts.tokenizer.decode(generated, skip_special_tokens=True)
    codes = list(map(int, re.findall(r"<\|s_(\d+)\|>", result)))
    return codes

@app.route("/tts", methods=["POST"])
def generate():

    text = request.json.get("text", "")
    gender = request.json.get("gender", "female")
    ref_audio = request.json.get("ref_audio")
    temperature = request.json.get("temperature", 0.8)
    top_p = request.json.get("top_p", 0.95)
    top_k = request.json.get("top_k", 40)
    repetition_penalty = request.json.get("repetition_penalty", 1.1)
    speed = request.json.get("speed", 1.0)
    max_length_multiplier = request.json.get("max_length_multiplier", 5)

    if not ref_audio:
        ref_audio = "/ref_audio/default_female.wav"

    output = generate_custom(text, gender=gender, temperature=temperature, top_p=top_p, top_k=top_k, repetition_penalty=repetition_penalty, max_length_multiplier=max_length_multiplier)

    outfile = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)

    tts.decode(
        output,
        ref_audio=ref_audio,
        output=outfile.name
    )

    trim_trailing_noise(outfile.name)

    if speed != 1.0:
        sped = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        subprocess.run(
            ["ffmpeg", "-y", "-i", outfile.name, "-filter:a", f"atempo={speed}", "-q:a", "0", sped.name],
            capture_output=True
        )
        os.unlink(outfile.name)
        outfile = sped

    return send_file(outfile.name, mimetype="audio/wav")


@app.route("/ref-audio-list", methods=["GET"])
def ref_audio_list():
    ref_dir = Path("/ref_audio")
    files = []
    for f in sorted(ref_dir.iterdir()):
        if f.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg"):
            files.append({"name": f.name, "path": str(f)})
    return jsonify(files)

@app.route("/upload-ref-audio", methods=["POST"])
def upload_ref_audio():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    name = request.form.get("name", "").strip()
    if not name:
        ts = int(__import__("time").time())
        name = f"recording_{ts}.wav"
    if not name.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
        name += ".wav"
    safe = "".join(c for c in name if c.isalnum() or c in "._- ")
    path = Path("/ref_audio") / safe
    f.save(str(path))
    return jsonify({"name": safe, "path": str(path)})

@app.route("/delete-ref-audio", methods=["POST"])
def delete_ref_audio():
    name = request.json.get("name", "")
    if not name:
        return jsonify({"error": "no name"}), 400
    safe = "".join(c for c in name if c.isalnum() or c in "._- ")
    path = Path("/ref_audio") / safe
    if path.exists() and path.is_file():
        path.unlink()
        return jsonify({"deleted": safe})
    return jsonify({"error": "not found"}), 404

app.run(host="0.0.0.0", port=7860)