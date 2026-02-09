import os
import re
import csv
from urllib.parse import urlparse

IN_PATH = "out/mapping_packages_to_github_with_index_html.csv"
OUT_DIR = "out/final"
os.makedirs(OUT_DIR, exist_ok=True)

OUT_ALL = os.path.join(OUT_DIR, "packages_to_repos_all.csv")
OUT_GH  = os.path.join(OUT_DIR, "packages_to_repos_github_only.csv")

GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+)", re.IGNORECASE)

def normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    p = urlparse(u)
    clean = f"{p.scheme}://{p.netloc}{p.path}"
    clean = clean.rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    return clean

def host_of(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    try:
        return urlparse(u).netloc.lower()
    except Exception:
        return ""

def parse_github_owner_repo(url_norm: str):
    m = GITHUB_RE.match(url_norm or "")
    if not m:
        return "", "", ""
    owner = m.group(1)
    repo = m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo, f"{owner}/{repo}"

def main():
    rows = list(csv.DictReader(open(IN_PATH, encoding="utf-8")))

    out_rows = []
    out_rows_gh = []

    for r in rows:
        repo_url = (r.get("repo_url") or "").strip()
        repo_url_norm = normalize_url(repo_url)
        host = host_of(repo_url_norm)

        resolved_repo_url = bool(repo_url_norm)

        gh_owner, gh_repo, full_name = parse_github_owner_repo(repo_url_norm)
        is_github = bool(full_name)

        resolved_via = (r.get("resolved_via") or "").strip() or "none"

        # build output row
        out = {
            "ros_distro": r.get("ros_distro", ""),
            "package": r.get("package", ""),
            "rosdistro_repo_key": (r.get("rosdistro_repo_key") or "").strip(),

            "repo_url": repo_url,
            "repo_url_normalized": repo_url_norm,
            "host": host,

            "resolved_repo_url": resolved_repo_url,
            "is_github": is_github,
            "github_owner": gh_owner,
            "github_repo": gh_repo,
            "full_name": full_name,

            "repo_url_type": (r.get("repo_url_type") or "").strip(),
            "resolved_via": resolved_via,
        }

        out_rows.append(out)
        if is_github:
            out_rows_gh.append(out)

    # write all
    fieldnames = list(out_rows[0].keys())
    with open(OUT_ALL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    # write github only
    with open(OUT_GH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows_gh)

    print(f"[OK] saved {OUT_ALL} rows={len(out_rows)}")
    print(f"[OK] saved {OUT_GH} rows={len(out_rows_gh)}")

if __name__ == "__main__":
    main()
