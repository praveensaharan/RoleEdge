"""Qwen3-TTS on Modal (file name must not be qwen_tts.py, which would shadow the package): speech for the "open" rules profile and for build-time comparisons.

Not used in the hackathon ("strict") build, where every model called at runtime must be a Meta model.

    modal run modal_apps/tts_qwen.py --text "..." --language Japanese --speaker Ryan --out output/compare/line.wav
"""

from __future__ import annotations

import io
import os

import modal

app = modal.App("roleedge-qwen-tts")
cache = modal.Volume.from_name("roleedge-hf-cache", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12")
         .apt_install("ffmpeg", "libsndfile1", "sox")
         .pip_install("qwen-tts", "soundfile")
         .env({"HF_HOME": "/cache/hf"}))


@app.cls(gpu="A10G", image=image, volumes={"/cache": cache}, scaledown_window=60, timeout=900)
class TTS:
    @modal.enter()
    def load(self) -> None:
        import torch
        from qwen_tts import Qwen3TTSModel

        self.model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", device_map="cuda:0",
                                                   dtype=torch.bfloat16)
        cache.commit()

    @modal.method()
    def speakers(self) -> list[str]:
        return list(self.model.get_supported_speakers())

    @modal.method()
    def speak(self, text: str, language: str = "Japanese", speaker: str = "Ryan") -> bytes:
        import soundfile as sf

        wavs, rate = self.model.generate_custom_voice(text=text, language=language, speaker=speaker)
        buf = io.BytesIO()
        sf.write(buf, wavs[0], rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()


@app.local_entrypoint()
def main(text: str, out: str, language: str = "Japanese", speaker: str = "Ryan") -> None:
    tts = TTS()
    print("speakers:", tts.speakers.remote())
    data = tts.speak.remote(text, language, speaker)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(data)
    print(f"wrote {out} ({len(data)} bytes)")
