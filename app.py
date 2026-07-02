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
from pathlib import Path

app = Flask(__name__)
CORS(app)

tts = VachaSpeech()

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
                        max_length=512).to("cpu")

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
    ts = int(__import__("time").time())
    name = f"recording_{ts}.wav"
    path = Path("/ref_audio") / name
    f.save(str(path))
    return jsonify({"name": name, "path": str(path)})

app.run(host="0.0.0.0", port=7860)