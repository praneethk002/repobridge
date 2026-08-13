#!/usr/bin/env python3
"""RepoBridge scout: deterministic GitHub retrieval and rule-based scoring.

No LLM calls happen here. All semantic reasoning (query generation, relevance
scoring, gap analysis) is done by Claude in the calling /repobridge skill —
this script only does auditable, rule-based work: search, filter, score.

Two stages, run separately so heavy calls (README, file tree, contributors)
only ever hit the handful of repos that survive cheap metadata scoring first:

    scout.py search --queries "..." [--topics ...] [--requirements ...]
    scout.py enrich --repos owner/repo [owner/repo ...]
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_ROOT = "https://api.github.com"
COPYLEFT_SPDX_IDS = {"gpl-3.0", "gpl-2.0", "agpl-3.0", "lgpl-3.0", "lgpl-2.1"}
DEPLOY_BUTTON_MARKERS = (
    "railway.app/button", "vercel.com/button", "heroku.com/deploy",
    "netlify.com/img/deploy", "render.com/deploy", "deploy.now.sh",
)
# github.com/<segment>/... paths that are site sections, not repos, and would
# otherwise get misread as "owner/repo" by the link-extraction regex.
NON_REPO_PATH_SEGMENTS = {
    "topics", "sponsors", "marketplace", "settings", "orgs", "features",
    "about", "pricing", "contact", "apps", "collections", "trending",
    "explore", "search", "issues", "pulls", "notifications", "login", "join",
}
MAX_README_CHARS = 4000
MAX_AWESOME_LISTS = 2
MAX_EXTRACTED_LINKS = 15
MAX_ENRICH_REPOS = 10


def die(message, code=1):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def warn(message):
    print(f"warning: {message}", file=sys.stderr)


def get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=10
        )
    except FileNotFoundError:
        die("no GITHUB_TOKEN set and the 'gh' CLI isn't installed. "
            "Set GITHUB_TOKEN or install and run 'gh auth login'.")
    if result.returncode != 0 or not result.stdout.strip():
        die("no GITHUB_TOKEN set and 'gh' isn't authenticated. "
            "Run 'gh auth login' or set GITHUB_TOKEN.")
    return result.stdout.strip()


def api_request(path, token, params=None, soft_fail_statuses=()):
    url = f"{API_ROOT}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repobridge-scout",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in soft_fail_statuses:
            return None
        body = e.read().decode("utf-8", errors="replace")[:300]
        if e.code == 403 and "rate limit" in body.lower():
            die(f"GitHub API rate limit hit on {path}. Wait and retry.")
        die(f"GitHub API error {e.code} on {path}: {body}")
    except urllib.error.URLError as e:
        die(f"network error calling GitHub API {path}: {e.reason}")


def months_since(iso_timestamp):
    pushed = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - pushed
    return delta.days / 30.44


def normalize(item):
    license_obj = item.get("license") or {}
    return {
        "id": item["id"],
        "full_name": item["full_name"],
        "url": item["html_url"],
        "description": item.get("description") or "",
        "stars": item["stargazers_count"],
        "license_spdx": license_obj.get("spdx_id"),
        "pushed_at": item["pushed_at"],
        "language": item.get("language"),
        "topics": item.get("topics", []),
        "default_branch": item.get("default_branch"),
    }


def apply_hard_filters(repos, allow_copyleft, stale_months):
    kept = []
    for r in repos:
        if not r["license_spdx"] or r["license_spdx"] == "NOASSERTION":
            continue
        if r["license_spdx"].lower() in COPYLEFT_SPDX_IDS and not allow_copyleft:
            continue
        if months_since(r["pushed_at"]) > stale_months:
            continue
        kept.append(r)
    return kept


def keyword_overlap(repo, requirements):
    if not requirements:
        return 0.0
    haystack = " ".join(
        [repo["full_name"], repo["description"], " ".join(repo["topics"])]
    ).lower()
    hits = sum(1 for kw in requirements if kw.lower() in haystack)
    return hits / len(requirements)


def score_metadata(repo, requirements):
    recency = max(0.0, 1 - months_since(repo["pushed_at"]) / 12) * 30
    stars = min(repo["stars"], 5000) / 5000 * 40
    overlap = keyword_overlap(repo, requirements) * 30
    repo["metadata_score"] = round(recency + stars + overlap, 1)
    repo["score_breakdown"] = {
        "recency": round(recency, 1),
        "stars": round(stars, 1),
        "keyword_overlap": round(overlap, 1),
    }
    return repo


def find_awesome_lists(repos):
    out = []
    for r in repos:
        short_name = r["full_name"].lower().split("/")[-1]
        topics = [t.lower() for t in r["topics"]]
        if "awesome" in short_name or "awesome-list" in topics:
            out.append(r)
    return out[:MAX_AWESOME_LISTS]


def fetch_readme_text(full_name, token, soft=False):
    data = api_request(
        f"/repos/{full_name}/readme", token,
        soft_fail_statuses=(404,) if soft else (),
    )
    if data is None:
        return ""
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def extract_repo_links(readme_text, exclude_full_name):
    pattern = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
    found = []
    seen = {exclude_full_name.lower()}
    for owner, repo in pattern.findall(readme_text):
        repo = repo.rstrip(".,)/")
        if owner.lower() in NON_REPO_PATH_SEGMENTS:
            continue
        full_name = f"{owner}/{repo}"
        if full_name.lower() in seen:
            continue
        seen.add(full_name.lower())
        found.append(full_name)
        if len(found) >= MAX_EXTRACTED_LINKS:
            break
    return found


def fetch_repo(full_name, token, soft=False):
    data = api_request(
        f"/repos/{full_name}", token,
        soft_fail_statuses=(404,) if soft else (),
    )
    return normalize(data) if data else None


def cmd_search(args):
    token = get_token()
    if not any(q.strip() for q in args.queries):
        die("at least one non-empty --query is required")

    merged = {}
    for q in args.queries:
        full_query = q.strip()
        for topic in args.topics:
            full_query += f" topic:{topic}"
        full_query += f" stars:>={args.min_stars}"
        data = api_request("/search/repositories", token, params={
            "q": full_query, "sort": "stars", "order": "desc", "per_page": 20,
        })
        for item in data.get("items", []):
            merged[item["id"]] = normalize(item)

    for awesome in find_awesome_lists(list(merged.values())):
        readme = fetch_readme_text(awesome["full_name"], token, soft=True)
        for full_name in extract_repo_links(readme, awesome["full_name"]):
            repo = fetch_repo(full_name, token, soft=True)
            if repo and repo["id"] not in merged:
                merged[repo["id"]] = repo

    survivors = apply_hard_filters(
        list(merged.values()), args.allow_copyleft, args.stale_months
    )
    if not survivors:
        die("no candidates survived search + hard filters — "
            "try broader queries, lower --min-stars, or --allow-copyleft")

    scored = [score_metadata(r, args.requirements) for r in survivors]
    scored.sort(key=lambda r: r["metadata_score"], reverse=True)
    print(json.dumps(scored[: args.limit], indent=2))


def cmd_enrich(args):
    token = get_token()
    requested = args.repos[:MAX_ENRICH_REPOS]
    if len(args.repos) > MAX_ENRICH_REPOS:
        warn(f"capping enrichment to first {MAX_ENRICH_REPOS} repos")

    out = []
    for full_name in requested:
        repo = fetch_repo(full_name, token, soft=True)
        if repo is None:
            warn(f"skipping {full_name}: not found or inaccessible")
            continue

        readme = fetch_readme_text(full_name, token, soft=True)[:MAX_README_CHARS]
        if not readme:
            warn(f"{full_name}: no README found")

        tree = api_request(
            f"/repos/{full_name}/git/trees/{repo['default_branch']}", token,
            params={"recursive": "1"},
        )
        paths = {entry["path"].lower() for entry in tree.get("tree", [])}
        contributors = api_request(
            f"/repos/{full_name}/contributors", token, params={"per_page": 5}
        )
        contributor_count = len(contributors) if isinstance(contributors, list) else 0

        verified_signals = {
            "recent": months_since(repo["pushed_at"]) <= 12,
            "contributors_ge_3": contributor_count >= 3,
            "ci_present": any(p.startswith(".github/workflows/") for p in paths),
        }
        deployability_signals = {
            "docker_present": bool(
                {"dockerfile", "docker-compose.yml", "docker-compose.yaml"} & paths
            ),
            "env_example_present": bool({".env.example", ".env.sample"} & paths),
            "deploy_button_present": any(
                marker in readme.lower() for marker in DEPLOY_BUTTON_MARKERS
            ),
        }

        repo.update({
            "readme_excerpt": readme,
            "verified_score": round(
                sum(verified_signals.values()) / len(verified_signals) * 100, 1
            ),
            "verified_signals": verified_signals,
            "deployability_score": round(
                sum(deployability_signals.values()) / len(deployability_signals) * 100, 1
            ),
            "deployability_signals": deployability_signals,
        })
        out.append(repo)

    print(json.dumps(out, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic GitHub retrieval/scoring for the /repobridge skill."
    )
    sub = parser.add_subparsers(dest="stage", required=True)

    p_search = sub.add_parser("search", help="metadata-only search + rule-based ranking")
    p_search.add_argument("--queries", nargs="+", required=True)
    p_search.add_argument("--topics", nargs="*", default=[])
    p_search.add_argument("--requirements", nargs="*", default=[],
                           help="keywords used for the cheap relevance proxy score")
    p_search.add_argument("--min-stars", type=int, default=50)
    p_search.add_argument("--stale-months", type=int, default=12)
    p_search.add_argument("--allow-copyleft", action="store_true")
    p_search.add_argument("--limit", type=int, default=30)
    p_search.set_defaults(func=cmd_search)

    p_enrich = sub.add_parser("enrich", help="README + structure enrichment for shortlisted repos")
    p_enrich.add_argument("--repos", nargs="+", required=True, help="owner/repo full names")
    p_enrich.set_defaults(func=cmd_enrich)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
