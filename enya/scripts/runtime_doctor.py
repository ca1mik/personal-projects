from __future__ import annotations

import socket
from pathlib import Path

from bridge_utils import project_root


def _status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def _check_port(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _print_line(label: str, value: str) -> None:
    print(f"{label:<26} {value}")


def main() -> None:
    root = project_root()
    env_path = root / ".env"
    web_env_path = root / "apps" / "web" / ".env.local"
    sf3d_repo = root / "third_party" / "stable-fast-3d"
    hunyuan_repo = root / "third_party" / "Hunyuan3D-2-official"
    lone_ckpt = Path("F:/models/hunyuan/model.fp16.ckpt")
    queue_mode = "redis"

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("QUEUE_MODE="):
                queue_mode = line.split("=", 1)[1].strip().lower() or "redis"
                break

    print("Enya Local 3D Studio Runtime Doctor")
    print()
    _print_line(".env", f"{_status(env_path.exists())} {env_path}")
    _print_line("apps/web/.env.local", f"{_status(web_env_path.exists())} {web_env_path}")
    _print_line("Queue mode", queue_mode)
    _print_line("SF3D repo", f"{_status((sf3d_repo / 'run.py').exists())} {sf3d_repo}")
    _print_line("Hunyuan repo", f"{_status((hunyuan_repo / 'gradio_app.py').exists())} {hunyuan_repo}")
    _print_line("Hunyuan lone ckpt", f"{_status(lone_ckpt.exists())} {lone_ckpt}")
    print()
    _print_line("Redis :6379", "SKIPPED" if queue_mode == "inline" else ("LISTENING" if _check_port("127.0.0.1", 6379) else "DOWN"))
    _print_line("API :8000", "LISTENING" if _check_port("127.0.0.1", 8000) else "DOWN")
    _print_line("Web :3000", "LISTENING" if _check_port("127.0.0.1", 3000) else "DOWN")
    print()

    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    cache_targets = {
        "SF3D HF cache": hf_cache / "models--stabilityai--stable-fast-3d",
        "Hunyuan MV HF cache": hf_cache / "models--tencent--Hunyuan3D-2mv",
        "Hunyuan texture HF cache": hf_cache / "models--tencent--Hunyuan3D-2",
    }
    for label, path in cache_targets.items():
        _print_line(label, f"{_status(path.exists())} {path}")

    print()
    if lone_ckpt.exists():
        print("Note: F:/models/hunyuan/model.fp16.ckpt exists, but a single ckpt file is not enough to run official")
        print("Hunyuan3D-2mv by itself. The official repo expects a full model directory or Hugging Face model id.")
        print()

    print("Recommended next steps:")
    if queue_mode == "inline":
        print("1. Start only API and web. Inline mode will process jobs in the API process without Redis or a worker.")
    else:
        print("1. Start Redis + API + worker + web for the normal RQ flow.")
    print("2. For real single-image generation, request/download Stability AI stable-fast-3d weights and switch SF3D_MODE=subprocess.")
    print("3. For real multiview generation, install the official Hunyuan3D-2 Python environment and switch HUNYUAN_MV_MODE=subprocess.")


if __name__ == "__main__":
    main()
