---
name: prepare-for-next-release
description: OpenELIS Global release-readiness verification on the openelis-docker deployment. Discovers the last official release and the develop image tags, starts the released images from this repository's docker-compose.yml on a run-specific database and configuration directory, loads the complete configuration metadata (every domain develop can load) and valid demonstration data through the UI, baseline-tests the release, backs up and verifies the database, switches the same database to the develop images, proves the Liquibase upgrade and the metadata migration with evidence, checks data integrity before/after, and loops on migration failures (fix in the source, build the WAR, mount it into the compose project, rerun the whole upgrade until it is clean). Then it tests the configuration loaders and every workflow live through Playwright MCP, tells defects apart from inconsistent test data, fixes upgraded-version bugs on the dev server with tests, a PR and a separate independent reviewer, and writes a detailed timestamped release-readiness report under release-reports/. Trigger phrases - "prepare for next release", "prepare for the next release", "release readiness", "verify the release upgrade", "test the upgrade from the last release".
---

# Prepare for next release

A release of OpenELIS Global is safe only when the current `develop` images
upgrade a database that the last official release created and filled, and
the upgraded application still works. This skill proves (or disproves) exactly
that on the real Docker deployment, including the configuration metadata the
deployment loads, fixes what it finds in the source with tests and a pull
request (migration fixes re-verified on this stack, post-upgrade bugs on the
dev server), and writes a detailed report.

Run it **autonomously**: no questions, no permission prompts. The two things
that stop the run are a non-isolated environment (`preflight` says the
database is not local) and an unsafe Docker host (daemon hanging, another
OpenELIS stack that cannot be stopped). Everything else is decided here and
written down in the report.

Creating demonstration data, pulling images, starting and stopping this
skill's own compose project, writing under `release-reports/` and
`release-test/`, and the fix loop of Phase 10 (code changes in the
application checkout with tests, the dev stack for post-upgrade fixes, a push
to the fork and a draft pull request with an independent reviewer, local WAR
or image builds mounted into this stack) are authorised by the trigger
phrase. Merging a pull request and pushing images to Docker Hub are
not. Read `references/safety-rules.md` before the first command.

**Everything is tested live through Playwright MCP.** Every check (baseline,
demonstration records, configuration metadata, integrity retrieval, every
workflow, every edge case) and every fix verification passes only on what
the real UI showed, with a screenshot. Logs, SQL, snapshots and API calls are
supporting evidence and diagnosis; they never make a test PASS on their own.
If Playwright MCP is unavailable, the affected tests are BLOCKED, not passed.

## Where things live

- Repository under test: `/Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/openelis-docker/openelis-docker`
  (the docker repo; `rt.sh` uses `OE_RT_REPO`, else the git checkout of the
  current directory, else this default path). The skill itself is not part
  of that project: it lives in the skills repository
  `/Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills`
  (`openelis-docker/prepare-for-next-release/`, GitHub
  `mozzy11/claude-dev-skills`), symlinked into `~/.claude/skills`. Edit the
  skill, its references and `rt.sh` only through the skills repository path
  (the `~/.claude/skills/...` symlink is a protected path and every edit
  through it asks for permission: two prompts on 2026-10-19). Run
  outputs (`release-reports/`, `release-test/`) stay in the docker checkout,
  ignored through its `.git/info/exclude`, never through its `.gitignore`.
- Application source for fixes: `/Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/develop/OpenELIS-Global-2`
  (the main checkout on `develop`; no worktrees, no feature branches).
- Driver: `scripts/rt.sh` (next to this file). Every command below is
  `RT=<skill dir>/scripts/rt.sh; $RT <subcommand>`; run `$RT help` once.
- Run directory: `release-reports/<run-id>/` with `state.json` (phase, tags,
  services, backup, local fixes, events), `env/`, `logs/`, `db/`, `backup/`,
  `screenshots/`, `ui/`, `compose.override.yml` and, once a fix is deployed,
  `compose.local-fix.yml`. Database directory: `release-test/runs/<run-id>/db-data`
  (plus `db-data-retry-<n>` for migration retries). Report:
  `release-reports/openelis-release-readiness-<run-id>.md`.
- References: `references/safety-rules.md`, `configuration-metadata.md`,
  `liquibase-verification.md`, `data-integrity.md`,
  `ui-regression-checklist.md`, `report-template.md`.
- Run configuration directory: `release-test/runs/<run-id>/configuration`
  (a checksum-free copy of `configs/configuration`, mounted over the
  repository's; `references/configuration-metadata.md` step 1).
- Dev server for post-upgrade application fixes: the shared dev stack of the
  application checkout (`scripts/dev-stack up`, see its `docs/dev_setup.md`).
- Session hygiene helpers (host conventions): `claude-work/bin/session-track.sh`
  for scratch dirs, `session-retro` skill at the end.

## Phase 0: environment inspection and resume

1. `$RT preflight`. Read all of it: git branch, uncommitted changes (they
   stay), ahead/behind upstream, compose services and their images, the
   isolation guard, the deployment's own database directory (untouched),
   clashing container names, port usage, other containers' memory with the
   room verdict, disk.
   - If the tree is clean and behind upstream: `$RT sync` (fast-forward only).
     If it has local changes, keep them and note it in the report.
   - If `ISOLATED LOCAL ENVIRONMENT: NO`: stop and report.
   - If a container name or port clashes with another stack, or the memory
     verdict is NO: that is someone's running environment. Stop only
     containers that belong to this host's own dev tooling after checking
     nothing else uses them (`docker stop`, never `rm`), record them
     (`$RT state log "stopped <names> for the run"`), and start them again in
     Phase 12. If you cannot tell who owns them, stop and report.
   - Disk: under 10 GB free is a reason to stop; the images are about 4 GB
     per tag and the backup needs space too. Preflight also prints the size
     of Docker's `Docker.raw`: every Testcontainers suite run and WAR build
     grows it, and on 2026-10-19 three suite runs beside the stack took it
     to 60 GB, left 3 GB on the host and gave the engine and the test
     Postgres I/O errors (2,246 connection failures, `docker exec` dead).
     Keep 15 GB free before each suite run or WAR build (Phase 10), delete
     each isolated copy right after its run, and never run the full suite
     more than once per push.
   - Docker Desktop hangs: a `docker info` that does not answer in 20 s is
     a hang, not a slow start. Never wait on it in a foreground loop (a
     restart script waited 4 hours on 2026-10-20). Force-kill the
     `com.docker.*` processes, `open -a Docker`, poll with time-boxed
     `docker info` calls (`dock 20`), and expect the stack to come back by
     restart policy on the host bind mount; then `$RT wait` and
     `$RT verify-running`.
2. Resume check: `$RT resume` (or `ls release-reports/`). If a run is in
   progress, its phase and events tell you where it stopped. Continue from
   the next safe step it prints; never re-run `up <release>` after the
   database has been migrated, never `init --new` while a previous run's
   containers are up (tear them down first with `$RT teardown`).
3. New run: `$RT init`. Register nothing that holds the database or the
   backup with the session tracker; scratch extraction directories only.
4. Playwright MCP: call `browser_tabs` (list). If it fails, UI phases are
   BLOCKED from the start; the migration phases still run and the report
   says the UI was not tested.

## Phase 1: determine the versions

`$RT versions`. It records in `env/versions.json` and `state.json`:
- the latest official release of DIGI-UW/OpenELIS-Global-2 (GitHub
  `releases/latest`, which excludes prereleases and drafts) and the recent
  release list for context,
- the develop tags the compose file uses (every image the deployment pins
  with `:develop`, read from `docker compose config`, never assumed),
- whether every pinned image exists on Docker Hub under both tags, with
  digests and architectures,
- the matching openelis-docker release, if any.
If a release image is missing on the registry, that is the finding: the
release artefacts are incomplete; report BLOCKED. If the latest release looks
ambiguous (a newer tag without a release, a release older than the compose
pins suggest), write the ambiguity into the report before continuing.
`OE_RT_RELEASE_TAG=<tag>` overrides the detected release for a deliberate
older-to-develop test; it is still verified on the registry.

## Phase 1b: configuration metadata

Before anything boots, follow `references/configuration-metadata.md` steps 1
to 3: isolate the run's configuration directory (checksum-free copy mounted
over the repository's), inventory the release and develop loaders
(`env/config-inventory.md`), and complete the metadata so every domain the
develop build can load has at least one valid file whose references resolve,
including the domains new in develop. Every file the run adds or adapts is
listed in `db/demo-manifest.md` as test data. Missing example metadata in the
deployment repository is recorded for Phase 10.5.

## Phase 2: run the last released version

1. `$RT config <release>` validates the compose configuration for that tag
   and saves the resolved file and image list under `env/`.
2. `$RT pull <release>` (long; run it in the background and watch its tail).
   Digests land in `env/digests-<release>.txt`.
3. `$RT up <release>`: starts certs and the database first, waits until
   PostgreSQL accepts TCP connections for `clinlims`, then starts the rest.
   The webapp has no wait-for-database, so this ordering avoids a dead
   context that would look like an application failure.
4. `$RT wait` (repeat while it exits 4; exit 3 is a fatal start-up error:
   read `docker logs` and decide). Ready means: database ready, Tomcat
   `Server startup in`, `/api/OpenELIS-Global/health` 200 with status UP
   through the proxy, front end 200.
5. `$RT verify-running <release>`: every pinned container runs the release
   tag with the registry digest, on this run's database directory. A
   mismatch means a stale local image or a wrong tag; fix it (pull again) and
   re-verify before any test.
6. `$RT logs release-boot`; `$RT status`. Record environmental problems met
   here separately from application defects.
7. Configuration load on the release: `references/configuration-metadata.md`
   step 4 with label `release-boot` (`db/config-load-release-boot.md`, UI
   check of every release domain through Playwright MCP). Files of domains
   new in develop must show no load line and no checksum here. A release-era
   file that fails on the release is a baseline finding, kept for the "in
   previous release?" column.

## Phase 3: demonstration data on the release

Follow `references/data-integrity.md` (table of records, naming stamp,
manifest). Use the UI through Playwright MCP (`references/ui-regression-checklist.md`
has the login recipe and the selectors that matter); fall back to the
application's own REST endpoints only where the UI cannot do it, and never to
SQL inserts. Write `db/demo-manifest.md`. Then:

`$RT snapshot before` (manifest of every table, the business records by
stable identifier, orphan checks, digests, sequences, changelog rows).
`$RT state set phase demo-data`.

## Phase 4: baseline test of the release

The short walk in `references/ui-regression-checklist.md` ("Baseline"):
login, patient found, order found with its sample and tests, results visible,
validation page, one report page, one admin page. Screenshots into
`screenshots/baseline-*.png`, results into `ui/test-log.md`. A failure here is
a property of the release, not of the upgrade: investigate whether it is
environmental, configuration or an application defect, and keep it for the
"in previous release?" column. `$RT state set phase baseline-tested`.

## Phase 5: preserve the database

`$RT backup`: `pg_dump` custom format plus the globals into `backup/`, then
`verify-backup` lists the archive and restores it into a scratch database in
the same server, compares table/patient/sample/changeset counts with the live
database and drops the scratch database. The run does not continue without
`backup.verified = true` (`switch` refuses). The backup is for recovery and
for migration retries in Phase 10; it is never restored over the run database
to hide a result. Copy the run configuration directory, with the checksums the
release wrote, to `backup/configuration/` in the same step: a migration retry
restores both.

## Phase 6: switch the same database to the develop images

1. `$RT config develop`, `$RT pull develop` (refreshes the local develop
   images to the registry's current digest; record them).
2. `$RT switch develop`. It refuses without a verified backup, a `before`
   snapshot and an initialised database directory. It then recreates the
   database container with the develop database image on the same
   directory, waits for it, takes `snapshot pre-upgrade` and compares it with
   `before` (the demonstration data must be present before migration begins),
   records the database time as `upgrade_started_at`, and starts the
   application images. The migration begins when the webapp boots.
3. `$RT wait 540`, repeated while it exits 4 (a migration with many
   changesets can take minutes under emulation). Exit 3: the log shows a
   migration or context failure; do not restart; go to Phase 7 with that
   evidence.
4. `$RT logs develop-boot`, `$RT verify-running develop` (same database
   directory, develop tags and digests), `$RT status`.

Never `up develop` on an empty directory (the script refuses: that would be
a fresh install, not an upgrade), never change credentials, database name or
connection settings between the two tags.

## Phase 7: verify the migration (Liquibase and configuration load)

Follow `references/liquibase-verification.md`. `$RT liquibase-verify`
produces `db/liquibase-verdict.md` (YES / NO / INCONCLUSIVE with the expected
vs applied changesets, exectypes, checksum changes, lock state, log scan).
Read the webapp log yourself around the first and last Liquibase lines and any
error. For a failure: changelog file, changeset id, author, the `Reason:`
line, which changesets applied before it, whether the database is partially
upgraded (`snapshot after-failure`, `compare before after-failure`), and the
probable cause class. Preserve everything; no retries beyond one for a proven
environmental cause; no changelog manipulation.

Then the configuration load of the develop boot:
`references/configuration-metadata.md` step 4 with label `develop-boot`
(release-era files UNCHANGED, new-domain files LOADED, nothing FAILED, STALE
or NOT SEEN, the UI shows every domain).

A clean migration means all three: Liquibase verdict YES, the develop
configuration load verdict YES, and the integrity checks of Phase 8 clean.
A NO or INCONCLUSIVE on any of them that is caused by a changeset, or a boot
that failed during the migration, is a CRITICAL migration defect: go to
Phase 10.2 now and loop there until the migration is clean. Phases 8 (final
pass) and 9 run on a clean migration only.

## Phase 8: data integrity

`$RT snapshot after`, `$RT compare before after` (`db/manifest-diff-before-after.md`).
Judge each difference against the applied changesets (intended transformation
vs defect) as `references/data-integrity.md` describes, then retrieve every
demonstration record through the UI on the develop build and screenshot it.
Lost, duplicated, orphaned or unusable pre-existing data is CRITICAL unless an
intended, validated migration behaviour. The metadata migration is part of
this phase: `references/configuration-metadata.md` step 5 (release-era
metadata intact, a forced reload of every domain on the upgraded database
with `after` / `after-reload` compared, one edited release-era file updating
its existing record), each confirmed in the admin pages through Playwright
MCP. `$RT state set phase integrity-checked`.

## Phase 9: UI regression on the develop build

Runs only after a clean migration (Phase 7). Test the updated configuration
loaders first, then the workflows, carefully and thoroughly: every step of
each workflow is driven in the UI and its outcome checked on screen, not just
the page opening.

Configuration loaders on the upgraded build: for every domain whose handler
changed or is new in develop (`env/config-inventory.md`), use the metadata it
loaded in a real workflow (a loaded test ordered for its sample type, a loaded
panel expanding to its tests, a loaded range flagging a result, a loaded
reflex or calculated rule firing, a loaded role granting its pages, loaded
dictionary entries offered as answers), and exercise the admin import /
reload paths the build offers (catalog import preview and apply, unresolved
references) through the UI.

`references/ui-regression-checklist.md`, all sections, through Playwright
MCP: explore the running menu first, then test everything, with the emphasis
on the core functionalities. The user asked for this emphasis (2026-10-19):

- **Tier 1, core, exhaustive, run first:** patient entry, order entry
  (default, clinical, vector, environmental), pathology /
  immunohistochemistry / cytology, result entry, multi-component and
  multi-sample-type tests with extra emphasis (numeric validation ranges per
  component and per sample type, terminology codes, reflex, alerts,
  calculated, end to end to the report; checklist section 4b), validation,
  reports, reflex
  tests, calculated tests, test catalogue management, and the admin
  management pages (users and roles, organisations, providers, dictionary,
  site information and the other management pages in section 9). Every case
  in those sections plus the edge-case matrix on every create and edit form
  (required fields one by one, invalid formats, boundaries, duplicates,
  Unicode, edit of pre-migration records, unsaved navigation, double submit,
  search hits and misses, permissions, recovery after an error), on
  pre-migration and new records alike. Tier 1 cases are never dropped for
  time; an untested Tier 1 case lowers the overall status.
- **Tier 2, everything else, breadth:** every remaining menu item opens
  cleanly, its list or search works, one safe create or edit.

New records carry
the `RT<run>-NEW` stamp. Log each test case as it happens in `ui/test-log.md`
with PASS / FAIL / BLOCKED / NOT TESTED / NOT APPLICABLE, evidence paths,
severity, and whether the same failed on the release in Phase 4 (re-check on
the release only if the stack can be switched back safely, which it cannot
once the database is migrated; otherwise say "not checked on the previous
release"). After each workflow: `browser_console_messages` (errors) and
`browser_network_requests` (failed requests). Copy any screenshots the MCP
wrote elsewhere with `$RT screenshots <dir>`. `$RT state set phase regression-tested`.

Do not claim the whole application was tested when a subset was: the report
lists what was and was not exercised, per tier, with the Tier 1 case counts
per functionality.

Before a FAIL goes into the log as a defect, verify it the way 10.1 describes
(the user asked for this on 2026-10-19 after two findings were withdrawn:
"please carefully test so that you don't incorrectly assume a bug"). A
reviewer agent (Phase 10.3 step 6) drives the same Playwright MCP browser as
this session: while one is active, run no browser step here (on 2026-10-20 a
walk script landed on the reviewer's page and a stray click opened a new
order); queue the step until the agent reports.

Status updates: at the end of every phase, and whenever a background wait
(suite, build, CI, Docker) runs past ten minutes, post a short status block
to the user: phase and verdicts so far, what was tested and what passed, the
defects found and which are being fixed, where the fixes are (branch, PR,
commits), what is waiting on what. The user asked for this three times during
the 2026-10-19 run and twice in the 2026-10-18 session ("what's the current
status of things", "tell me a detailed status, what you tested, what passed,
what you're fixing", "where are you pushing the fixes").

The same tiers apply to every fix in Phase 10: the regression matrix after a
fix re-runs the Tier 1 cases of every core functionality the changed files
reach, not only the failed case.

## Phase 10: fix the defects

The run tests published images, but fixes are made now, not in a later
ticket. `$RT state set phase fixing`. Where a fix is made and tested depends
on what broke:

| Defect | Fixed in | Tested on |
|---|---|---|
| Migration: a changeset, a failed upgrade boot, data or metadata a changeset breaks | application checkout | this openelis-docker compose project only (local WAR mounted, whole upgrade rerun) |
| Bug on the upgraded version after a clean migration: backend, front end, configuration loader | application checkout | the dev server (dev stack), then confirmed once on the upgraded instance |
| Deployment: compose, `.env`, `configs/`, nginx, image wiring | this repository | this compose project |
| Test data: inconsistent demonstration data or metadata the run created | the run's data (and this skill's recipe) | this compose project |
| Environmental: host memory, Docker, MCP | nothing | recorded |

Write the defect register first (`ui/defects.md`: id, title, severity,
workflow, reproduction, evidence, cause class from the table), then work every
CRITICAL, HIGH and MEDIUM defect, and every LOW one that is cheap. A baseline
defect that also exists in the release is still fixed when it is CRITICAL or
HIGH; otherwise it is listed for the recommendation.

**One pull request for the run.** The first application fix opens a draft PR
to `DIGI-UW:develop` (from the fork, following the `resolve-issue` gates:
failing test first, minimal general fix, targeted tests, full backend suite in
an isolated copy before the first push, cold spotless in the maven container,
no AI attribution, concise body, CI watcher). Every further issue discovered
on the upgraded instance, migration or application, is a new commit on that
same PR, and the PR body's issue list grows with it. Merge only when the user
says so. If Jira (Atlassian MCP) is connected, one issue per defect, keys in
the commits; otherwise the commits reference the defect ids.

### 10.1 Test data or defect?

Before any code change, rule out the run's own data. A symptom is caused by
test data when it disappears with consistent data:

1. Was the failing record or file created by this run (`RT<run>` stamp,
   `db/demo-manifest.md`, the run's configuration files)? If not, it is not
   test data.
2. How was it created? UI-created records are what production has; REST
   fallbacks, adapted or hand-written metadata files, and anything created out
   of order (a result before its test was mapped to the sample type, a range
   for a test that does not exist) are suspects. Compare it field by field with
   what the UI writes and with the example metadata in the app repository.
3. Reproduce with a fresh, consistent record created through the UI with
   Playwright MCP on the same build (or the app repository's example file
   copied verbatim). It works: the cause is TEST DATA. It fails the same way:
   it is a defect, continue with 10.2 / 10.3.
4. If the same data failed the same way on the release baseline (Phase 4),
   that points at the data too; record it.
5. Configuration default or UI step, not a defect? Before registering a UI
   finding: screenshot and read the page after the action; answer every
   modal (the result alert modal left unanswered looked like "an
   out-of-range value is silently discarded"); re-read any two-step control
   ("Send for retest needs two clicks" was its visible confirmation step);
   check the `site_information` setting behind the behaviour (name
   charsets, allow duplicate national ids, alertWhenInvalidResult: duplicate
   ids and dropped accented characters were defaults, not bugs); read the
   handler code; reproduce once more from a fresh page. A single occurrence
   is "observed once", not a defect. (2026-10-19: VAL-2 and RES-2 withdrawn,
   PAT-1/PAT-2 reclassified after the user asked for careful testing.)

For TEST DATA: correct the run's data or file the proper way (through the UI,
or a corrected file plus a reload), re-test the affected cases live, record it
in the register as "test data, not a product defect" with the evidence, and
fix the recipe in this skill (`references/data-integrity.md` or
`configuration-metadata.md`) so the next run does not repeat it. No product
PR. One exception: when the UI, the API or a loader accepted the inconsistent
input without a validation error, that acceptance is a product defect of its
own (validation gap, severity by impact), fixed through 10.3; the downstream
symptom is not counted twice.

### 10.2 Migration defects: loop on the compose project until clean

Migration fixes are tested directly on this openelis-docker compose project,
never only on the dev server: only this stack holds a database the release
created and filled.

1. Diagnose from Phase 7 evidence (failed changeset, `Reason:` line, partial
   state). Write the failing test the app repository supports for it
   (changeset or data-migration test); the upgrade on this stack is the
   acceptance test either way.
2. Fix in the application checkout. A changeset a release already applied is
   never edited (its checksum is recorded): guards and corrections go into a
   new changeset. No `validCheckSum`, no marking as ran.
3. Build: `mvn -f <app>/pom.xml clean install -DskipTests -Dmaven.test.skip=true`
   (`clean` matters), then `$RT local-fix war <app>/target/OpenELIS-Global.war`:
   the WAR is mounted over the webapp's WAR path in this compose project
   (`compose.local-fix.yml`). `unzip -l` the WAR to confirm the new changeset
   is inside.
4. Rerun the whole upgrade from the release state: `$RT restore-run` (it
   restores the database, the run configuration directory and the run
   properties directory from `backup/`; on 2026-10-19 the properties files
   of attempt 1 leaked into the retry and set site information at boot
   before the fix did that), `$RT switch develop`, `$RT wait 540` (repeat on exit 4), `$RT logs develop-boot-retry<n>`,
   `$RT verify-running develop`, `$RT liquibase-verify` (expected set from the
   local WAR), configuration load verification, `$RT snapshot after`,
   `$RT compare before after`, the metadata migration checks, and the
   retrieval of every demonstration record through Playwright MCP. When the fix
   touches what the release side wrote, or the backup's state is in doubt,
   start over from Phase 1b with `$RT init --new` instead (the WAR stays
   built).
5. Not clean: back to step 1 with the new evidence. Clean (Liquibase YES,
   configuration load YES, integrity clean, records retrieved in the UI):
   commit the fix to the run's PR, push, and continue with Phase 8 and 9 on
   this stack, the local WAR still mounted.

### 10.3 Bugs on the upgraded version: fix on the dev server

After a clean migration, defects in the application itself (backend, front
end, configuration loaders) are fixed and tested on the dev server, in the
application checkout:

1. Memory: the release stack and the dev stack do not fit together on this
   host. `$RT stop` (containers and data kept) before starting the dev stack,
   `$RT start` after.
2. Reproduce on the dev stack through Playwright MCP. If it does not
   reproduce there, the difference is the data: recreate the upgraded
   instance's data on the dev stack through the UI; if it reproduces only on a
   migrated database, it is a migration defect after all (10.2).
3. Failing test first, then the fix; targeted tests, the full backend suite in
   an isolated copy, front-end tests and lint where touched, formatting.
   The isolated copy is an rsync that excludes only `.git`, `target`,
   `frontend/node_modules`, `frontend/build` and `projects/catalyst`, never
   `projects/` as a whole (HarnessDictionaryIntegrationTest and
   MenuConfigurationLoaderTest read `projects/analyzer-harness`; two false
   failures on 2026-10-19). The full suite runs once per push, before the
   first push of the PR and before a push that touches test infrastructure;
   a follow-up commit gets the classes its files reach plus the new tests,
   red on the previous code then green. Delete the copy's `target/` when
   done (disk, Phase 0). Cold spotless: the maven container has no npm, so
   the Markdown step fails on every run; use the scoped helper
   `claude-work/bin/spotless-docker.sh check <app> <base> <head>` (or
   `apply`), which limits spotless to the changed Java and XML files.
4. Live test on the dev stack, through Playwright MCP and the API: the fixed
   case, every function the changed files reach, and a regression matrix of
   every existing workflow and scenario those files touch (order, results,
   validation, reports, admin, as the `resolve-issue` skill describes), so no
   regression slips in. Fix every regression found the same way.
5. Commit to the run's PR, push, watch CI until green.
6. Independent review: spin up a separate reviewer, a fresh session with no
   context from this run (the `review-pr` skill on the PR, through the
   headless reviewer CLI or a fresh agent), and address every finding with
   the same test and live-test gates. Tell the reviewer the PR head to pin
   and that the release stack is read-only for it; it shares this session's
   Playwright MCP browser, so no browser step runs here until it reports
   (Phase 9). Optional findings that name a real defect are fixed in the
   response commit too (2026-10-20: five optional findings, all real).
7. Confirm on the upgraded instance: build the WAR, `$RT start`,
   `$RT local-fix war <war>` (front-end fixes: `local-fix frontend`), and
   re-run the failed test cases and their neighbours through Playwright MCP.
   No migration rerun unless the WAR changed changesets.

### 10.4 Deploying local artefacts into the stack

The fix is not on Docker Hub, so the stack runs it from local artefacts;
`verify-running` and the report show exactly what was mounted (path, sha,
commit, dirty/clean):

- Backend or Liquibase change: the WAR, as in 10.2 step 3; `$RT wait` after.
- Front-end change: `npm --prefix <app>/frontend ci` once if `node_modules`
  is stale, `npm --prefix <app>/frontend run build`, then
  `$RT local-fix frontend <app>/frontend/dist` (mounted over the nginx root).
- Database image or several images at once: build locally with the
  application's own Dockerfiles (`docker build -f <app>/db/Dockerfile -t
  itechuw/openelis-global-2-database:rt-local <app>`, likewise `Dockerfile`
  for the backend and `frontend/Dockerfile` for the front end; the backend
  build runs Maven inside and takes long, so prefer the WAR mount) and
  `$RT local-fix image <service> <image:rt-local>`. Never push a local image
  to Docker Hub; the `develop` tags are published by the application's CI
  after the merge.
- `$RT local-fix show` lists what is active; `$RT local-fix clear` returns
  every service to the published images.

Record every re-verification in `ui/test-log.md` (same test ids, "after fix
<commit>") and the defect register (FIXED-LOCALLY with the PR and commit, or
OPEN with the reason the fix is out of reach).

### 10.5 Deployment fixes

Edit this repository (including missing example metadata for develop
domains), `$RT config <tag>` to re-validate, recreate the affected services
(`compose up -d` through `$RT switch`/`$RT up` picks the change up), re-verify
live through Playwright MCP, then commit on a branch from `main` and open a
pull request to `DIGI-UW/openelis-docker` from the fork.

### 10.6 Loop and stop

Repeat until the migration is clean and every triaged defect is FIXED-LOCALLY,
TEST DATA (corrected and re-tested) or has a documented reason it stays OPEN.
Do not weaken a test, mark a changeset as run, or change the test data to get
past a real defect (10.1 is the only legitimate data correction, and it needs
the consistent-data reproduction as evidence). Leave the local fix mounted at
the end so the final state is reproducible; `local-fix show` goes into the
report. `$RT state set phase fixed`.

## Phase 11: release-readiness report

`$RT report-skeleton` creates `release-reports/openelis-release-readiness-<run-id>.md`
from `references/report-template.md` with the environment facts filled in.
The report is detailed: someone who was not there must be able to follow the
whole migration and judge every result from it. It covers the migration
process step by step with timestamps (release boot, data and metadata loaded,
backup, switch, each upgrade attempt with its verdicts, what failed and why,
the fix and the rerun), the configuration metadata per domain (release load,
develop load, migration, forced reload), every issue found with its cause
class (migration / application / deployment / test data / environmental) and
how it was told apart, what was tested and how (each workflow and edge case,
live through Playwright MCP, with screenshot paths), what was not tested and
why, the fixes with commits, the PR and its review outcome.
Complete every section: executive summary with exactly one overall status
(READY FOR RELEASE / READY WITH KNOWN NON-BLOCKING ISSUES / NOT READY FOR
RELEASE / BLOCKED, INSUFFICIENT EVIDENCE) and the counts; environment (no
secrets); Liquibase results with the explicit YES/NO/INCONCLUSIVE answer for
the published images and, separately, for the local fix; data integrity
(verified vs not performed); workflow results per workflow; defect register;
fixes applied with their PRs and re-verification evidence; recommendation
(the nine questions); final state. Link evidence by relative path. Never
overwrite an earlier report (the file name carries the run id). Rules of
judgement:
- the application starting is not readiness; a healthy start with a NO or
  INCONCLUSIVE migration verdict is NOT READY or BLOCKED,
- the status describes the **published** images. A defect fixed and
  re-verified only on a local WAR or image keeps the status at NOT READY FOR
  RELEASE (or BLOCKED) until its PR is merged and the develop images are
  republished; the recommendation then says: merge the listed PRs, let CI
  publish `develop`, and run this skill again on the republished images,
- untested is never PASS; a core workflow untested for an environmental
  reason lowers confidence and is said so,
- a defect present in the release baseline is not a regression but still
  counts for the recommendation.
`$RT state set phase reported`.

## Phase 12: final state and clean-up

Default: `$RT teardown` (containers and network removed, named volumes, the
database directories and the backup kept; it also restores the two tracked
log placeholders `configs/logs/oeLogs/log` and `configs/logs/tomcatLogs/log`
the webapp writes into, so the docker checkout is clean again, as on
2026-10-20). If the user asked to keep the
stack running for their own look, `$RT stop`/leave it and say so. Restart any
container you stopped in Phase 0. State in the final message: which tag is
running or that the stack is down, which local fix was mounted, the database
directories, the backup path, the report path, the open PRs, and the overall
status. Remove only scratch extraction directories (`db/changelogs-*`) if
space is short; everything else is evidence.

## Phase 13: retro

Invoke the `session-retro` skill as the last step (the user asked that every
run of this skill ends with it, 2026-10-16). It audits this session and
improves this skill, its references and the memory from what happened:
commands that failed or were retried, waits that ran long, selectors that
broke, fixes that needed more than one round, anything the user corrected.
Its findings go into this skill's files in the skills repository
(`claude-dev-skills/openelis-docker/prepare-for-next-release/`) and its
`CHANGELOG.md`, committed and pushed to `mozzy11/claude-dev-skills` like
every other skill change.

## Final message

Written for the release manager, and detailed, not a one-line status. Lead
with the overall status and the Liquibase and configuration-metadata answers,
then: the migration process as it happened (attempts, failures, fixes,
reruns, the clean result), the issues found with severity and cause class
(test-data findings listed separately from product defects), what was tested
live through Playwright MCP and what was not, the counts, the fixes, the PR
and its review outcome, the report path, and the final state of the
environment. No passwords, no secrets.

A PR comment on the run (when the user asks to post it on the PR) is the
report summary only, under about 15 lines: status, the Liquibase and
configuration answers, the fixes, the open items, the next step and the
report path. No retro or skill content, no migration narrative (2026-10-20:
the first post was the full closing message and the user asked for "just a
report summary").
