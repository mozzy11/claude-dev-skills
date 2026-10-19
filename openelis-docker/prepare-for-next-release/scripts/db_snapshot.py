#!/usr/bin/env python3
"""Database manifest for the prepare-for-next-release skill.

  db_snapshot.py snapshot --psql "<psql command prefix>" --out manifest.json [--label before]
  db_snapshot.py compare before.json after.json --out diff.md

The snapshot records, for the clinlims schema: every table's exact row count,
the business records (patients, samples, sample items, analyses, results,
catalogue, menus, users, site information) keyed by stable identifiers, orphan
checks across the core foreign keys, and order-independent digests of the core
relational views. Columns are discovered from information_schema, so the same
script works on any version of the schema; a check whose table or column does
not exist is recorded as "not available" rather than failing.

compare prints every difference and exits 1 when a record went missing, a
relationship broke, or an orphan appeared. Legitimate migrations change
counts (new tables, new menu rows, backfilled columns): those differences are
listed so the operator can judge them against the changesets, and they do not
by themselves fail the comparison.
"""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys

SCHEMA = "clinlims"

# Entities: table, stable-key expression, preferred columns, optional join for the key.
ENTITIES = {
    "patients": {
        "table": "patient",
        "columns": ["id", "person_id", "national_id", "external_id", "birth_date", "gender", "entered_date", "chart_number", "fhir_uuid", "upid_code"],
        "join": "left join {s}.person pe on pe.id = t.person_id",
        "extra": {"first_name": "pe.first_name", "last_name": "pe.last_name"},
        "key": "coalesce(t.national_id, '') || '|' || coalesce(t.external_id, '') || '|' || coalesce(pe.last_name, '') || '|' || coalesce(pe.first_name, '') || '|' || t.id",
    },
    "patient_identities": {
        "table": "patient_identity",
        "columns": ["id", "patient_id", "identity_type_id", "identity_data"],
        "key": "t.patient_id || '|' || t.identity_type_id || '|' || coalesce(t.identity_data, '')",
    },
    "samples": {
        "table": "sample",
        "columns": ["id", "accession_number", "status_id", "entered_date", "received_date", "collection_date", "domain", "fhir_uuid", "is_confirmation", "order_progress_status", "clinical_order_id"],
        "join": "left join {s}.status_of_sample sos on sos.id = t.status_id left join {s}.sample_human sh on sh.samp_id = t.id left join {s}.patient pt on pt.id = sh.patient_id",
        "extra": {"status_name": "sos.name", "patient_id": "sh.patient_id", "patient_national_id": "pt.national_id"},
        "key": "t.accession_number",
    },
    "sample_items": {
        "table": "sample_item",
        "columns": ["id", "samp_id", "typeosamp_id", "sort_order", "external_id", "status_id", "collection_date", "fhir_uuid", "rejected"],
        "join": "left join {s}.sample s on s.id = t.samp_id left join {s}.type_of_sample tos on tos.id = t.typeosamp_id",
        "extra": {"accession_number": "s.accession_number", "sample_type": "tos.description"},
        "key": "s.accession_number || '|' || t.sort_order",
    },
    "analyses": {
        "table": "analysis",
        "columns": ["id", "sampitem_id", "test_id", "status_id", "started_date", "completed_date", "released_date", "revision", "analysis_type", "panel_id", "parent_analysis_id", "parent_result_id", "is_reportable", "referred_out", "corrected", "fhir_uuid", "result_calculated", "reflex_trigger"],
        "join": "left join {s}.sample_item si on si.id = t.sampitem_id left join {s}.sample s on s.id = si.samp_id left join {s}.test te on te.id = t.test_id left join {s}.status_of_sample sos on sos.id = t.status_id",
        "extra": {"accession_number": "s.accession_number", "test_name": "te.name", "test_description": "te.description", "status_name": "sos.name"},
        "key": "s.accession_number || '|' || coalesce(si.sort_order::text,'') || '|' || te.name || '|' || coalesce(t.revision::text,'0') || '|' || t.id",
    },
    "results": {
        "table": "result",
        "columns": ["id", "analysis_id", "test_result_id", "value", "result_type", "is_reportable", "min_normal", "max_normal", "analyte_id", "fhir_uuid"],
        "join": "left join {s}.analysis an on an.id = t.analysis_id left join {s}.sample_item si on si.id = an.sampitem_id left join {s}.sample s on s.id = si.samp_id left join {s}.test te on te.id = an.test_id",
        "extra": {"accession_number": "s.accession_number", "test_name": "te.name"},
        "key": "s.accession_number || '|' || te.name || '|' || t.id",
    },
    "notes": {
        "table": "note",
        "columns": ["id", "table_id", "reference_table_id", "subject", "text", "note_type"],
        "key": "t.id",
    },
    "referrals": {
        "table": "referral",
        "columns": ["id", "analysis_id", "status", "referral_type_id", "referral_reason_id", "organization_name"],
        "key": "t.id",
    },
    "tests": {
        "table": "test",
        "columns": ["id", "name", "description", "loinc", "is_active", "test_section_id", "uom_id", "orderable", "is_reportable", "guid"],
        "key": "t.name || '|' || coalesce(t.description,'') || '|' || t.id",
    },
    "panels": {
        "table": "panel",
        "columns": ["id", "name", "description", "is_active"],
        "key": "t.name",
    },
    "panel_items": {
        "table": "panel_item",
        "columns": ["id", "panel_id", "test_id"],
        "join": "left join {s}.panel p on p.id = t.panel_id left join {s}.test te on te.id = t.test_id",
        "extra": {"panel_name": "p.name", "test_name": "te.name"},
        "key": "p.name || '|' || te.name",
    },
    "test_reflexes": {
        "table": "test_reflex",
        "columns": ["id", "test_result_id", "test_id", "add_test_id", "flags", "relation", "sibling_reflex", "actionable"],
        "key": "t.id",
    },
    "calculations": {
        "table": "calculation",
        "columns": ["id", "name", "sample_id", "test_id", "result", "toggled", "active", "note", "component_id"],
        "key": "t.id",
    },
    "calculation_operations": {
        "table": "calculation_operation",
        "columns": ["id", "calculation_id", "type", "value", "order_"],
        "key": "t.id",
    },
    "reflex_rules": {
        "table": "reflex_rule",
        "columns": ["id", "name", "overall", "toggled", "active"],
        "key": "t.id",
    },
    "reflex_rule_conditions": {
        "table": "reflex_rule_condition",
        "columns": ["id", "reflex_rule_id", "sample_id", "test_id", "relation", "value"],
        "key": "t.id",
    },
    "reflex_rule_actions": {
        "table": "reflex_rule_action",
        "columns": ["id", "reflex_rule_id", "action", "reflex_result"],
        "key": "t.id",
    },
    "sample_types": {
        "table": "type_of_sample",
        "columns": ["id", "description", "domain", "is_active", "local_abbrev"],
        "key": "t.description || '|' || coalesce(t.domain,'')",
    },
    "result_limits": {
        "table": "result_limits",
        "columns": ["id", "test_id", "test_result_type_id", "min_age", "max_age", "gender", "low_normal", "high_normal", "low_valid", "high_valid"],
        "key": "t.id",
    },
    "menus": {
        "table": "menu",
        "columns": ["id", "parent_id", "element_id", "action_url", "display_key", "is_active", "presentation_order"],
        "key": "t.element_id",
    },
    "users": {
        "table": "system_user",
        "columns": ["id", "login_name", "first_name", "last_name", "is_active", "is_admin"],
        "key": "t.login_name",
    },
    "login_users": {
        "table": "login_user",
        "columns": ["id", "login_name", "is_admin", "account_locked", "account_disabled", "system_user_id"],
        "key": "t.login_name",
    },
    "roles": {
        "table": "system_role",
        "columns": ["id", "name", "description", "is_active", "grouping_role"],
        "key": "t.name",
    },
    "user_roles": {
        "table": "system_user_role",
        "columns": ["system_user_id", "role_id"],
        "key": "t.system_user_id || '|' || t.role_id",
    },
    "site_information": {
        "table": "site_information",
        "columns": ["id", "name", "value", "encrypted", "value_type", "tag"],
        "key": "t.name",
    },
    "organizations": {
        "table": "organization",
        "columns": ["id", "name", "short_name", "is_active", "org_type"],
        "key": "t.name || '|' || t.id",
    },
    "providers": {
        "table": "provider",
        "columns": ["id", "person_id", "external_id", "active"],
        "key": "t.id",
    },
    "external_connections": {
        "table": "external_connection",
        "columns": ["id", "uri", "active", "programmed_connection", "active_authentication_type"],
        "key": "t.id",
    },
    "dictionary": {
        "table": "dictionary",
        "columns": ["id", "dictionary_category_id", "dict_entry", "is_active", "local_abbrev"],
        "key": "t.dictionary_category_id || '|' || t.dict_entry",
    },
    "observation_history": {
        "table": "observation_history",
        "columns": ["id", "patient_id", "sample_id", "observation_history_type_id", "value", "value_type"],
        "key": "t.id",
    },
    "sample_qa_events": {
        "table": "sample_qaevent",
        "columns": ["id", "sample_id", "qa_event_id", "completed_date"],
        "key": "t.id",
    },
}

ORPHAN_CHECKS = [
    ("sample_human.samp_id -> sample", "sample_human", "samp_id", "sample", "id"),
    ("sample_human.patient_id -> patient", "sample_human", "patient_id", "patient", "id"),
    ("sample_item.samp_id -> sample", "sample_item", "samp_id", "sample", "id"),
    ("sample_item.typeosamp_id -> type_of_sample", "sample_item", "typeosamp_id", "type_of_sample", "id"),
    ("analysis.sampitem_id -> sample_item", "analysis", "sampitem_id", "sample_item", "id"),
    ("analysis.test_id -> test", "analysis", "test_id", "test", "id"),
    ("result.analysis_id -> analysis", "result", "analysis_id", "analysis", "id"),
    ("patient.person_id -> person", "patient", "person_id", "person", "id"),
    ("patient_identity.patient_id -> patient", "patient_identity", "patient_id", "patient", "id"),
    ("panel_item.panel_id -> panel", "panel_item", "panel_id", "panel", "id"),
    ("panel_item.test_id -> test", "panel_item", "test_id", "test", "id"),
    ("test_reflex.test_id -> test", "test_reflex", "test_id", "test", "id"),
    ("test_reflex.add_test_id -> test", "test_reflex", "add_test_id", "test", "id"),
    ("system_user_role.system_user_id -> system_user", "system_user_role", "system_user_id", "system_user", "id"),
    ("system_user_role.role_id -> system_role", "system_user_role", "role_id", "system_role", "id"),
    ("sample without sample_item", "sample", None, "sample_item", "samp_id"),
    ("sample_item without analysis", "sample_item", None, "analysis", "sampitem_id"),
]


class Db:
    def __init__(self, prefix):
        # The prefix is a psql command without a field separator; tab is added here
        # because a literal tab inside the prefix string would be split as whitespace.
        self.prefix = shlex.split(prefix) + ["-F", "\t"]

    def q(self, sql):
        p = subprocess.run(self.prefix + ["-c", sql], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.strip()[:400])
        return [ln.split("\t") for ln in p.stdout.split("\n") if ln != ""]

    def scalar(self, sql):
        r = self.q(sql)
        return r[0][0] if r and r[0] else None


def snapshot(db, label):
    m = {"label": label, "schema": SCHEMA, "taken_at": db.scalar("select to_char(now(),'YYYY-MM-DD HH24:MI:SS')"),
         "server_version": db.scalar("show server_version"), "tables": {}, "entities": {}, "orphans": {}, "digests": {}, "not_available": []}
    cols = {}
    for t, c in db.q(f"select table_name, column_name from information_schema.columns where table_schema='{SCHEMA}' order by 1, ordinal_position"):
        cols.setdefault(t, []).append(c)
    tables = sorted(r[0] for r in db.q(f"select table_name from information_schema.tables where table_schema='{SCHEMA}' and table_type='BASE TABLE'"))
    for t in tables:
        try:
            m["tables"][t] = int(db.scalar(f'select count(*) from {SCHEMA}."{t}"'))
        except RuntimeError as e:
            m["tables"][t] = f"error: {e}"
    for name, spec in ENTITIES.items():
        t = spec["table"]
        if t not in cols:
            m["not_available"].append(f"{name}: table {t} absent")
            continue
        present = [c for c in spec["columns"] if c in cols[t]]
        extra = spec.get("extra", {})
        join = spec.get("join", "").format(s=SCHEMA)
        sel = ", ".join([f"t.{c}" for c in present] + [f"{e} as {k}" for k, e in extra.items()])
        try:
            rows = db.q(f"select {spec['key']} as k, {sel} from {SCHEMA}.{t} t {join} order by 1")
        except RuntimeError as e:
            # A join column may not exist on this version; retry without the join and the extras.
            try:
                rows = db.q(f"select t.id::text as k, {', '.join('t.'+c for c in present)} from {SCHEMA}.{t} t order by 1")
                extra = {}
                m["not_available"].append(f"{name}: key/join fallback to id ({str(e)[:120]})")
            except RuntimeError as e2:
                m["not_available"].append(f"{name}: {str(e2)[:160]}")
                continue
        names = present + list(extra.keys())
        recs = {}
        for r in rows:
            k = r[0]
            rec = dict(zip(names, r[1:]))
            if k in recs:
                k = f"{k}#dup{len(recs)}"
            recs[k] = rec
        m["entities"][name] = {"count": len(recs), "columns": names, "records": recs if len(recs) <= 5000 else {}, "truncated": len(recs) > 5000}
        digest_src = "\n".join(f"{k}\t" + "\t".join(str(v) for v in recs[k].values()) for k in sorted(recs))
        m["digests"][name] = hashlib.sha256(digest_src.encode()).hexdigest()[:24]
    for label_, child, fk, parent, pk in ORPHAN_CHECKS:
        if child not in cols or parent not in cols:
            m["orphans"][label_] = "not available"
            continue
        try:
            if fk is None:
                sql = f"select count(*) from {SCHEMA}.{child} c where not exists (select 1 from {SCHEMA}.{parent} p where p.{pk} = c.id)"
            else:
                if fk not in cols[child]:
                    m["orphans"][label_] = "not available"
                    continue
                sql = f"select count(*) from {SCHEMA}.{child} c where c.{fk} is not null and not exists (select 1 from {SCHEMA}.{parent} p where p.{pk} = c.{fk})"
            m["orphans"][label_] = int(db.scalar(sql))
        except RuntimeError as e:
            m["orphans"][label_] = f"error: {str(e)[:120]}"
    try:
        m["changelog"] = {"rows": int(db.scalar(f"select count(*) from {SCHEMA}.databasechangelog")),
                          "last": db.q(f"select filename, id, author, exectype, to_char(dateexecuted,'YYYY-MM-DD HH24:MI:SS') from {SCHEMA}.databasechangelog order by orderexecuted desc limit 1")[0],
                          "lock": db.q(f"select id, locked, coalesce(lockedby,'') from {SCHEMA}.databasechangeloglock")}
    except RuntimeError as e:
        m["changelog"] = {"error": str(e)[:200]}
    seq_issues = []
    for t in ("patient", "person", "sample", "sample_item", "analysis", "result", "test", "panel", "menu", "system_user", "note"):
        if t in cols and "id" in cols[t]:
            try:
                seq = db.scalar(f"select pg_get_serial_sequence('{SCHEMA}.{t}', 'id')")
                if seq:
                    last = db.scalar(f"select last_value from {seq}")
                    mx = db.scalar(f"select coalesce(max(id),0) from {SCHEMA}.{t}")
                    if last is not None and mx is not None and int(mx) > int(last):
                        seq_issues.append(f"{t}: sequence {seq} last_value {last} < max(id) {mx}")
            except RuntimeError:
                pass
    m["sequence_issues"] = seq_issues
    return m


def compare(before, after, out):
    lines = [f"# Manifest comparison: {before['label']} ({before['taken_at']}) vs {after['label']} ({after['taken_at']})\n"]
    failures = 0
    notes = 0
    bt, at = before["tables"], after["tables"]
    new_tables = sorted(set(at) - set(bt)); gone = sorted(set(bt) - set(at))
    changed = [(t, bt[t], at[t]) for t in sorted(set(bt) & set(at)) if bt[t] != at[t]]
    lines.append("## Tables\n")
    lines.append(f"- tables before: {len(bt)}, after: {len(at)}; new: {len(new_tables)}; removed: {len(gone)}; row-count changes: {len(changed)}")
    for t in new_tables:
        lines.append(f"- NEW table {t}: {at[t]} rows"); notes += 1
    for t in gone:
        lines.append(f"- REMOVED table {t} (had {bt[t]} rows): check the changesets that drop it"); notes += 1
    for t, b, a in changed:
        tag = "DECREASED" if isinstance(a, int) and isinstance(b, int) and a < b else "changed"
        lines.append(f"- {tag} {t}: {b} -> {a}"); notes += 1
    lines.append("\n## Business records (by stable identifier)\n")
    for name in ENTITIES:
        be, ae = before["entities"].get(name), after["entities"].get(name)
        if be is None or ae is None:
            lines.append(f"- {name}: NOT CHECKED (not available on one side)"); continue
        bk, ak = set(be["records"]), set(ae["records"])
        missing = sorted(bk - ak); added = sorted(ak - bk)
        field_diffs = []
        for k in sorted(bk & ak):
            br, ar = be["records"][k], ae["records"][k]
            for c in be["columns"]:
                if c in ar and str(br.get(c)) != str(ar.get(c)):
                    field_diffs.append((k, c, br.get(c), ar.get(c)))
        status = "VERIFIED" if not missing and not field_diffs else ("MISSING RECORDS" if missing else "FIELDS CHANGED")
        if be.get("truncated"):
            status = f"count only ({be['count']} -> {ae['count']})"
        lines.append(f"- {name}: {status}; before {be['count']}, after {ae['count']}, missing {len(missing)}, added {len(added)}, field changes {len(field_diffs)}, digest {'same' if before['digests'].get(name)==after['digests'].get(name) else 'DIFFERENT'}")
        if missing:
            failures += 1
            for k in missing[:30]:
                lines.append(f"  - MISSING: {k}")
        for k, c, b, a in field_diffs[:60]:
            lines.append(f"  - {k} . {c}: {b!r} -> {a!r}")
            if c in ("value", "accession_number", "national_id", "status_id", "test_id", "patient_id", "samp_id", "sampitem_id", "analysis_id", "login_name", "is_active"):
                failures += 1
        if len(field_diffs) > 60:
            lines.append(f"  - ... {len(field_diffs)-60} more field changes")
        for k in added[:15]:
            lines.append(f"  - added: {k}")
    lines.append("\n## Relationship and orphan checks\n")
    for label_, bv in before["orphans"].items():
        av = after["orphans"].get(label_)
        flag = ""
        if isinstance(av, int) and isinstance(bv, int) and av > bv:
            flag = " <- NEW ORPHANS"; failures += 1
        elif isinstance(av, int) and av > 0:
            flag = " (pre-existing)"
        lines.append(f"- {label_}: before {bv}, after {av}{flag}")
    lines.append("\n## Sequences\n")
    for s in after.get("sequence_issues", []):
        lines.append(f"- SEQUENCE BEHIND: {s}"); failures += 1
    if not after.get("sequence_issues"):
        lines.append("- every checked id sequence is at or beyond max(id)")
    lines.append("\n## Liquibase\n")
    lines.append(f"- changelog rows: {before.get('changelog',{}).get('rows')} -> {after.get('changelog',{}).get('rows')}; last after: {after.get('changelog',{}).get('last')}; lock: {after.get('changelog',{}).get('lock')}")
    na = sorted(set(before.get("not_available", []) + after.get("not_available", [])))
    if na:
        lines.append("\n## Checks not available on this schema\n")
        for n in na:
            lines.append(f"- {n}")
    lines.append(f"\n## Summary\n\n- failures (missing records, key field changes, new orphans, sequences behind): {failures}\n- differences to judge against the changesets: {notes}\n")
    open(out, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))
    print(f"... written to {out}: failures={failures}, differences={notes}")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--psql", required=True); s.add_argument("--out", required=True); s.add_argument("--label", default="snapshot")
    c = sub.add_parser("compare"); c.add_argument("before"); c.add_argument("after"); c.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "snapshot":
        m = snapshot(Db(a.psql), a.label)
        json.dump(m, open(a.out, "w"), indent=1, default=str)
        print(f"{a.label}: {len(m['tables'])} tables, entities: " + ", ".join(f"{k}={v['count']}" for k, v in m["entities"].items()) + f"; orphans with issues: {[k for k, v in m['orphans'].items() if isinstance(v, int) and v > 0]}; not available: {len(m['not_available'])}")
        return 0
    return compare(json.load(open(a.before)), json.load(open(a.after)), a.out)


if __name__ == "__main__":
    sys.exit(main())
