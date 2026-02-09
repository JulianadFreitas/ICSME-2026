"""
extract_repo_features_and_snapshots.py

Input:
  - github_repos_unique.csv (must contain at least a repo identifier per row)
    Supported columns (auto-detected):
      - full_name  (e.g., "owner/repo")
      - html_url   (e.g., "https://github.com/owner/repo")
      - url        (e.g., "https://github.com/owner/repo")

Output (per repo):
  data/ros_robotics_data/<owner>__<repo>/
    - general_info.json
    - commits.json
    - forks.json
    - stars.json
    - contributors.json
    - pull_requests.json
    - issues.json
    - license.json
    - readme.json
    - contributing.json
    - languages.json
    - weekly_commit_activity.json
    - code_of_conduct.json
    - issue_template.json
    - pr_template.json

All JSON files are saved as SNAPSHOTS:
{
  "_meta": {... "fetched_at": "...Z", "owner": "...", "repo": "...", "endpoint": "..."},
  "data": <raw payload or simplified list>
}

Notes:
- This script DOES NOT create/modify github_repos_unique.csv.
- Commits are stored as simplified objects (sha, author, date, message) to keep size manageable.
- weekly_commit_activity uses the stats endpoint and retries 202 responses.
"""

import os
import csv
import json
import time
import re
from datetime import datetime, timezone
from collections import defaultdict, Counter

import requests
from dotenv import load_dotenv
from dateutil.parser import parse as parse_date

# =========================
# 0) CONFIG
# =========================
load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("GitHub token not found. Set GITHUB_TOKEN in your environment (.env).")

HEADERS_REST = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS_GQL = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

OUT_ROOT = "data/ros_robotics_data"
REQUEST_SLEEP = 0.2
PER_PAGE = 100

# =========================
# 1) SNAPSHOT HELPERS
# =========================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def save_snapshot_json(data, filename, meta: dict):
    snapshot = {
        "_meta": {"fetched_at": utc_now_iso(), **(meta or {})},
        "data": data,
    }
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
    print(f"[OK] Saved: {filename}")

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def is_snapshot(obj) -> bool:
    return isinstance(obj, dict) and "_meta" in obj and "data" in obj

def load_snapshot_data(path: str):
    obj = load_json(path)
    return obj["data"] if is_snapshot(obj) else obj

# =========================
# 2) URL PARSING (from CSV)
# =========================
def parse_owner_repo(row: dict):
    """
    Detect repo identifier from row and return (owner, repo) or (None, None).
    Priority:
      1) full_name: owner/repo
      2) html_url or url: https://github.com/owner/repo[...]
    """
    full_name = (row.get("full_name") or "").strip()
    if full_name and "/" in full_name:
        parts = full_name.split("/")
        return parts[0].strip(), parts[1].strip()

    for k in ("html_url", "url"):
        v = (row.get(k) or "").strip()
        if not v:
            continue
        m = re.search(r"github\.com/([^/]+)/([^/#?]+)", v)
        if m:
            return m.group(1), m.group(2)

    return None, None

# =========================
# 3) REST + GRAPHQL FETCH
# =========================
def fetch_rest(url, params=None):
    time.sleep(REQUEST_SLEEP)
    r = requests.get(url, headers=HEADERS_REST, params=params)
    if r.status_code == 200:
        return r.json()
    print(f"[REST] {r.status_code} for {url} :: {r.text[:200]}")
    return None

def fetch_gql(query: str, variables: dict):
    time.sleep(REQUEST_SLEEP)
    r = requests.post(GRAPHQL_URL, headers=HEADERS_GQL, json={"query": query, "variables": variables})
    if r.status_code == 200:
        payload = r.json()
        if "errors" in payload:
            print(f"[GQL] errors: {payload['errors'][:1]}")
            return None
        return payload
    print(f"[GQL] {r.status_code} :: {r.text[:200]}")
    return None

# =========================
# 4) FEATURE FETCHERS
# =========================
def fetch_repo_general_info(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    r = fetch_rest(url)
    if not r:
        return None

    topics = r.get("topics", None)
    
    # Get commits count
    commits = fetch_commits(owner, repo)
    commits_count = len(commits) if isinstance(commits, list) else 0

    return {
        "full_name": r.get("full_name"),
        "html_url": r.get("html_url"),
        "description": r.get("description"),
        "archived": r.get("archived"),
        "fork": r.get("fork"),
        "default_branch": r.get("default_branch"),
        "license": (r.get("license") or {}).get("spdx_id") or (r.get("license") or {}).get("name"),
        "size": r.get("size"),
        "language": r.get("language"),
        "topics": topics,
        "stargazers_count": r.get("stargazers_count"),
        "forks_count": r.get("forks_count"),
        "open_issues_count": r.get("open_issues_count"),
        "subscribers_count": r.get("subscribers_count"),
        "watchers_count": r.get("watchers_count"),
        "commits_count": commits_count,
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
        "pushed_at": r.get("pushed_at"),
    }

def fetch_readme(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    r = fetch_rest(url)
    if r and isinstance(r, dict):
        return {"download_url": r.get("download_url"), "path": r.get("path"), "name": r.get("name")}
    return {"download_url": None, "path": None, "name": None}

def fetch_license(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/license"
    r = fetch_rest(url)
    if r and isinstance(r, dict):
        lic = r.get("license") or {}
        return {"spdx_id": lic.get("spdx_id"), "name": lic.get("name")}
    return {"spdx_id": None, "name": None}

def fetch_languages(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    r = fetch_rest(url)
    return r or {}

def fetch_contributing(owner, repo):
    # common paths
    candidates = [
        "CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "docs/CONTRIBUTING.md",
        "contributing.md",
    ]
    for path in candidates:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        r = fetch_rest(url)
        if r and isinstance(r, dict) and r.get("download_url"):
            return {"found": True, "path": path, "download_url": r.get("download_url")}
    return {"found": False, "path": None, "download_url": None}

def fetch_code_of_conduct(owner, repo):
    candidates = [
        "CODE_OF_CONDUCT.md",
        ".github/CODE_OF_CONDUCT.md",
        "docs/CODE_OF_CONDUCT.md",
        "code-of-conduct.md",
        ".github/code-of-conduct.md",
    ]
    for path in candidates:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        r = fetch_rest(url)
        if r and isinstance(r, dict) and r.get("download_url"):
            content_url = r["download_url"]
            time.sleep(REQUEST_SLEEP)
            cr = requests.get(content_url, headers=HEADERS_REST)
            if cr.status_code == 200:
                return {"found": True, "path": path, "download_url": content_url, "preview": cr.text[:500]}
            return {"found": True, "path": path, "download_url": content_url, "preview": None}
    return {"found": False, "path": None, "download_url": None, "preview": None}

def fetch_issue_template(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE"
    r = fetch_rest(url)
    if isinstance(r, list):
        # any template-like file
        found = any(("issue" in (x.get("name", "").lower())) for x in r)
        return {"has_issue_template": bool(found), "files": [x.get("name") for x in r]}
    return {"has_issue_template": False, "files": []}

def fetch_pr_template(owner, repo):
    candidates = [
        ".github/PULL_REQUEST_TEMPLATE.md",
        "PULL_REQUEST_TEMPLATE.md",
        ".github/pull_request_template.md",
        "pull_request_template.md",
        ".github/PULL_REQUEST_TEMPLATE",
    ]
    for path in candidates:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        r = fetch_rest(url)
        if r and isinstance(r, dict) and r.get("download_url"):
            return {"has_pr_template": True, "path": path, "download_url": r.get("download_url")}
    url_dir = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/PULL_REQUEST_TEMPLATE"
    r = fetch_rest(url_dir)
    if isinstance(r, list) and len(r) > 0:
        return {"has_pr_template": True, "path": ".github/PULL_REQUEST_TEMPLATE/", "download_url": None}
    return {"has_pr_template": False, "path": None, "download_url": None}

def fetch_commits(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    out = []
    page = 1
    while True:
        r = fetch_rest(url, params={"per_page": PER_PAGE, "page": page})
        if not r:
            break
        if not isinstance(r, list) or len(r) == 0:
            break
        for c in r:
            out.append({
                "sha": c.get("sha"),
                "author": (c.get("commit") or {}).get("author", {}).get("name"),
                "date": (c.get("commit") or {}).get("author", {}).get("date"),
                "message": (c.get("commit") or {}).get("message"),
            })
        page += 1
    return out

def fetch_forks(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    out = []
    page = 1
    while True:
        r = fetch_rest(url, params={"per_page": PER_PAGE, "page": page})
        if not r:
            break
        if not isinstance(r, list) or len(r) == 0:
            break
        for f in r:
            out.append({
                "forked_at": f.get("created_at"),
                "owner": (f.get("owner") or {}).get("login"),
                "full_name": f.get("full_name"),
                "html_url": f.get("html_url"),
            })
        page += 1
    return out

def fetch_pull_requests(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    out = []
    page = 1
    while True:
        r = fetch_rest(url, params={"state": "all", "per_page": PER_PAGE, "page": page})
        if not r:
            break
        if not isinstance(r, list) or len(r) == 0:
            break
        for pr in r:
            out.append({
                "id": pr.get("id"),
                "number": pr.get("number"),
                "state": pr.get("state"),
                "title": pr.get("title"),
                "created_at": pr.get("created_at"),
                "closed_at": pr.get("closed_at"),
                "merged_at": pr.get("merged_at"),
                "user": (pr.get("user") or {}).get("login"),
            })
        page += 1
    return out

def fetch_contributors(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    out = []
    page = 1
    while True:
        r = fetch_rest(url, params={"per_page": PER_PAGE, "page": page})
        if not r:
            break
        if not isinstance(r, list) or len(r) == 0:
            break
        for c in r:
            out.append({
                "login": c.get("login"),
                "contributions": c.get("contributions"),
            })
        page += 1
    return out

def fetch_stars_with_dates(owner, repo):
    query = """
    query ($owner: String!, $repo: String!, $after: String) {
      repository(owner: $owner, name: $repo) {
        stargazers(first: 100, after: $after) {
          edges {
            starredAt
            node { login }
          }
          pageInfo { endCursor hasNextPage }
        }
      }
    }
    """
    stars = []
    after = None
    while True:
        data = fetch_gql(query, {"owner": owner, "repo": repo, "after": after})
        if not data:
            break
        edges = data["data"]["repository"]["stargazers"]["edges"]
        for e in edges:
            stars.append({"starred_at": e["starredAt"], "user": e["node"]["login"]})
        pi = data["data"]["repository"]["stargazers"]["pageInfo"]
        if pi["hasNextPage"]:
            after = pi["endCursor"]
        else:
            break
    return stars

def fetch_issues(owner, repo):
    query = """
    query ($owner: String!, $repo: String!, $after: String) {
      repository(owner: $owner, name: $repo) {
        issues(first: 100, after: $after) {
          edges {
            node {
              number title state createdAt closedAt
              author { login }
            }
          }
          pageInfo { endCursor hasNextPage }
        }
      }
    }
    """
    issues = []
    after = None
    while True:
        data = fetch_gql(query, {"owner": owner, "repo": repo, "after": after})
        if not data:
            break
        edges = data["data"]["repository"]["issues"]["edges"]
        for e in edges:
            n = e["node"]
            issues.append({
                "number": n["number"],
                "title": n["title"],
                "state": n["state"],
                "created_at": n["createdAt"],
                "closed_at": n["closedAt"],
                "author": (n.get("author") or {}).get("login"),
            })
        pi = data["data"]["repository"]["issues"]["pageInfo"]
        if pi["hasNextPage"]:
            after = pi["endCursor"]
        else:
            break
    return issues

def fetch_weekly_commit_activity(owner, repo, retries=6, delay=10):
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity"
    for attempt in range(retries):
        time.sleep(REQUEST_SLEEP)
        r = requests.get(url, headers=HEADERS_REST)
        if r.status_code == 200:
            data = r.json() or []
            # normalize weeks into readable date
            return [{"week": datetime.utcfromtimestamp(x["week"]).strftime("%Y-%m-%d"), "total": x["total"]} for x in data]
        if r.status_code == 202:
            print(f"[STATS] 202 generating {owner}/{repo}... wait {delay}s ({attempt+1}/{retries})")
            time.sleep(delay)
            continue
        print(f"[STATS] {r.status_code} {owner}/{repo} :: {r.text[:200]}")
        break
    return []

# =========================
# 5) DERIVED FLAGS (has_*)
# =========================
def compute_has_flags(readme_obj, contributing_obj, coc_obj, pr_template_obj, issue_template_obj):
    return {
        "has_readme": bool(readme_obj and readme_obj.get("download_url")),
        "has_contributing": bool(contributing_obj and contributing_obj.get("found")),
        "has_code_of_conduct": bool(coc_obj and coc_obj.get("found")),
        "has_pr_template": bool(pr_template_obj and pr_template_obj.get("has_pr_template")),
        "has_issue_template": bool(issue_template_obj and issue_template_obj.get("has_issue_template")),
    }

# =========================
# 6) PROCESSING
# =========================
REQUIRED_FILES = [
    "general_info.json",
    "commits.json",
    "forks.json",
    "stars.json",
    "contributors.json",
    "pull_requests.json",
    "issues.json",
    "license.json",
    "readme.json",
    "contributing.json",
    "languages.json",
    "weekly_commit_activity.json",
    "code_of_conduct.json",
    "issue_template.json",
    "pr_template.json",
]

def get_missing(repo_dir: str):
    missing = []
    for f in REQUIRED_FILES:
        p = os.path.join(repo_dir, f)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            missing.append(f)
            continue
        try:
            _ = load_json(p)
        except Exception:
            missing.append(f)
    return missing

def process_repo(owner: str, repo: str):
    repo_dir = os.path.join(OUT_ROOT, f"{owner}__{repo}")
    os.makedirs(repo_dir, exist_ok=True)

    missing = get_missing(repo_dir)
    if not missing:
        print(f"[SKIP] {owner}/{repo} already complete")
        return

    print(f"[RUN] {owner}/{repo} missing: {missing}")

    # 1) general info
    if "general_info.json" in missing:
        info = fetch_repo_general_info(owner, repo)
        if info is None:
            print(f"[WARN] Failed repo: {owner}/{repo}")
            return
        save_snapshot_json(info, os.path.join(repo_dir, "general_info.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}", "owner": owner, "repo": repo})

    # 2) readme / contributing / coc / templates
    if "readme.json" in missing:
        readme = fetch_readme(owner, repo)
        save_snapshot_json(readme, os.path.join(repo_dir, "readme.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/readme", "owner": owner, "repo": repo})

    if "contributing.json" in missing:
        contributing = fetch_contributing(owner, repo)
        save_snapshot_json(contributing, os.path.join(repo_dir, "contributing.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/contents/<CONTRIBUTING*>", "owner": owner, "repo": repo})

    if "code_of_conduct.json" in missing:
        coc = fetch_code_of_conduct(owner, repo)
        save_snapshot_json(coc, os.path.join(repo_dir, "code_of_conduct.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/contents/<CODE_OF_CONDUCT*>", "owner": owner, "repo": repo})

    if "issue_template.json" in missing:
        it = fetch_issue_template(owner, repo)
        save_snapshot_json(it, os.path.join(repo_dir, "issue_template.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/contents/.github/ISSUE_TEMPLATE", "owner": owner, "repo": repo})

    if "pr_template.json" in missing:
        pt = fetch_pr_template(owner, repo)
        save_snapshot_json(pt, os.path.join(repo_dir, "pr_template.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/contents/<PR_TEMPLATE*>", "owner": owner, "repo": repo})

    # 3) commits (save ALL as JSON snapshot)
    if "commits.json" in missing:
        commits = fetch_commits(owner, repo)
        save_snapshot_json(commits, os.path.join(repo_dir, "commits.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/commits", "owner": owner, "repo": repo, "per_page": PER_PAGE})

    # 4) forks, stars, contributors, PRs, issues
    if "forks.json" in missing:
        forks = fetch_forks(owner, repo)
        save_snapshot_json(forks, os.path.join(repo_dir, "forks.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/forks", "owner": owner, "repo": repo, "per_page": PER_PAGE})

    if "stars.json" in missing:
        stars = fetch_stars_with_dates(owner, repo)
        save_snapshot_json(stars, os.path.join(repo_dir, "stars.json"),
                           meta={"source": "github_graphql", "endpoint": "repository.stargazers(edges{starredAt,node{login}})", "owner": owner, "repo": repo})

    if "contributors.json" in missing:
        contributors = fetch_contributors(owner, repo)
        save_snapshot_json(contributors, os.path.join(repo_dir, "contributors.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/contributors", "owner": owner, "repo": repo, "per_page": PER_PAGE})

    if "pull_requests.json" in missing:
        prs = fetch_pull_requests(owner, repo)
        save_snapshot_json(prs, os.path.join(repo_dir, "pull_requests.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/pulls?state=all", "owner": owner, "repo": repo, "per_page": PER_PAGE})

    if "issues.json" in missing:
        issues = fetch_issues(owner, repo)
        save_snapshot_json(issues, os.path.join(repo_dir, "issues.json"),
                           meta={"source": "github_graphql", "endpoint": "repository.issues(edges{node{...}})", "owner": owner, "repo": repo})

    # 5) license + languages
    if "license.json" in missing:
        lic = fetch_license(owner, repo)
        save_snapshot_json(lic, os.path.join(repo_dir, "license.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/license", "owner": owner, "repo": repo})

    if "languages.json" in missing:
        langs = fetch_languages(owner, repo)
        save_snapshot_json(langs, os.path.join(repo_dir, "languages.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/languages", "owner": owner, "repo": repo})

    # 6) weekly commit activity (stats endpoint)
    if "weekly_commit_activity.json" in missing:
        w = fetch_weekly_commit_activity(owner, repo)
        save_snapshot_json(w, os.path.join(repo_dir, "weekly_commit_activity.json"),
                           meta={"source": "github_rest", "endpoint": "/repos/{owner}/{repo}/stats/commit_activity", "owner": owner, "repo": repo})

    print(f"[DONE] {owner}/{repo}")

def process_csv(csv_path: str):
    os.makedirs(OUT_ROOT, exist_ok=True)

    # count rows
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    ok = 0
    skipped = 0

    for i, row in enumerate(rows, start=1):
        owner, repo = parse_owner_repo(row)
        if not owner or not repo:
            print(f"[{i}/{total}] [SKIP] cannot parse repo from row keys={list(row.keys())}")
            skipped += 1
            continue

        print(f"\n[{i}/{total}] Processing {owner}/{repo}")
        try:
            process_repo(owner, repo)
            ok += 1
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[ERR] {owner}/{repo}: {repr(e)}")

    print(f"\n[SUMMARY] processed={ok} skipped={skipped} total_rows={total}")

if __name__ == "__main__":
    process_csv("out/repos/github_repos_unique.csv")
