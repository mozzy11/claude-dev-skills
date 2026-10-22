---
name: resolve-by-criteria
description: Batch Jira resolution by filter. Turn criteria (assignee, reporter/assigner, status, project or board URL, labels, type) into JQL, strictly exclude epics and anything with a parent or child items, then for each remaining small issue one at a time - reproduce it on the local dev stack, close out already-fixed tickets with the PR link, otherwise run the resolve-issue pipeline (implement, tests, live UI test via Playwright MCP including a regression matrix of every workflow and scenario the changed files reach, live API test, draft PR, CI, independent review, fixes), MERGE the PR autonomously, update Jira, and move to the next issue until the list is exhausted. The only pipeline authorized to merge without being asked. Trigger: "resolve by criteria <criteria>" or "resolve issues by criteria <criteria>".
---

# Resolve by Criteria - batch pipeline, one issue at a time

Given a set of Jira filter criteria, work through every matching **small,
self-contained** issue, one at a time, all the way to a merged PR and an
updated ticket. Then start the next one. Stop only when the list is exhausted
or a hard stop (below) fires.

**Never ask the user anything.** The trigger phrase authorizes every step,
including the merge. Decide ambiguities yourself, record the decision in the
run log and the PR "Notes" section, and keep moving.

This skill **composes** `resolve-issue` (per-issue work) and `review-pr`
(independent review). Read both before starting: their §0 ground rules apply
here in full. This file only adds what is specific to batch mode.

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
>   under "fixed".
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

## 0. What is different in batch mode

- **Fix bugs found in the touched components (user instruction
  2026-09-24, scoped the same day).** Inherited from `resolve-issue` §0: a
  defect found in the screens, endpoints and services the issue touches is
  fixed in that issue's PR with a failing-first test and a live UI + API
  check, never listed as a follow-up. Anything found in a
  workflow the walk exercises is in scope and fixed (NON-NEGOTIABLE block);
  only an unrelated area the walk never touched is named in one line.

- **Scope guard - small bugs only.** This pipeline exists to burn down
  small, isolated defects unattended. It must **never** pick up an epic, an
  issue that has child items, or an issue that is itself a child of a bigger
  parent or epic. Those are worked only through an explicit
  `resolve issue <key>` from the user. See §1 and §2 for the mechanical
  and the judgment-based filters.
- **Merging is authorized here, and only here.** `resolve-issue` on its own
  merges only when the user says so. Inside this pipeline, once a PR has
  passed the §3e merge gate, merge it without asking. The gate is the
  protection, so it is applied literally, from command output, every time.
- **Strictly serial.** One issue in flight, one open PR, one dev stack. The
  fork's `develop` branch *is* the PR branch, so a second in-flight change
  would corrupt the first PR. If the next issue is started while the PR
  waits on review or CI, its commit is parked with the flow in memory
  `project-parked-commit-one-pr-at-a-time` (tag, rebase the fix onto the PR
  head, cherry-pick after the merge; fold a review fix into the PR commit
  with `git commit --fixup` + `GIT_SEQUENCE_EDITOR=true git rebase -i
  --autosquash`, never with a copy-aside then `git reset --hard`: on
  2026-10-20 zsh did not split `$FILES`, the copy failed and the reset
  dropped the edits, see memory `zsh-no-word-split-reset-trap`), and every status update says that the
  working tree holds the next issue's staged work and why (2026-10-16: the
  user asked "what are these changes for ie the staged changes").
- **Two live-test rounds per issue, both mandatory, both careful.**
  Reproduce on the dev stack **before** writing code (UI via the Playwright
  MCP + API), and verify on the dev stack **after** the fix (UI via the
  Playwright MCP + API), on top of the backend, frontend and Playwright e2e
  suites. Neither round can be skipped or replaced by a passing test suite.
  The second round covers **the entire workflow the change affects, end to
  end**, not the lines you edited (user instruction, 2026-09-23): every
  screen, report, dashboard, export and endpoint that reads or writes what
  you touched, found by grepping the callers, each one driven in the browser
  until you are certain every pushed change behaves as expected. No
  exemption for a one-line fix, a SQL expression or a mapping change;
  checking a layer in isolation (`psql`, a unit test, a green suite) proves
  that layer only and never substitutes for opening the screen that uses it;
  and missing fixture data is created through the UI or API rather than used
  as a reason to skip a surface. Anything genuinely unreachable is named as
  unverified **in the push message**, never left for the user to discover.
  Every check is discriminating (user-confirmed pattern, 2026-09-23): pick
  values whose expected outcome is only reachable through the code under
  test, drive one value that must trigger each rule or branch and one that
  must not, and accept a claim only when the UI row, the database row and
  the audit row agree.
  Every function row and regression cell is clicked by hand through the
  Playwright MCP; a spec run (yours or an existing one) is extra evidence,
  never a substitute for a row (user instruction, 2026-10-15).
  The second round follows `resolve-issue` §3b literally: build the
  **surface inventory and the function inventory** from the diff, then walk
  **every** changed screen, control, **modal and dialog** step by step in the
  browser, and drive **every function the fix adds or alters, one at a
  time, with its expected result written down first and the observed result
  compared against it**: each modal in both its states (fresh, and opened
  on an existing record), each field round-tripped through a save, each
  validation made to reject its invalid input, each conditional branch made
  to render, both sides of every role or config gate, and each server-side
  function probed via the API with its row read back. On top of that, at
  every diff size, it builds and walks the `resolve-issue` §3b **regression
  matrix** (user instruction, 2026-09-26: as much live UI testing through
  the Playwright MCP as possible, every case scenario related to the changed
  files, so no existing workflow breaks): each changed file's consumers,
  each consumer's workflows including the ones the ticket never mentions,
  each workflow's scenarios (happy, negative, lanes, data states, roles and
  config gates), baselined on `upstream/develop` in the reproduce round
  where the expected outcome is not obvious, plus the existing Playwright
  specs for those screens run against the stack. Expected
  vs observed for every row goes into the run log (user instruction,
  2026-09-21: every function must be shown to perform as expected, on the
  UI and via the API, before the PR moves).
  Batch mode is the pipeline most tempted to skip this because the suites
  are green; green suites are exactly what hid the last set of defects.
- **Run log.** Create `<scratchpad>/CRITERIA-RUN-<yyyymmdd-hhmm>.md` at the
  start: the resolved JQL, the worklist with each issue's eligibility
  decision and reason, then one section per issue updated as it moves
  (`pending` → `reproduced` / `already-resolved` / `not-reproducible` /
  `escalated` / `merged` / `blocked-*`). Update it on every state change,
  not at the end, so a context reset never loses the campaign.
- **Authorship.** Everything is mozzy11 with no AI attribution, with the
  single exception inherited from `review-pr` §0: the independent review
  carries one line showing it came from Claude. It is posted from mozzy11
  with the footer `Generated by Claude Reviewer` as the body's last line
  (revised 2026-10-07: footer, no "posted via" text); that one line and
  nothing else, no tag on inline comments. Because GitHub blocks approve and
  request-changes on your own PR, the self-review is a comment event whose
  first line is `Decision: Approve / Request changes / Comment` (review-pr
  §5); reviews of other people's PRs carry no such line and use the
  action itself.
  It lands on the PR, mozzy11 responds to it, and the disposition
  of every finding goes into the run log. Nothing blocks.

## 1. Turn the criteria into JQL

Map the user's words to fields. Accept loose phrasing:

| User says | JQL field |
|---|---|
| assignee, assigned to, owner, "me" | `assignee` (`currentUser()` for me) |
| reporter, assigner, described by, created by, raised by, filed by | `reporter` |
| status, state, column | `status` |
| project, or a board URL like `/projects/OGC/boards/51` | `project` (key from the URL) |
| label(s) | `labels` |
| type | `issuetype` |
| priority | `priority` |
| sprint | `sprint` |

- **People become account IDs.** Use `lookupJiraAccountId` for every name.
  A name can match several accounts (for example two "Casey Iiams-Hauser"
  accounts exist); include **all** matches: `reporter in (id1, id2)`. Never
  put display names in JQL. Spellings in the request are approximate
  ("Caesy" → search "Casey"); if the exact string finds nobody, try the
  obvious variants, then fall back to running the query without the person
  filter and matching reporters by display name from the result.
- **Board quick filters are not readable through the MCP.** A board URL
  contributes only the project key. The status, assignee and reporter must
  come from the user's words; if only a board URL is given, use
  `status = Backlog AND assignee = currentUser()` and say so in the run log.
- **Standing exclusions, appended to every query, no exceptions:**

  ```
  AND issuetype != Epic AND parent IS EMPTY AND issuetype not in subTaskIssueTypes()
  ```

- Order: `ORDER BY priority DESC, created ASC` (most urgent, then oldest).
- Fetch with `searchJiraIssuesUsingJql`, fields
  `summary, issuetype, status, priority, parent, subtasks, issuelinks,
  labels, reporter, assignee, created, updated`, paginating with
  `nextPageToken` until `hasNextPage` is false. Large results are saved to a
  file by the tool; parse that file with python rather than reading it.

Worked example (the request that created this skill):

> resolve by criteria: assignee mozzy, assigner Casey, status Backlog,
> board https://uwdigi.atlassian.net/jira/software/c/projects/OGC/boards/51

```
project = OGC AND status = Backlog AND assignee = currentUser()
  AND reporter in (557058:99fa116c-0d0d-4dd2-aa5c-a335a4160851, 557058:b690c5cf-c52a-4508-b7a0-518a5c2503c9)
  AND issuetype != Epic AND parent IS EMPTY AND issuetype not in subTaskIssueTypes()
ORDER BY priority DESC, created ASC
```

## 2. Build the worklist

JQL cannot see everything. For every returned issue run these checks and
record the verdict and reason in the run log:

1. **Children.** `searchJiraIssuesUsingJql` with `parent = <KEY>` in
   `count` mode must return 0, and `subtasks` must be empty. Anything with
   children is out, whatever its type.
2. **Parent.** `parent` must be empty (already filtered, re-check on the
   fetched issue, the field is omitted when null).
3. **Links that make it part of something bigger.** Inspect `issuelinks`.
   Out if any link points at an Epic, or is a parent-shaped type ("is child
   of", "is part of", "split from", "is a slice of"). "relates to" alone is
   fine.
4. **Size triage from the ticket text.** Eligible means: one screen, one
   endpoint or one entity; concrete reproduction steps or a concrete
   expected/actual pair; no product decision left open; no new module,
   table redesign or FRS-driven feature scope. Words like "remaining
   scope", "v2", "full", "complete the editor" mark a slice of a larger
   effort: out. Stories are eligible only when they are a single
   self-contained change (a debounce, a missing control, a wrong filter);
   feature stories are out.

Ineligible issues are logged as `skipped: <reason>` with the exact reason,
they are **not** commented on in Jira, and the final report lists them so
the user can run `resolve issue <key>` explicitly.

Print the worklist to the transcript as a short table (key, type, priority,
verdict) **before** touching any code. This is the only place where the
plan is shown; the rest of the run is execution.

## 3. Work the list

For each eligible issue, in order:

### 3a. Re-check state

- `getJiraIssue` again. Skip (log `skipped: state changed`) if the status,
  assignee or parent no longer match the criteria, or if someone else has
  commented that they are on it.
- **Prior work.** `git log upstream/develop --grep <KEY>`,
  `gh pr list --repo DIGI-UW/OpenELIS-Global-2 --search "<KEY>" --state all`,
  and PR links in the ticket comments. Note what you find; §3b decides
  what it means.
- **Hard stop: a foreign open PR.** `gh pr list --repo DIGI-UW/OpenELIS-Global-2
  --author mozzy11 --state open`. If an open PR exists that this run did not
  create, stop the whole run and report: pushing the fork's `develop` would
  rewrite that PR. Do not stash, rebase or "fix" it.
- `git status --porcelain` must be clean of work that is not yours.

### 3b. Reproduce on the dev stack (before any code)

- Sync: `git fetch upstream && git reset --hard upstream/develop`, then
  `mvn clean install -DskipTests -Dmaven.test.skip=true`, then
  `docker compose -f dev.docker-compose.yml up -d --force-recreate` for the
  webapp (and restart the proxy). Confirm the served build via
  `WEB-INF/classes/build.properties`, not by trusting the restart. If a
  long-lived volume trips an `onFail="HALT"` data gate, recreate the volume
  before concluding anything.
- **UI, via the Playwright MCP**: `browser_navigate` to the login page, log
  in with the documented `.env` test credentials, then follow the ticket's
  steps literally with `browser_click` / `browser_type` / `browser_select_option`,
  reading state with `browser_snapshot` and keeping a
  `browser_take_screenshot` of the defect for the run log. Open the modals
  and dialogs on that path too: the defect is often in the form rather than
  the list behind it.
- **Baseline the neighbours.** While develop is deployed, also drive the
  existing workflows around the defect that the fix will likely touch
  (same screen, upstream and downstream steps) and record what they do.
  That record is the "before" the §3b regression matrix compares against
  after the fix.
- **API**: get the session and the `csrf` field from
  `GET /api/OpenELIS-Global/session`, then call the endpoints behind the
  screen with the cookie + `X-CSRF-Token`, and read back the persisted row
  (a GET or a `psql` query in the database container).
- Decide, from evidence:
  1. **Reproduced** → §3c.
  2. **Not reproducible, and a merged PR or commit found in §3a explains
     why** → §3d.
  3. **Not reproducible and nothing explains it** → one honest Jira
     comment (develop sha, the exact steps taken, what was observed
     instead), leave the status alone, log `not-reproducible`, next issue.
     Never fix what you cannot see.

### 3c. Fix through the resolve-issue pipeline

- Invoke the `resolve-issue` skill for the key. It owns: the full ticket
  read, root cause, minimal fix, tests for every changed behavior (backend
  integration, frontend unit, and a permanent Playwright e2e spec),
  inversion verification, the **live-test gate** (surface and function
  inventories built from the diff, every function driven carefully through
  the UI via the Playwright MCP and via the API, expected vs observed
  recorded per row, evidence pasted), draft PR, CI to green, ready, the independent
  review carrying the Claude attribution line, addressing that review as
  mozzy11, CI green again, and the Jira "In Review" move with a short
  comment.
- Do not weaken any of its gates for speed. Batch mode is allowed to be slow;
  it is not allowed to be sloppy.
- **Per-issue escalation.** If root-causing reveals the issue is larger than
  triaged (touches several modules, needs a schema redesign or a product
  decision, or is really a slice of the parent epic), stop that issue:
  `git reset --hard upstream/develop`, close the draft PR if one exists,
  post a 2-3 line Jira comment saying what was found and that it needs an
  explicit `resolve issue` pass, log `escalated`, next issue.

### 3d. Already resolved

- Name the PR or commit and the develop sha that carries the fix; the
  §3b live check is the evidence that the behavior is correct now.
- Jira comment, 3-5 lines for the product owner: fixed by PR #n (link),
  verified on develop at sha via the ticket's steps, any heads-up.
- Transition: **Acceptance** if that sha is deployed to
  testing.openelis-global.org (the push-triggered "Publish Images" run for a
  sha at or after the merge succeeded, or the DockerHub `:develop` tag is
  dated after it); otherwise **In Review**. Log `already-resolved`.

### 3e. Merge gate (this pipeline only)

Every condition below is verified from command output in this session, for
the **current head sha** of the PR, immediately before merging. Any miss
means no merge: log `blocked-<reason>`, leave the PR open and ready, and
continue with the next issue.

1. PR is ready (not draft). `gh pr view <n> --repo DIGI-UW/OpenELIS-Global-2
   --json isDraft,mergeable,mergeStateStatus,reviewDecision,headRefOid,statusCheckRollup`.
2. Every **required** status check is green. Read the list from
   `gh api repos/DIGI-UW/OpenELIS-Global-2/branches/develop/protection`
   (today: `01 Checkpoint - Backend`, `02 Checkpoint - Frontend`,
   `03 Checkpoint - E2E`), and match it against `statusCheckRollup`.
   A required check red from an external outage (read the failing job's
   log first: a vendor download page, a registry 5xx) is still red: rerun
   once, and if the outage outlasts about two hours put a general fallback
   in the current PR, proven in a fresh container without caches, rather
   than waiting on it (2026-10-22: download.eclipse.org down 16 hours,
   Formatting red on every PR; the eclipse-p2-mirror fallback went into
   #4800).
3. The independent review round from `resolve-issue` §7 has happened on this
   head sha (or on a sha differing only by the fixes it asked for), and
   every thread it opened is either fixed or answered, with only acted-on
   threads resolved. The branch requires conversation resolution. The
   review was posted from mozzy11 carrying the `Generated by Claude
   Reviewer` footer as its only attribution, with each finding's disposition
   recorded in the run log.
4. No `CHANGES_REQUESTED` from **any other person**. If a human other than
   mozzy11 has requested changes: address what you can, reply on the
   threads, but **do not merge**, log `blocked-review`. Plain comments from
   others are addressed and replied to, then the gate continues.
5. Both live-test rounds are recorded in the run log for this issue, the
   second one against the final head sha, **with the function inventory
   fully ticked**: every function the diff adds or alters has an observed
   result, in the browser via the Playwright MCP and via the API, that
   matches the expected one written down beforehand, **and the regression
   matrix fully walked**: every scenario of every workflow that passes
   through a changed file behaves as it did on the develop baseline unless
   the ticket asked for the change. Any row or cell never exercised, or
   exercised with a mismatch, means no merge: log
   `blocked-live-test`, leave the PR open and ready, and move on.
6. `git diff upstream/develop...HEAD --stat` shows only the intended files.

Merge with a squash and a compressed four-section body (`resolve-issue` §4,
no trailers, no attribution):

```bash
gh pr merge <n> --repo DIGI-UW/OpenELIS-Global-2 --squash \
  --subject "<conventional title with the Jira key>" \
  --body "<What changed / Why / How tested compressed to 3-6 sentences>"
```

- **One merge call, then read the state.** If the merge call errors (a 504,
  a timeout, "Merge already in progress"), poll `gh pr view <n> --json
  state,mergeCommit` until it settles; never send a second merge while the
  first may still land (2026-10-14: a REST retry after a 504'd `gh pr merge`
  added an empty duplicate commit to develop, f863283df, #4728).
- **No app code, no full-CI wait** (user, 2026-10-20: "just merge the PR
  since no app code changes"; "then just merge because the PR won't catch
  it"). A PR touching only workflows, deploy scripts, docs or markdown merges
  once Formatting and the checks its files feed are green; E2E is not
  awaited. A deploy-only fix the PR checks cannot exercise is proven on the
  merge sha's deploy (§3f), not on the PR. Any frontend, backend, message or
  Liquibase file means the full condition 2 (same day: "wait for ci to run
  and then you'll merge" on #4783, which carried en.json and a component).
- The self-review cannot approve (GitHub refuses approval on your own PR),
  so the branch's required approving review is
  never satisfied by this pipeline and GitHub will answer that the PR is not
  mergeable even though all six conditions hold. Retry once with `--admin`.
  The six conditions are the real gate; `--admin` is only the mechanism.
- **If `--admin` is still refused ("the base branch policy prohibits the
  merge"), force it through branch protection** (user instruction,
  2026-09-14; standing authorization from mozzy11, an org admin in DIGI-UW).
  Bypass the *review* gate only — never merge on red CI; condition 2 stands.
  Use exactly this sequence, proven on DIGI-UW/OpenELIS-Global-2#4143:

  ```bash
  R=DIGI-UW/OpenELIS-Global-2; B=develop
  gh api repos/$R/branches/$B/protection > prot-before.json   # 1. snapshot
  restore() { gh api -X POST repos/$R/branches/$B/protection/enforce_admins --silent; }
  trap restore EXIT                                           # 2. restore even on failure
  gh api -X DELETE repos/$R/branches/$B/protection/enforce_admins --silent
  gh pr merge <n> --repo $R --squash --admin --delete-branch=false
  # trap fires; then prove no residue:
  gh api repos/$R/branches/$B/protection > prot-after.json
  diff prot-before.json prot-after.json   # must be empty
  ```

  Toggle **only** `enforce_admins`, via its dedicated endpoint — never edit
  required checks, review counts or rulesets. Both steps are needed:
  disabling `enforce_admins` without `--admin` still refuses. Rulesets need
  no action: mozzy11 is an Organization Admin, so "CI Required Gates"
  (bypass: RepositoryRole 5) and "Copilot review for default branch"
  (bypass: OrganizationAdmin) are bypassed automatically. Report the diff
  result in the run log. If protection cannot be restored, stop the whole
  pipeline and tell the user — a repo left unprotected is worse than an
  unmerged PR.

### 3f. After the merge

> **Retro after every issue, not only at the end** (2026-10-15: after a
> 17-issue run the user asked "so did the skill improve after the previous
> session"; the retro had never run). Once Jira reads In Review, run
> `session-retro` on the current session and the queue, so the next issue
> starts with the lessons of this one.

> **Jira first, immediately (user instruction 2026-09-29).** When the first
> draft PR for the issue opens, transition it to **In Progress** and comment
> the draft PR link. As soon as the merge succeeds, and before the reset,
> cleanup or the next issue, comment the merged PR and the issues it fixed,
> then transition to **In Review**. Read the status back with
> `getJiraIssue` after each. Do not start the next ticket until the
> post-merge update is done.

- `git fetch upstream && git reset --hard upstream/develop &&
  git push --force-with-lease origin develop`. PRs are squash-merged; no
  lost-commit analysis. **Guard first (2026-09-24, this reset wiped PR
  #4415 and hours of another session's uncommitted work):** only run it when
  `git status --porcelain` shows no work you did not author and
  `gh pr list --author mozzy11 --state open` lists no PR other than the one
  just merged. Otherwise leave `develop` and the fork alone and report it.
- Jira (done first, see above): comment (3-6 lines: what changed in user
  terms, PR link, one line on verification, any QA heads-up) and transition
  to **In Review**, read back. The move to Acceptance happens in §4 once the
  change is actually on testing.
- **Watch the merge sha's push-triggered runs right after the merge**
  (2026-10-20: the user asked "can you see the ci failed on merge of 1514"
  an hour after the merge; E2E / Tests had failed on runner problems and so
  Publish images never deployed testing). Arm a monitor on
  `gh api "repos/DIGI-UW/OpenELIS-Global-2/actions/runs?head_sha=<merge sha>"`
  until E2E / Tests and Publish images / Deploy testing (both
  `workflow_run`, event of the push) settle. A red one is triaged at once:
  a code cause gets a fix, a runner cause gets the general workflow fix plus
  `gh run rerun <id> --failed` of the E2E run, then of the publish run.
  CI fixes found while a PR is in flight go into that PR (user, same day:
  "push the fix as part of the current PR"). Runs whose head is the merge
  sha but whose event is `pull_request` are the next PR's, not the merge's.
- Clean up live-test data (probe orders, patients, results) so the next
  issue's reproduction starts from a known state. Log `merged` with the PR
  link and the merge sha.
- Next issue: back to §3a.

## 4. After the list

- Re-run the resolved JQL once. Issues that appeared since the run started
  get one more pass through §2 and §3. Never a third pass: the run ends.
- **Deployment check for everything merged.** For each `merged` issue, find
  the push-triggered "Publish Images" run for its merge sha (or later) and
  the DockerHub `:develop` tag date. Deployed → transition to Acceptance
  with a one-line comment. Not yet → leave In Review and say so in the
  report. A green PR-triggered run is not a deployment; read the
  push-triggered one.
- Leave the dev stack up but with probe data removed.

## Hard stops (report, never ask)

- An open upstream PR by mozzy11 that this run did not create.
- Uncommitted foreign work in the tree.
- The dev stack will not come up after a volume recreation.
- Someone else's `CHANGES_REQUESTED` on the current PR.
- A second review round that still ends in a blocking disagreement.
- Loss of access to Jira, GitHub or Docker.

On a hard stop: finish the current issue's bookkeeping (run log, Jira
comment if a PR exists), then emit the final report with the stop reason at
the top.

## Docker teardown (always, after each issue and before the final report)

Docker here has 7.6 GB and is shared with other sessions, so every stack this
session started is removed as soon as its issue is done, and again before the
final report (user instruction, 2026-10-12):
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
- Report the teardown in the final report (projects removed, containers
  left = 0, free disk).

## Final report (always emit)

- The resolved JQL and the worklist table: key · type · priority · verdict.
- One line per worked issue: outcome (`merged` / `already-resolved` /
  `not-reproducible` / `escalated` / `blocked-*`), PR link, merge sha,
  Jira status after the run, review decision and what changed in response.
- Skipped issues with the exact exclusion reason (epic, has children, has
  parent, linked to epic, too large), so the user can run
  `resolve issue <key>` on the ones they want.
- Deployment state: which merges are on testing.openelis-global.org already,
  which are still In Review.
- Unverified items and anything left for the user.
- **Answer the question asked, first, in plain words** (2026-10-20: "you
  talked too much i didn't get your point, be direct"; "you didn't answer
  my question"). Lead with yes / no or the one-line cause, then at most a
  few lines of support. No CI job names or run ids unless asked.

## Retro (always, after the final report)

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
