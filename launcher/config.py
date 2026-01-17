import json
import sys
from pathlib import Path

APP_FOLDER_NAME = "WWMRU"


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_app_dir() -> Path:
    d = _base_dir() / APP_FOLDER_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = get_app_dir() / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg.setdefault("game_root", "")
            cfg.setdefault("installed_version", "—")
            cfg.setdefault("backup_enabled", True)
            cfg.setdefault("backup_done", False)
            cfg.setdefault("recent_versions", [])
            return cfg
        except Exception:
            pass

    return {
        "game_root": "",
        "installed_version": "—",
        "backup_enabled": True,
        "backup_done": False,
        "recent_versions": [],
    }


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
