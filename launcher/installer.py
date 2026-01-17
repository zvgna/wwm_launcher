import shutil
import tempfile
from pathlib import Path

from launcher.github_api import get_latest_release, find_asset, download_asset


RELATIVE_LOCALE_DIR = Path("Where Winds Meet") / "Package" / "HD" / "oversea" / "locale"
ASSET_MAIN = "translate_words_map_en"
ASSET_DIFF = "translate_words_map_en_diff"


def _resolve_game_base(user_selected: Path) -> Path:
    """
    user_selected может быть:
    1) ...\Where Winds Meet
    2) ...\ (папка уровнем выше, внутри есть Where Winds Meet)
    Возвращаем base так, чтобы base / RELATIVE_LOCALE_DIR существовал (или был близок).
    """
    user_selected = user_selected.resolve()

    # Вариант: выбрали папку уровнем выше
    cand1 = user_selected / RELATIVE_LOCALE_DIR
    if cand1.exists():
        return user_selected

    # Вариант: выбрали саму папку "Where Winds Meet"
    # Тогда base = parent, чтобы base/Where Winds Meet/... работал
    cand2 = user_selected.parent / RELATIVE_LOCALE_DIR
    if cand2.exists():
        return user_selected.parent

    # Если пока не существует (например игра не установлена полностью),
    # всё равно пробуем считать, что выбрали корень игры (= Where Winds Meet)
    # и тогда base = parent
    if user_selected.name.lower() == "where winds meet":
        return user_selected.parent

    # Иначе считаем, что выбрали базу, как есть
    return user_selected


def _backup_file(dst: Path, backup_root: Path) -> None:
    backup_root.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.copy2(dst, backup_root / dst.name)


def install_from_github(owner: str, repo: str, user_selected_path: str) -> str:
    user_selected = Path(user_selected_path)
    base = _resolve_game_base(user_selected)

    locale_dir = base / RELATIVE_LOCALE_DIR
    locale_dir.mkdir(parents=True, exist_ok=True)

    target_main = locale_dir / ASSET_MAIN
    target_diff = locale_dir / ASSET_DIFF

    release = get_latest_release(owner, repo)

    main_asset = find_asset(release, ASSET_MAIN)
    if not main_asset:
        return f"В latest release не найден asset: {ASSET_MAIN}"

    diff_asset = find_asset(release, ASSET_DIFF)  # может отсутствовать — это ок

    backup_dir = locale_dir / "_backup_launcher"

    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            # MAIN
            tmp_main = td / ASSET_MAIN
            download_asset(main_asset, str(tmp_main))
            _backup_file(target_main, backup_dir)
            shutil.copy2(tmp_main, target_main)

            # DIFF (опционально)
            if diff_asset:
                tmp_diff = td / ASSET_DIFF
                download_asset(diff_asset, str(tmp_diff))
                _backup_file(target_diff, backup_dir)
                shutil.copy2(tmp_diff, target_diff)

        msg = (
            "Установлено:\n"
            f"- {target_main}\n"
        )
        if diff_asset:
            msg += f"- {target_diff}\n"
        else:
            msg += "- diff-файл в релизе не найден (это нормально, поставили только основной)\n"

        return msg

    except PermissionError:
        return (
            "Нет прав на запись в папку игры.\n"
            "Решение: запусти лаунчер от администратора или перенеси игру из Program Files."
        )
    except OSError as e:
        return f"Ошибка файловой системы: {e}"
