"""Give a fork PR a fresh CI run: update-branch when it can merge, then approve the new head's waiting runs.

Usage: python3 -I kick_ci.py <pr number> [<pr number> ...]
"""
import json
import subprocess
import sys
import time

REPO = "DIGI-UW/OpenELIS-Global-2"
PRS = "/Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills/openelis-global/review-all-prs/scripts/prs.py"


def sh(args):
    return subprocess.run(args, capture_output=True, text=True)


def head(n):
    return json.loads(sh(["gh", "pr", "view", n, "--repo", REPO, "--json", "headRefOid,mergeable"]).stdout)


for n in sys.argv[1:]:
    before = head(n)
    if before["mergeable"] == "CONFLICTING":
        print(f"#{n}: conflicts with develop, no CI kick")
        continue
    up = sh(["python3", "-I", PRS, "update-branch", f"{REPO}#{n}"])
    print(f"#{n}: {(up.stdout or up.stderr).strip()[:160]}")
    moved = "merged the base branch" in (up.stdout or "") or "rebase" in (up.stdout or "")
    end = time.time() + 300
    runs, h = [], before["headRefOid"]
    while time.time() < end:
        h = head(n)["headRefOid"]
        if moved and h == before["headRefOid"]:
            time.sleep(10)
            continue
        runs = json.loads(sh(["gh", "api", f"repos/{REPO}/actions/runs?head_sha={h}"]).stdout or "{}").get("workflow_runs", [])
        if sum(1 for r in runs if r["conclusion"] == "action_required") >= 3 or any(r["name"] == "01 - Backend" and r["status"] != "completed" for r in runs):
            break
        time.sleep(15)
    ap = sh(["python3", "-I", PRS, "approve-runs", f"{REPO}#{n}"])
    print(f"#{n}: head {h[:10]}; {ap.stdout.strip().replace(chr(10), '; ')[:300]}")
    runs = json.loads(sh(["gh", "api", f"repos/{REPO}/actions/runs?head_sha={h}"]).stdout or "{}").get("workflow_runs", [])
    missing = [w for w in ("01 - Backend", "02 - Frontend", "03 - E2E") if w not in {r["name"] for r in runs}]
    if missing:
        print(f"#{n}: GitHub created no {', '.join(missing)} run on {h[:10]}; kick again later "
              "(2026-11-26: four heads sat with a required checkpoint missing for a day)")
