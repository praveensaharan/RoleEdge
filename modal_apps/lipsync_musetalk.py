"""MuseTalk 1.5 on Modal (file name must not be musetalk.py, which would shadow the package): lip-sync a face (photo or video) to an audio file.

For the "open" rules profile and build-time comparison only; the hackathon ("strict") build animates avatars with
Meta models plus plain code instead.

    modal run modal_apps/lipsync_musetalk.py --face web/app/avatars/kenji-photo/base.jpg --audio output/compare/line.wav \
        --out output/compare/musetalk_kenji.mp4
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time

import modal

app = modal.App("roleedge-musetalk")
REPO = "/opt/MuseTalk"


def download_weights() -> None:
    """The repo's download_weights.sh calls tools this image lacks (huggingface-cli, curl) and still reports
    success, so the same files are fetched here directly."""
    import os
    import subprocess
    import urllib.request

    from huggingface_hub import hf_hub_download

    models = f"{REPO}/models"
    wanted = [("TMElyralab/MuseTalk", ["musetalk/musetalk.json", "musetalk/pytorch_model.bin",
                                       "musetalkV15/musetalk.json", "musetalkV15/unet.pth"], ""),
              ("stabilityai/sd-vae-ft-mse", ["config.json", "diffusion_pytorch_model.bin"], "sd-vae"),
              ("openai/whisper-tiny", ["config.json", "pytorch_model.bin", "preprocessor_config.json"], "whisper"),
              ("yzd-v/DWPose", ["dw-ll_ucoco_384.pth"], "dwpose")]
    for repo, files, sub in wanted:
        for name in files:
            hf_hub_download(repo, name, local_dir=os.path.join(models, sub))
    try:  # syncnet is only used for training; inference works without it
        hf_hub_download("ByteDance/LatentSync", "latentsync_syncnet.pt", local_dir=f"{models}/syncnet")
    except Exception as exc:  # noqa: BLE001
        print("syncnet skipped:", exc)
    os.makedirs(f"{models}/face-parse-bisent", exist_ok=True)
    subprocess.run(["gdown", "154JgKpzCPW82qINcVieuPH3fZ2e0P812", "-O",
                    f"{models}/face-parse-bisent/79999_iter.pth"], check=True)
    urllib.request.urlretrieve("https://download.pytorch.org/models/resnet18-5c106cde.pth",
                               f"{models}/face-parse-bisent/resnet18-5c106cde.pth")
    for root, _, files in os.walk(models):
        for name in files:
            print(os.path.join(root, name), os.path.getsize(os.path.join(root, name)))


image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "wget")
    .pip_install("torch==2.0.1", "torchvision==0.15.2", "torchaudio==2.0.2",
                 index_url="https://download.pytorch.org/whl/cu118")
    .run_commands(f"git clone --depth 1 https://github.com/TMElyralab/MuseTalk {REPO}")
    .run_commands(f"cd {REPO} && pip install -r requirements.txt")
    .pip_install("openmim", "huggingface_hub<1.0", "gdown")  # transformers 4.39 needs huggingface_hub < 1.0
    .run_commands("mim install mmengine", 'mim install "mmcv==2.0.1"', 'mim install "mmdet==3.1.0"',
                  'mim install "mmpose==1.1.0"')
    .run_function(download_weights)
)


@app.function(gpu="A10G", image=image, timeout=1200, scaledown_window=60)
def lipsync(face: bytes, face_name: str, audio: bytes) -> tuple[bytes, float]:
    work = pathlib.Path(tempfile.mkdtemp())
    face_path, audio_path = work / face_name, work / "audio.wav"
    face_path.write_bytes(face)
    audio_path.write_bytes(audio)
    config = work / "task.yaml"
    config.write_text(f'task_0:\n  video_path: "{face_path}"\n  audio_path: "{audio_path}"\n')
    out_dir = work / "results"
    started = time.time()
    result = subprocess.run(
        ["python", "-m", "scripts.inference", "--inference_config", str(config), "--result_dir", str(out_dir),
         "--unet_model_path", "models/musetalkV15/unet.pth", "--unet_config", "models/musetalkV15/musetalk.json",
         "--version", "v15", "--ffmpeg_path", "/usr/bin"],
        cwd=REPO, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": REPO})
    seconds = time.time() - started
    videos = sorted(out_dir.rglob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True)
    if result.returncode != 0 or not videos:
        raise RuntimeError(f"MuseTalk failed ({result.returncode}):\n{result.stderr[-3000:]}")
    return videos[0].read_bytes(), seconds


@app.local_entrypoint()
def main(face: str, audio: str, out: str) -> None:
    data, seconds = lipsync.remote(pathlib.Path(face).read_bytes(), pathlib.Path(face).name,
                                   pathlib.Path(audio).read_bytes())
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    pathlib.Path(out).write_bytes(data)
    print(f"wrote {out} ({len(data)} bytes); MuseTalk took {seconds:.1f}s on the GPU")
