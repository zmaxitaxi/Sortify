#!/usr/bin/env python3
"""Publish Sprint 2 GitHub issues to BoppingNoodles/Sortify using GitHub REST API.

Zero external dependencies required (uses standard library urllib).

Usage:
    # 1. Test parsing and view payloads without making network requests:
    python scripts/publish_sprint2_issues.py --dry-run

    # 2. Publish all issues using saved git credentials / env token:
    python scripts/publish_sprint2_issues.py

    # 3. Or pass token explicitly via command line:
    python scripts/publish_sprint2_issues.py --token ghp_...
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        # sys.stdout may not support reconfigure in non-standard environments
        pass

REPO_DEFAULT = "BoppingNoodles/Sortify"
ISSUES_DIR_DEFAULT = (
    Path(__file__).resolve().parent.parent / ".github" / "sprint-2-issues"
)

LABEL_COLORS = {
    "sprint-2": ("0e8a16", "Sprint 2 (Weeks 8-9) deliverable"),
    "frontend": ("1d76db", "Frontend mobile / React Native issues"),
    "backend": ("d93f0b", "Backend FastAPI and cloud services"),
    "ml": ("5319e7", "Machine learning and computer vision pipeline"),
    "feature": ("a2eeef", "New feature development"),
    "devops": ("006b75", "Infrastructure, Docker, and cloud deployment"),
    "resilience": ("fbca04", "Centralized exceptions and server stability"),
    "analysis": ("c2e0c6", "Threshold and data distribution analysis"),
    "performance": ("d4c5f9", "Model and API latency benchmarks"),
    "documentation": ("0075ca", "Improvements or additions to documentation"),
}


def get_git_credential_token() -> str | None:
    """Retrieves stored GitHub token via Git Credential Manager."""
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            capture_output=True,
            text=True,
            check=True,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("password="):
                token = line.split("=", 1)[1].strip()
                if token:
                    return token
    except (subprocess.SubprocessError, OSError):
        return None
    return None


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extracts simple YAML frontmatter and body from markdown content."""
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return {}, content

    raw_yaml, body = match.groups()
    metadata = {}
    for line in raw_yaml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            # Parse simple string quotes
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            # Parse simple inline JSON list e.g. ["sprint-2", "frontend"]
            elif val.startswith("[") and val.endswith("]"):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    val = [
                        item.strip().strip("'\"")
                        for item in val[1:-1].split(",")
                        if item.strip()
                    ]

            metadata[key] = val

    return metadata, body.strip()


def load_sprint2_issues(issues_dir: Path) -> list[dict]:
    """Discovers and parses all issue markdown files."""
    if not issues_dir.exists():
        raise FileNotFoundError(f"Issues directory does not exist: {issues_dir}")

    issue_files = sorted(issues_dir.glob("0*.md"))
    if not issue_files:
        raise FileNotFoundError(f"No issue template files found in {issues_dir}")

    parsed_issues = []
    for filepath in issue_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        meta, body = parse_frontmatter(content)
        title = meta.get("title")
        if not title:
            # Fallback to first H1 or H2 in body
            h_match = re.search(r"^#+\s+(.+)$", body, re.MULTILINE)
            title = h_match.group(1).strip() if h_match else filepath.stem

        labels = meta.get("labels", ["sprint-2"])
        if isinstance(labels, str):
            labels = [labels]

        parsed_issues.append(
            {
                "filename": filepath.name,
                "filepath": filepath,
                "title": title,
                "labels": labels,
                "body": body,
            }
        )

    return parsed_issues


def ensure_labels_and_milestone(repo: str, token: str) -> int | None:
    """Ensures necessary labels and Sprint 2 milestone exist on the repository."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Sortify-Sprint2-Setup",
        "Content-Type": "application/json",
    }

    # 1. Fetch existing labels
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/labels", headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            existing_labels = {
                item["name"] for item in json.loads(resp.read().decode())
            }
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        existing_labels = set()

    for name, (color, desc) in LABEL_COLORS.items():
        if name not in existing_labels:
            try:
                payload = json.dumps(
                    {"name": name, "color": color, "description": desc}
                ).encode("utf-8")
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/labels",
                    data=payload,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req):
                    print(f"  [+] Created repository label: '{name}'")
            except urllib.error.HTTPError as e:
                if e.code != 422:  # Already exists
                    print(f"  [!] Notice: could not create label {name}: {e}")

    # 2. Check / Create Milestone
    milestone_id = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/milestones", headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            milestones = json.loads(resp.read().decode())
            for m in milestones:
                if "Sprint 2" in m["title"]:
                    milestone_id = m["number"]
                    break

        if not milestone_id:
            payload = json.dumps(
                {
                    "title": "Sprint 2 (Weeks 8–9)",
                    "description": "Cloud Deployment, Streaks/Stats, and Confidence Threshold Calibration",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/milestones",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                m_data = json.loads(resp.read().decode())
                milestone_id = m_data.get("number")
                print(
                    f"  [+] Created Milestone: 'Sprint 2 (Weeks 8–9)' (ID #{milestone_id})"
                )
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  [!] Notice: Milestone lookup/creation skipped: {e}")

    return milestone_id


def create_github_issue(
    repo: str,
    token: str,
    title: str,
    body: str,
    labels: list[str],
    milestone: int | None,
) -> dict:
    """Dispatches a POST request to GitHub API to create an issue."""
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Sortify-Sprint2-Issue-Publisher",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": labels,
    }
    if milestone:
        payload["milestone"] = milestone

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="Publish Sprint 2 GitHub Issues for Sortify."
    )
    parser.add_argument(
        "--repo", default=REPO_DEFAULT, help="GitHub repository (owner/repo)"
    )
    parser.add_argument(
        "--token",
        help="GitHub Personal Access Token (PAT). Defaults to GITHUB_TOKEN or git credential.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print payloads without publishing.",
    )
    parser.add_argument(
        "--dir",
        default=str(ISSUES_DIR_DEFAULT),
        help="Directory containing issue markdown files.",
    )

    args = parser.parse_args()
    issues_dir = Path(args.dir)

    try:
        issues = load_sprint2_issues(issues_dir)
    except (FileNotFoundError, OSError) as e:
        print(f"[!] Error loading issue files: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Found {len(issues)} Sprint 2 issue definitions in {issues_dir}")

    if args.dry_run:
        print("\n--- [DRY RUN MODE] Simulating Issue Creation ---\n")
        for i, issue in enumerate(issues, start=1):
            print(f"[{i:02d}/{len(issues):02d}] {issue['filename']}")
            print(f"  Title:  {issue['title']}")
            print(f"  Labels: {', '.join(issue['labels'])}")
            print(f"  Body Preview ({len(issue['body'])} chars):")
            first_lines = "\n".join(
                f"    | {line}" for line in issue["body"].splitlines()[:6]
            )
            print(first_lines)
            print("    ...\n")
        print("[*] Dry run completed successfully. All 9 tickets parsed cleanly.")
        return

    token = (
        args.token
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or get_git_credential_token()
    )
    if not token:
        print(
            "\n[!] Error: No GitHub Personal Access Token or Git credentials found.\n"
            "    Provide via --token argument or set $env:GITHUB_TOKEN = 'ghp_...'\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[*] Authenticating with GitHub repository: https://github.com/{args.repo}")
    print("[*] Ensuring repository labels and milestone exist...")
    milestone_id = ensure_labels_and_milestone(args.repo, token)

    print(
        f"\n[*] Publishing {len(issues)} issues to https://github.com/{args.repo}...\n"
    )
    created_count = 0

    for i, issue in enumerate(issues, start=1):
        print(f"[{i:02d}/{len(issues):02d}] Publishing: {issue['title']}...")
        try:
            created = create_github_issue(
                repo=args.repo,
                token=token,
                title=issue["title"],
                body=issue["body"],
                labels=issue["labels"],
                milestone=milestone_id,
            )
            issue_num = created.get("number")
            html_url = created.get("html_url")
            print(f"  [OK] Created #{issue_num}: {html_url}\n")
            created_count += 1
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            print(
                f"  [FAIL] HTTP {e.code}: {e.reason}\n  Details: {err_msg}\n",
                file=sys.stderr,
            )
        except urllib.error.URLError as e:
            print(f"  [FAIL] Network connection error: {e.reason}\n", file=sys.stderr)

    print(f"[*] Finished: Successfully published {created_count}/{len(issues)} issues.")


if __name__ == "__main__":
    main()
