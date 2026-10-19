#!/usr/bin/env python3
"""Liquibase upgrade verdict for the prepare-for-next-release skill.

Inputs
  --old-root DIR   directory holding liquibase/ as shipped in the previous release's webapp image
  --new-root DIR   directory holding liquibase/ as shipped in the development webapp image
  --before TSV     DATABASECHANGELOG export taken before the development application started
  --after  TSV     DATABASECHANGELOG export taken after it finished starting
  --lock   TSV     DATABASECHANGELOGLOCK export (id, locked, lockgranted, lockedby)
  --log    FILE    the application's docker log for the upgrade boot (optional, scanned for errors)
  --contexts CSV   runtime contexts (what LiquibaseConfig passes, 'default' unless overridden)
  --upgrade-started 'YYYY-MM-DD HH:MM:SS'  database time when the development app was started

Output: a JSON file and a Markdown file; the exit code is 0 for YES (the upgrade
applied every expected changeset and nothing failed), 2 for NO, 3 for INCONCLUSIVE.

The expected set is computed from the actual changelog tree inside each image
(base-changelog.xml and its includes), filtered by context and dbms the way
Liquibase evaluates them. Nothing in this script writes to the database.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.liquibase.org/xml/ns/dbchangelog}"
ENTRY = "liquibase/base-changelog.xml"


def local(tag):
    return tag.split("}")[-1]


def context_matches(expr, runtime):
    """Minimal Liquibase context expression evaluation: ',' and 'or' = OR, 'and' = AND, '!' = NOT."""
    if not expr:
        return True
    runtime = {c.strip().lower() for c in runtime if c.strip()}
    expr = expr.strip().lower()
    if not expr:
        return True
    for or_term in re.split(r",|\s+or\s+", expr):
        ok = True
        for and_term in re.split(r"\s+and\s+", or_term.strip()):
            t = and_term.strip().strip("()")
            if not t:
                continue
            if t.startswith("!"):
                ok = ok and (t[1:] not in runtime)
            else:
                ok = ok and (t in runtime)
        if ok:
            return True
    return False


def dbms_matches(expr, dbms="postgresql"):
    if not expr:
        return True
    parts = [p.strip().lower() for p in expr.split(",")]
    negs = [p[1:] for p in parts if p.startswith("!")]
    poss = [p for p in parts if not p.startswith("!")]
    if dbms in negs:
        return False
    return (not poss) or (dbms in poss) or ("all" in poss)


def load_tree(root_dir):
    """Walk base-changelog.xml and its includes; return the changesets in changelog order."""
    out = []
    problems = []
    visited = set()

    def walk(rel, inherited_ctx):
        rel = rel.lstrip("/")
        if rel.startswith("classpath:"):
            rel = rel[len("classpath:"):]
        if rel in visited:
            return
        visited.add(rel)
        path = os.path.join(root_dir, rel)
        if not os.path.exists(path):
            problems.append(f"included file missing: {rel}")
            return
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as e:
            problems.append(f"parse error in {rel}: {e}")
            return
        logical = root.get("logicalFilePath")
        for el in root:
            t = local(el.tag)
            if t == "include":
                f = el.get("file", "")
                if el.get("relativeToChangelogFile", "false") == "true":
                    f = os.path.normpath(os.path.join(os.path.dirname(rel), f))
                walk(f, el.get("context") or el.get("contextFilter") or inherited_ctx)
            elif t == "includeAll":
                p = el.get("path", "").rstrip("/")
                d = os.path.join(root_dir, p)
                if os.path.isdir(d):
                    for fn in sorted(os.listdir(d)):
                        if fn.endswith(".xml"):
                            walk(f"{p}/{fn}", el.get("context") or el.get("contextFilter") or inherited_ctx)
                else:
                    problems.append(f"includeAll path missing: {p}")
            elif t == "changeSet":
                pre = el.find(NS + "preConditions")
                out.append({
                    "id": el.get("id"), "author": el.get("author"),
                    "file": logical or rel, "physical": rel,
                    "context": el.get("context") or el.get("contextFilter") or inherited_ctx,
                    "dbms": el.get("dbms"),
                    "runAlways": el.get("runAlways") == "true",
                    "runOnChange": el.get("runOnChange") == "true",
                    "failOnError": el.get("failOnError"),
                    "onFail": pre.get("onFail") if pre is not None else None,
                })
    walk(ENTRY, None)
    return out, problems


def norm_file(f):
    f = (f or "").strip()
    if f.startswith("classpath:"):
        f = f[len("classpath:"):]
    return f.lstrip("/")


def key(cs):
    return (cs["id"], cs["author"], norm_file(cs["file"]))


def key_base(cs):
    return (cs["id"], cs["author"], os.path.basename(norm_file(cs["file"])))


def read_rows(tsv):
    rows = []
    if not tsv or not os.path.exists(tsv):
        return rows
    for line in open(tsv, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if not line:
            continue
        p = line.split("\t")
        while len(p) < 10:
            p.append("")
        rows.append({"id": p[0], "author": p[1], "file": p[2], "md5sum": p[3], "exectype": p[4],
                     "orderexecuted": int(p[5]) if p[5].isdigit() else None, "dateexecuted": p[6],
                     "contexts": p[7], "labels": p[8], "deployment_id": p[9]})
    return rows


def scan_log(path):
    if not path or not os.path.exists(path):
        return {"available": False}
    pats = {
        "migration_failed": r"MigrationFailedException",
        "validation_failed": r"ValidationFailedException|Validation Failed|checksum (was|changed|mismatch|validation)|is now: [0-9]:",
        "liquibase_exception": r"liquibase\.exception\.",
        "lock_exception": r"LockException|Waiting for changelog lock",
        "bean_failure": r"Error creating bean with name 'liquibase'",
        "context_failed": r"startup failed",
        "sql_errors": r"ERROR: |PSQLException|SQLException",
        "ran_successfully": r"ran successfully|ChangeSet .* ran",
        "update_done": r"Update command completed successfully|Update has been successful|Successfully released change log lock",
        "server_started": r"Server startup in",
    }
    counts = {k: 0 for k in pats}
    samples = {k: [] for k in pats}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            for k, p in pats.items():
                if re.search(p, ln):
                    counts[k] += 1
                    if len(samples[k]) < 5:
                        samples[k].append(ln.strip()[:300])
    return {"available": True, "counts": counts, "samples": samples}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-root", required=True)
    ap.add_argument("--new-root", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--lock")
    ap.add_argument("--log")
    ap.add_argument("--contexts", default="default")
    ap.add_argument("--upgrade-started", default="")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    a = ap.parse_args()
    runtime = a.contexts.split(",")

    old_cs, old_problems = load_tree(a.old_root)
    new_cs, new_problems = load_tree(a.new_root)

    def expected(cs_list):
        return [c for c in cs_list if context_matches(c["context"], runtime) and dbms_matches(c["dbms"])]

    old_exp, new_exp = expected(old_cs), expected(new_cs)
    old_keys = {key(c) for c in old_exp}
    new_keys = {key(c) for c in new_exp}
    new_only = [c for c in new_exp if key(c) not in old_keys]
    removed = [c for c in old_exp if key(c) not in new_keys]

    before, after = read_rows(a.before), read_rows(a.after)
    b_keys = {key(r): r for r in before}
    b_keys_base = {key_base(r): r for r in before}
    a_keys = {key(r): r for r in after}
    a_keys_base = {key_base(r): r for r in after}

    # Rows that are new in the after export. Both exports come from the same database, so the
    # full (id, author, filename) key is exact here.
    applied = [r for r in after if key(r) not in b_keys]
    applied_base = {key_base(r): r for r in applied}
    # Rows whose exectype says Liquibase re-ran them (runAlways / runOnChange).
    reran = [r for r in after if r["exectype"] in ("RERAN",)]
    # Rows that were in before but changed checksum (would fail validation unless runOnChange).
    checksum_changed = [(b_keys[k]["md5sum"], a_keys[k]["md5sum"], k) for k in b_keys if k in a_keys and b_keys[k]["md5sum"] != a_keys[k]["md5sum"] and b_keys[k]["md5sum"] and a_keys[k]["md5sum"]]
    lost = [k for k in b_keys if k not in a_keys]

    def find_row(c):
        # A tree changeset matches a database row by its full recorded path; the basename
        # fallback (logicalFilePath and classpath prefix differences) is allowed only against
        # rows that are new since the pre-upgrade export, so an old row can never satisfy a
        # new changeset.
        return a_keys.get(key(c)) or applied_base.get(key_base(c))

    missing = [c for c in new_only if find_row(c) is None and not c["runAlways"]]
    applied_expected = [c for c in new_only if find_row(c) is not None]
    exp_keys_full = {key(c) for c in new_only} | {key_base(c) for c in new_only}
    unexpected = [r for r in applied if key(r) not in exp_keys_full and key_base(r) not in exp_keys_full]
    # Changesets of the previous release the old database never had (pre-existing gaps; informational).
    pre_existing_gaps = [c for c in old_exp if key(c) not in b_keys and key_base(c) not in b_keys_base and not c["runAlways"]]

    exectypes = {}
    for r in applied:
        exectypes[r["exectype"]] = exectypes.get(r["exectype"], 0) + 1
    bad_exectype = [r for r in applied if r["exectype"] not in ("EXECUTED", "MARK_RAN", "RERAN")]

    orders = [r["orderexecuted"] for r in applied if r["orderexecuted"] is not None]
    order_ok = orders == sorted(orders) and (not orders or orders == list(range(orders[0], orders[0] + len(orders))))
    after_start = [r for r in applied if a.upgrade_started and r["dateexecuted"] and r["dateexecuted"] < a.upgrade_started]

    lock_rows = read_rows(a.lock) if a.lock else []
    lock_held = None
    if a.lock and os.path.exists(a.lock):
        raw = [ln.rstrip("\n").split("\t") for ln in open(a.lock) if ln.strip()]
        lock_held = any(len(p) > 1 and p[1].lower() in ("t", "true") for p in raw)

    log = scan_log(a.log)
    log_errors = 0
    if log.get("available"):
        c = log["counts"]
        log_errors = c["migration_failed"] + c["validation_failed"] + c["bean_failure"] + c["context_failed"]

    # Verdict
    reasons = []
    verdict = "YES"
    if missing:
        verdict = "NO"; reasons.append(f"{len(missing)} expected changesets were not recorded in DATABASECHANGELOG")
    if bad_exectype:
        verdict = "NO"; reasons.append(f"{len(bad_exectype)} applied rows have an unexpected EXECTYPE")
    if lost:
        verdict = "NO"; reasons.append(f"{len(lost)} rows present before the upgrade are gone afterwards")
    if log_errors:
        verdict = "NO"; reasons.append("the application log shows a migration, validation or context failure")
    if lock_held:
        verdict = "NO" if verdict == "NO" else "INCONCLUSIVE"; reasons.append("DATABASECHANGELOGLOCK is still held")
    if verdict == "YES":
        if not after:
            verdict = "INCONCLUSIVE"; reasons.append("no DATABASECHANGELOG rows after the upgrade")
        elif new_only and not applied_expected:
            verdict = "INCONCLUSIVE"; reasons.append("the new image carries new changesets but none were recorded (did the application start against this database?)")
        elif not log.get("available"):
            reasons.append("no application log was scanned (log evidence missing); DATABASECHANGELOG evidence alone supports YES")
        elif log["counts"]["server_started"] == 0:
            verdict = "INCONCLUSIVE"; reasons.append("the application log has no 'Server startup' line")
    if checksum_changed:
        reasons.append(f"{len(checksum_changed)} previously applied changesets have a different MD5SUM now (Liquibase re-validated them; check runOnChange or edited changesets)")
    if unexpected:
        reasons.append(f"{len(unexpected)} applied rows were not predicted from the changelog tree (logicalFilePath or context differences; listed below)")
    if not order_ok:
        reasons.append("ORDEREXECUTED of the applied rows is not a contiguous increasing range")
    if after_start:
        reasons.append(f"{len(after_start)} applied rows carry a DATEEXECUTED before the recorded upgrade start")
    if pre_existing_gaps:
        reasons.append(f"{len(pre_existing_gaps)} changesets of the previous release's tree were never in the old database (pre-existing, not caused by this upgrade)")

    result = {
        "verdict": verdict, "reasons": reasons, "contexts": runtime,
        "tree": {"old_total": len(old_cs), "old_expected": len(old_exp), "new_total": len(new_cs), "new_expected": len(new_exp),
                 "new_only": len(new_only), "removed_from_tree": len(removed), "old_problems": old_problems, "new_problems": new_problems},
        "database": {"rows_before": len(before), "rows_after": len(after), "applied_rows": len(applied), "exectypes": exectypes,
                     "applied_expected": len(applied_expected), "missing": [key(c) + (c["physical"], c["onFail"] or "") for c in missing],
                     "unexpected": [(r["id"], r["author"], r["file"], r["exectype"]) for r in unexpected],
                     "bad_exectype": [(r["id"], r["author"], r["file"], r["exectype"]) for r in bad_exectype],
                     "reran": [(r["id"], r["author"], r["file"]) for r in reran],
                     "checksum_changed": [list(k) + [b, a_] for (b, a_, k) in checksum_changed],
                     "lost_rows": [list(k) for k in lost], "order_contiguous": order_ok,
                     "dated_before_start": [(r["id"], r["author"], r["file"], r["dateexecuted"]) for r in after_start],
                     "pre_existing_gaps": [key(c) for c in pre_existing_gaps],
                     "last_row": after[-1] if after else None, "lock_held": lock_held},
        "log": log,
    }
    json.dump(result, open(a.out_json, "w"), indent=2, default=str)

    md = []
    md.append(f"# Liquibase upgrade verdict: {verdict}\n")
    md.append("Did the development version successfully upgrade the database created by the previous release? **%s**\n" % verdict)
    for r in reasons:
        md.append(f"- {r}")
    md.append("\n## Changelog trees (from the images)\n")
    md.append(f"- previous release: {len(old_cs)} changesets, {len(old_exp)} runnable in contexts {runtime}")
    md.append(f"- development: {len(new_cs)} changesets, {len(new_exp)} runnable; {len(new_only)} new relative to the previous release; {len(removed)} removed from the tree")
    for p in old_problems + new_problems:
        md.append(f"- tree problem: {p}")
    md.append("\n## DATABASECHANGELOG\n")
    md.append(f"- rows before: {len(before)}, after: {len(after)}, newly recorded: {len(applied)} (exectypes {exectypes})")
    md.append(f"- expected new changesets recorded: {len(applied_expected)} of {len(new_only)}; missing: {len(missing)}; unpredicted: {len(unexpected)}")
    md.append(f"- ORDEREXECUTED contiguous: {order_ok}; rows dated before the upgrade start: {len(after_start)}; rows lost: {len(lost)}")
    md.append(f"- checksum changes on previously applied rows: {len(checksum_changed)}; re-ran (runAlways/runOnChange): {len(reran)}")
    md.append(f"- DATABASECHANGELOGLOCK held at the end: {lock_held}")
    if after:
        lr = after[-1]
        md.append(f"- last row: {lr['file']}::{lr['id']}::{lr['author']} {lr['exectype']} at {lr['dateexecuted']}")
    if missing:
        md.append("\n### Missing (expected, not recorded)\n")
        for c in missing[:200]:
            md.append(f"- {c['physical']} :: {c['id']} :: {c['author']} (onFail={c['onFail'] or '-'}, context={c['context'] or '-'})")
    if bad_exectype:
        md.append("\n### Unexpected EXECTYPE\n")
        for r in bad_exectype:
            md.append(f"- {r['file']} :: {r['id']} :: {r['author']} -> {r['exectype']}")
    if unexpected:
        md.append("\n### Recorded but not predicted from the tree\n")
        for r in unexpected[:100]:
            md.append(f"- {r['file']} :: {r['id']} :: {r['author']} ({r['exectype']})")
    if checksum_changed:
        md.append("\n### Checksum changes\n")
        for (b, a_, k) in checksum_changed[:100]:
            md.append(f"- {k[2]} :: {k[0]} :: {k[1]}: {b} -> {a_}")
    if pre_existing_gaps:
        md.append("\n### Pre-existing gaps (previous release's tree vs the old database; informational)\n")
        for c in pre_existing_gaps[:50]:
            md.append(f"- {c['physical']} :: {c['id']} :: {c['author']} (context={c['context'] or '-'})")
    md.append("\n## Application log scan\n")
    if log.get("available"):
        for k, v in log["counts"].items():
            md.append(f"- {k}: {v}")
        for k in ("migration_failed", "validation_failed", "bean_failure", "context_failed", "lock_exception", "sql_errors"):
            for s in log["samples"].get(k, []):
                md.append(f"  - {k}: `{s}`")
    else:
        md.append("- no log file scanned")
    md.append("\n## Applied changesets (newly recorded rows, in execution order)\n")
    for r in applied[:400]:
        md.append(f"- {r['orderexecuted']}: {r['file']} :: {r['id']} :: {r['author']} {r['exectype']} {r['dateexecuted']}")
    open(a.out_md, "w").write("\n".join(md) + "\n")
    print("\n".join(md[:12]))
    return {"YES": 0, "NO": 2, "INCONCLUSIVE": 3}[verdict]


if __name__ == "__main__":
    sys.exit(main())
