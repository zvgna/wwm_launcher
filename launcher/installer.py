import shutil
import tempfile
from pathlib import Path

from launcher.config import get_app_dir, load_config, save_config
from launcher.github_api import (
    download_asset,
    find_asset,
    get_latest_release,
    get_recent_releases,
    get_release_by_tag,
)

OWNER = "zvgna"
REPO = "translate"

ASSET_MAIN = "translate_words_map_en"
ASSET_DIFF = "translate_words_map_en_diff"

RELATIVE_LOCALE_DIR = Path("Where Winds Meet") / "Package" / "HD" / "oversea" / "locale"


def _resolve_base(user_selected: Path) -> Path:
    user_selected = user_selected.resolve()

    if (user_selected / RELATIVE_LOCALE_DIR).exists():
        return user_selected

    if user_selected.name.lower() == "where winds meet":
        return user_selected.parent

    cand = user_selected.parent / RELATIVE_LOCALE_DIR
    if cand.exists():
        return user_selected.parent

    return user_selected


def _backup_originals_once(target_main: Path, target_diff: Path) -> None:
    cfg = load_config()
    if not cfg.get("backup_enabled", True):
        return
    if cfg.get("backup_done", False):
        return

    backup_dir = get_app_dir() / "backup" / "original"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if target_main.exists():
        shutil.copy2(target_main, backup_dir / ASSET_MAIN)
    if target_diff.exists():
        shutil.copy2(target_diff, backup_dir / ASSET_DIFF)

    cfg["backup_done"] = True
    save_config(cfg)


def get_latest_version() -> tuple[str, str]:
    release = get_latest_release(OWNER, REPO)
    version = release.get("tag_name") or release.get("name") or "unknown"
    notes = release.get("body") or ""
    return version, notes


def get_recent_versions(limit: int = 5) -> list[str]:
    releases = get_recent_releases(OWNER, REPO, limit=limit)
    tags: list[str] = []
    for r in releases:
        tag = r.get("tag_name") or r.get("name")
        if tag:
            tags.append(tag)
    return tags[:limit]


def install_latest(user_selected_path: str) -> tuple[bool, str, str]:
    release = get_latest_release(OWNER, REPO)
    version = release.get("tag_name") or release.get("name") or "unknown"
    return _install_release(user_selected_path, release, version)


def install_version(user_selected_path: str, tag: str) -> tuple[bool, str, str]:
    release = get_release_by_tag(OWNER, REPO, tag)
    version = release.get("tag_name") or release.get("name") or tag
    return _install_release(user_selected_path, release, version)


def _install_release(user_selected_path: str, release: dict, version: str) -> tuple[bool, str, str]:
    base = _resolve_base(Path(user_selected_path))
    locale_dir = base / RELATIVE_LOCALE_DIR
    locale_dir.mkdir(parents=True, exist_ok=True)

    target_main = locale_dir / ASSET_MAIN
    target_diff = locale_dir / ASSET_DIFF

    try:
        main_asset = find_asset(release, ASSET_MAIN)
        if not main_asset:
            return False, version, f"В релизе {version} нет файла '{ASSET_MAIN}'."

        diff_asset = find_asset(release, ASSET_DIFF)

        _backup_originals_once(target_main, target_diff)

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            tmp_main = td / ASSET_MAIN
            download_asset(main_asset, str(tmp_main))
            shutil.copy2(tmp_main, target_main)

            installed = [ASSET_MAIN]

            if diff_asset:
                tmp_diff = td / ASSET_DIFF
                download_asset(diff_asset, str(tmp_diff))
                shutil.copy2(tmp_diff, target_diff)
                installed.append(ASSET_DIFF)

        msg = (
            f"Установлена версия: {version}\n"
            f"Файлы: {', '.join(installed)}\n"
            f"Путь: {locale_dir}"
        )
        if not diff_asset:
            msg += "\n(diff отсутствует — это нормально)"

        return True, version, msg

    except PermissionError:
        return False, "unknown", "Нет прав на запись в папку игры. Запусти WWMRU от администратора."
    except Exception as e:
        return False, "unknown", f"Ошибка: {e}"
