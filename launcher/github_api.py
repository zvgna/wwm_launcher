import requests

GITHUB_API = "https://api.github.com"


def get_latest_release(owner: str, repo: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/latest"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def get_recent_releases(owner: str, repo: str, limit: int = 5) -> list[dict]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases"
    r = requests.get(url, params={"per_page": limit}, timeout=30)
    r.raise_for_status()
    return r.json()


def get_release_by_tag(owner: str, repo: str, tag: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/tags/{tag}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def find_asset(release_json: dict, name: str) -> dict | None:
    for a in release_json.get("assets", []):
        if a.get("name") == name:
            return a
    return None


def download_asset(asset: dict, dst_path: str) -> None:
    url = asset["browser_download_url"]
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dst_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
