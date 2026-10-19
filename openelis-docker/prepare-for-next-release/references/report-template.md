# OpenELIS Global release-readiness report

Run `{{RUN_ID}}`, generated {{DATE}}. Evidence: `release-reports/{{RUN_ID}}/`.

## 1. Executive summary

| Item | Value |
|---|---|
| Last officially released version | {{RELEASE_TAG}} |
| Development image tag | {{DEVELOP_TAG}} |
| Images (previous -> development) | see Environment |
| Test execution date | {{DATE}} |
| **Overall status** | **_READY FOR RELEASE / READY WITH KNOWN NON-BLOCKING ISSUES / NOT READY FOR RELEASE / BLOCKED, INSUFFICIENT EVIDENCE_** |
| Tests passed | _n_ |
| Tests failed | _n_ |
| Tests blocked or not executed | _n_ |
| Migration failures | _n_ |
| Data-integrity failures | _n_ |
| Critical / high defects | _n_ / _n_ |

_One paragraph: what was proven, what was not, and why the status follows._

## 2. Environment

| Item | Value |
|---|---|
| Docker repository | {{REPO}} |
| Git branch / commit | {{BRANCH}} / {{COMMIT}} |
| Repository sync | _clean / local changes preserved / ahead-behind upstream_ |
| Compose configuration | `docker-compose.yml` + `release-reports/{{RUN_ID}}/compose.override.yml` (project `oe-release-test`) |
| Previous release images | _from env/images-{{RELEASE_TAG}}.txt with digests (env/digests-{{RELEASE_TAG}}.txt)_ |
| Development images | _from env/images-{{DEVELOP_TAG}}.txt with digests_ |
| Database engine | _PostgreSQL version from the manifest_ |
| Database directory | {{DB_DATA_DIR}} |
| Container health | _env/running-*.txt, wait timings_ |
| Backup | {{BACKUP}} (verified: {{BACKUP_VERIFIED}}; backup/restore-check.txt) |
| Other stacks stopped for the run | _none / list, and whether restarted_ |
| Environmental events and recovery actions | _from state.json events_ |

Pinned images:
{{IMAGES}}

## 3. Liquibase migration results

**Did the current development version successfully upgrade the database
created by the last officially released version? _YES / NO / INCONCLUSIVE_**

| Item | Value |
|---|---|
| Previous application version | {{RELEASE_TAG}} |
| Target application tag | {{DEVELOP_TAG}} |
| Existing database reused (same directory, same data) | _yes/no, evidence: env/running-{{DEVELOP_TAG}}.txt, db/manifest-diff-before-pre-upgrade.md_ |
| Database reinitialised | _no (PG_VERSION and row counts unchanged before migration)_ |
| Liquibase start-up outcome | _from logs/<app>-develop-boot.log_ |
| Changesets expected / applied | _n / n (db/liquibase-verdict.md)_ |
| Exectypes | _EXECUTED n, MARK_RAN n, RERAN n_ |
| Validation / checksum results | _none changed / list_ |
| Failed changesets | _none / table below_ |
| Skipped changesets needing investigation | _MARK_RAN list with judgement_ |
| Database errors in the log | _none / excerpts_ |
| Lock state at the end | _released_ |
| Application completed start-up after migration | _health 200, front end 200, login OK_ |
| Final schema check | _table count, new tables (db/manifest-diff-before-after.md)_ |

Failed changesets (if any):

| Changelog file | Changeset id | Author | Error | Impact |
|---|---|---|---|---|

### Migration process, step by step

One row per step, in order, every upgrade attempt included (attempt 1 on the
published images, then each rerun after a fix):

| Time | Step | Tag / artefact | Outcome | Evidence |
|---|---|---|---|---|
| | release boot, metadata and demonstration data loaded | {{RELEASE_TAG}} | | logs/, db/config-load-release-boot.md |
| | backup + verification (database and configuration directory) | | | backup/ |
| | switch, attempt 1 | {{DEVELOP_TAG}} | _Liquibase / config load / integrity verdicts_ | |
| | fix: _changeset / commit_ | local WAR _sha_ | | |
| | restore-run + switch, attempt _n_ | local WAR _sha_ | | db/attempt-<n>/ |

Clean migration reached at attempt _n_: _yes / no_, with which artefact.

## 3b. Configuration metadata

Inventory: `env/config-inventory.md` (_n_ develop domains, _n_ new in
develop, _n_ files, files added by the run listed in db/demo-manifest.md).

| Domain | New in develop? | Files | Release load | Develop load (upgraded DB) | Migrated intact | Forced reload | Used in a workflow (UI) | Evidence |
|---|---|---|---|---|---|---|---|---|

Configuration load verdicts: release boot _YES/NO_, develop boot _YES/NO_
(published images), develop boot with the local fix _YES/NO_. Open
unresolved references: _n_.

## 4. Data-integrity results

| Check | Result | Evidence |
|---|---|---|
| Demonstration records created (manifest) | _n patients, n orders, n results, ..._ | db/demo-manifest.md |
| Table counts before/after | _verified; intended changes listed_ | db/manifest-diff-before-after.md |
| Patients and identifiers | _VERIFIED / FAIL_ | |
| Orders, samples, accession numbers | | |
| Sample items and sample types | | |
| Analyses, tests, panels, statuses | | |
| Results and values | | |
| Notes, referrals, observations | | |
| Catalogue (tests, panels, reflex, calculated, ranges) | | |
| Menus, users, roles, site information | | |
| Orphan and relationship checks | | |
| Id sequences | | |
| Expected transformations (changeset -> observed) | | |
| Records retrieved through the UI | _per record PASS/FAIL_ | ui/test-log.md, screenshots/ |
| Checks not performed | _list and why_ | |

## 5. Workflow test results

Coverage summary first (from `references/ui-regression-checklist.md`):

| Tier | Functionality | Cases run | PASS | FAIL | BLOCKED / NOT TESTED (why) |
|---|---|---|---|---|---|
| 1 | Patient entry and management | | | | |
| 1 | Order entry (default, clinical, vector, environmental) | | | | |
| 1 | Pathology / immunohistochemistry / cytology | | | | |
| 1 | Result entry | | | | |
| 1 | Multi-component and multi-sample-type tests (ranges, terminology, reflex, alerts, calculated) | | | | |
| 1 | Validation | | | | |
| 1 | Reports | | | | |
| 1 | Reflex tests | | | | |
| 1 | Calculated tests | | | | |
| 1 | Test catalogue management | | | | |
| 1 | Users and roles, organisations, providers, other admin management | | | | |
| 2 | Every other menu item (listed) | | | | |

Then one table per functionality, Tier 1 first, each case naming the edge
case it covers and whether it ran on pre-migration or new records.

| Id | Test case | Expected | Actual | Status | Evidence | Severity | In previous release? |
|---|---|---|---|---|---|---|---|

Baseline (previous release) results:

| Id | Test case | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|

## 6. Defect register

| Id | Title | Severity | Cause (migration / application / deployment / test data / environmental) | Workflow | Reproduction | Expected | Actual | Evidence | Regression? | Blocks release? | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|

Test-data findings (not product defects): each with the inconsistent record
or file, the consistent-data reproduction that passed (screenshot), the
correction made, and the skill recipe changed. A validation gap that let the
inconsistent data in is listed above as a product defect.

Severity: CRITICAL (data loss/corruption, failed essential migration, unsafe
release), HIGH (core workflow broken or existing data unusable), MEDIUM
(impaired with workaround), LOW (minor). Confirmed vs suspected is stated in
the title.

## 7. Fixes applied during the run

Fixes are verified here on local artefacts mounted into the stack; the
status in section 1 stays about the published images until these pull
requests are merged and the develop images are republished.

| Defect id | Fix (repo, commit) | Pull request | Jira | Tested on (this stack / dev server, then this stack) | Deployed as (WAR sha / image, commit) | Live re-verification (Playwright MCP, screenshots) | Regression matrix | Result |
|---|---|---|---|---|---|---|---|---|

Pull request: _link_, commits _n_, CI _green/red_, independent review _by a
separate fresh reviewer: outcome, findings addressed_.

Migration retry (if any): attempt `n`, previous evidence in
`db/attempt-<n>/`, restored directory `release-test/runs/{{RUN_ID}}/db-data-retry-<n>`,
verdict of the local fix: _YES / NO / INCONCLUSIVE_ (`db/liquibase-verdict.md`).

## 8. Release recommendation

1. Did the Liquibase upgrade succeed (published images)? And with the fixes?
2. Was existing data preserved?
3. Did the core workflows pass?
4. Were important edge cases tested? Which?
5. Critical or high-severity defects? Which are fixed locally, which open?
6. Tests that remain incomplete, and the limitation behind each.
7. Is the release safe to proceed to production?
8. What must be fixed or merged before release?
9. What additional verification is recommended (re-run after the images are
   republished)?

## 9. Final state of the environment

_Which tag is running or that the stack is stopped; local fix mounted (from
`rt.sh local-fix show`); database directories (run and retries); backup path;
named volumes kept; anything stopped for the run and whether it was
restarted; open pull requests._
