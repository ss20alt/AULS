# Descarga de los modelos del estudio (una sola vez; ≈ 4.6 GB): alineación forzada, verificación de voz y whisper large-v3.
import os, sys
from huggingface_hub import snapshot_download
D = os.path.dirname(os.path.abspath(__file__))
for repo, allow in (("jonatasgrosman/wav2vec2-large-xlsr-53-spanish", ["*.json", "*.txt", "*.safetensors", "pytorch_model.bin", "vocab.json"]),
                    ("microsoft/wavlm-base-plus-sv", ["*.json", "*.txt", "*.safetensors", "pytorch_model.bin"])):
    p = snapshot_download(repo, local_dir=os.path.join(D, repo.split("/")[1]), allow_patterns=allow)
    tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(p) for f in fs)
    print("OK", repo, round(tot / 1e6), "MB", flush=True)
from faster_whisper.utils import download_model
p = download_model("large-v3")                                   # queda en la caché de Hugging Face (~3 GB)
print("OK whisper large-v3", p, flush=True)
import urllib.request                                           # caras: detector YuNet y reconocedor SFace (OpenCV Zoo, ≈ 37 MB)
for f, url in (("yunet.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"),
               ("sface.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx")):
    if not os.path.exists(os.path.join(D, f)):
        urllib.request.urlretrieve(url, os.path.join(D, f))
    print("OK", f, round(os.path.getsize(os.path.join(D, f)) / 1e6), "MB", flush=True)
print("FIN")
