#!/usr/bin/env python3
"""review-all-prs command line.

    python3 -I prs.py run-start [--new]
    python3 -I prs.py inventory
    python3 -I prs.py plan
    python3 -I prs.py show <key>
    python3 -I prs.py record <key> [--review clean|fixed|changes|waiting-on-author --sha SHA] [...]
    python3 -I prs.py decide <key>
    python3 -I prs.py review <key> --event approve|request-changes|comment --body-file F [--sha SHA]
    python3 -I prs.py merge <key>
    python3 -I prs.py close <key> --why TEXT --evidence URL [--evidence URL] --salvage TEXT --comment-file F
    python3 -I prs.py update-branch <key>
    python3 -I prs.py approve-runs <key>
    python3 -I prs.py wait-ci <key> [<key> ...] [--minutes N]
    python3 -I prs.py report
    python3 -I prs.py run-end

<key> is owner/repo#number, repo#number or a pull request URL.

GitHub is the source of truth. The ledger (state_home/ledger.json) remembers
what this skill did across runs; runs/<id>/run.json holds one run. merge and
close re-check everything from live GitHub data and refuse on any blocker.
merge passes --admin only for a low-risk PR whose remaining blockers are all
branch-protection rules (policy.split_bypass); it never passes --auto and
never edits protection settings.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import policy  # noqa: E402

CONFIG_PATH = HERE.parent / "config.json"
FORBIDDEN_MERGE_FLAGS = ("--auto",)
DASHES = (chr(0x2014), chr(0x2013))


# ------------------------------------------------------------------ util

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_config() -> dict:
    cfg = json.loads(CONFIG_PATH.read_text())
    home = os.environ.get("REVIEW_ALL_PRS_HOME")
    if home:
        cfg["state_home"] = home
    return cfg


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def die(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    sys.exit(code)


class GhError(RuntimeError):
    pass


def gh(args: list[str], check: bool = True, retries: int = 3) -> str | None:
    """Run gh. Reads retry on transient network errors; writes pass retries=1."""
    for attempt in range(retries):
        p = subprocess.run(["gh", *args], capture_output=True, text=True)
        if p.returncode == 0:
            return p.stdout
        transient = re.search(r"\b50[234]\b|timed? ?out|connection reset|EOF|TLS handshake", p.stderr, re.I)
        if transient and attempt < retries - 1:
            time.sleep(5 * (attempt + 1))
            continue
        if check:
            raise GhError(f"gh {' '.join(args[:3])}: {p.stderr.strip()[:400]}")
        return None
    return None


def graphql(query: str, **variables) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        if v is None:
            continue
        args += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
    data = json.loads(gh(args))
    if data.get("errors"):
        raise GhError(json.dumps(data["errors"])[:400])
    return data["data"]


def rest(path: str, method: str = "GET", fields: dict | None = None, check: bool = True):
    args = ["api", "-X", method, path]
    for k, v in (fields or {}).items():
        args += ["-f", f"{k}={v}"]
    out = gh(args, check=check, retries=3 if method == "GET" else 1)
    return json.loads(out) if out and out.strip() else None


def parse_key(raw: str, cfg: dict) -> tuple[str, int]:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", raw)
    if m:
        return m.group(1), int(m.group(2))
    m = re.match(r"^([\w.-]+/)?([\w.-]+)#(\d+)$", raw)
    if not m:
        die(f"cannot read PR key {raw!r}; use owner/repo#number")
    owner = m.group(1)[:-1] if m.group(1) else cfg["repos"][0].split("/")[0]
    return f"{owner}/{m.group(2)}", int(m.group(3))


def key_of(repo: str, number: int) -> str:
    return f"{repo}#{number}"


# ----------------------------------------------------------------- state

class State:
    def __init__(self, cfg: dict):
        self.home = Path(cfg["state_home"])
        self.ledger_path = self.home / "ledger.json"
        self.runs_dir = self.home / "runs"

    def ledger(self) -> dict:
        if self.ledger_path.exists():
            return json.loads(self.ledger_path.read_text())
        return {"version": 1, "prs": {}}

    def save_ledger(self, data: dict) -> None:
        write_json(self.ledger_path, data)

    def run_dirs(self) -> list[Path]:
        if not self.runs_dir.exists():
            return []
        return sorted(p for p in self.runs_dir.iterdir() if (p / "run.json").exists())

    def open_run(self) -> dict | None:
        for d in reversed(self.run_dirs()):
            run = json.loads((d / "run.json").read_text())
            if run.get("status") == "open":
                return run
        return None

    def require_run(self) -> dict:
        run = self.open_run()
        if not run:
            die("no open run: start one with `prs.py run-start`")
        return run

    def save_run(self, run: dict) -> None:
        write_json(self.runs_dir / run["id"] / "run.json", run)

    def inventory(self, run: dict) -> dict:
        p = self.runs_dir / run["id"] / "inventory.json"
        if not p.exists():
            die("no inventory for this run: run `prs.py inventory` first")
        return json.loads(p.read_text())


def entry_for(ledger: dict, key: str) -> dict:
    return ledger["prs"].setdefault(key, {"issues": [], "fixes": [], "reviews": [], "history": []})


def rec_for(run: dict, key: str) -> dict:
    return run["prs"].setdefault(key, {})


def history(entry: dict, run: dict, event: str) -> None:
    entry.setdefault("history", []).append({"run": run["id"], "at": iso(now_utc()), "event": event})


# ---------------------------------------------------------------- GitHub

PR_FIELDS = """
number title url body isDraft createdAt updatedAt state
author{__typename login ... on User{name}}
baseRefName headRefName headRefOid isCrossRepository maintainerCanModify
headRepository{nameWithOwner}
additions deletions changedFiles mergeable mergeStateStatus reviewDecision
labels(first:20){nodes{name}}
closingIssuesReferences(first:10){nodes{number state url}}
files(first:100){nodes{path additions deletions changeType}}
reviews(last:60){nodes{author{__typename login} state submittedAt commit{oid}}}
reviewThreads(first:100){nodes{isResolved isOutdated}}
comments(last:15){nodes{author{login} createdAt}}
commits(last:40){totalCount nodes{commit{oid committedDate messageHeadline parents{totalCount}}}}
headCommit: commits(last:1){nodes{commit{oid statusCheckRollup{state contexts(first:80){nodes{__typename
  ... on CheckRun{name status conclusion completedAt startedAt REQ}
  ... on StatusContext{context state createdAt REQ}}}}}}}
"""

LIST_QUERY = (
    "query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){"
    "nameWithOwner isArchived defaultBranchRef{name}"
    "pullRequests(states:OPEN,first:12,after:$cursor,orderBy:{field:CREATED_AT,direction:ASC}){"
    "pageInfo{hasNextPage endCursor} nodes{" + PR_FIELDS.replace("REQ", "") + "}}}}"
)

ONE_QUERY = (
    "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){"
    "defaultBranchRef{name} pullRequest(number:$number){"
    + PR_FIELDS.replace("REQ", "isRequired(pullRequestNumber:$number)")
    + " mergeCommit{oid}}}}"
)


def norm_contexts(nodes: list[dict]) -> list[dict]:
    out = []
    for n in nodes or []:
        if n.get("__typename") == "CheckRun":
            out.append({
                "name": n["name"], "status": n.get("status"), "conclusion": n.get("conclusion"),
                "at": n.get("completedAt") or n.get("startedAt"), "required": bool(n.get("isRequired")),
            })
        elif n.get("__typename") == "StatusContext":
            st = n.get("state")
            out.append({
                "name": n["context"],
                "status": "COMPLETED" if st in ("SUCCESS", "FAILURE", "ERROR") else "PENDING",
                "conclusion": "SUCCESS" if st == "SUCCESS" else ("FAILURE" if st in ("FAILURE", "ERROR") else None),
                "at": n.get("createdAt"), "required": bool(n.get("isRequired")),
            })
    return out


def norm_pr(node: dict, repo: str, default_branch: str) -> dict:
    head = (node.get("headCommit") or {}).get("nodes") or []
    rollup = (head[0]["commit"].get("statusCheckRollup") or {}) if head else {}
    commits = [
        {
            "oid": c["commit"]["oid"],
            "headline": c["commit"].get("messageHeadline"),
            "parents": (c["commit"].get("parents") or {}).get("totalCount", 1),
            "date": c["commit"].get("committedDate"),
        }
        for c in (node.get("commits") or {}).get("nodes") or []
    ]
    return {
        "key": key_of(repo, node["number"]),
        "repo": repo,
        "number": node["number"],
        "title": node["title"],
        "url": node["url"],
        "body": node.get("body") or "",
        "state": node.get("state", "OPEN"),
        "isDraft": node["isDraft"],
        "createdAt": node["createdAt"],
        "updatedAt": node["updatedAt"],
        "author": node.get("author") or {"login": "ghost"},
        "baseRefName": node["baseRefName"],
        "defaultBranch": default_branch,
        "headRefName": node["headRefName"],
        "headRefOid": node["headRefOid"],
        "isCrossRepository": node["isCrossRepository"],
        "maintainerCanModify": node["maintainerCanModify"],
        "headRepository": (node.get("headRepository") or {}).get("nameWithOwner"),
        "additions": node["additions"],
        "deletions": node["deletions"],
        "changedFiles": node["changedFiles"],
        "mergeable": node["mergeable"],
        "mergeStateStatus": node["mergeStateStatus"],
        "reviewDecision": node.get("reviewDecision"),
        "labels": [l["name"] for l in (node.get("labels") or {}).get("nodes") or []],
        "closing_issues": (node.get("closingIssuesReferences") or {}).get("nodes") or [],
        "files": (node.get("files") or {}).get("nodes") or [],
        "reviews": (node.get("reviews") or {}).get("nodes") or [],
        "unresolved_threads": sum(
            1 for t in (node.get("reviewThreads") or {}).get("nodes") or [] if not t.get("isResolved")
        ),
        "comments": (node.get("comments") or {}).get("nodes") or [],
        "commits": commits,
        "commit_count": (node.get("commits") or {}).get("totalCount", len(commits)),
        "contexts": norm_contexts((rollup.get("contexts") or {}).get("nodes")),
        "mergeCommit": (node.get("mergeCommit") or {}).get("oid"),
    }


def fetch_live(repo: str, number: int) -> dict:
    owner, name = repo.split("/")
    data = graphql(ONE_QUERY, owner=owner, name=name, number=number)
    r = data["repository"]
    if not r or not r.get("pullRequest"):
        die(f"{repo}#{number} not found")
    pr = norm_pr(r["pullRequest"], repo, r["defaultBranchRef"]["name"])
    pr["reviewer_permissions"] = reviewer_permissions(repo, pr["reviews"])
    return pr


_PERM_CACHE: dict[tuple, str] = {}


def reviewer_permissions(repo: str, reviews: list[dict]) -> dict:
    out = {}
    for r in reviews:
        login = (r.get("author") or {}).get("login")
        if not login or r.get("state") != "APPROVED" or (r.get("author") or {}).get("__typename") == "Bot":
            continue
        k = (repo, login)
        if k not in _PERM_CACHE:
            data = rest(f"repos/{repo}/collaborators/{login}/permission", check=False) or {}
            _PERM_CACHE[k] = data.get("role_name") or data.get("permission") or "none"
        out[policy.norm_login(login)] = _PERM_CACHE[k]
    return out


def branch_rules(repo: str, branch: str) -> dict:
    names: set[str] = set()
    approvals, threads = 0, False
    b = quote(branch, safe="")
    prot = rest(f"repos/{repo}/branches/{b}/protection", check=False)
    if prot and "url" in prot:
        rsc = prot.get("required_status_checks") or {}
        names |= set(rsc.get("contexts") or [])
        names |= {c["context"] for c in rsc.get("checks") or []}
        approvals = (prot.get("required_pull_request_reviews") or {}).get("required_approving_review_count") or 0
        threads = bool((prot.get("required_conversation_resolution") or {}).get("enabled"))
    rules = rest(f"repos/{repo}/rules/branches/{b}", check=False) or []
    for r in rules if isinstance(rules, list) else []:
        p = r.get("parameters") or {}
        if r.get("type") == "required_status_checks":
            names |= {c["context"] for c in p.get("required_status_checks") or []}
        elif r.get("type") == "pull_request":
            approvals = max(approvals, p.get("required_approving_review_count") or 0)
            threads = threads or bool(p.get("required_review_thread_resolution"))
    return {"required_checks": sorted(names), "required_approvals": approvals, "thread_resolution": threads}


def discover_repos(cfg: dict) -> list[str]:
    repos = list(cfg["repos"])
    d = cfg.get("discover") or {}
    if d.get("org"):
        cursor = None
        q = ("query($org:String!,$cursor:String){organization(login:$org){repositories(first:100,after:$cursor)"
             "{pageInfo{hasNextPage endCursor} nodes{nameWithOwner name isArchived}}}}")
        while True:
            data = graphql(q, org=d["org"], cursor=cursor)["organization"]["repositories"]
            for n in data["nodes"]:
                if not n["isArchived"] and re.search(d["name_regex"], n["name"]):
                    repos.append(n["nameWithOwner"])
            if not data["pageInfo"]["hasNextPage"]:
                break
            cursor = data["pageInfo"]["endCursor"]
    seen, out = set(), []
    for r in repos:
        if r.lower() in seen or (d.get("exclude_regex") and re.search(d["exclude_regex"], r)):
            continue
        seen.add(r.lower())
        out.append(r)
    return out


def merged_history(repo: str, limit: int) -> list[dict]:
    owner, name = repo.split("/")
    q = ("query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){"
         "pullRequests(states:MERGED,first:100,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}){"
         "pageInfo{hasNextPage endCursor} nodes{number title headRefName mergedAt url}}}}")
    out, cursor = [], None
    while len(out) < limit:
        data = graphql(q, owner=owner, name=name, cursor=cursor)["repository"]["pullRequests"]
        out += data["nodes"]
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return out[:limit]


# --------------------------------------------------------------- analysis

JIRA = re.compile(r"\bOGC-\d+\b", re.I)


def jira_keys(*texts: str) -> set[str]:
    return {k.upper() for t in texts for k in JIRA.findall(t or "")}


def obsolete_hints(pr: dict, inv: dict, cfg: dict) -> list[str]:
    hints = []
    closed = [i for i in pr["closing_issues"] if i.get("state") == "CLOSED"]
    if pr["closing_issues"] and len(closed) == len(pr["closing_issues"]):
        hints.append("every linked issue is closed: " + ", ".join(i["url"] for i in closed))
    created = pr["createdAt"]
    keys = jira_keys(pr["title"], pr["headRefName"])
    for m in inv["repos"][pr["repo"]].get("merged", []):
        if m["mergedAt"] and m["mergedAt"] > created and keys & jira_keys(m["title"], m["headRefName"]):
            hints.append(f"{', '.join(sorted(keys & jira_keys(m['title'], m['headRefName'])))} also landed in {m['url']} ({m['mergedAt'][:10]})")
    if policy.is_bot(pr["author"], cfg):
        stem = re.sub(r"\d+", "#", pr["title"]).strip()
        newer = [
            p for p in inv["prs"].values()
            if p["repo"] == pr["repo"] and p["number"] > pr["number"]
            and policy.norm_login(p["author"].get("login")) == policy.norm_login(pr["author"].get("login"))
            and re.sub(r"\d+", "#", p["title"]).strip() == stem
        ]
        if newer:
            hints.append(f"newer PR in the same automated series is open: #{max(p['number'] for p in newer)}")
    if pr["baseRefName"] != pr["defaultBranch"]:
        hints.append(f"targets {pr['baseRefName']}, not {pr['defaultBranch']}")
    age = (now_utc() - policy.parse_time(created)).days
    if age > cfg["obsolete"]["age_hint_days"] and pr["mergeable"] == "CONFLICTING":
        hints.append(f"{age} days old with conflicts (age alone is never a reason to close)")
    return hints


def recorded_updates(rec: dict, entry: dict):
    return rec.get("updates") or entry.get("updates")


def category_for(pr: dict, cfg: dict, rec: dict, entry: dict) -> tuple[str, dict, str | None]:
    cls = policy.classify(pr, cfg, recorded_updates(rec, entry))
    override = rec.get("category_override") or entry.get("category_override")
    why = rec.get("category_why") or entry.get("category_why")
    category, note = policy.apply_override(cls["category"], override, why)
    return category, cls, note


def current_review(rec: dict, entry: dict, live: dict) -> tuple[str, str | None, bool]:
    """(review, reviewed_sha, reused). A clean or changes result counts only for the head it saw."""
    review = rec.get("review")
    sha = rec.get("review_sha")
    if review == "fixed":
        return "fixed", sha, False
    if review == "waiting-on-author":
        return review, sha, False
    if review in ("clean", "changes"):
        return (review, sha, False) if sha == live["headRefOid"] else ("not-reviewed", sha, False)
    last = (entry.get("reviews") or [{}])[-1] if entry.get("reviews") else {}
    if last.get("sha") == live["headRefOid"] and last.get("result") == "clean":
        return "clean", last["sha"], True
    if last.get("sha") == live["headRefOid"] and last.get("result") == "changes":
        return "waiting-on-author", last["sha"], True
    return "not-reviewed", None, False


def facts_for(key: str, cfg: dict, run: dict, ledger: dict, live: dict, rules: dict) -> dict:
    entry = ledger["prs"].get(key) or {"issues": [], "fixes": [], "reviews": []}
    rec = run["prs"].get(key) or {}
    excluded = policy.exclusion_reason(live["author"], cfg)
    category, cls, note = category_for(live, cfg, rec, entry)
    fixes = entry.get("fixes") or []
    own_fix_shas = {f["sha"] for f in fixes}
    approval = policy.approval_analysis(live, cfg, policy.parse_time(run["started"]), own_fix_shas, rec.get("delta"))
    ci = policy.ci_state(live["contexts"], rules["required_checks"], now_utc())
    review, reviewed_sha, reused = current_review(rec, entry, live)
    fixed_this_run = any(f.get("run") == run["id"] for f in fixes)
    prior_fixes = any(f.get("run") != run["id"] for f in fixes)
    open_issues = sum(1 for i in entry.get("issues") or [] if i.get("status") == "open")
    self_approved = policy.self_approved_head(live, cfg)
    gate_live = dict(live, ci=ci)
    ctx = {
        "excluded": excluded,
        "ledger_merged": entry.get("state") == "merged",
        "category": category,
        "review": review,
        "reviewed_sha": reviewed_sha,
        "approval": approval,
        "fixed_this_run": fixed_this_run,
        "open_issues": open_issues,
        "rules": rules,
        "threads_nonblocking": rec.get("threads_nonblocking"),
    }
    gate = policy.merge_gate(gate_live, ctx, cfg)
    hard, bypassed = policy.split_bypass(gate, category, cfg)
    admin = [g["text"] for g in hard if g["code"] in ("admin", "protection") or g["text"].startswith("CI last ran")]
    if not self_approved:
        admin = [a for a in admin if not a.startswith("required approval missing")]
    decision = policy.decide({
        "excluded": excluded,
        "merged": live["state"] == "MERGED",
        "closed": live["state"] == "CLOSED",
        "draft": live["isDraft"],
        "category": category,
        "review": review,
        "ci": ci["state"],
        "approval_counts": approval["counts"],
        "fixed_this_run": fixed_this_run,
        "prior_fixes": prior_fixes,
        "open_issues": open_issues,
        "self_approved_head": self_approved,
        "admin_blockers": admin,
        "bypass": [g["text"] for g in bypassed],
    })
    return {
        "key": key, "category": category, "classification": cls, "override_note": note,
        "approval": approval, "ci": ci, "review": review, "reviewed_sha": reviewed_sha,
        "review_reused": reused, "fixed_this_run": fixed_this_run, "prior_fixes": prior_fixes,
        "open_issues": open_issues, "self_approved_head": self_approved, "gate": hard,
        "bypassed": bypassed, "decision": decision, "excluded": excluded, "head": live["headRefOid"],
    }


def rules_for(run_dir_inventory: dict | None, repo: str, branch: str) -> dict:
    if run_dir_inventory:
        cached = run_dir_inventory["repos"].get(repo, {}).get("rules", {}).get(branch)
        if cached:
            return cached
    return branch_rules(repo, branch)


# --------------------------------------------------------------- commands

def cmd_run_start(args, cfg, st):
    run = st.open_run()
    if run and not args.new:
        age = now_utc() - policy.parse_time(run["started"])
        if age < timedelta(hours=cfg["resume_window_hours"]):
            print(f"resuming run {run['id']} (started {run['started']}, {len(run['prs'])} PR records)")
            return
        run["status"] = "abandoned"
        st.save_run(run)
        print(f"run {run['id']} is older than {cfg['resume_window_hours']} h: marked abandoned")
    elif run:
        run["status"] = "abandoned"
        st.save_run(run)
    started = now_utc()
    run = {"id": started.strftime("%Y%m%d-%H%M%S"), "started": iso(started), "status": "open", "prs": {}}
    st.save_run(run)
    ledger = st.ledger()
    carried = [k for k, e in ledger["prs"].items() if e.get("state") == "waiting-ci-next-run"]
    print(f"new run {run['id']}")
    if carried:
        print("carried from earlier runs (fixed, waiting for CI): " + ", ".join(carried))


def cmd_inventory(args, cfg, st):
    run = st.require_run()
    repos = discover_repos(cfg)
    inv = {"fetched_at": iso(now_utc()), "repos": {}, "prs": {}}
    for repo in repos:
        owner, name = repo.split("/")
        cursor, nodes, meta = None, [], None
        while True:
            data = graphql(LIST_QUERY, owner=owner, name=name, cursor=cursor)["repository"]
            meta = data
            page = data["pullRequests"]
            nodes += page["nodes"]
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
        if meta["isArchived"]:
            continue
        default = meta["defaultBranchRef"]["name"]
        info = {"default_branch": default, "rules": {}, "merged": []}
        if nodes:
            info["merged"] = merged_history(repo, cfg["obsolete"]["merged_history"])
        for n in nodes:
            pr = norm_pr(n, repo, default)
            if pr["baseRefName"] not in info["rules"]:
                info["rules"][pr["baseRefName"]] = branch_rules(repo, pr["baseRefName"])
            if not policy.exclusion_reason(pr["author"], cfg):
                pr["reviewer_permissions"] = reviewer_permissions(repo, pr["reviews"])
            inv["prs"][pr["key"]] = pr
        inv["repos"][repo] = info
        print(f"{repo}: {len(nodes)} open")
    write_json(st.runs_dir / run["id"] / "inventory.json", inv)
    ledger = st.ledger()
    for key, e in ledger["prs"].items():
        if key not in inv["prs"] and e.get("state") not in ("merged", "closed", "gone"):
            repo, num = key.split("#")
            if repo in inv["repos"]:
                e["state"] = "gone"
                history(e, run, "no longer open on GitHub")
    st.save_ledger(ledger)
    print(f"inventory: {len(inv['prs'])} open PRs in {len(inv['repos'])} repositories")


STEP_ORDER = {
    "exclude": 0, "skip-draft": 1, "check-base": 2, "check-obsolete": 3, "gate": 4, "verify-fixes": 5,
    "waiting-on-author": 6, "low-risk-review": 7, "review-approved": 8, "re-review": 9,
    "review-major": 10, "review": 11,
}
DEEP_STEPS = {"review-approved", "re-review", "review-major", "review"}


def plan_step(pr, cfg, inv, run, ledger) -> dict:
    key = pr["key"]
    entry = ledger["prs"].get(key) or {}
    rec = run["prs"].get(key) or {}
    excluded = policy.exclusion_reason(pr["author"], cfg)
    category, cls, note = category_for(pr, cfg, rec, entry)
    rules = inv["repos"][pr["repo"]]["rules"][pr["baseRefName"]]
    ci = policy.ci_state(pr["contexts"], rules["required_checks"], now_utc())
    hints = [] if excluded else obsolete_hints(pr, inv, cfg)
    approval = policy.approval_analysis(
        pr, cfg, policy.parse_time(run["started"]), {f["sha"] for f in entry.get("fixes") or []}
    ) if not excluded else {"approved_by": [], "changes_requested_by": [], "counts": False, "delta": "-"}
    last = (entry.get("reviews") or [None])[-1] if entry.get("reviews") else None
    then = None
    if excluded:
        step = "exclude"
    elif pr["isDraft"]:
        step = "skip-draft"
    elif pr["baseRefName"] != pr["defaultBranch"]:
        step = "check-base"
    else:
        step = _work_step(pr, cfg, entry, last, category, approval)
        if hints:
            step, then = "check-obsolete", step
    return {
        "step": step, "then": then, "category": category, "kind": cls["kind"],
        "low_risk_blockers": cls["low_risk_blockers"],
        "major_signals": cls["major_signals"], "override_note": note, "ci": ci["state"],
        "approved_by": approval["approved_by"], "approval_delta": approval["delta"],
        "changes_requested_by": approval["changes_requested_by"], "excluded": excluded, "hints": hints,
        "waiting": policy.waiting_on_author(pr, cfg) if not excluded else None, "head": pr["headRefOid"],
    }


def _work_step(pr, cfg, entry, last, category, approval) -> str:
    if last and last.get("sha") == pr["headRefOid"] and last.get("result") == "clean":
        return "gate"
    if entry.get("fixes") and entry.get("state") != "merged":
        return "verify-fixes"
    if policy.waiting_on_author(pr, cfg):
        return "waiting-on-author"
    if category == "low-risk":
        return "low-risk-review"
    if category == "regular" and approval["approved_by"]:
        return "review-approved"
    if last:
        return "re-review"
    if category == "major":
        return "review-major"
    return "review"


def cmd_plan(args, cfg, st):
    run = st.require_run()
    inv = st.inventory(run)
    ledger = st.ledger()
    rows = []
    for key, pr in inv["prs"].items():
        p = plan_step(pr, cfg, inv, run, ledger)
        rec_for(run, key)["plan"] = p
        rows.append((STEP_ORDER[p["step"]], pr["createdAt"], key, pr, p))
    rows.sort(key=lambda r: (r[0], r[1]))
    deep = 0
    for _, _, key, pr, p in rows:
        if p["step"] in DEEP_STEPS:
            deep += 1
            p["in_budget"] = deep <= cfg["deep_review_budget"]
    st.save_run(run)
    counts: dict[str, int] = {}
    for *_, p in rows:
        counts[p["step"]] = counts.get(p["step"], 0) + 1
    print("steps: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: STEP_ORDER[kv[0]])))
    print(f"deep reviews this run: {min(deep, cfg['deep_review_budget'])} of {deep} (budget {cfg['deep_review_budget']})")
    for _, _, key, pr, p in rows:
        flag = "" if p.get("in_budget", True) else " [queued: budget]"
        who = pr["author"].get("login")
        then = f"(then {p['then']}) " if p.get("then") else ""
        extra = then + (p["excluded"] or "; ".join(p["hints"]) or p.get("waiting") or "") or (
            "approved by " + ",".join(p["approved_by"]) if p["approved_by"] else ""
        )
        print(f"{p['step']:<18} {key:<38} {who:<18} {p['category']:<8} ci={p['ci']:<7} {extra[:90]}{flag}")


def cmd_show(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    live = fetch_live(repo, number)
    inv = None
    try:
        inv = st.inventory(run)
    except SystemExit:
        pass
    rules = rules_for(inv, repo, live["baseRefName"])
    facts = facts_for(key, cfg, run, ledger, live, rules)
    out = {
        "key": key, "title": live["title"], "url": live["url"], "author": live["author"],
        "base": live["baseRefName"], "head": live["headRefOid"], "head_branch": live["headRefName"],
        "head_repo": live["headRepository"], "cross_repo": live["isCrossRepository"],
        "maintainer_can_modify": live["maintainerCanModify"], "draft": live["isDraft"],
        "size": f"+{live['additions']}/-{live['deletions']} in {live['changedFiles']} files",
        "files": [f["path"] for f in live["files"]],
        "reviews": [
            f"{r['submittedAt'][:16] if r.get('submittedAt') else '?'} {(r.get('author') or {}).get('login')} {r['state']} @{((r.get('commit') or {}).get('oid') or '')[:9]}"
            for r in live["reviews"] if r["state"] != "COMMENTED" or (r.get("author") or {}).get("login") == cfg["self_login"]
        ],
        "unresolved_threads": live["unresolved_threads"], "mergeable": live["mergeable"],
        "merge_state": live["mergeStateStatus"], "review_decision": live["reviewDecision"],
        "rules": rules, "facts": {k: v for k, v in facts.items() if k not in ("key",)},
        "ledger": ledger["prs"].get(key), "run_record": run["prs"].get(key),
    }
    print(json.dumps(out, indent=2, default=str))


def cmd_record(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    entry = entry_for(ledger, key)
    rec = rec_for(run, key)
    if args.review:
        if args.review != "waiting-on-author" and not args.sha:
            die("--review needs --sha (the head you reviewed)")
        rec["review"] = args.review
        rec["review_sha"] = args.sha
        entry["reviews"].append({"run": run["id"], "sha": args.sha, "result": args.review, "at": iso(now_utc())})
        history(entry, run, f"review {args.review} @{(args.sha or '')[:9]}")
    if args.category:
        rec["category_override"] = args.category
        rec["category_why"] = args.why
        entry["category_override"] = args.category
        entry["category_why"] = args.why
        history(entry, run, f"category {args.category}: {args.why}")
    if args.delta:
        rec["delta"] = args.delta
    for text in args.issue or []:
        iid = f"I{len(entry['issues']) + 1}"
        entry["issues"].append({"id": iid, "text": text, "status": "open", "run": run["id"]})
        print(f"recorded issue {iid}")
    for iid in args.issue_fixed or []:
        _set_issue(entry, iid, "fixed", run)
    for iid in args.issue_dropped or []:
        if not args.why:
            die("--issue-dropped needs --why")
        _set_issue(entry, iid, "dropped", run, args.why)
    if args.fix_sha:
        if not args.fix_summary:
            die("--fix-sha needs --fix-summary")
        entry["fixes"].append({"run": run["id"], "sha": args.fix_sha, "summary": args.fix_summary, "at": iso(now_utc())})
        rec.setdefault("fixes", []).append({"sha": args.fix_sha, "summary": args.fix_summary})
        history(entry, run, f"fix pushed @{args.fix_sha[:9]}: {args.fix_summary}")
    for field in ("summary", "findings", "tests", "remaining", "threads_nonblocking", "ci_note"):
        val = getattr(args, field)
        if val:
            rec[field] = val
    if args.updates:
        ups = []
        for part in args.updates.split(";"):
            pkg, frm, to = part.strip().rsplit(":", 2)
            ups.append({"package": pkg, "from": frm, "to": to})
        rec["updates"] = entry["updates"] = ups
    if args.posted:
        rec.setdefault("posted", []).append(args.posted)
    st.save_ledger(ledger)
    st.save_run(run)
    print(f"recorded {key}")


def _set_issue(entry, iid, status, run, why=None):
    for i in entry["issues"]:
        if i["id"] == iid:
            i["status"] = status
            i["closed_run"] = run["id"]
            if why:
                i["why"] = why
            history(entry, run, f"issue {iid} {status}")
            return
    die(f"no issue {iid}")


def _live_facts(key, cfg, st, run, ledger):
    repo, number = key.split("#")
    live = fetch_live(repo, int(number))
    inv = None
    p = st.runs_dir / run["id"] / "inventory.json"
    if p.exists():
        inv = json.loads(p.read_text())
    rules = rules_for(inv, repo, live["baseRefName"])
    return live, facts_for(key, cfg, run, ledger, live, rules)


def cmd_decide(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    live, facts = _live_facts(key, cfg, st, run, ledger)
    d = facts["decision"]
    rec = rec_for(run, key)
    rec.update({
        "bucket": d["bucket"], "actions": d["actions"], "why": d["why"], "merge_kind": d.get("merge_kind"),
        "category": facts["category"], "title": live["title"], "author": live["author"].get("login"),
        "url": live["url"], "ci": facts["ci"]["state"], "decided_at": iso(now_utc()),
        "blockers": [g["text"] for g in facts["gate"]],
    })
    st.save_run(run)
    print(json.dumps({
        "bucket": f"{d['bucket']} ({policy.BUCKETS[d['bucket']]})", "actions": d["actions"], "why": d["why"],
        "category": facts["category"], "review": facts["review"], "review_reused": facts["review_reused"],
        "ci": facts["ci"], "approval": facts["approval"], "merge_gate_blockers": rec["blockers"],
        "bypassed_for_low_risk": [g["text"] for g in facts["bypassed"]],
    }, indent=2))


def _refuse_excluded(live, cfg):
    reason = policy.exclusion_reason(live["author"], cfg)
    if reason:
        die(f"refused: {reason}; this skill takes no action on it")


def _check_body(path: str, live: dict, cfg: dict) -> str:
    body = Path(path).read_text()
    if any(d in body for d in DASHES):
        die("refused: the body contains an em or en dash; rewrite it")
    if policy.norm_login(live["author"].get("login")) != policy.norm_login(cfg["self_login"]) and re.search(
        r"\bclaude\b|generated (by|with)|co-authored-by", body, re.I
    ):
        die("refused: a review of someone else's PR carries no AI attribution")
    return body


def cmd_review(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    live = fetch_live(repo, number)
    _refuse_excluded(live, cfg)
    if args.sha and args.sha != live["headRefOid"]:
        die(f"refused: the head is now {live['headRefOid'][:9]}, not {args.sha[:9]}; review the new commits first")
    state = {"approve": "APPROVED", "request-changes": "CHANGES_REQUESTED", "comment": "COMMENTED"}[args.event]
    me = policy.norm_login(cfg["self_login"])
    dup = [
        r for r in live["reviews"]
        if policy.norm_login((r.get("author") or {}).get("login")) == me
        and r["state"] == state and (r.get("commit") or {}).get("oid") == live["headRefOid"]
    ]
    if dup:
        print(f"already posted: {args.event} on {live['headRefOid'][:9]}; nothing sent")
        return
    _check_body(args.body_file, live, cfg)
    gh(["pr", "review", str(number), "--repo", repo, f"--{args.event}", "--body-file", args.body_file], retries=1)
    entry = entry_for(ledger, key)
    entry.setdefault("posted", []).append({"run": run["id"], "event": args.event, "sha": live["headRefOid"], "at": iso(now_utc())})
    history(entry, run, f"posted {args.event} @{live['headRefOid'][:9]}")
    rec_for(run, key).setdefault("posted", []).append(args.event)
    st.save_ledger(ledger)
    st.save_run(run)
    print(f"posted {args.event} on {key} @{live['headRefOid'][:9]}")


def cmd_merge(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    live, facts = _live_facts(key, cfg, st, run, ledger)
    rec = rec_for(run, key)
    if live["state"] == "MERGED":
        print(f"{key} is already merged ({live['mergeCommit']}); nothing to do")
        return
    blockers = [g["text"] for g in facts["gate"]]
    if "merge" not in facts["decision"]["actions"]:
        blockers.append(f"the decision is {facts['decision']['bucket']}: {facts['decision']['why']}")
    if blockers:
        rec["blockers"] = blockers
        rec["bucket"] = facts["decision"]["bucket"] if facts["decision"]["bucket"] != "A" else "G"
        rec["why"] = "; ".join(blockers)
        st.save_run(run)
        die("merge refused:\n  - " + "\n  - ".join(dict.fromkeys(blockers)))
    cmd = ["pr", "merge", str(number), "--repo", repo, f"--{cfg['merge_method']}",
           "--match-head-commit", live["headRefOid"]]
    bypassed = [g["text"] for g in facts["bypassed"]]
    if bypassed:
        if facts["category"] != "low-risk" or not cfg["low_risk"].get("bypass_protection"):
            die("merge refused: a protection bypass is allowed for low-risk maintenance only")
        cmd.append("--admin")
        print("bypassing branch protection for low-risk maintenance: " + "; ".join(bypassed))
    assert not any(f in cmd for f in FORBIDDEN_MERGE_FLAGS)
    p = subprocess.run(["gh", *cmd], capture_output=True, text=True)
    merged = None
    for _ in range(10):
        state = fetch_live(repo, number)
        if state["state"] == "MERGED":
            merged = state
            break
        time.sleep(6)
    entry = entry_for(ledger, key)
    if not merged:
        msg = (p.stderr or p.stdout).strip()[:300]
        rec.update({"bucket": "G", "why": f"merge call did not land: {msg}", "blockers": [msg]})
        history(entry, run, f"merge attempt failed: {msg}")
        st.save_ledger(ledger)
        st.save_run(run)
        die(f"merge did not land: {msg}", 3)
    entry["state"] = "merged"
    entry["merged"] = {"run": run["id"], "sha": merged["mergeCommit"], "at": iso(now_utc()),
                       "kind": facts["decision"].get("merge_kind"), "bypassed": bypassed}
    history(entry, run, f"merged as {merged['mergeCommit']}" + (f" (bypassed: {'; '.join(bypassed)})" if bypassed else ""))
    rec.update({"bucket": "A", "merge_sha": merged["mergeCommit"], "merge_kind": facts["decision"].get("merge_kind"),
                "bypassed": bypassed,
                "why": facts["decision"]["why"], "ci": facts["ci"]["state"], "title": live["title"],
                "author": live["author"].get("login"), "url": live["url"], "category": facts["category"]})
    st.save_ledger(ledger)
    st.save_run(run)
    print(f"merged {key} as {merged['mergeCommit']} ({facts['decision'].get('merge_kind')})")


def _verify_evidence(url: str) -> str | None:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/(pull|issues|commit)/([0-9a-f]+|\d+)", url)
    if not m:
        return None
    repo, kind, ref = m.groups()
    if kind == "pull":
        data = rest(f"repos/{repo}/pulls/{ref}", check=False) or {}
        return "merged PR" if data.get("merged_at") else None
    if kind == "issues":
        data = rest(f"repos/{repo}/issues/{ref}", check=False) or {}
        return "closed issue" if data.get("state") == "closed" else None
    default = (rest(f"repos/{repo}", check=False) or {}).get("default_branch")
    cmp = rest(f"repos/{repo}/compare/{default}...{ref}", check=False) or {}
    return "commit on the default branch" if cmp.get("status") in ("behind", "identical") else None


def cmd_close(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    live = fetch_live(repo, number)
    _refuse_excluded(live, cfg)
    if live["state"] != "OPEN":
        print(f"{key} is already {live['state'].lower()}")
        return
    verified = [(u, _verify_evidence(u)) for u in args.evidence]
    good = [f"{u} ({kind})" for u, kind in verified if kind]
    if not good:
        die("close refused: no evidence verified (needs a merged PR, a closed issue or a commit on the default branch)")
    if not args.salvage:
        die("close refused: say what useful work is kept or why there is none (--salvage)")
    _check_body(args.comment_file, live, cfg)
    gh(["pr", "comment", str(number), "--repo", repo, "--body-file", args.comment_file], retries=1)
    gh(["pr", "close", str(number), "--repo", repo], retries=1)
    entry = entry_for(ledger, key)
    entry["state"] = "closed"
    entry["closed"] = {"run": run["id"], "why": args.why, "evidence": good, "salvage": args.salvage}
    history(entry, run, f"closed: {args.why}")
    rec_for(run, key).update({"bucket": "E", "why": args.why, "evidence": good, "salvage": args.salvage,
                              "title": live["title"], "author": live["author"].get("login"), "url": live["url"]})
    st.save_ledger(ledger)
    st.save_run(run)
    print(f"closed {key}; evidence: {', '.join(good)}")


def cmd_update_branch(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    key = key_of(repo, number)
    run = st.require_run()
    ledger = st.ledger()
    live = fetch_live(repo, number)
    _refuse_excluded(live, cfg)
    if policy.norm_login(live["author"].get("login")) == "dependabot":
        gh(["pr", "comment", str(number), "--repo", repo, "--body", "@dependabot rebase"], retries=1)
        how = "asked Dependabot to rebase"
    else:
        gh(["pr", "update-branch", str(number), "--repo", repo], retries=1)
        how = "merged the base branch in"
    entry = entry_for(ledger, key)
    history(entry, run, f"update-branch: {how}")
    rec_for(run, key)["branch_updated"] = how
    st.save_ledger(ledger)
    st.save_run(run)
    print(f"{key}: {how}; CI re-runs on the new head")


def cmd_approve_runs(args, cfg, st):
    repo, number = parse_key(args.key, cfg)
    live = fetch_live(repo, number)
    _refuse_excluded(live, cfg)
    runs = rest(f"repos/{repo}/actions/runs?head_sha={live['headRefOid']}&per_page=50") or {}
    waiting = [r for r in runs.get("workflow_runs", []) if r.get("conclusion") == "action_required" or r.get("status") == "action_required"]
    for r in waiting:
        rest(f"repos/{repo}/actions/runs/{r['id']}/approve", method="POST", check=False)
        print(f"approved workflow run {r['id']} ({r['name']})")
    if not waiting:
        started = [r for r in runs.get("workflow_runs", [])]
        print(f"no run waits for approval; {len(started)} run(s) exist for {live['headRefOid'][:9]}")


def cmd_wait_ci(args, cfg, st):
    run = st.require_run()
    keys = [key_of(*parse_key(k, cfg)) for k in args.keys]
    deadline = now_utc() + timedelta(minutes=args.minutes)
    last: dict[str, str] = {}
    inv = None
    p = st.runs_dir / run["id"] / "inventory.json"
    if p.exists():
        inv = json.loads(p.read_text())
    while True:
        states = {}
        for key in keys:
            repo, number = key.split("#")
            try:
                live = fetch_live(repo, int(number))
            except GhError as e:
                states[key] = last.get(key, "pending")
                print(f"{iso(now_utc())} {key}: fetch failed ({e}); retrying", flush=True)
                continue
            if live["state"] != "OPEN":
                states[key] = live["state"].lower()
                continue
            rules = rules_for(inv, repo, live["baseRefName"])
            ci = policy.ci_state(live["contexts"], rules["required_checks"], now_utc())
            states[key] = ci["state"]
            if last.get(key) != ci["state"]:
                print(f"{iso(now_utc())} {key} @{live['headRefOid'][:9]}: {ci['state']} {ci['required']}", flush=True)
        last.update(states)
        if all(s not in ("pending", "none") for s in states.values()):
            print("settled: " + ", ".join(f"{k}={v}" for k, v in states.items()))
            return
        if now_utc() > deadline:
            print("timed out: " + ", ".join(f"{k}={v}" for k, v in states.items()))
            sys.exit(4)
        time.sleep(60)


def cmd_report(args, cfg, st):
    run = st.require_run()
    inv = st.inventory(run)
    ledger = st.ledger()
    buckets: dict[str, list] = {b: [] for b in policy.BUCKETS}
    for key, pr in inv["prs"].items():
        rec = run["prs"].get(key) or {}
        plan = rec.get("plan") or {}
        bucket = rec.get("bucket")
        if not bucket:
            bucket = "F" if plan.get("excluded") else "N"
        buckets[bucket].append((key, pr, rec, ledger["prs"].get(key) or {}))
    inspected = len(inv["prs"])
    total = sum(len(v) for v in buckets.values())
    reviewed = sum(1 for r in run["prs"].values() if r.get("review") in ("clean", "fixed", "changes"))
    approved = sum(1 for r in run["prs"].values() if "approve" in (r.get("posted") or []))
    lines = [f"# PR sweep {run['id']}", ""]

    def item(key, pr, rec, entry, extra: list[str]):
        head = f"- [{key}]({pr['url']}) {pr['title']} (by {pr['author'].get('login')}, {rec.get('category') or (rec.get('plan') or {}).get('category', '?')})"
        body = [f"  - {x}" for x in extra if x]
        return [head] + body

    sec = {
        "A": lambda k, p, r, e: item(k, p, r, e, [
            r.get("summary"), f"why it qualified: {r.get('why')}",
            f"merge: {r.get('merge_kind')} ({'low-risk maintenance' if r.get('category') == 'low-risk' else 'previously approved regular PR'}), {(r.get('merge_sha') or '')[:9]}",
            "bypassed branch protection: " + "; ".join(r["bypassed"]) if r.get("bypassed") else None,
            "fixes: " + "; ".join(f["summary"] for f in e.get("fixes", [])) if e.get("fixes") else None,
            f"tests: {r.get('tests')}" if r.get("tests") else None, f"CI: {r.get('ci')}"]),
        "B": lambda k, p, r, e: item(k, p, r, e, [r.get("summary"), f"findings: {r.get('findings')}" if r.get("findings") else None,
                                                  f"tests: {r.get('tests')}" if r.get("tests") else None,
                                                  "why manual: " + ", ".join((r.get("plan") or {}).get("major_signals") or [r.get("why", "")])]),
        "C": lambda k, p, r, e: item(k, p, r, e, [r.get("why"), "issues: " + "; ".join(i["text"] for i in e.get("issues", []) if i["status"] == "open") if any(i["status"] == "open" for i in e.get("issues", [])) else None,
                                                  "my fixes: " + "; ".join(f["summary"] for f in r.get("fixes", [])) if r.get("fixes") else "my fixes: none",
                                                  f"remaining: {r.get('remaining')}" if r.get("remaining") else None]),
        "D": lambda k, p, r, e: item(k, p, r, e, ["issues: " + "; ".join(i["text"] for i in e.get("issues", []) if i.get("run") == run["id"]),
                                                  "fixes pushed: " + "; ".join(f"{f['summary']} ({f['sha'][:9]})" for f in r.get("fixes", [])),
                                                  f"CI at report time: {r.get('ci')}", "re-evaluated on the next run"]),
        "E": lambda k, p, r, e: item(k, p, r, e, [f"why: {r.get('why')}", "evidence: " + ", ".join(r.get("evidence", [])), f"salvage: {r.get('salvage')}"]),
        "F": lambda k, p, r, e: item(k, p, r, e, [(r.get("plan") or {}).get("excluded")]),
        "G": lambda k, p, r, e: item(k, p, r, e, [
            f"blocker: {r.get('why')}",
            "before it can merge: " + "; ".join(b for b in dict.fromkeys(r.get("blockers", [])) if b not in (r.get("why") or ""))
            if any(b not in (r.get("why") or "") for b in r.get("blockers", [])) else None,
            f"note: {r.get('remaining')}" if r.get("remaining") else None]),
        "N": lambda k, p, r, e: item(k, p, r, e, [f"next step: {(r.get('plan') or {}).get('step')}" + ("" if (r.get("plan") or {}).get("in_budget", True) else " (deep-review budget reached)")]),
    }
    for b, title in policy.BUCKETS.items():
        rows = buckets[b]
        lines += [f"## {b}. {title} ({len(rows)})", ""]
        if not rows:
            lines += ["None.", ""]
            continue
        for k, p, r, e in sorted(rows, key=lambda x: x[0]):
            lines += sec[b](k, p, r, e)
        lines.append("")
    lines += [
        "## H. Overall summary", "",
        f"- inspected: {inspected}",
        f"- excluded: {len(buckets['F'])}",
        f"- reviewed in this run: {reviewed}",
        f"- approvals posted: {approved}",
        f"- merged: {len(buckets['A'])}",
        f"- fixed and waiting for CI: {len(buckets['D'])}",
        f"- approved, awaiting manual merge: {len(buckets['B'])}",
        f"- requiring further changes: {len(buckets['C'])}",
        f"- closed: {len(buckets['E'])}",
        f"- blocked: {len(buckets['G'])}",
        f"- not processed in this run: {len(buckets['N'])}",
        f"- check: A+B+C+D+E+F+G+N = {total} {'=' if total == inspected else '!='} inspected {inspected}",
    ]
    text = "\n".join(lines) + "\n"
    out = st.home / "reports" / f"{run['id']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)
    print(f"written to {out}")
    if total != inspected:
        sys.exit(5)


def cmd_run_end(args, cfg, st):
    run = st.require_run()
    ledger = st.ledger()
    for key, rec in run["prs"].items():
        e = ledger["prs"].get(key)
        if e is None or e.get("state") in ("merged", "closed"):
            continue
        state = {"D": "waiting-ci-next-run", "B": "awaiting-manual-merge", "C": "awaiting-changes",
                 "G": "blocked", "F": "excluded", "N": "queued"}.get(rec.get("bucket"))
        if state:
            e["state"] = state
    run["status"] = "finished"
    run["finished"] = iso(now_utc())
    st.save_ledger(ledger)
    st.save_run(run)
    print(f"run {run['id']} finished")


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="prs.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run-start")
    s.add_argument("--new", action="store_true")
    sub.add_parser("inventory")
    sub.add_parser("plan")
    s = sub.add_parser("show")
    s.add_argument("key")
    s = sub.add_parser("record")
    s.add_argument("key")
    s.add_argument("--review", choices=["clean", "fixed", "changes", "waiting-on-author"])
    s.add_argument("--sha")
    s.add_argument("--category", choices=["low-risk", "regular", "major"])
    s.add_argument("--why")
    s.add_argument("--delta", choices=["minor", "substantial"])
    s.add_argument("--issue", action="append")
    s.add_argument("--issue-fixed", action="append")
    s.add_argument("--issue-dropped", action="append")
    s.add_argument("--fix-sha")
    s.add_argument("--fix-summary")
    s.add_argument("--summary")
    s.add_argument("--findings")
    s.add_argument("--tests")
    s.add_argument("--remaining")
    s.add_argument("--threads-nonblocking")
    s.add_argument("--ci-note")
    s.add_argument("--updates", help="pkg:from:to;pkg:from:to for a person's dependency PR")
    s.add_argument("--posted", choices=["approve", "request-changes", "comment"])
    s = sub.add_parser("decide")
    s.add_argument("key")
    s = sub.add_parser("review")
    s.add_argument("key")
    s.add_argument("--event", required=True, choices=["approve", "request-changes", "comment"])
    s.add_argument("--body-file", required=True)
    s.add_argument("--sha")
    s = sub.add_parser("merge")
    s.add_argument("key")
    s = sub.add_parser("close")
    s.add_argument("key")
    s.add_argument("--why", required=True)
    s.add_argument("--evidence", action="append", required=True)
    s.add_argument("--salvage", required=True)
    s.add_argument("--comment-file", required=True)
    s = sub.add_parser("update-branch")
    s.add_argument("key")
    s = sub.add_parser("approve-runs")
    s.add_argument("key")
    s = sub.add_parser("wait-ci")
    s.add_argument("keys", nargs="+")
    s.add_argument("--minutes", type=int)
    sub.add_parser("report")
    sub.add_parser("run-end")
    args = ap.parse_args(argv)
    cfg = load_config()
    if getattr(args, "minutes", None) is None and args.cmd == "wait-ci":
        args.minutes = cfg["ci_wait_minutes"]
    st = State(cfg)
    handler = globals()["cmd_" + args.cmd.replace("-", "_")]
    try:
        handler(args, cfg, st)
    except GhError as e:
        die(f"GitHub call failed: {e}", 6)


if __name__ == "__main__":
    main()
