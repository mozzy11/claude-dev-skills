---
name: resolve-issue
description: End-to-end Jira issue resolution — read the ticket fully, sync the repo, implement with verified tests, live-test every changed function carefully through the real UI (Playwright MCP) and the API on the dev stack before any push, plus a regression matrix walking every existing workflow and case scenario the changed files reach so nothing that worked before breaks, open a draft PR from develop, drive CI green, flip to ready, take one mandatory independent review from a fresh unbiased session and address it, update Jira. Trigger: "resolve issue <Jira link or key>", and every other coding task the user gives (a pasted brief, a bug description, a one-line request) unless the user explicitly says not to.
---

# Resolve Issue — end-to-end pipeline

Given a Jira issue link or key, run the whole pipeline **100% autonomously**.

**Every task, not only Jira tickets.** A brief, a bug report or a one-line request
runs this same pipeline; without a ticket only the Jira steps (§1 ticket read, §8)
fall away, and §7 the independent review is never skipped unless the user says so
(2026-10-18: a six-issue brief, PR #4757, was reported done with CI green and no
review; the user: "you're supposed to follow the resolve skill for every task").

**Never ask the user anything.** No permission requests, no "shall I…?", no
"which option do you prefer?", no AskUserQuestion — the trigger phrase is the
complete authorization for every step below (read, sync, implement, test,
commit, push, draft PR, CI, ready, independent review, Jira). When something is ambiguous, decide
it yourself from the ticket, the code's existing conventions, and the safest
backward-compatible option; record the decision and its reasoning in the PR
description's "Assumptions" section so the reviewer can overrule it there.
The only reason to stop is a hard external block (no access to a required
system) — and then you report what was blocked and what you completed, not a
question.

> **NON-NEGOTIABLE: FIX EVERY BUG IDENTIFIED WHILE DOING THE WORK (user
> instruction, restated 2026-09-27 after I listed bugs found in the walk as
> "out of scope, seen live").** Every bug found while implementing, testing,
> live-walking or reviewing a change is **related to the change** and is fixed
> in the same PR, with a failing-first test, a live UI walk and a general fix
> (see the general-fix rule above). That covers every screen, endpoint, report
> and workflow step the walk touches (order entry -> results -> validation ->
> reports, and any report or export the user asked to check), not only the
> files in the diff.
> - A final report may **never** contain an "out of scope, seen live" list of
>   bugs from the walk. If one is found, fix it, re-walk, then report it
>   under "fixed". A PR "Notes" line saying a defect the walk saw is "left
>   for a separate pass" counts as such a list (2026-10-12: OGC-1448 noted
>   "other pages lack an h1"; the user asked for it to be fixed in the PR).
> - The only thing that may be left is a genuinely unrelated area of the app
>   that the walk never exercised; name it in one line and ask whether to take
>   it on. Product decisions get the safest default, implemented, and named.
> - Reviewers (review-pr) mark such unfixed, walk-found bugs as Required.

> **NON-NEGOTIABLE, READ FIRST: GENERAL FIX, NEVER A LOCAL-ONLY FIX (user
> instruction 2026-09-27, after I "fixed" failing data exports with a `chown`
> inside the local dev container and reported it as solved).**
> Every bug found, in any environment, gets a **general fix that is committed,
> pushed and shipped in the product** (code, Dockerfile/Dockerfile.dev,
> entrypoint, Liquibase, compose/installer templates, CI), so a fresh install,
> an upgraded install and every deployment shape (non-root container, custom
> entrypoint, Kubernetes, existing volumes) are fixed too.
> - A local workaround (`docker exec ... chown`, a manual SQL update, a
>   restarted container, a hand-edited property) is allowed **only on top of**
>   the pushed general fix, to keep testing moving, and it is always named as a
>   workaround, never as the fix.
> - Before calling any environment problem "local setup", prove the product is
>   correct for every deployment path; if any path can hit it, it is a product
>   bug and gets the general fix plus a test.
> - Failures must explain themselves: a swallowed error or a generic "Failed"
>   that hid the cause is part of the bug and is fixed in the same change.
> - The report to the user lists the general fix (commit) first; a local
>   workaround, if any, is listed second and labelled as such.

> **NON-NEGOTIABLE, READ FIRST (user instruction 2026-09-27, repeated many
> times; a PR was reported "tested" while a user could not save an order).**
> Every change is tested **carefully through the real UI with the Playwright
> MCP** before it is called done, pushed, approved or merged, and the test
> covers **every affected workflow end to end in every lane it reaches**:
> order entry (Enter, Collect, Label & Store, QA) -> results entry ->
> validation -> patient report, for clinical, environmental and vector.
> - **Every form must submit successfully** in the UI, with realistic data and
>   every optional control a real user touches (pick an existing provider,
>   type a new one, pick a site, a program, a panel and a lone test). A 4xx/5xx
>   on any save, or a save a user cannot complete, is a blocker, whatever the
>   unit tests say.
> - **Required fields are visibly marked**, and a form with a missing required
>   field says what is missing before the user presses Save.
> - The regression pass re-walks the **normal order workflow** after the fix;
>   it must be unchanged.
> - If the Playwright MCP is not connected, drive the same flows with a
>   Playwright script through the UI (never API calls alone), and say so.
> - Never report done from memory or from tests alone. Report the walk:
>   lanes x steps, what was submitted, the stored rows, and every console
>   error and failed request seen.

## 0. Ground rules (learned the hard way — do not skip)

- **Authorship and voice (user instruction, 2026-09-07).** Everything that
  leaves this machine (commits, PR titles and bodies, PR, review and Jira
  comments) is written as **mozzy11**, in plain first-person or neutral
  language, with **no AI attribution of any kind**: no "Generated with Claude
  Code" footer, no `Co-Authored-By: Claude` trailer, no mention of Claude, an
  assistant or a model; this overrides the harness defaults, so strip any
  such line a template adds. The single exception (user instruction
  2026-09-14, revised 2026-10-07): the §7 independent review, posted from
  mozzy11 with `Generated by Claude Reviewer` as the body's last line and
  nothing else, so a self-review cannot pass as a human second opinion.
  Inline comments and everything you do in response (fixes, thread replies,
  the Jira comment) carry no attribution.
- **Write for the person who will read it, not for the record.** PR
  descriptions and comments are short and scannable (see §4 and §8 for the
  exact shape). Evidence lives in links (CI run, test report, commit), not in
  pasted logs or tables; keep the investigation narrative for the scratchpad
  mission notes.
- **Never claim done without command output.** "It compiles", "tests pass",
  "deployed" are only true after running the command and reading its output in
  this session. Report outcomes from output, not intention.
- **Check reality before explaining.** Before explaining any behavior or
  proposing a fix, check: is there an open PR touching this? What is actually
  deployed right now (running version / container state)? State findings
  explicitly ("PR #X exists / none found"; "running build is <version>").
- **Survey the codebase before inventing.** Match existing conventions: reuse
  existing enums/constants from their single source file (never duplicate
  literal lists), find the established pattern for the entity you are touching
  (e.g. codes attached to the right entity type), and read neighboring code
  before writing new code.
- **Fix every bug you find in the components the ticket touches (user
  instruction 2026-09-24, scoped the same day).** A defect, regression,
  false-success message, 500, stale data or wrong label you discover in the
  screens, endpoints and services the change touches (or their direct callers)
  is fixed in the same PR, with a test that fails without the fix and a live
  UI + API check; never park those as follow-ups. True product decisions get
  the safest default, implemented and named under Assumptions. Anything found
  in a workflow the walk exercises is in scope and fixed (see the
  NON-NEGOTIABLE "fix every bug identified" block); only an unrelated app area
  the walk never touched is named in one line, with a question.
- **Never push unverified code.** Hard gate before every push:
  compile + the affected module's tests locally. CI is not the compile check.
  (A PreToolUse hook — `~/.claude/hooks/pre-push-gate.sh` — enforces
  compile + cold-format on `git push`; treat a block as your own failed gate:
  fix and re-verify, never work around the hook.)
- **Live-test the whole affected workflow before every push: UI *and* API,
  every changed function, carefully** (user instruction, repeated 2026-09-18,
  2026-09-21 and 2026-09-26: the step most often skipped and the one that has
  found the most defects). Unit and integration tests run against mocks, so
  they cannot see a config key the server publishes under a different name,
  a Liquibase changeset that never ran, a Carbon constraint, or a gate that
  blocks a real user. §3b is the gate: the function inventory driven through
  the Playwright MCP with each expected result written down first, the
  regression matrix (every existing workflow through a changed file, every
  case scenario, at every diff size, maximum coverage), the API probes with
  the stored row read back, and the config and schema assertions
  (`/rest/configuration-properties`, `databasechangelog`). Paste the
  evidence. If a live check contradicts a passing unit test, the unit test is
  wrong: a mock agreed with you. Keep a permanent Playwright spec for the
  workflow, and note that a long-lived dev DB can fail `onFail="HALT"` data
  gates that a fresh volume passes.
- **Definition of done is an observable end-state**, not an applied config: a
  command whose output proves the behavior (an HTTP probe, a DB row, a test
  run). Paste that output when reporting success; if you cannot reach the
  environment, say so and hand over the exact command instead of a claim.
- **Mission notes on long investigations.** Append to a scratchpad
  `MISSION-<issue>.md` as you go: confirmed facts, hypotheses ruled out (with
  the evidence that killed each), files touched, commands that work verbatim,
  exact next action. Update it on every significant finding — not at session
  end — so context exhaustion never loses the campaign. Timebox: if ~20
  minutes of digging yields no root cause, log the state and prefer the
  smallest safe mitigation over open-ended exploration.
- **Delegate read-heavy discovery to subagents** (Explore) when the answer
  needs sweeping many files: have them report file:line conclusions only,
  keeping grep output out of the main context.

## 1. Read the ticket — all of it

- Fetch the Jira issue via the Atlassian tools: description, acceptance
  criteria, **every comment** (including corrections/withdrawals in later
  comments — the newest comment wins over earlier claims), linked issues,
  remote links, attachments, FRS/design references.
- If referenced artifacts (QA repos, run reports, design docs) are not
  accessible, say so explicitly in the PR later — do not guess their contents.
- Treat reporter hypotheses as leads, not conclusions. Reproduce before
  fixing: a reported correlation (e.g. "session-scoped") may be an artifact of
  how it was observed. Get the actual stack trace / failing output first.
- If requirements are unclear or conflicting, resolve them yourself: the
  ticket's newest comment wins, then the code's existing conventions, then the
  safest backward-compatible behavior. Write the resolution into the PR's
  "Assumptions" section — do not stop to ask.

## 2. Sync the repository

- `git status --porcelain` first — if the working tree has uncommitted work
  that is not yours, stash or stop; never reset over it.
- Fetch upstream; update local `develop` to `upstream/develop`. PRs here are
  squash-merged, so after a merge just `git reset --hard upstream/develop` and
  force-push the fork — no "lost commits" analysis needed.
- **Everything flows through `develop`**: commit on local `develop` → push to
  the fork's `origin/develop` → PR from fork `develop` to upstream `develop`.
  One open PR at a time keeps that flow unambiguous.

## 3. Implement

- Root cause before code: reproduce the bug locally (live stack if needed) and
  capture the real error/stack trace. Fix causes, not symptoms.
- Minimal, focused diff. No drive-by refactors. No inline explanatory comments
  inside method bodies — rationale goes in the commit message or Javadoc.
- Multi-part work → one meaningful commit per logical piece; small fix → one
  clean commit. Reference the Jira key in the commit subject. Commit body:
  a few plain sentences on why, no trailers (see §0 Authorship — no
  `Co-Authored-By` lines).
- **A new Playwright spec seeds every precondition through the app's API**
  (checklist items, enrollments, cycles, reference data) and removes or
  retires what it created; data that only the dev DB has is not a
  precondition (2026-10-14: ogc-1488 passed locally and failed in CI, which
  has no acceptance checklist, #4731). **When the change alters user-visible
  text** (a toast, label or message), grep `frontend/playwright` and
  `frontend/cypress` for the old text and update every spec and helper in the
  same commit (2026-10-14: the save-toast change broke three vector demo
  specs in CI, #4731).
- **Tests for every changed behavior**, and **inversion-verify each new test**:
  revert the fix, watch the test fail, restore the fix. After inversion
  testing in an isolated copy, delete `target/` or rerun clean — stale
  inverted bytecode has produced false failures before.
- Project specifics that recur (OpenELIS):
  - `frontend/src/languages/en.json`: edit **in place** (targeted
    replace/insert) — never re-serialize the whole file. New keys in en.json
    only; Transifex owns other locales.
  - Backend suites run in an **isolated copy** built with `git archive <sha>`
    (IDE rebuilds corrupt in-repo `target/`) through
    `claude-work/bin/iso-suite.sh <repo> <sha> <copy> <log> [-Dtest=...]`, never a
    `cd <copy> && mvn` chain (2026-10-15: that chain prompted again); run the **full** backend suite
    on the exact head before the first push of a PR — order-dependent
    failures are real here. A suite-only failure usually means a sibling
    fixture replaced a table the test reads (system_role, site_information,
    the test catalogue, the delivery channels): make the test create its own
    rows with an `ensure*` helper and reset shared state in its cleanup
    (2026-10-16: three suite-only failures on #4755, memory
    `project-test-fixtures-replace-system-role`). Launch the suite with the
    Bash tool's `run_in_background` (its exit wakes the session) and go on
    with the next step; never grep its log by hand (2026-10-16: 211 grep
    polls of suite logs in one session while every suite already ran in the
    background). **A review-response or CI-fix push on an open PR
    goes out as soon as the targeted tests, their inversion and the live check
    pass**; start the full suite on that head at the same time and treat it as
    part of the merge gate, not the push gate (2026-10-14: "where is the fix
    pushed ??" and "all checks are green ... can you respond to the review"
    while finished fixes waited on the local suite, #4723, #4728).
  - Formatting: run spotless **cold** in the CI-matching container through
    `claude-work/bin/spotless-docker.sh <apply|check> <repo> [<base> [<head>]]`
    (scopes to changed Java/XML/Markdown; Markdown goes through Prettier, which
    #4748 failed CI on, 2026-10-15; `check <repo> all` for a full check); local
    warm caches hide violations CI will flag. Never hand-build the
    `docker run ... $(git diff ...)` one-liner: it prompted five times on
    2026-10-13 (session ae493b76).
    Spotless also formats XML test fixtures (`src/test/resources/testdata/*.xml`):
    include changed fixtures in the `-DspotlessFiles` regex, or the push hook
    blocks the push (2026-10-12). Prettier for frontend, and for any
    Playwright spec or fixture change run `npm --prefix frontend run lint`
    (CI's Static check fails on a single warning, e.g. `.catch(() => {})`;
    2026-10-12, #4685). Run frontend tools through `npm --prefix frontend
    test|run ...`, which runs in the frontend directory; `npm exec` keeps the
    caller's directory and cwd-relative tests then fail.
  - Disk: before a full suite, a WAR build or a docker build, check
    `df -h /System/Volumes/Data`; below 10 GB, delete the isolated copy's
    `target/` and old suite logs first. A full disk stops every tool, even the
    shell (2026-10-12).
  - Live-test on `dev.docker-compose.yml` (never build.docker-compose.yml).
    After `mvn clean install`, `docker restart` fails on the stale WAR mount —
    use `docker compose up -d --force-recreate <webapp-service>` and restart
    the proxy. On a `scripts/dev-stack` stack use
    `claude-work/bin/devstack-compose.py <repo> up -d --no-deps
    --force-recreate oe.openelis.org` (dev-stack's own project, files and
    env; plain compose fails on DEV_STACK_PROJECT, and `dev-stack env`
    fails once the bridge or simulator is stopped, 2026-10-15). A
    `dev-stack up` rebuild changes the published port, so every probe script
    reads BASE_URL from `scripts/dev-stack env` at run time (2026-10-16: five
    ports in one session). A screen edited in a directory created after the
    Vite container started never hot-reloads: `docker restart` the frontend
    container (memory `project-vite-watcher-misses-new-directories`). Wait for the
    recreated webapp with the Monitor tool on `docker inspect --format
    '{{.State.Health.Status}}' <container>` until it prints `healthy`; a
    `sleep N; until ...` chain is blocked by the Bash hook (2026-10-15:
    twenty blocked retries in one session). Bound every Docker Desktop
    restart wait (daemon back, containers up) to about 5 minutes; on expiry
    run the hang recipe in memory `project-docker-vm-readonly-kills-postgres`
    and report it, never wait silently (2026-10-16: 4 h idle on a hung
    restart until the user asked). Verify the deployed build by reading
    `WEB-INF/classes/build.properties`, not by trusting the restart. Probe
    APIs with the session cookie + `X-CSRF-Token` from the `/session` endpoint;
    use documented test credentials from `.env` — never hardcode credentials
    in scripts you commit.
  - Leave live-test data as you found it; clean up probe rows.

## 3b. Live-test gate (mandatory, before any push, in every pipeline)

The user has said this repeatedly and it is the step most often skipped:
**after the backend and frontend tests are written and green, live-test the
change on the dev stack through the real UI and the real API, carefully,
function by function, until every function the change touches has been
shown to perform as expected.** No push, no draft PR, no "ready" before
this section has produced evidence. It applies equally when this skill is
run directly and when `resolve-by-criteria` drives it, and it applies with
more depth, not less, when the diff is large.

**It covers the whole blast radius of the change, not the part you set out
to fix** (user instruction, 2026-09-23, after a change to a dashboard's SQL
and to a range comparison was pushed having exercised neither the dashboard
nor the critical tier). Before pushing, list every screen, report,
dashboard, export, scheduled job and endpoint that reads or writes what you
touched — find them by grepping the callers, not by recalling what you had
in mind — and drive every one through the Playwright MCP. Three corollaries,
each of which has bitten:
- **No exemption for size or layer.** A one-line fix, a SQL expression, a
  Hibernate mapping, a formatter change: all of it goes through the gate.
- **Verifying a layer in isolation proves that layer only.** A SQL
  expression checked in `psql`, a helper with a unit test, a green suite:
  none is evidence that the screen using it works, and none substitutes for
  driving that screen. If you changed a query a dashboard runs, you open the
  dashboard.
- **Missing fixture data is not a reason to skip a surface.** Create the
  order, the site, the threshold, the critical range through the UI or the
  API, then exercise the screen. If a surface is genuinely impossible to
  reach, say so **in the message that accompanies the push**, naming it as
  unverified — never leave it to be discovered when the user asks.
- **Make every check discriminating** (confirmed by the user on #4380,
  2026-09-23: "you should always do this"). An input whose expected outcome
  could also arise without the code under test proves nothing (`6.5×10¹` and
  plain `65` both gave 66; a fresh order with `8.5×10¹` → `86.0` was the
  proof). For every rule, threshold or branch drive **one value that must
  trigger it and one that must not**. A claim about an engine or a save
  stands only when **the UI row, the database row and the audit row agree**
  (the `notifications` table logs each reflex, calculation and alert firing).
  Use fresh records on distinct parents when a table is keyed per patient or
  per order. When the live run contradicts an earlier claim of yours, the
  claim was wrong: correct it in the same thread.

0. **Order save path changes need a re-save walk.** When the diff touches
   order save validation or a save side effect (notes, EQA rows, overrides),
   re-save one order at every later step (Prepare Samples, Label, Sample
   Check) for each specimen state it can reach: accepted, rejected in Sample
   Check, resampled, pool-rejected (2026-10-14: a duplicate `sample_eqa` on
   the Collect re-save was found in the walk, but duplicate rejection notes
   and an unsavable resampled order were found only by the reviewer, #4731).
1. **Deploy the exact code you will push.** `mvn clean install -DskipTests
   -Dmaven.test.skip=true`, `docker compose -f dev.docker-compose.yml up -d
   --force-recreate` for the webapp, restart the proxy, then read
   `WEB-INF/classes/build.properties` (and `unzip -l target/*.war | grep
   <Class>` for anything you removed) to prove the served build is yours.
2. **UI, via the Playwright MCP: every changed surface and every changed
   function, step by step, carefully** (user-scope server `playwright`;
   tools `browser_navigate`, `browser_snapshot`, `browser_click`,
   `browser_type`, `browser_select_option`, `browser_take_screenshot`,
   `browser_console_messages`, `browser_network_requests`).

   **Build two inventories from the diff before clicking anything.**
   - *Surface inventory.* `git diff upstream/develop...HEAD --stat --
     frontend/src`, then list every screen, menu entry, table column,
     filter, form field, **modal, dialog and drawer**, notification, empty
     state and error state the change touches, plus every other screen
     that reads the same data.
   - *Function inventory.* Read the full diff, frontend **and** backend,
     and list every function the change adds or alters, in user terms
     ("save a provider with a title", "reject a duplicate title", "filter
     the list by X", "export the CSV"). For each row write down, before
     testing it: the user action that exercises it, the expected result on
     screen, the request it should send, and the persisted state it should
     leave. One function is one row; a form with six controls is at least
     six rows.
   Write both lists into the mission notes as checklists. Nothing is ticked
   off until it has been exercised in the browser and the observed result
   matched the expected one you wrote down.

   Then walk it, one action at a time: `browser_snapshot`, one
   `browser_click` / `browser_type` / `browser_select_option`,
   `browser_snapshot` again, compare with the expected result, then the
   next action. Never chain several actions and check only the end state;
   a silent failure in the middle is invisible from the end. Log in with
   the `.env` test credentials, follow the ticket's reproduction steps end
   to end, plus the step before and after the change, in every lane the
   change reaches, and **exercise every row of both inventories
   individually**. Reading the component and reasoning that it must work is
   not testing it.

   Per function, non-negotiable:
   - **Happy path and negative paths.** The valid input, then the invalid
     input, the required field left empty, the duplicate, the cancel
     button, the boundary value. Every validation message the diff adds
     must be seen on screen once, and every error the server can return
     must be made to happen once.
   - **Open every modal and dialog, in both of its states**: created fresh
     (fields must start empty or at their default) and opened on an existing
     record (fields must be pre-filled from that record). These two states
     are where the defects hide. An add form that leaks stale state and an
     edit form that silently blanks a value both pass every unit test and
     both destroy user data in production.
   - **Round-trip every field the change touches**: set it, save, leave the
     screen, come back, confirm the value survived. A save that returns 200
     and drops the field is the most common defect in this codebase.
   - **Force each conditional branch to actually render**, every warning,
     notification, empty state and error path, instead of assuming it
     would. A missing import throws only when the branch renders.
   - **Both sides of every gate.** If the change sits behind a role, a
     permission or a config flag, test it with the flag on and off, and as
     a user who has the role and one who does not.
   - Read `browser_console_messages` and `browser_network_requests` after
     each step: a 4xx/5xx or a React error there is a defect even when the
     screen looks right.

   **Every row of the function inventory is tested individually, whatever
   the size of the diff**, and the regression matrix below is walked on
   top of it. Spot-checking is the same as not testing. A long inventory
   takes as long as it takes; this pipeline is allowed to be slow and not
   allowed to be sloppy.

   **Each row is clicked by hand through the Playwright MCP; a spec run
   never replaces one** (user instruction, 2026-10-15, after a review left
   five rows to the feature's own CLI specs). Playwright specs, including
   the ones you add, are extra evidence on top of the hand walk. A row
   counts as exercised only once you drove it yourself in the MCP browser
   and checked the screen, the request and the stored row; the same holds
   for every regression matrix cell.

   **Regression matrix: every case scenario the changed files reach
   (mandatory before any push, user instruction 2026-09-26).** The function
   inventory proves the new behavior works; this matrix proves the old
   behavior still does. Build it from the changed files, not from memory:
   - *Per changed file, list its consumers.* Frontend component or util:
     grep its imports up to the routes/menu entries that render it. Java
     service, DAO, valueholder, mapping or SQL: grep the callers up to the
     controllers, then the screens, reports, exports, dashboards and
     scheduled jobs behind them. Shared code (a formatter, a validator, a
     common component, a base DAO) fans out widely; every consumer goes on
     the list. Delegate the grep sweep to an Explore subagent on a wide
     fan-out and keep only the consumer list.
   - *Per consumer, list its workflows*, including the ones the ticket never
     mentions: the list, search, add, edit, delete, print, export and
     navigation on that screen, and the upstream and downstream steps
     (order entry -> results -> validation -> report for a lab flow).
   - *Per workflow, list its case scenarios*: happy path; each negative
     path (invalid, empty, duplicate, cancel, boundary); each lane or
     variant (sample type, test type, result type numeric/dictionary/text,
     patient with and without optional data, single and multiple rows);
     each data state (no records, existing records created before the
     change, legacy or null values in the touched columns); each role and
     config gate on and off; and each locale-sensitive or date-sensitive
     input when the change touches formatting.
   - *Lab data shapes, whenever results, validation or a report are
     touched* (2026-10-15, OGC-932: the user asked twice; this walk found a
     unit breaking mid-word, "<LOD" printing blank and an aliquot crashing
     the report): a multi-component test (one component hidden from the
     report, one left empty), a multi-sample order and an aliquot whose
     primary has no test of its own, an order with no results, partial and
     completed orders, and results below/above normal, critical low/high
     (with the acknowledgement), outside the valid range, and text results
     containing "<". Walk each through entry, validation and the printout.
     A change that adds a partial state (one part validated while its test
     is not) walks every surface that reads the whole record's status in
     that mixed state: the Results status column and chips, the save
     response's sibling rows, Validation, the printout (2026-10-19, #4757:
     per-part validation shipped, and the user found Results showing every
     part "Accepted by technician" and the report only "Awaiting validation").
   - *Dates, whenever a date is parsed, formatted or defaulted*: walk it on
     a month-first and a day-first site (flip DEFAULT_DATE_LOCALE in Site
     Information), and test the component with the settings arriving after
     the first render (2026-10-15: a picker kept the month-first format it
     was created with; only CI's day-first run caught it).
   - *Baseline where the outcome is not obvious.* When the expected
     behavior of an existing scenario is uncertain, drive it on
     `upstream/develop` first (the reproduce round is the natural time) and
     record what it did; after the fix the same scenario must behave the
     same unless the ticket says it should change. A difference the ticket
     did not ask for is a regression until proven otherwise.
   - *Walk every cell* through the Playwright MCP exactly like the function
     inventory: snapshot, one action, snapshot, compare, console and
     network panes clean. Then run the existing Playwright specs that cover
     those screens (`npm run pw:test*` filtered to them) against the same
     stack. Find them by grepping `frontend/playwright/tests` for each
     changed route, test id and REST path, not only the spec you wrote
     (2026-10-14: OGC-1466 ran its own spec only; ogc-1194 on the same
     import screen failed in review because a preview stopped recording
     names).
   For an access or scope change (lab units, roles, ownership), the matrix
   lists every endpoint that lists, counts, opens or writes the entity, found
   by an Explore sweep of the routes and controllers, not only the screens
   the request names; check each one as at least two scoped users plus admin
   (2026-10-18: PR #4757 scoped the order screens only; the user asked about
   vector and environmental dashboards and the sweep found nine more
   unscoped lists).
   Write the matrix into the mission notes as a checklist (consumer ->
   workflow -> scenario -> expected -> observed). The push is blocked until
   every cell is ticked or explicitly named as unreachable with the reason.
   Any regression found is fixed in the same PR with a test that fails
   without the fix (§0 "Fix every bug you find"), then the matrix is walked
   again on the new build.

   Keep a screenshot of each surface in its fixed state and record in the
   mission notes, per row, what was done and the expected and observed
   result. If something on either inventory was never exercised, it was not
   tested: say so plainly in the PR instead of implying coverage that does
   not exist.
3. **API, function by function.** Session + `csrf` from
   `GET /api/OpenELIS-Global/session`, then one call per function-inventory
   row that lives server-side, with the cookie + `X-CSRF-Token`: the valid
   request, and the invalid input each validation must reject. Assert the
   status, the body, and the persisted row read back (a GET or `psql` in
   the database container). A 200 is not proof; the stored row is. For a
   new config property assert the key the server publishes on
   `/rest/configuration-properties`; for a Liquibase changeset assert the
   `databasechangelog` row and the object it creates.
4. **Permanent e2e spec.** Encode the same walk as a Playwright spec under
   `frontend/playwright/tests/` in the right project bucket, run it with the
   `npm run pw:test*` script (never raw `npx playwright test`), and follow
   `.specify/guides/playwright-best-practices.md` (no `force: true` on
   Carbon inputs, no `response.ok()` as the assertion). Locators use exact
   names (`getByLabel("Port", { exact: true })`, `getByRole("heading", ...)`),
   scoped to the mounted panel, with `.last()` for a stacked dialog's Close;
   a label substring or a hidden tab's toast fails strict mode (2026-10-16:
   five locator retries on the ogc-439 spec). The spec is a
   regression guard for the next change; it does not replace the manual
   Playwright MCP walk above for this one.
5. **Record the evidence** in the mission notes: the two inventories and
   the regression matrix with expected vs observed per row and both tallies
   (functions inventoried / exercised / passed; regression scenarios
   listed / walked / passed), URLs walked, request/response pairs, the row read
   back, the screenshot path. Paste a one-line summary of it in the PR's
   "How it was tested" and cite it in the Jira comment.

If a live check contradicts a passing unit test, the unit test is wrong: a
mock agreed with you. Fix the code, then fix the test.

## 4. Draft pull request

> Note: this supersedes the earlier flow of opening PRs directly as
> ready-for-review — create as **draft** first, flip later (newest
> instruction wins).

- Push `develop` to the fork; open a **draft** PR targeting upstream
  `develop`.
- Title: conventional-commit style with the Jira key.
- Description: **short and readable by the actual user in under a minute** —
  aim for 10–15 lines, four small sections, plain sentences, no tables of
  test counts, no pasted logs, no scratch details or transient ids:

  ```
  Fixes OGC-NNNN.

  **What changed**
  - 2–4 bullets, one line each, in user terms (what a lab user or admin sees).

  **Why**
  - 1–2 lines: the problem or root cause, in plain words.

  **How it was tested**
  - 1–3 lines: unit/integration suites green, live check on dev compose
    (name the functions walked in the browser and via the API, and
    anything on the inventory that was not exercised), CI green — link the
    run rather than quoting it.

  **Notes**
  - Only if needed: assumptions the reviewer may overrule, follow-ups,
    anything not verified and why. Omit the section when there is nothing.
  ```

- No footer, no signature, no "Generated with …" line (§0 Authorship).
- Squash-merge commit body (when merging is instructed): the same four
  sections compressed to 3–6 sentences, again without trailers.

## 5. Monitor CI to green

- Poll `gh pr checks <n>` (or `claude-work/ci-watch.py`) with the Bash tool's
  `run_in_background`, or arm a Monitor on its log, so that completion wakes
  the session; never detach it with `&` or `( ... &)`, which never notifies.
  Do the same for the reviewer: a Monitor that waits for its process to exit.
  Report a red check or a posted review the moment it lands, before the user
  sees it (2026-10-14/15: the user reported "also fix e2e failure" and "the
  PR ci failed and the reviewer posted" before the session did).
- On failure, read the failing job's log (`gh run view --log-failed`) before
  changing anything. Known recurring causes in this repo:
  - Spotless cold-run skew (fix: cold spotless locally, commit).
  - The E2E shared build pins the version the plugins submodule expects —
    version bumps must keep every component pinned.
  - `E2E / Tests` reads artifacts from its triggering `03 - E2E` run: rerun
    the **build** workflow, not the chained test workflow; a push to develop
    cancels in-flight develop runs (`cancel-in-progress`).
  - Transient Maven Central fetch failures → rerun, don't "fix".
  - Every shard failing at the Playwright install ("does not support
    chromium-headless-shell on ubuntuNN") → the runner image moved; the fix
    is a workflow change in its own PR, merged to develop first, because
    `E2E / Tests` is a `workflow_run` that reads develop's file; then update
    the feature branch (2026-10-19, #4764).
- Distinguish *caused by this change* from pre-existing/transient; fix the
  former, document the latter. Never mark ready while a relevant check fails.

## 6. Ready for review

- Final pass: effective diff is only the intended files
  (`git diff upstream/develop...HEAD --stat`), tests green, description
  current with what actually shipped.
- `gh pr ready <n>`. Ready is a gate, not the finish: §7 must still run.
- **Do not merge.** Merging (and any branch-protection override) happens only
  on explicit instruction, or under `resolve-by-criteria`, whose §3e merge
  gate also holds the blocker survey and the `enforce_admins` override
  recipe; run directly, this skill never merges on its own. A merge cancels
  in-flight develop CI (`cancel-in-progress`); don't chase the superseded
  run's failure as if it were real.
- Never dismiss or override another reviewer's CHANGES_REQUESTED without
  explicit instruction.

## 7. Independent review round (mandatory — at least one, before Jira)

Green CI is not the finish line. Every ticket takes **at least one review from
a session that has never seen this work**, so the approach and any regression
are judged on the diff alone and not on the reasoning that produced it. The
pipeline is incomplete until that round has happened and its findings are
resolved.

**Spawn the reviewer as a genuinely separate session, not a subagent of this
one.** Run it headless from the repo root as a background task, passing it
nothing but the trigger and the PR URL:

```bash
CLAUDE_BIN=$(ls -t ~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | head -1)
nohup "${CLAUDE_BIN:-/opt/homebrew/bin/claude}" -p "Use your review-pr skill: review PR <pr-url>." \
  --model opus --permission-mode bypassPermissions \
  > "<scratchpad>/review-<pr>.log" 2>&1 &
```

- **Prompt form.** Name the skill as above; a bare "review PR <url>" or the
  slash form does not load review-pr in print mode (2026-09-14). Keep `nohup`.
- **Identity.** The reviewer notices on its own that the PR author is the
  same GitHub account and posts the review from mozzy11 with the `Generated
  by Claude Reviewer` footer as its only attribution (review-pr §0), logging
  it to `review-<pr>.log`. You do not tell it to, never re-post it, and never
  ask the user to configure anything. Treat it like any posted review: fix
  every Required item, answer every finding, and keep the review text with
  your responses in the mission notes. Your responses are mozzy11 with no
  attribution.
- It loads the same MCP servers and, per review-pr §3, deploys the PR head
  and walks every changed function in the UI and the API.

- **The prompt carries no context, by design.** No ticket summary, no
  root-cause story, no "look closely at X", no hint that the branch is yours.
  Every extra word is bias; the PR and the code carry everything a reviewer is
  entitled to. Natural language is what fires the skill — its documented
  trigger is exactly "review PR <link>".
- **Background it** and arm the §5 Monitor on its exit; it takes tens of
  minutes and recreates the shared dev stack, so run no live stack meanwhile.
- **The action is the verdict, except on a self-review (user instruction,
  2026-10-07).** review-pr §5 submits a review of someone else's PR as the
  matching GitHub action with no "Decision:" line. On mozzy11's own PR
  GitHub refuses approve and request-changes, so a self-review lands as a
  comment event whose first line is `Decision: Approve`, `Decision:
  Request changes` or `Decision: Comment`, with the `Generated by Claude
  Reviewer` footer last. Read the verdict from that line, the Required
  section and the reviewer's last log line in `review-<pr>.log`.
  It therefore never satisfies the branch's approving-review rule; merging,
  when authorized, follows the path described in resolve-by-criteria §3e.
- Brevity and proportionality are review-pr's own contracts (review-pr §0);
  never ask it to soften or expand findings.
- If the CLI is unavailable, fall back to a `general-purpose` subagent with the
  same one-line prompt and the same silence about context.

**Then address it from this session:**

- Read the submitted review and every inline thread (`gh pr view --json
  reviews,comments`, `gh api .../pulls/<n>/comments`).
- Fix every blocking finding, or reply on its thread with the concrete reason
  it does not apply — no silent dismissals. Reply to each thread saying what
  you did, and resolve only the threads you actually acted on.
- Re-run the affected suites, push, and drive CI green again (§5). Update the
  PR description if the fixes changed what shipped (§4).
- **One round is the requirement.** Order a second only when your own response
  was itself substantial — new behavior, a new migration, a reworked approach.
  If a second round still leaves a blocking disagreement, stop and report it
  with both positions; never loop.
- Keep the review link; §8's Jira comment and the final summary both cite it.

## 8. Update Jira

> **Two Jira touch-points per ticket, each done immediately (user
> instruction 2026-09-29).**
> 1. **When the first draft PR opens:** transition the ticket to **In
>    Progress** and post a comment with the draft PR link and a 2-4 line
>    summary of the change.
> 2. **Right after the merge**, before cleanup, the develop reset, a deploy
>    check or the next ticket: post a comment naming the merged PR and the
>    issues it fixed, and transition the ticket to **In Review**.
>
> After each one, read the status back with `getJiraIssue` and confirm it
> changed. A merge is not finished until step 2 is done. Acceptance comes
> later, only once the change is on testing.
>
> **When Jira cannot be reached** (MCP disconnected or timing out), the first
> line of your very next message says which ticket step was skipped and asks
> for `/mcp`; repeat it at the top of every later message until done, and do
> the step as soon as the tool is back. Never only log it or mention it at the
> end of a summary (2026-10-12: OGC-1399 sat in Backlog with a PR open; the
> user had to ask "did you forget" and "why didn't you report").

- Move the ticket per the team workflow (In Progress when the draft PR
  opens, In Review after the merge; Acceptance only once the change is
  actually on testing.openelis-global.org —
  check the DockerHub `:develop` tag date / deploy run, not the run colour).
- Comment: **3–6 short lines**, readable by the product owner — what changed
  (user terms), the PR link, one line on how it was verified, and any heads-up
  for QA (e.g. an error contract change their specs assert on). No logs, no
  test-count tables, no AI attribution (§0 Authorship).
- Credit correct leads in the ticket; correct wrong ones with evidence,
  respectfully.

## Docs and IG pull requests

A green CI job is not a clean build. For the FHIR IG
(`DIGI-UW/openelis-global2-fhir-ig`) read the IG Publisher QA line in the
build log (`Errors: N, Warnings: N, Info: N, Broken Links: N`) and compare it
with the last clean build on main: errors and broken links must be 0, and any
new warning must be explained in the PR. Run SUSHI locally first
(`npx -y fsh-sushi build <ig>`). Never report a docs build as clean from the
job colour (2026-10-12: #21 merged with 1 error, 1 broken link and 1252
warnings behind a green job; fixed in #22).

## Docker teardown (once the work is done)

**When "done" is depends on who merges** (user instruction, 2026-10-16,
OGC-932: "where the PR doesn't auto merge, you tear down the session
artifacts after I manually validate and merge; that's when we consider it
done"):
- *The pipeline merges* (resolve-by-criteria, or the user said "merge"):
  tear down right after the merge, before the final summary.
- *The PR waits for the user's manual validation and merge* (the default for
  this skill): the work is **not** done at "ready + review addressed".
  Leave the stack running on the PR head (or `develop` once merged), with
  the claude-work copy and registered items in place, and give the URL and
  login in the final summary. Tear down and run `session-cleanup.sh` only
  once the user confirms they validated it **and** `gh pr view <n> --json
  state` says MERGED. Free memory meanwhile by stopping what the manual
  test does not need (analyzer bridge, simulator), never by removing the
  stack. Ending the session still triggers the SessionEnd cleanup hook.

Docker here has 7.6 GB and is shared with other sessions, so every stack this
session started is removed once the work is done (user instruction, 2026-10-12):
- **Register everything the moment you create it** (user instruction,
  2026-10-15: "as soon as a session completes its work, it cleans up the
  containers and volumes, data inserted, just not to fill up the memory"):
  `claude-work/bin/session-track.sh <kind> <value>` for every stack
  (`stack <copy-dir|project>`), container, cloned database
  (`db <container>/<name>`), claude-work copy or scratch dir (`dir`), local
  branch (`branch`) and long-running process such as Vite
  (`process <pkill pattern>`). `light-stack-up.sh` registers its own. Test
  data goes into a registered cloned database or an isolated stack, never
  the shared database.
- **When the work is done, run `claude-work/bin/session-cleanup.sh`** (no
  argument; it reads `CLAUDE_CODE_SESSION_ID`). It removes the registered
  items newest first, then prunes unused anonymous volumes (testcontainers
  leftovers) and dangling images; named volumes, the build cache and other
  sessions' items are never touched. The SessionEnd hook runs the same
  script as a safety net, so a session that ends early still cleans up; the
  log is `claude-work/run/sessions/<id>.cleanup.log`.
- Run `claude-work/bin/teardown-stack.sh <copy-dir-or-compose-project> ...`
  for every isolated stack, `dev-stack` copy or `-p` project you brought up.
  It removes containers, volumes, the project's built images and analyzer
  mock networks, prunes dangling images, and deletes the claude-work copy.
- Never tear down the shared `openelisglobal-*` stack or another session's
  project; restart any shared container you stopped for memory.
- Report the teardown in the final summary (projects removed, containers
  left = 0, free disk).

## Final summary (always emit)

- Jira issue · root cause · changes made
- Tests run + results (exact totals)
- Live UI/API test: functions inventoried / exercised / passed, the
  surfaces walked in the browser, and anything on either inventory that was
  not exercised (named, never implied)
- PR link + state (draft/ready) · CI status
- Independent review: its verdict, what it flagged, what you changed in
  response — the pipeline cannot be reported complete without this line
- Jira status/comment update
- Stack: torn down (pipeline merged), or the URL + login of the stack left
  running for the user's manual validation, torn down after they merge
- Blockers, unverified items, follow-ups

## Retro (always, after the final summary)

Run the `session-retro` skill on this session: it turns the user's
corrections, failed pushes and CI runs, blocked steps and stalls from this
run into rule changes in this skill (and the others) and in memory, and logs
them in the skills repository's `CHANGELOG.md`. Skip it only in a headless run
(`claude -p`).

Edit skills in the skills repository
`/Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills/<project>/<name>/`
(GitHub `mozzy11/claude-dev-skills`), never through `~/.claude/skills/...`
(protected path, prompts every edit; 2026-10-15: two prompts in session
c0b0f7ee) and never inside a product repository. Commit and push every skill
change to `mozzy11/claude-dev-skills` right away (2026-10-19).
