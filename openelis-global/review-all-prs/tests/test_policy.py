"""Scenario tests for review-all-prs.

Run: python3 -I -m unittest discover -s openelis-global/review-all-prs/tests -v
(from the skills repository root), or python3 -I tests/test_policy.py.
"""

import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import policy  # noqa: E402
import prs  # noqa: E402

CFG = json.loads((ROOT / "config.json").read_text())
RUN_START = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 23, 13, 0, tzinfo=timezone.utc)
BEFORE = "2026-11-20T10:00:00Z"
DURING = "2026-11-23T12:30:00Z"
GREEN = [
    {"name": n, "status": "COMPLETED", "conclusion": "SUCCESS", "required": True, "at": "2026-11-23T11:00:00Z"}
    for n in ("01 Checkpoint - Backend", "02 Checkpoint - Frontend", "03 Checkpoint - E2E", "Validation / Submodule pins")
]
RULES = {
    "required_checks": [c["name"] for c in GREEN],
    "required_approvals": 1,
    "thread_resolution": True,
}


def make_pr(**kw):
    pr = {
        "key": "DIGI-UW/OpenELIS-Global-2#100",
        "repo": "DIGI-UW/OpenELIS-Global-2",
        "number": 100,
        "title": "fix(results): keep the unit when a result is edited",
        "body": "",
        "state": "OPEN",
        "isDraft": False,
        "createdAt": "2026-11-01T09:00:00Z",
        "author": {"__typename": "User", "login": "contributor1", "name": "A Contributor"},
        "baseRefName": "develop",
        "defaultBranch": "develop",
        "headRefOid": "sha2",
        "additions": 40,
        "deletions": 10,
        "changedFiles": 3,
        "files": [
            {"path": "src/main/java/org/openelisglobal/result/ResultServiceImpl.java"},
            {"path": "src/test/java/org/openelisglobal/result/ResultServiceImplTest.java"},
            {"path": "frontend/src/components/resultPage/ResultRow.js"},
        ],
        "reviews": [],
        "reviewer_permissions": {},
        "commits": [
            {"oid": "sha1", "headline": "fix unit", "parents": 1, "date": "2026-11-02T09:00:00Z"},
            {"oid": "sha2", "headline": "address review", "parents": 1, "date": "2026-11-10T09:00:00Z"},
        ],
        "contexts": copy.deepcopy(GREEN),
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "REVIEW_REQUIRED",
        "unresolved_threads": 0,
    }
    pr.update(kw)
    return pr


def review(login, state, sha, at=BEFORE):
    return {"author": {"__typename": "User", "login": login}, "state": state, "submittedAt": at, "commit": {"oid": sha}}


def evaluate(pr, *, review_result="clean", reviewed_sha=None, fixes=(), run_id="run2", open_issues=0,
             delta=None, override=None, why=None, rules=RULES):
    """Mirror prs.facts_for with plain data: returns (decision, gate blockers)."""
    cls = policy.classify(pr, CFG)
    category, _ = policy.apply_override(cls["category"], override, why)
    own = {f["sha"] for f in fixes}
    approval = policy.approval_analysis(pr, CFG, RUN_START, own, delta)
    ci = policy.ci_state(pr["contexts"], rules["required_checks"], NOW)
    fixed_this_run = any(f["run"] == run_id for f in fixes)
    prior = any(f["run"] != run_id for f in fixes)
    self_ok = policy.self_approved_head(pr, CFG)
    ctx = {
        "excluded": policy.exclusion_reason(pr["author"], CFG),
        "category": category,
        "review": review_result,
        "reviewed_sha": reviewed_sha or pr["headRefOid"],
        "approval": approval,
        "fixed_this_run": fixed_this_run,
        "open_issues": open_issues,
        "rules": rules,
    }
    gate = policy.merge_gate(dict(pr, ci=ci), ctx, CFG)
    admin = [g["text"] for g in gate if g["code"] == "admin" or g["text"].startswith("CI last ran")]
    if not self_ok:
        admin = [a for a in admin if not a.startswith("required approval missing")]
    d = policy.decide({
        "excluded": ctx["excluded"], "merged": False, "closed": False, "draft": pr["isDraft"],
        "category": category, "review": review_result, "ci": ci["state"], "approval_counts": approval["counts"],
        "fixed_this_run": fixed_this_run, "prior_fixes": prior, "open_issues": open_issues,
        "self_approved_head": self_ok, "admin_blockers": admin,
    })
    return d, [g["text"] for g in gate], category


def dependabot_pr(title, body, files, **kw):
    return make_pr(
        title=title, body=body, author={"__typename": "Bot", "login": "dependabot"},
        files=[{"path": f} for f in files], changedFiles=len(files), additions=4, deletions=4,
        commits=[{"oid": "dsha1", "headline": title, "parents": 1, "date": "2026-11-21T09:00:00Z"}],
        headRefOid="dsha1", **kw,
    )


LODASH = dependabot_pr(
    "build(deps): bump lodash from 4.17.20 to 4.17.21 in /frontend",
    "Bumps [lodash](https://github.com/lodash/lodash) from 4.17.20 to 4.17.21.\n<details><summary>Commits</summary>Bump x from 1 to 9</details>",
    ["frontend/package.json", "frontend/package-lock.json"],
)

PR4606_BODY = """Bumps the maven-security group with 4 updates in the / directory: com.sun.mail:jakarta.mail, [org.springframework:spring-webmvc](https://github.com/spring-projects/spring-framework), [net.sf.jasperreports:jasperreports](x) and [org.apache.poi:poi](y).

Updates `com.sun.mail:jakarta.mail` from 1.6.5 to 1.6.8

Updates `org.springframework:spring-webmvc` from 6.2.19 to 7.0.9
<details>
<summary>Release notes</summary>
<li>Bump flatted from 3.3.1 to 3.4.2</li>
</details>

Updates `net.sf.jasperreports:jasperreports` from 6.20.0 to 6.20.6

Updates `org.apache.poi:poi` from 5.2.3 to 5.4.0
"""

PR4751_BODY = """Bumps the docker-images group with 1 update in the / directory: maven.
Bumps the docker-images group with 2 updates in the /fhir directory: tomcat and hapiproject/hapi.

Updates `maven` from 3-eclipse-temurin-21 to 3-eclipse-temurin-26

Updates `tomcat` from 9.0.121-jre17-temurin-noble to 9.0.122-jre17-temurin-noble

Updates `hapiproject/hapi` from v6.6.0-tomcat to v6.10.1-tomcat

Updates `nginx` from 1.27-alpine to 1.29-alpine
"""

PR4902_BODY = """Bumps the github-actions group with 6 updates in the / directory:

| Package | From | To |
| --- | --- | --- |
| [actions/checkout](https://github.com/actions/checkout) | `6` | `7` |
| [actions/setup-python](https://github.com/actions/setup-python) | `5` | `7` |
| [actions/setup-java](https://github.com/actions/setup-java) | `5` | `6` |
| [actions/upload-artifact](https://github.com/actions/upload-artifact) | `4` | `7` |
| [actions/setup-node](https://github.com/actions/setup-node) | `6` | `7` |
| [actions/download-artifact](https://github.com/actions/download-artifact) | `7` | `8` |
"""


class Scenarios(unittest.TestCase):
    def test_01_previously_approved_bug_fix_merges(self):
        pr = make_pr(
            reviews=[review("kakumba", "CHANGES_REQUESTED", "sha1", "2026-11-05T09:00:00Z"),
                     review("kakumba", "APPROVED", "sha2", BEFORE)],
            reviewer_permissions={"kakumba": "write"}, reviewDecision="APPROVED",
        )
        d, gate, category = evaluate(pr)
        self.assertEqual(category, "regular")
        self.assertEqual(gate, [])
        self.assertEqual(d["bucket"], "A")
        self.assertIn("merge", d["actions"])
        self.assertEqual(d["merge_kind"], "approved-regular")

    def test_02_previously_approved_with_minor_fix_merges_after_ci(self):
        pr = make_pr(reviews=[review("kakumba", "APPROVED", "sha2")], reviewer_permissions={"kakumba": "write"},
                     reviewDecision="APPROVED")
        d, gate, _ = evaluate(pr, review_result="fixed", reviewed_sha="sha2")
        self.assertEqual((d["bucket"], d["actions"]), ("G", ["wait-ci"]))
        self.assertNotIn("merge", d["actions"])
        fixed = make_pr(
            reviews=pr["reviews"], reviewer_permissions=pr["reviewer_permissions"], reviewDecision="APPROVED",
            headRefOid="fix1",
            commits=pr["commits"] + [{"oid": "fix1", "headline": "rename helper", "parents": 1, "date": DURING}],
        )
        pending = copy.deepcopy(GREEN)
        pending[2].update(status="IN_PROGRESS", conclusion=None)
        d, gate, _ = evaluate(dict(fixed, contexts=pending), fixes=[{"sha": "fix1", "run": "run2"}])
        self.assertEqual(d["bucket"], "G")
        self.assertIn("wait-ci", d["actions"])
        d, gate, _ = evaluate(fixed, fixes=[{"sha": "fix1", "run": "run2"}])
        self.assertEqual(gate, [])
        self.assertEqual(d["bucket"], "A")

    def test_03_previously_approved_major_feature_is_approved_not_merged(self):
        files = [{"path": f"frontend/src/components/x/F{i}.js"} for i in range(8)] + [
            {"path": f"src/main/java/org/openelisglobal/x/S{i}.java"} for i in range(8)
        ] + [{"path": "src/main/resources/liquibase/3.6.x.x/040-x.xml"}]
        pr = make_pr(title="feat(storage): box view for sample storage", files=files, changedFiles=len(files),
                     additions=900, deletions=50, reviews=[review("kakumba", "APPROVED", "sha2")],
                     reviewer_permissions={"kakumba": "write"}, reviewDecision="APPROVED")
        d, gate, category = evaluate(pr)
        self.assertEqual(category, "major")
        self.assertEqual(d["bucket"], "B")
        self.assertNotIn("merge", d["actions"])
        self.assertIn("major change: left open for your manual merge", gate)

    def test_04_new_regular_pr_is_approved_not_merged(self):
        pr = make_pr(title="feat(reports): add a site column to the export", additions=70, deletions=5)
        d, gate, category = evaluate(pr)
        self.assertEqual(category, "regular")
        self.assertEqual(d["bucket"], "G")
        self.assertEqual(d["actions"], ["approve"])
        self.assertIn("no qualifying approval from before this run", gate)
        big = make_pr(title="feat(reports): new export builder", additions=500, deletions=20)
        d, gate, category = evaluate(big)
        self.assertEqual((category, d["bucket"], d["actions"]), ("major", "B", ["approve"]))

    def test_04b_approval_given_during_this_run_never_counts(self):
        pr = make_pr(reviews=[review("mozzy11", "APPROVED", "sha2", DURING)], reviewer_permissions={"mozzy11": "admin"},
                     reviewDecision="APPROVED")
        d, gate, _ = evaluate(pr)
        self.assertEqual(d["bucket"], "G")
        self.assertNotIn("merge", d["actions"])

    def test_05_new_dependabot_pr_without_issues_merges_on_first_run(self):
        self.assertEqual(policy.classify(LODASH, CFG)["category"], "low-risk")
        d, gate, _ = evaluate(LODASH)
        self.assertEqual(d["bucket"], "A")
        self.assertEqual(d["actions"], ["approve", "merge"])
        self.assertEqual(d["merge_kind"], "first-run")
        approved = dict(LODASH, reviews=[review("mozzy11", "APPROVED", "dsha1", DURING)], reviewDecision="APPROVED")
        d, gate, _ = evaluate(approved)
        self.assertEqual(gate, [])
        self.assertEqual(d["actions"], ["merge"])

    def test_06_dependabot_fixed_in_this_run_stops(self):
        pr = dict(LODASH, headRefOid="fix9", reviews=[review("mozzy11", "APPROVED", "fix9", DURING)],
                  reviewDecision="APPROVED",
                  commits=LODASH["commits"] + [{"oid": "fix9", "headline": "pin peer", "parents": 1, "date": DURING}])
        d, gate, _ = evaluate(pr, review_result="fixed", reviewed_sha="dsha1", fixes=[{"sha": "fix9", "run": "run2"}])
        self.assertEqual((d["bucket"], d["actions"]), ("D", []))
        d, gate, _ = evaluate(pr, review_result="clean", fixes=[{"sha": "fix9", "run": "run2"}])
        self.assertEqual(d["bucket"], "D")
        self.assertIn("fixed in this run: the merge waits for the next run", gate)

    def test_07_dependabot_after_fix_merges_on_next_run(self):
        pr = dict(LODASH, headRefOid="fix9", reviews=[review("mozzy11", "APPROVED", "fix9", DURING)],
                  reviewDecision="APPROVED",
                  commits=LODASH["commits"] + [{"oid": "fix9", "headline": "pin peer", "parents": 1, "date": BEFORE}])
        d, gate, _ = evaluate(pr, fixes=[{"sha": "fix9", "run": "run1"}])
        self.assertEqual(gate, [])
        self.assertEqual((d["bucket"], d["merge_kind"]), ("A", "after-fix"))
        d, gate, _ = evaluate(pr, fixes=[{"sha": "fix9", "run": "run1"}], open_issues=1)
        self.assertEqual(d["bucket"], "C")

    def test_08_dependabot_with_failing_ci_is_not_merged(self):
        red = copy.deepcopy(GREEN)
        red[0]["conclusion"] = "FAILURE"
        d, gate, _ = evaluate(dict(LODASH, contexts=red))
        self.assertEqual((d["bucket"], d["actions"]), ("G", []))
        self.assertTrue(any(g.startswith("checks failing") for g in gate))
        running = copy.deepcopy(GREEN)
        running[2].update(status="IN_PROGRESS", conclusion=None)
        d, gate, _ = evaluate(dict(LODASH, contexts=running))
        self.assertEqual((d["bucket"], d["actions"]), ("G", ["wait-ci"]))
        self.assertTrue(any(g.startswith("checks pending") for g in gate))
        d, gate, _ = evaluate(dict(LODASH, contexts=[]), rules=dict(RULES, required_checks=[]))
        self.assertEqual((d["bucket"], d["actions"]), ("G", []))
        self.assertTrue(any(g.startswith("checks none") for g in gate))

    def test_09_outdated_pr_is_flagged_and_closed(self):
        pr = make_pr(title="OGC-1234: show the unit on the results page", headRefName="ogc-1234-unit",
                     url="u", closing_issues=[], mergeable="MERGEABLE")
        inv = {"repos": {pr["repo"]: {"merged": [
            {"number": 200, "title": "fix(results): unit on results (OGC-1234)", "headRefName": "x",
             "mergedAt": "2026-11-15T00:00:00Z", "url": "https://github.com/DIGI-UW/OpenELIS-Global-2/pull/200"}]}},
               "prs": {pr["key"]: pr}}
        hints = prs.obsolete_hints(pr, inv, CFG)
        self.assertTrue(any("OGC-1234 also landed in" in h for h in hints))
        d = policy.decide({"closed": True})
        self.assertEqual(d["bucket"], "E")

    def test_09b_automated_series_older_pr_is_superseded(self):
        a = make_pr(key="DIGI-UW/OpenELIS-QA#270", repo="DIGI-UW/OpenELIS-QA", number=270, headRefName="b1",
                    title="Known reds: remove those that passed in run 313",
                    author={"__typename": "Bot", "login": "github-actions"}, closing_issues=[])
        b = dict(a, key="DIGI-UW/OpenELIS-QA#276", number=276, title="Known reds: remove those that passed in run 319")
        inv = {"repos": {a["repo"]: {"merged": []}}, "prs": {a["key"]: a, b["key"]: b}}
        self.assertTrue(any("#276" in h for h in prs.obsolete_hints(a, inv, CFG)))
        self.assertFalse(any("series" in h for h in prs.obsolete_hints(b, inv, CFG)))

    def test_10_core_team_pr_is_excluded(self):
        for author in ({"login": "pmanko"}, {"login": "SamuelMale"}, {"login": "someone", "name": "Samwe Male"},
                       {"login": "reagan-meant"}, {"login": "mherman22"}, {"login": "ibacher"}):
            pr = make_pr(author=author, reviews=[review("kakumba", "APPROVED", "sha2")],
                         reviewer_permissions={"kakumba": "write"}, reviewDecision="APPROVED")
            d, gate, _ = evaluate(pr)
            self.assertEqual((d["bucket"], d["actions"]), ("F", []), author)
            self.assertTrue(any(g.startswith("excluded") for g in gate))
        self.assertIsNone(policy.exclusion_reason({"login": "caseyi", "name": "Casey Iiams-Hauser"}, CFG))
        self.assertIn("own PR", policy.exclusion_reason({"login": "mozzy11"}, CFG))

    def test_11_major_dependency_upgrade_is_not_low_risk(self):
        spring = dependabot_pr("build(deps): bump the maven-security group across 1 directory with 4 updates",
                               PR4606_BODY, ["pom.xml"])
        cls = policy.classify(spring, CFG)
        self.assertEqual(cls["category"], "major")
        self.assertTrue(any("spring-webmvc" in b for b in cls["low_risk_blockers"]))
        d, gate, _ = evaluate(spring)
        self.assertEqual(d["bucket"], "B")
        self.assertNotIn("merge", d["actions"])
        actions = dependabot_pr("build(deps): bump the github-actions group across 1 directory with 6 updates",
                                PR4902_BODY, [f".github/workflows/w{i}.yml" for i in range(6)])
        self.assertEqual(policy.classify(actions, CFG)["category"], "regular")
        d, gate, _ = evaluate(actions)
        self.assertEqual(d["bucket"], "G")
        self.assertNotIn("merge", d["actions"])
        approved = dict(actions, reviews=[review("kakumba", "APPROVED", "dsha1")], reviewer_permissions={"kakumba": "write"},
                        reviewDecision="APPROVED")
        d, gate, _ = evaluate(approved)
        self.assertEqual(d["bucket"], "A")

    def test_12_low_risk_blocked_by_branch_protection_is_reported(self):
        pr = dict(LODASH, reviews=[review("mozzy11", "APPROVED", "dsha1", DURING)], reviewDecision="REVIEW_REQUIRED",
                  mergeStateStatus="BLOCKED")
        d, gate, _ = evaluate(pr)
        self.assertEqual(d["bucket"], "G")
        self.assertNotIn("merge", d["actions"])
        self.assertIn("GitHub merge state is BLOCKED", gate)
        self.assertTrue(any(g.startswith("required approval missing") for g in gate))


class Rules(unittest.TestCase):
    def test_bump_kind(self):
        cases = {
            ("1.6.5", "1.6.8"): "patch", ("6.2.19", "7.0.9"): "major", ("1.27-alpine", "1.29-alpine"): "minor",
            ("3-eclipse-temurin-21", "3-eclipse-temurin-26"): "unknown", ("v6.6.0-tomcat", "v6.10.1-tomcat"): "minor",
            ("9.0.121-jre17-temurin-noble", "9.0.122-jre17-temurin-noble"): "patch", ("0.3.1", "0.4.0"): "major",
            ("2.0.0", "2.0.0-rc1"): "unknown", ("6", "7"): "major", ("1.2.3", "1.2.1"): "downgrade", (None, "1.0"): "unknown",
        }
        for (a, b), want in cases.items():
            self.assertEqual(policy.bump_kind(a, b), want, (a, b))

    def test_release_notes_are_not_read_as_updates(self):
        ups, expected = policy.parse_updates("build(deps): bump the maven-security group across 1 directory with 4 updates", PR4606_BODY)
        self.assertEqual(expected, 4)
        self.assertEqual({u["package"] for u in ups}, {
            "com.sun.mail:jakarta.mail", "org.springframework:spring-webmvc", "net.sf.jasperreports:jasperreports", "org.apache.poi:poi"})

    def test_docker_flavour_change_blocks_low_risk(self):
        pr = dependabot_pr("build(deps): bump the docker-images group across 4 directories with 4 updates",
                           PR4751_BODY, ["Dockerfile", "fhir/Dockerfile", "frontend/Dockerfile", "nginx-proxy/Dockerfile"])
        cls = policy.classify(pr, CFG)
        self.assertNotEqual(cls["category"], "low-risk")
        self.assertTrue(any("maven" in b and "unknown" in b for b in cls["low_risk_blockers"]))

    def test_table_and_group_limits(self):
        ups, expected = policy.parse_updates("bump the github-actions group with 6 updates", PR4902_BODY)
        self.assertEqual((len(ups), expected), (6, 6))
        many = dependabot_pr("build(deps): bump the npm group across 1 directory with 35 updates", "", ["frontend/package.json"])
        cls = policy.classify(many, CFG)
        self.assertTrue(any("could not read" in b for b in cls["low_risk_blockers"]))
        self.assertNotEqual(cls["category"], "low-risk")

    def test_patch_only_packages_block_minor_bumps(self):
        pr = dependabot_pr("build(deps): bump org.springframework:spring-core from 6.2.11 to 6.3.0", "", ["pom.xml"])
        self.assertNotEqual(policy.classify(pr, CFG)["category"], "low-risk")
        pr = dependabot_pr("build(deps): bump org.springframework:spring-core from 6.2.11 to 6.2.12", "", ["pom.xml"])
        self.assertEqual(policy.classify(pr, CFG)["category"], "low-risk")
        for name, want in (("node", True), ("actions/setup-node", False), ("nginx", True), ("react", True),
                           ("@testing-library/react", False), ("org.hibernate.orm:hibernate-core", True)):
            self.assertEqual(policy.is_patch_only(name, CFG), want, name)

    def test_dependabot_touching_code_is_not_low_risk(self):
        pr = dependabot_pr("build(deps): bump lodash from 4.17.20 to 4.17.21", "",
                           ["frontend/package.json", "frontend/src/index.js"])
        self.assertNotEqual(policy.classify(pr, CFG)["category"], "low-risk")

    def test_docs(self):
        small = make_pr(title="docs: fix a typo in the README", files=[{"path": "README.md"}], changedFiles=1,
                        additions=1, deletions=1)
        self.assertEqual(policy.classify(small, CFG)["category"], "low-risk")
        design = dict(small, repo="DIGI-UW/openelis-work", title="docs: clarify the order flow")
        self.assertNotEqual(policy.classify(design, CFG)["category"], "low-risk")
        spec = dict(small, title="EHR Lab Interface FRS v0.3")
        self.assertNotEqual(policy.classify(spec, CFG)["category"], "low-risk")
        long = dict(small, additions=300)
        self.assertNotEqual(policy.classify(long, CFG)["category"], "low-risk")

    def test_override_rules(self):
        self.assertEqual(policy.apply_override("regular", "major", None), ("major", None))
        self.assertEqual(policy.apply_override("regular", "low-risk", "x")[0], "regular")
        self.assertEqual(policy.apply_override("major", "regular", None)[0], "major")
        self.assertEqual(policy.apply_override("major", "regular", "small feat"), ("regular", None))
        self.assertEqual(policy.apply_override("low-risk", "regular", None), ("regular", None))

    def test_approval_rules(self):
        base = dict(reviewDecision="APPROVED")
        cases = [
            ({"reviewer_permissions": {"kakumba": "read"}}, False),
            ({"reviewer_permissions": {"kakumba": "triage"}}, False),
            ({"reviewer_permissions": {"kakumba": "write"}}, True),
        ]
        for extra, want in cases:
            pr = make_pr(reviews=[review("kakumba", "APPROVED", "sha2")], **base, **extra)
            self.assertEqual(policy.approval_analysis(pr, CFG, RUN_START)["counts"], want, extra)
        dismissed = make_pr(reviews=[review("kakumba", "APPROVED", "sha2"), review("kakumba", "DISMISSED", "sha2", "2026-11-21T00:00:00Z")],
                            reviewer_permissions={"kakumba": "write"})
        self.assertFalse(policy.approval_analysis(dismissed, CFG, RUN_START)["counts"])
        bot = make_pr(reviews=[{"author": {"__typename": "Bot", "login": "copilot"}, "state": "APPROVED",
                                "submittedAt": BEFORE, "commit": {"oid": "sha2"}}], reviewer_permissions={"copilot": "write"})
        self.assertFalse(policy.approval_analysis(bot, CFG, RUN_START)["counts"])
        later = make_pr(reviews=[review("kakumba", "APPROVED", "sha1")], reviewer_permissions={"kakumba": "write"})
        a = policy.approval_analysis(later, CFG, RUN_START)
        self.assertEqual((a["delta"], a["counts"]), ("author-changes", False))
        self.assertTrue(policy.approval_analysis(later, CFG, RUN_START, delta_assessment="minor")["counts"])
        merged_base = make_pr(reviews=[review("kakumba", "APPROVED", "sha1")], reviewer_permissions={"kakumba": "write"},
                              commits=[{"oid": "sha1", "headline": "x", "parents": 1},
                                       {"oid": "sha2", "headline": "Merge branch 'develop' into fix-unit", "parents": 2}])
        self.assertEqual(policy.approval_analysis(merged_base, CFG, RUN_START)["delta"], "base-merges")
        other_merge = dict(merged_base, commits=[{"oid": "sha1", "headline": "x", "parents": 1},
                                                 {"oid": "sha2", "headline": "Merge branch 'feature-y' into fix-unit", "parents": 2}])
        self.assertEqual(policy.approval_analysis(other_merge, CFG, RUN_START)["delta"], "author-changes")
        cr = make_pr(reviews=[review("kakumba", "APPROVED", "sha2"), review("okello", "CHANGES_REQUESTED", "sha2")],
                     reviewer_permissions={"kakumba": "write"}, reviewDecision="CHANGES_REQUESTED")
        d, gate, _ = evaluate(cr)
        self.assertNotIn("merge", d["actions"])
        self.assertIn("changes requested by okello", gate)

    def test_ci_state(self):
        self.assertEqual(policy.ci_state([], ["a"])["state"], "pending")
        self.assertEqual(policy.ci_state([], [])["state"], "none")
        extra = GREEN + [{"name": "codecov", "status": "COMPLETED", "conclusion": "FAILURE", "required": False, "at": "x"}]
        s = policy.ci_state(extra, RULES["required_checks"])
        self.assertEqual((s["state"], s["other_failing"]), ("green", ["codecov"]))
        rerun = GREEN + [dict(GREEN[0], conclusion="FAILURE", at="2026-11-22T00:00:00Z")]
        self.assertEqual(policy.ci_state(rerun, RULES["required_checks"])["state"], "green")
        old = policy.ci_state(GREEN, RULES["required_checks"], datetime(2026, 12, 30, tzinfo=timezone.utc))
        self.assertGreater(old["age_days"], CFG["ci_max_age_days"])
        pr = make_pr(reviews=[review("kakumba", "APPROVED", "sha2")], reviewer_permissions={"kakumba": "write"},
                     reviewDecision="APPROVED", contexts=[dict(c, at="2026-10-01T00:00:00Z") for c in GREEN])
        d, gate, _ = evaluate(pr)
        self.assertEqual(d["bucket"], "G")
        self.assertTrue(any(g.startswith("CI last ran") for g in gate))

    def test_gate_refuses_moved_head_conflicts_and_threads(self):
        pr = make_pr(reviews=[review("kakumba", "APPROVED", "sha2")], reviewer_permissions={"kakumba": "write"},
                     reviewDecision="APPROVED")
        _, gate, _ = evaluate(pr, reviewed_sha="sha1")
        self.assertIn("the head moved after the review: review the new commits first", gate)
        d, gate, _ = evaluate(dict(pr, mergeable="CONFLICTING", mergeStateStatus="DIRTY"))
        self.assertEqual(d["bucket"], "G")
        self.assertIn("merge conflicts", gate)
        d, gate, _ = evaluate(dict(pr, unresolved_threads=2))
        self.assertEqual(d["bucket"], "G")
        d, gate, _ = evaluate(dict(pr, isDraft=True))
        self.assertEqual(d["bucket"], "G")
        self.assertIn("draft", gate)

    def test_review_body_guard(self):
        import tempfile
        other = {"author": {"login": "contributor1"}}
        own = {"author": {"login": "mozzy11"}}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.md"
            p.write_text("Walked it end to end " + chr(0x2014) + " looks good.")
            with self.assertRaises(SystemExit):
                prs._check_body(str(p), other, CFG)
            p.write_text("Looks good.\n\nGenerated by Claude Reviewer")
            with self.assertRaises(SystemExit):
                prs._check_body(str(p), other, CFG)
            self.assertIn("Claude Reviewer", prs._check_body(str(p), own, CFG))
            p.write_text("Walked it end to end, looks good.")
            self.assertTrue(prs._check_body(str(p), other, CFG))

    def test_merge_command_never_bypasses(self):
        src = (ROOT / "scripts" / "prs.py").read_text()
        merge_src = src[src.index("def cmd_merge"):src.index("def _verify_evidence")]
        self.assertIn("--match-head-commit", merge_src)
        self.assertIn("assert not any(f in cmd for f in FORBIDDEN_MERGE_FLAGS)", merge_src)
        self.assertNotIn('"--admin"', merge_src)
        self.assertEqual(prs.FORBIDDEN_MERGE_FLAGS, ("--admin", "--auto"))
        self.assertNotIn("enforce_admins", src)
        self.assertNotIn("bypass", src.lower())


if __name__ == "__main__":
    unittest.main()
