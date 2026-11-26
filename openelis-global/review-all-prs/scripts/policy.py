"""Decision rules for review-all-prs.

Pure functions over plain dicts: no network and no files. prs.py feeds them
GitHub facts and the ledger, and tests/test_policy.py pins every rule.

Categories:  low-risk | regular | major
Buckets:     A merged, B approved awaiting manual merge, C awaiting changes,
             D fixed and waiting for CI (next run), E closed, F excluded,
             G blocked, N not processed in this run
"""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime

BUCKETS = {
    "A": "Successfully merged",
    "B": "Approved, awaiting your manual merge",
    "C": "Awaiting further changes",
    "D": "Fixed and waiting for CI (re-evaluated on the next run)",
    "E": "Closed as outdated or superseded",
    "F": "Excluded",
    "G": "Not merged because of blockers",
    "N": "Not processed in this run",
}

CATEGORY_RANK = {"low-risk": 0, "regular": 1, "major": 2}
OK_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}


# ---------------------------------------------------------------- basics

def norm_login(login: str | None) -> str:
    s = (login or "").strip().lower()
    if s.startswith("app/"):
        s = s[4:]
    if s.endswith("[bot]"):
        s = s[:-5]
    return s


def is_bot(author: dict | None, cfg: dict) -> bool:
    author = author or {}
    if author.get("__typename") == "Bot":
        return True
    login = norm_login(author.get("login"))
    bots = cfg["bots"]["dependency"] + cfg["bots"]["automation"]
    return (author.get("login") or "").lower().endswith("[bot]") or login in {norm_login(b) for b in bots}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def match_any(path: str, globs: list[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatchcase(path, g):
            return True
        if g.startswith("**/") and fnmatch.fnmatchcase(path, g[3:]):
            return True
    return False


def exclusion_reason(author: dict, cfg: dict) -> str | None:
    """Excluded authors are matched on the PR author (the opener), by login or display name."""
    login = norm_login(author.get("login"))
    name = (author.get("name") or "").strip().casefold()
    if login and login == norm_login(cfg["self_login"]):
        return "your own PR (resolve-issue owns it)"
    for member in cfg["excluded_authors"]:
        names = {n.strip().casefold() for n in member.get("names", [])}
        if login == norm_login(member["login"]) or (name and name in names):
            return f"core team ({member['login']})"
    return None


# ---------------------------------------------------- dependency updates

_DETAILS = re.compile(r"<details>.*?</details>", re.S | re.I)
_UPDATES_LINE = re.compile(
    r"^Updates (?:the requirements on )?`([^`]+)`(?: from `?([^\s`]+?)`?)? to `?([^\s`]+?)`?\.?\s*$", re.M
)
_TABLE_ROW = re.compile(
    r"^\|\s*(?:\[([^\]]+)\]\([^)]*\)|`?([^|`]+?)`?)\s*\|\s*`?([^|`]+?)`?\s*\|\s*`?([^|`]+?)`?\s*\|\s*$", re.M
)
_TITLE_SINGLE = re.compile(r"(?i)\bbump (?!the\b)(\S+) from (\S+) to (\S+)")
_TITLE_COUNT = re.compile(r"(?i)with (\d+) updates?")
_VERSION = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(.*)$")


def parse_updates(title: str, body: str) -> tuple[list[dict], int | None]:
    """Read (package, from, to) triples from a Dependabot or Renovate PR.

    Returns the updates and the count the PR announces (None when it does not
    say). Release notes inside <details> are ignored: they quote other bumps.
    """
    text = _DETAILS.sub("", body or "")
    found: dict[tuple, dict] = {}

    def add(pkg, frm, to):
        pkg = (pkg or "").strip()
        if not pkg:
            return
        to = (to or "").strip().rstrip(".")
        frm = (frm or "").strip() or None
        found.setdefault((pkg, frm, to), {"package": pkg, "from": frm, "to": to})

    for m in _UPDATES_LINE.finditer(text):
        add(m.group(1), m.group(2), m.group(3))
    for m in _TABLE_ROW.finditer(text):
        pkg = (m.group(1) or m.group(2) or "").strip()
        frm, to = m.group(3).strip(), m.group(4).strip()
        if pkg.lower() == "package" or set(frm) <= set("-: "):
            continue
        add(pkg, frm, to)
    single = _TITLE_SINGLE.search(title or "")
    if single:
        add(single.group(1), single.group(2), single.group(3))
    count = _TITLE_COUNT.search(title or "")
    expected = int(count.group(1)) if count else (1 if single else None)
    return list(found.values()), expected


def bump_kind(frm: str | None, to: str | None) -> str:
    """patch | minor | major | none | downgrade | unknown.

    A changed suffix (base image flavour, JDK in a tag, pre-release) is
    unknown, and a 0.x minor counts as major, because both can break.
    """
    if not frm or not to:
        return "unknown"
    a, b = _VERSION.match(frm.strip()), _VERSION.match(to.strip())
    if not a or not b or a.group(2) != b.group(2):
        return "unknown"
    x = [int(p) for p in a.group(1).split(".")]
    y = [int(p) for p in b.group(1).split(".")]
    width = max(len(x), len(y))
    x += [0] * (width - len(x))
    y += [0] * (width - len(y))
    if x == y:
        return "none"
    if y < x:
        return "downgrade"
    if x[0] != y[0]:
        return "major"
    if x[0] == 0:
        return "major" if width > 1 and x[1] != y[1] else "patch"
    if x[1] != y[1]:
        return "minor"
    return "patch"


def is_patch_only(package: str, cfg: dict) -> bool:
    """Core frameworks and runtimes take patch bumps only; patterns are regexes on the package name."""
    p = package.lower()
    return any(re.search(rx, p) for rx in cfg["low_risk"]["patch_only_packages"])


# -------------------------------------------------------- classification

def classify(pr: dict, cfg: dict, recorded_updates: list[dict] | None = None) -> dict:
    """Suggest low-risk, regular or major, with the reasons.

    Low-risk is mechanical: every rule must pass. When any fails, the PR is
    major if it shows a major signal, otherwise regular.
    """
    lr = cfg["low_risk"]
    files = [f["path"] for f in pr.get("files", [])]
    lines = (pr.get("additions") or 0) + (pr.get("deletions") or 0)
    nfiles = pr.get("changedFiles") or len(files)
    title = pr.get("title") or ""
    dep_bot = norm_login(pr["author"].get("login")) in {norm_login(b) for b in cfg["bots"]["dependency"]}
    blockers: list[str] = []
    updates: list[dict] = []
    expected = None
    kind = None

    if nfiles > len(files):
        blockers.append(f"only {len(files)} of {nfiles} changed files could be listed")
    never = [p for p in files if match_any(p, lr["never_globs"])]
    if never:
        more = f" and {len(never) - 1} more" if len(never) > 1 else ""
        blockers.append(f"touches {never[0]}{more}")
    manifest_only = bool(files) and all(match_any(p, lr["dependency_globs"]) for p in files)

    if dep_bot or recorded_updates:
        kind = "dependency"
        if recorded_updates and not dep_bot:
            updates = [dict(u) for u in recorded_updates]
            expected = len({u["package"] for u in updates})
        else:
            updates, expected = parse_updates(title, pr.get("body") or "")
        names = {u["package"] for u in updates}
        if not manifest_only:
            blockers.append("changes files other than manifests, lockfiles, workflow pins or image tags")
        if not updates:
            blockers.append("could not read the version changes from the PR")
        elif expected and len(names) < expected:
            blockers.append(f"read {len(names)} of the {expected} announced updates")
        n = max(expected or 0, len(names))
        if n > lr["max_grouped_updates"]:
            blockers.append(f"{n} updates in one PR (low-risk limit {lr['max_grouped_updates']})")
        for u in updates:
            u["bump"] = bump_kind(u["from"], u["to"])
            if u["bump"] in ("major", "unknown", "downgrade"):
                blockers.append(f"{u['package']} {u['from']} -> {u['to']} is a {u['bump']} change")
            elif u["bump"] == "minor" and is_patch_only(u["package"], cfg):
                blockers.append(f"{u['package']} {u['from']} -> {u['to']} is a minor bump of a core framework or runtime")
    else:
        docs = bool(files) and all(match_any(p, lr["docs_globs"]) for p in files)
        config = bool(files) and all(match_any(p, lr["docs_globs"] + lr["simple_config_globs"]) for p in files)
        if docs:
            kind = "docs"
            if pr.get("repo") in lr["docs_not_maintenance_repos"] or re.search(
                lr["docs_not_maintenance_title_regex"], title
            ):
                blockers.append("documentation with design or specification content, not maintenance")
            if lines > lr["docs_max_changed_lines"]:
                blockers.append(f"{lines} changed lines of documentation (limit {lr['docs_max_changed_lines']})")
        elif config:
            kind = "config"
            if lines > lr["config_max_changed_lines"]:
                blockers.append(f"{lines} changed lines of configuration (limit {lr['config_max_changed_lines']})")
        else:
            blockers.append("not a dependency, documentation or simple configuration change")
        if nfiles > lr["max_changed_files"]:
            blockers.append(f"{nfiles} files (limit {lr['max_changed_files']})")

    signals = major_signals(pr, cfg, files, lines, nfiles, title, kind, updates, expected)
    if not blockers:
        category = "low-risk"
    elif signals:
        category = "major"
    else:
        category = "regular"
    return {
        "category": category,
        "kind": kind or ("feature" if re.search(cfg["major"]["feature_title_regex"], title) else "change"),
        "low_risk_blockers": blockers,
        "major_signals": signals,
        "updates": updates,
        "lines": lines,
        "files": nfiles,
    }


def major_signals(pr, cfg, files, lines, nfiles, title, kind, updates, expected) -> list[str]:
    mj = cfg["major"]
    s: list[str] = []
    if kind == "dependency":
        for u in updates:
            if u.get("bump") in ("major", "unknown") and is_patch_only(u["package"], cfg):
                s.append(f"{u['bump']} upgrade of {u['package']} ({u['from']} -> {u['to']})")
        n = max(expected or 0, len({u["package"] for u in updates}))
        if n >= mj["large_dependency_group"]:
            s.append(f"{n} dependency updates in one PR")
        return s
    if lines >= mj["min_changed_lines"]:
        s.append(f"{lines} changed lines")
    if nfiles >= mj["min_changed_files"]:
        s.append(f"{nfiles} changed files")
    schema = [p for p in files if match_any(p, mj["schema_globs"])]
    if schema:
        s.append(f"schema change ({schema[0]})")
    sensitive = [p for p in files if match_any(p, mj["sensitive_globs"])]
    if sensitive:
        s.append(f"security or deployment surface ({sensitive[0]})")
    if re.search(mj["architecture_title_regex"], title):
        s.append("title names an architectural change")
    if re.search(mj["feature_title_regex"], title) and lines >= mj["feature_min_changed_lines"]:
        s.append(f"feature of {lines} lines")
    frontend = any(p.startswith("frontend/") for p in files)
    backend = any(p.startswith("src/main/") for p in files)
    if frontend and backend and lines >= mj["cross_stack_min_changed_lines"]:
        s.append("cross-stack change (frontend and backend)")
    return s


def apply_override(computed: str, override: str | None, why: str | None) -> tuple[str, str | None]:
    """A recorded category may raise the computed one freely. It may lower
    major to regular only with a reason, and nothing becomes low-risk by hand."""
    if not override or override == computed:
        return computed, None
    if override == "low-risk":
        return computed, "refused: low-risk is decided by the rules, not by hand"
    if CATEGORY_RANK[override] > CATEGORY_RANK[computed]:
        return override, None
    if computed == "major" and override == "regular" and why:
        return "regular", None
    return computed, f"refused: lowering {computed} to {override} needs a reason (only major -> regular)"


# ------------------------------------------------------------- approvals

def _base_merge_regex(base: str) -> re.Pattern:
    b = re.escape(base)
    return re.compile(rf"^Merge (?:remote-tracking )?branch '(?:[\w.-]+/)?{b}'", re.I)


def commit_delta(pr: dict, approved_sha: str, own_fix_shas: set[str]) -> str:
    """What landed after an approval: none | base-merges | own-fixes | author-changes | rewritten."""
    if approved_sha == pr["headRefOid"]:
        return "none"
    commits = pr.get("commits") or []
    oids = [c["oid"] for c in commits]
    if approved_sha not in oids:
        return "rewritten"
    base_merge = _base_merge_regex(pr.get("baseRefName") or "develop")
    kinds = set()
    for c in commits[oids.index(approved_sha) + 1:]:
        if c["oid"] in own_fix_shas:
            kinds.add("own")
        elif (c.get("parents") or 1) > 1 and base_merge.search(c.get("headline") or ""):
            kinds.add("base")
        else:
            kinds.add("author")
    if "author" in kinds:
        return "author-changes"
    if "own" in kinds:
        return "own-fixes"
    return "base-merges"


def approval_analysis(
    pr: dict,
    cfg: dict,
    run_started: datetime,
    own_fix_shas: set[str] | None = None,
    delta_assessment: str | None = None,
) -> dict:
    """Does a previous approval let this regular PR merge?

    It counts when the reviewer's latest decisive review is APPROVED, the
    reviewer is a person with write access who is not the author, it was
    submitted before this run started, and what landed after it is nothing,
    base merges, our own recorded fixes, or author changes reviewed as minor.
    """
    own_fix_shas = own_fix_shas or set()
    author = norm_login(pr["author"].get("login"))
    me = norm_login(cfg["self_login"])
    latest: dict[str, dict] = {}
    for r in sorted(pr.get("reviews") or [], key=lambda r: r.get("submittedAt") or ""):
        who = norm_login((r.get("author") or {}).get("login"))
        if not who or who == author:
            continue
        if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[who] = r
    perms = pr.get("reviewer_permissions") or {}
    allowed = set(cfg["authorized_reviewer_permissions"])
    qualifying = [
        r
        for who, r in latest.items()
        if r["state"] == "APPROVED"
        and not is_bot(r.get("author"), cfg)
        and perms.get(who) in allowed
        and r.get("submittedAt")
        and parse_time(r["submittedAt"]) < run_started
    ]
    result = {
        "approved_by": sorted(norm_login(r["author"]["login"]) for r in qualifying),
        "changes_requested_by": sorted(w for w, r in latest.items() if r["state"] == "CHANGES_REQUESTED" and w != me),
        "own_changes_requested": latest.get(me, {}).get("state") == "CHANGES_REQUESTED",
        "approved_sha": None,
        "delta": "no-approval",
        "counts": False,
    }
    if not qualifying:
        return result
    newest = max(qualifying, key=lambda r: r["submittedAt"])
    sha = (newest.get("commit") or {}).get("oid") or ""
    delta = commit_delta(pr, sha, own_fix_shas)
    result["approved_sha"] = sha
    result["delta"] = delta
    result["counts"] = delta in ("none", "base-merges", "own-fixes") or (
        delta in ("author-changes", "rewritten") and delta_assessment == "minor"
    )
    return result


def self_approved_head(pr: dict, cfg: dict) -> bool:
    me = norm_login(cfg["self_login"])
    return any(
        norm_login((r.get("author") or {}).get("login")) == me
        and r.get("state") == "APPROVED"
        and (r.get("commit") or {}).get("oid") == pr["headRefOid"]
        for r in pr.get("reviews") or []
    )


def waiting_on_author(pr: dict, cfg: dict) -> str | None:
    """A person's latest decisive review asks for changes and nothing was pushed since."""
    author = norm_login(pr["author"].get("login"))
    latest: dict[str, dict] = {}
    for r in sorted(pr.get("reviews") or [], key=lambda r: r.get("submittedAt") or ""):
        who = norm_login((r.get("author") or {}).get("login"))
        if who and who != author and r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[who] = r
    requests = [r for r in latest.values() if r["state"] == "CHANGES_REQUESTED"]
    if not requests:
        return None
    newest = max(requests, key=lambda r: r["submittedAt"])
    pushed_after = [c for c in pr.get("commits") or [] if (c.get("date") or "") > newest["submittedAt"]]
    if pushed_after:
        return None
    who = norm_login(newest["author"]["login"])
    return f"{who} requested changes on {newest['submittedAt'][:10]}; nothing pushed since"


# -------------------------------------------------------------------- CI

def ci_state(contexts: list[dict], required_names: list[str] | set[str], now: datetime | None = None) -> dict:
    """contexts: normalised [{name, status, conclusion, required, at}].

    green | pending | failing | none. Every check that reported on the head
    must pass, required or not (user, 2026-11-23: "all PRs must pass
    validation CI checks"), and a required check that has not reported yet
    counts as pending. SUCCESS, NEUTRAL and SKIPPED pass.
    """
    by: dict[str, list[dict]] = {}
    for c in contexts:
        by.setdefault(c["name"], []).append(c)

    def one(name: str) -> str:
        runs = by.get(name, [])
        if not runs:
            return "missing"
        if any(r["status"] != "COMPLETED" for r in runs):
            return "pending"
        newest = max(runs, key=lambda r: r.get("at") or "")
        return "ok" if newest.get("conclusion") in OK_CONCLUSIONS else "failing"

    required = set(required_names) | {c["name"] for c in contexts if c.get("required")}
    detail = {n: one(n) for n in sorted(required)}
    others = {n: one(n) for n in sorted(by) if n not in required}
    considered = {**detail, **others}
    if not considered:
        state = "none"
    elif any(v == "failing" for v in considered.values()):
        state = "failing"
    elif any(v in ("pending", "missing") for v in considered.values()):
        state = "pending"
    else:
        state = "green"
    age_days = None
    if state == "green" and now is not None:
        stamps = [r.get("at") for n in considered for r in by.get(n, []) if r.get("at")]
        if stamps:
            age_days = (now - parse_time(max(stamps))).days
    return {
        "state": state,
        "required": detail,
        "other_failing": sorted(n for n, v in others.items() if v == "failing"),
        "other_pending": sorted(n for n, v in others.items() if v == "pending"),
        "age_days": age_days,
    }


# ------------------------------------------------------------ merge gate

def merge_gate(live: dict, ctx: dict, cfg: dict) -> list[dict]:
    """Every condition for a merge, from fresh GitHub data. Empty list = merge allowed.

    live: state, isDraft, baseRefName, defaultBranch, headRefOid, mergeable,
          mergeStateStatus, reviewDecision, unresolved_threads, ci (ci_state)
    ctx:  excluded, ledger_merged, category, review, reviewed_sha, approval
          (approval_analysis), fixed_this_run, open_issues, rules
          {required_approvals, thread_resolution}, threads_nonblocking
    Each blocker is {code, text}; code is one of policy, review, ci, admin,
    protection. Only protection blockers (required approvals, code owners,
    a BLOCKED or BEHIND merge state) can be bypassed, and only for low-risk
    maintenance (split_bypass).
    """
    b: list[dict] = []

    def add(code, text):
        b.append({"code": code, "text": text})

    if ctx.get("excluded"):
        add("policy", f"excluded: {ctx['excluded']}")
    if ctx.get("ledger_merged"):
        add("policy", "the ledger already records a merge of this PR")
    if live.get("state") != "OPEN":
        add("admin", f"PR is {str(live.get('state')).lower()}")
    if live.get("isDraft"):
        add("admin", "draft")
    if live.get("baseRefName") != live.get("defaultBranch"):
        add("admin", f"targets {live.get('baseRefName')}, not {live.get('defaultBranch')}")

    if not ctx.get("reviewed_sha"):
        add("review", "no review of the current head is recorded")
    elif ctx["reviewed_sha"] != live.get("headRefOid"):
        add("review", "the head moved after the review: review the new commits first")
    if ctx.get("review") != "clean":
        add("review", f"the review result is '{ctx.get('review')}', not clean")
    if ctx.get("open_issues"):
        add("review", f"{ctx['open_issues']} recorded issue(s) still open")

    if live.get("mergeable") == "CONFLICTING":
        add("admin", "merge conflicts")
    elif live.get("mergeable") != "MERGEABLE":
        add("admin", "GitHub has not computed mergeability yet; check again")
    mss = live.get("mergeStateStatus")
    if mss in ("BLOCKED", "BEHIND"):
        add("protection", f"GitHub merge state is {mss}")
    elif mss in ("DIRTY", "DRAFT", "UNKNOWN"):
        add("admin", f"GitHub merge state is {mss}")

    ci = live.get("ci") or {"state": "none"}
    if ci["state"] != "green":
        bad = [f"{k}: {v}" for k, v in (ci.get("required") or {}).items() if v != "ok"]
        bad += [f"{k}: failing" for k in ci.get("other_failing") or []]
        bad += [f"{k}: pending" for k in ci.get("other_pending") or []]
        add("ci", f"checks {ci['state']}" + (f" ({', '.join(bad)})" if bad else ""))
    elif ci.get("age_days") is not None and ci["age_days"] > cfg["ci_max_age_days"]:
        add("ci", f"CI last ran {ci['age_days']} days ago: update the branch and let it run again")

    rules = ctx.get("rules") or {}
    approval = ctx.get("approval") or {}
    if rules.get("required_approvals") and live.get("reviewDecision") != "APPROVED":
        add("protection", f"required approval missing (review decision {live.get('reviewDecision')})")
    if approval.get("changes_requested_by"):
        add("admin", "changes requested by " + ", ".join(approval["changes_requested_by"]))
    if approval.get("own_changes_requested"):
        add("review", "your own earlier request for changes still stands")
    threads = live.get("unresolved_threads") or 0
    if threads and (rules.get("thread_resolution") or not ctx.get("threads_nonblocking")):
        add("admin", f"{threads} unresolved review thread(s)")

    category = ctx.get("category")
    if category == "major":
        add("policy", "major change: left open for your manual merge")
    elif category == "regular" and not approval.get("counts"):
        add("policy", "no qualifying approval from before this run")
    elif category == "low-risk" and ctx.get("fixed_this_run"):
        add("policy", "fixed in this run: the merge waits for the next run")
    elif category not in CATEGORY_RANK:
        add("policy", f"unknown category {category!r}")
    return b


def approved_merge_blockers(live: dict, ci: dict, cfg: dict) -> list[str]:
    """Why an open PR may not merge on the user's "merge all the approved PRs".

    User, 2026-11-26: "merge all the PRs approved, don't rebase, just ensure
    all are merged as long as their CI is green, merge each one at a time
    without rebasing the next". Your own latest decisive review must be an
    approval of the current head; every check green and fresh; no other
    standing change request; no unresolved thread; GitHub reports the PR
    CLEAN. No bypass of any kind: an empty list means a plain squash merge.
    """
    out: list[str] = []
    excluded = exclusion_reason(live["author"], cfg)
    if excluded:
        out.append(f"excluded: {excluded}")
    if live.get("state") != "OPEN":
        out.append(f"PR is {str(live.get('state')).lower()}")
    if live.get("isDraft"):
        out.append("draft")
    if live.get("baseRefName") != live.get("defaultBranch"):
        out.append(f"targets {live.get('baseRefName')}, not {live.get('defaultBranch')}")
    me = norm_login(cfg["self_login"])
    author = norm_login(live["author"].get("login"))
    latest: dict[str, dict] = {}
    for r in sorted(live.get("reviews") or [], key=lambda r: r.get("submittedAt") or ""):
        who = norm_login((r.get("author") or {}).get("login"))
        if who and who != author and r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[who] = r
    mine = latest.get(me)
    if not mine or mine["state"] != "APPROVED":
        out.append("no standing approval of yours")
    elif (mine.get("commit") or {}).get("oid") != live.get("headRefOid"):
        out.append("head moved after your approval: review the new commits first")
    others = sorted(w for w, r in latest.items() if r["state"] == "CHANGES_REQUESTED" and w != me)
    if others:
        out.append("changes requested by " + ", ".join(others))
    if live.get("unresolved_threads"):
        out.append(f"{live['unresolved_threads']} unresolved review thread(s)")
    if live.get("mergeable") != "MERGEABLE":
        out.append(f"mergeable is {live.get('mergeable')}")
    if live.get("mergeStateStatus") not in ("CLEAN", "HAS_HOOKS"):
        out.append(f"GitHub merge state is {live.get('mergeStateStatus')}")
    if ci["state"] != "green":
        bad = [f"{k}: {v}" for k, v in (ci.get("required") or {}).items() if v != "ok"]
        bad += [f"{k}: failing" for k in ci.get("other_failing") or []]
        bad += [f"{k}: pending" for k in ci.get("other_pending") or []]
        out.append(f"checks {ci['state']}" + (f" ({', '.join(bad)})" if bad else ""))
    elif ci.get("age_days") is not None and ci["age_days"] > cfg["ci_max_age_days"]:
        out.append(f"CI last ran {ci['age_days']} days ago")
    return out


def split_bypass(blockers: list[dict], category: str, cfg: dict) -> tuple[list[dict], list[dict]]:
    """(hard, bypassed). Low-risk maintenance may merge past branch-protection
    rules when low_risk.bypass_protection is on (user decision, 2026-11-23).
    CI, conflicts, change requests, open threads and every policy and review
    blocker stay hard for every category."""
    if category == "low-risk" and cfg["low_risk"].get("bypass_protection"):
        return [x for x in blockers if x["code"] != "protection"], [x for x in blockers if x["code"] == "protection"]
    return list(blockers), []


# --------------------------------------------------------------- decide

def decide(f: dict) -> dict:
    """Map one PR's facts to a report bucket and the actions to take now.

    f: excluded, closed, merged, draft, category, review (clean | fixed |
       changes | waiting-on-author | not-reviewed), ci (green | pending |
       failing | none), approval_counts, fixed_this_run, prior_fixes,
       open_issues, self_approved_head, admin_blockers [text]
    actions: approve, request-changes, merge, wait-ci (in order)
    """

    def out(bucket, actions, why, **extra):
        return {"bucket": bucket, "actions": actions, "why": why, **extra}

    if f.get("excluded"):
        return out("F", [], f"excluded: {f['excluded']}")
    if f.get("merged"):
        return out("A", [], "merged")
    if f.get("closed"):
        return out("E", [], "closed")
    if f.get("draft"):
        return out("G", [], "draft: the author has not marked it ready")
    review = f.get("review") or "not-reviewed"
    if review == "not-reviewed":
        return out("N", [], "not reviewed in this run; the next run continues from the ledger")
    if review == "waiting-on-author":
        return out("C", [], "waiting on the author: the requested changes have not been pushed")
    if review == "changes":
        return out("C", ["request-changes"], "the review found issues the author must address")

    category = f.get("category")
    ci = f.get("ci") or "none"
    admin = f.get("admin_blockers") or []
    approve = [] if f.get("self_approved_head") else ["approve"]

    if f.get("open_issues") and review == "clean":
        return out("C", [], f"{f['open_issues']} recorded issue(s) are still open; the review cannot be clean")

    if category == "low-risk":
        if f.get("fixed_this_run") or review == "fixed":
            return out("D", [], "fixes pushed in this run; CI re-runs and the merge is decided on the next run")
        if ci == "failing":
            return out("G", [], "required checks failing")
        if ci in ("pending", "none"):
            why = "required checks still running" if ci == "pending" else "no CI ran on the head, so it cannot be verified"
            return out("G", ["wait-ci"] if ci == "pending" else [], why)
        if admin:
            return out("G", approve, "; ".join(admin))
        kind = "after-fix" if f.get("prior_fixes") else "first-run"
        why = f"low-risk maintenance, {kind} merge"
        if f.get("bypass"):
            why += "; bypassing branch protection: " + "; ".join(f["bypass"])
        return out("A", approve + ["merge"], why, merge_kind=kind, bypass=list(f.get("bypass") or []))

    if category == "regular":
        if review == "fixed":
            return out("G", ["wait-ci"], "minor fixes pushed in this run: re-check after CI, then merge if the prior approval still counts")
        if ci == "failing":
            return out("G", [], "required checks failing")
        if ci in ("pending", "none"):
            return out("G", ["wait-ci"] if ci == "pending" else [], "required checks still running" if ci == "pending" else "no CI ran on the head")
        if not f.get("approval_counts"):
            return out("G", approve, "no qualifying approval from before this run: approved now, mergeable on the next run if the head is unchanged")
        if admin:
            return out("G", approve, "; ".join(admin))
        return out("A", approve + ["merge"], "previously approved, review clean, checks green", merge_kind="approved-regular")

    if category == "major":
        if review == "fixed":
            return out("G", ["wait-ci"], "minor fixes pushed in this run: approve once CI is green")
        if ci == "failing":
            return out("G", [], "required checks failing")
        if ci in ("pending", "none"):
            return out("G", ["wait-ci"] if ci == "pending" else [], "required checks still running" if ci == "pending" else "no CI ran on the head")
        hard = [a for a in admin if "conflict" in a or "targets" in a]
        if hard:
            return out("G", [], "; ".join(hard))
        return out("B", approve, "major change approved; your manual merge decides")

    return out("G", [], f"unknown category {category!r}")
