---
name: review-all-prs
description: Sweep every open pull request in DIGI-UW/OpenELIS-Global-2. Leaves the core team's PRs untouched, classifies the rest as low-risk maintenance, regular or major, reviews them with the review-pr skill, fixes minor issues on the PR branch, merges a low-risk maintenance PR on a clean first review with green checks (past branch-protection rules if needed), merges a regular PR only on an approval given before the run and never past protection, approves major PRs and leaves them for the user's manual merge, closes PRs only on verified evidence that they are obsolete, and reports the run in sections A to H. Resumable through a ledger. Trigger: "review all PRs", "review all open PRs", "PR sweep".
---

# Review all PRs

This skill **orchestrates**. The review itself is the `review-pr` skill; read
its §0 to §5 before the first deep review of a run. The rules that decide
what happens to a PR live in code, so they are applied the same way every
run:

- `scripts/policy.py`: classification, approval, CI and merge-gate rules and
  the decision table (pure functions, pinned by `tests/test_policy.py`).
- `scripts/prs.py`: GitHub access, the ledger, and the only commands that
  approve, merge or close. `merge` and `close` re-read GitHub and refuse on
  any blocker.

Run **autonomously; never ask the user anything.** The trigger authorizes:
reviews, approvals, change requests, minor fixes pushed to PR branches,
`update-branch`, approving fork workflow runs, merges that `prs.py merge`
accepts and closures that `prs.py close` accepts. Anything else (a judgment
call on a product decision, a possibly obsolete PR without proof) goes into
the report for the user.

## Where things live

- Skill: `/Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills/openelis-global/review-all-prs`
- `prs.py` below means
  `python3 -I /Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills/openelis-global/review-all-prs/scripts/prs.py`;
  write it out in full in every command (a variable in a command can raise
  a permission prompt in bypass mode).
- State (durable, not the scratchpad):
  `/Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/claude-work/review-all-prs/`
  with `ledger.json` (every PR this skill touched, across runs),
  `runs/<id>/run.json` + `inventory.json` (one run), `reports/<id>.md`,
  and `checkouts/` (disposable clones for pushing fixes).
- Config: `config.json` next to this file (repositories, excluded authors,
  low-risk and major thresholds, budgets). The scope is
  **DIGI-UW/OpenELIS-Global-2 only** (user, 2026-11-23): `repos` lists it and
  `discover` is empty. To widen it later, add repositories to `repos` or set
  `discover` to `{"org": "DIGI-UW", "name_regex": "(?i)openelis",
  "exclude_regex": "(?i)-ghsa-"}`. After changing the config or `policy.py`,
  run `python3 -I <skill>/tests/test_policy.py`.
- Review drafts: `claude-work/reviews/pr<N>-review.md` (review-pr §5).

## 0. Ground rules (they override other skills where they differ)

1. **Bypass only what the user allowed, only through `prs.py merge`.**
   Merge only with `prs.py merge`, which re-checks live data and merges with
   `--match-head-commit`. Close only with `prs.py close`. A refusal is final
   for this run, and the PR goes into the report with the unmet rule.
   - **Low-risk maintenance may bypass branch-protection rules** (user,
     2026-11-23): a missing required approval or code-owner review, and a
     BLOCKED or BEHIND merge state. When those are the only blockers left,
     `prs.py merge` adds `--admin` and the report names what was bypassed.
     Switch it off with `low_risk.bypass_protection: false`.
   - **Never bypassed, for any PR:** any validation check that is not green
     (see rule 2); CI older than 14 days; merge conflicts; someone else's
     change request; unresolved review threads; a draft; a moved head; a
     review that is not clean; the "fixed in this run, merge next run" rule.
   - **Regular and major PRs never bypass anything.** Never `--auto`, never
     toggle `enforce_admins`, never edit branch protection or rulesets, never
     dismiss anyone's review, never resolve a thread you did not act on. If
     `--admin` itself is refused, report it (G); do not go further.
   - This replaces review-pr §5 ("merge means now") and resolve-by-criteria
     §3e inside this skill. Your account can bypass the develop rulesets
     (`current_user_can_bypass: always`), so GitHub may not stop a wrong
     merge. The gate in `prs.py` will.
2. **Every PR must pass every validation check before it merges** (user,
   2026-11-23: "all PRs must pass validation CI checks"). That means every
   check run and status reported on the head, required or not, is
   SUCCESS, NEUTRAL or SKIPPED, and every required check has reported. A
   failing optional shard, a cancelled job or a fork run waiting for approval
   (ACTION_REQUIRED) blocks the merge like a red checkpoint. Low-risk PRs
   included: a bypass covers branch-protection rules only, never a check.
3. **Excluded PRs get no action of any kind**: no review, comment, label,
   push, update-branch, rerun or close. The author is the PR's opener
   (matched by login and display name in `config.json`
   `excluded_authors`): Piotr (pmanko), Samuel Male (samuelmale), Herman
   (mherman22), Reagan (reagan-meant), Ian (ibacher). Your own PRs are also
   excluded, because resolve-issue owns them. `prs.py review/close/
   update-branch/approve-runs` refuse excluded PRs. To add a person, add
   `{"login": ..., "names": [...]}` to the list.
4. **A previous approval** (needed to merge a regular PR) is the reviewer's
   latest decisive review (not dismissed, not followed by their own change
   request), from a person with write, maintain or admin access who is not
   the author, **submitted before this run started** (`prs.py run-start`).
   It counts if what landed after it is nothing, base merges, your recorded
   fixes, or author commits you reviewed and recorded as `--delta minor`.
   Approvals you post during this run never count for a merge in this run.
5. **Low-risk is mechanical** (`policy.classify`). You can raise a category
   (`record --category major --why ...`). You can lower major to regular
   only with a reason. You can never make a PR low-risk by hand. When unsure,
   raise it.
6. **The review method is review-pr**: its §0 rules (the blocking bar,
   respecting standing reviews, authorship as mozzy11 with no AI attribution
   and no "Decision:" line on other people's PRs), §1 reading, §2 structural
   checks, §3 verification by running (including the live UI and API walk
   where §3 requires one, and its "batch sweep" rule), §4 inline comments
   and §5 review text. This skill changes only who merges, when, and how the
   batch is run.
7. **One PR at a time, at most two parallel tool calls or agents.** One
   status line at each phase and after each PR.
8. **Never a foreground `sleep`.** Long waits (`wait-ci`, a slow
   `inventory`) run with `run_in_background`, and their completion notice
   ends the wait.
9. **GitHub is the source of truth; the ledger is the memory.** Every claim
   in the report comes from a command run in this session.

## 1. Start or resume

```
prs.py run-start      # resumes an open run younger than 12 h, else starts a new one
prs.py inventory      # every open PR + branch rules + merged history; ~5 min for ~230 PRs (Bash timeout 600000)
prs.py plan           # one line per PR: step, category, CI, approvals, hints, in processing order
```

- A resumed run keeps its id and start time, so the "this run" rules hold
  across an interruption. A low-risk PR fixed before the interruption still
  waits for the next run. Re-run `inventory` on a resume only if it is more
  than about two hours old. `show`, `decide` and `merge` always read live
  data anyway.
- `run-start` lists PRs carried in section D from the previous run; they are
  processed first (step `verify-fixes`).
- Tell the user the plan's `steps:` line and the deep-review budget line.

## 2. Work the plan, in order, one PR at a time

For each PR: `prs.py show <key>` (live facts, the ledger entry, the plan),
then the step below, then `prs.py decide <key>`, then carry out its actions
(§2b), then one status line. `<key>` is `owner/repo#n`, `repo#n` or the URL.

| Step | What to do |
|---|---|
| `exclude` | Nothing. It is reported under F. |
| `skip-draft` | Nothing. `decide` puts it in G (draft). |
| `check-base` | The PR targets another branch. If that branch is retired, use §4. Otherwise `decide` puts it in G with the reason. |
| `check-obsolete` | §4. If it is not obsolete, continue with the step shown as `(then ...)`. |
| `gate` | The head is unchanged since your last clean review. Read the comments and reviews posted since that review. If nothing new, go straight to `decide` (no re-review, no re-test). If something new, review it as `re-review`. |
| `verify-fixes` | §5e: verify the fixes from an earlier run. |
| `waiting-on-author` | `prs.py record <key> --review waiting-on-author`, then `decide` (C). No new review and no comment: the request already stands. |
| `low-risk-review` | §3. |
| `review-approved`, `re-review`, `review-major`, `review` | Deep review, §2a. |

**Budget.** At most `deep_review_budget` (6) deep reviews per run, in plan
order: previously approved regular PRs first, then re-reviews, majors, then
never-reviewed PRs, oldest first. The rest show `[queued: budget]`, stay in N
and come first next run. Raise the number in `config.json`, or when the user
says "no budget".

### 2a. Deep review (regular and major PRs)

1. Run review-pr §1 to §3 on the PR. For a previously approved PR or a
   re-review, use review-pr §1 "Re-review after a fix round": diff the
   approved sha (`show` → `facts.approval.approved_sha`) to the head, and
   for author commits after the approval record `--delta minor` or
   `--delta substantial`.
2. Confirm the category from the diff, not the heuristics. Record
   `--category major --why ...` for a new workflow, a new screen, a schema
   change, an architectural change or a substantial change to existing
   behaviour. Record `--category regular --why ...` to lower a heuristic
   major, for example a `feat:` title on a 60-line change.
3. Live test exactly where review-pr §3 requires it, with its "batch sweep"
   rule: deploy several app-code candidates together on one isolated stack
   and walk each before approving. Dependency and test-only PRs may approve
   on green CI.
4. Findings: a minor issue you fix yourself (§5). A blocking issue, measured
   against the review-pr §0 bar, becomes `--issue "..."` and a change
   request.
5. Record what you found:
   `prs.py record <key> --review clean|fixed|changes --sha <head you reviewed> --summary "..." --findings "..." --tests "..."`
   adding `--issue "..."` for each blocking finding.
6. `prs.py decide <key>`, then §2b.

### 2b. Carrying out the decision

- **approve**: write the body per review-pr §5 (a colleague's voice, what
  you verified first) to the review draft file, then
  `prs.py review <key> --event approve --body-file <file> --sha <head>`.
  It does nothing if you already approved this head. It refuses a body with
  an em or en dash, or with any AI attribution on someone else's PR.
- **request-changes**: post with inline comments per review-pr §4 and §5
  (pending review through the API, then submit with `REQUEST_CHANGES`),
  then `prs.py record <key> --posted request-changes`. A body-only review
  can go through `prs.py review <key> --event request-changes`. On a bot PR
  nobody answers a change request: comment instead and leave it in C.
- **merge**: `prs.py merge <key>`. Never `gh pr merge` directly. If it
  refuses, the PR is in G with the reason; do not retry with anything else.
  After an approve, `merge` re-checks the live review decision, which is
  where a branch rule your approval does not satisfy (code owners, a second
  reviewer) shows up. For a low-risk PR that rule is bypassed with
  `--admin` (`decide` lists it under `bypassed_for_low_risk`); for any other
  PR it is a blocker.
- **wait-ci**: add the key to the CI sweep (§6) and go on to the next PR.

## 3. Low-risk maintenance PRs

Low-risk means a Dependabot or Renovate update where every bump is a patch,
or a minor that is not a core framework or runtime, with at most 10 updates
and only manifests, lockfiles, workflow pins or image tags touched. It also
means a small docs-only or simple-config change that is not a design
document. Major bumps, changed image flavours, groups of more than 10 updates,
schema or code changes, and documents in `openelis-work` are never low-risk
(`show` lists the blockers). There is **no previous-approval requirement**
for this category: that exception is deliberate.

In plain terms (user, 2026-11-23):
- **The first-run merge is for low-risk maintenance only.** A feature PR,
  small or large, never merges on the run that first reviews it: a regular
  PR needs an approval from before the run, and a major PR (a large
  feature) is never merged by this skill at all, only approved for the
  user (B).
- **The review finds nothing** (a clean version bump) and **every validation
  check is green** → merge it in this run.
- **You push a fix** → stop. Its checks run, and the **next** run verifies
  the fix and merges it once every check is green.
- **Anything else** (a check red or still running, an issue you cannot fix)
  → not merged.

Review it fully, on the first encounter:

1. Read the whole diff (`gh pr diff <n> --repo <repo>`). Only the announced
   packages and their own lock entries change, the versions match the PR
   text, and there are no new registries, `resolved` hosts or install
   scripts in a lockfile.
2. Read each package's release notes between the two versions (breaking
   changes, changed defaults, new minimum runtime). For a minor, read that
   minor's notes.
3. Security: `gh api "/advisories?ecosystem=<maven|npm|pip|actions>&affects=<package>@<to>"`
   shows no advisory for the new version. For a security bump, confirm the
   advisory it fixes is covered by the new version.
4. Compatibility: grep the code for anything the notes deprecate or remove.
   For an image tag, check that it exists for the platforms used
   (`docker buildx imagetools inspect <image:tag>`). For a workflow pin,
   run actionlint per review-pr §2.
5. Docs-only: read every line, and check each link and each stated fact
   against the code.
6. CI: `decide` shows every check on the head (`required`, `other_failing`,
   `other_pending`); all must pass (§0 rule 2). Results older than
   `ci_max_age_days` (14) need `prs.py update-branch <key>` first; for
   Dependabot that comments `@dependabot rebase`. Then wait-ci.

Outcomes:

- **No issues and checks green** → `record --review clean --sha <head>` →
  `decide` gives A with `approve, merge` → approve (a two-line body: what
  you checked) → `prs.py merge <key>`. This is a **first-run merge**. If a
  branch rule your approval does not satisfy remains (code owners, a BLOCKED
  merge state), the merge bypasses it with `--admin` and the report says so.
- **Issues you can fix safely** (§5) → fix, push, confirm CI started, then
  `record <key> --review fixed --sha <head you reviewed> --issue "..." --fix-sha <sha> --fix-summary "..." --issue-fixed I<n>`
  → `decide` gives D. **Stop there for this PR**: no approval and no merge
  in this run, even if CI turns green while the run continues. The next run
  verifies and merges it (§5e).
- **Issues you cannot fix** → `record --review changes --issue ...` and
  request changes (comment on a bot PR) → C.
- **CI failing** → attribute it per review-pr §3. Caused by the bump and
  fixable: the fix path above. Not fixable: C. Infrastructure: rerun the
  failed jobs once (`gh run rerun <id> --failed`) and wait-ci. Never merge
  with any check red or pending, required or not.

## 4. Outdated and superseded PRs

The plan's hints are leads, never reasons. Close a PR only when all five
hold, each shown by a command in this session:

1. **History read**: `gh pr view <n> --repo <repo> --comments`, its commits,
   its reviews, and its last activity.
2. **Linked issue read**: the GitHub issue, or the Jira key's status through
   the Atlassian tools.
3. **Equivalent work is on the default branch**: the merged PR or commit
   that does the same thing, compared with this PR's diff (`gh pr diff` of
   both, or `git log -S '<key line>' upstream/develop`).
4. **Why it is obsolete**, in one sentence.
5. **Nothing useful is lost**: anything this PR has that the replacement
   lacks (a test, a fix, documentation) is named in `--salvage`. If it is
   worth keeping, do not close: report it in G as "needs your decision".

Then
`prs.py close <key> --why "..." --evidence <merged PR, closed issue or commit URL> --salvage "..." --comment-file <file>`.
It refuses unless at least one evidence URL checks out as a merged PR, a
closed issue or a commit on the default branch. The comment is plain and
kind, in mozzy11's voice: thank them, name what landed (with its link and
date) and what it covers, say it is closed as superseded, add the salvage
line if any, and invite them to reopen if it still adds something.

- **Never close for age or inactivity alone.** Old with conflicts is a hint
  to look, nothing more.
- **Automated series** (a bot that opens one PR per run with a numbered
  title): close an older one only after checking that the newest PR contains
  its changes. If each run's PR changes different entries, they are not
  superseded.
- **Uncertain** → leave it open, `record <key> --remaining "possibly
  superseded by <link>: <why unsure>"`, and `decide`. It ends in the
  report for the user.

## 5. Minor fixes on the PR branch

**5a. What qualifies:** formatting, naming, a small refactor inside the
changed lines, documentation corrections, lint, small test improvements, a
missing message key in `en.json`, a lockfile regeneration. Not new
behaviour, architecture, or anything beyond the PR's scope; those are
issues for the author. review-pr §3 "Any change YOU author" applies to every
line you write: test it, and walk it live where the PR needed a walk.

**5b. Can you push?** Yes for a same-repository branch (Dependabot) or a
fork PR with `maintainer_can_modify` true (`show` prints both). Otherwise
put the change in a review comment as a suggestion and treat it as an issue
for the author. Pushing to a Dependabot branch stops Dependabot from
rebasing it; say so in the fix summary.

**5c. How:**
- No worktree and no branch in the main checkout. Use a disposable clone
  that shares the main checkout's objects, with the PR branch tracking the
  fork, registered for cleanup:
  ```
  git clone --shared --no-checkout /Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/develop/OpenELIS-Global-2 /Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/claude-work/review-all-prs/checkouts/<repo>-<n>
  /Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/claude-work/bin/session-track.sh dir <that path>
  git -C <that path> remote add fork https://github.com/<head repo>.git
  git -C <that path> fetch fork <head branch>
  git -C <that path> checkout -b <head branch> --track fork/<head branch>
  ```
  The tracking branch matters: the pre-push gate diffs against `@{u}`, and
  from a detached HEAD it falls back to develop and checks develop's own
  changes. A `--filter=blob:none` clone of a contributor fork took over 10
  minutes; the shared clone fetches only the PR's new objects (2026-11-23,
  #3922). For a repository other than OpenELIS-Global-2, share its local
  checkout the same way, or clone it blob:none if there is none.
- Commit as mozzy11 with a conventional message and no AI trailer. Format
  what you touched (cold `mvn spotless:apply`, `npm run format`).
- Test from the main checkout as review-pr §3 says (`git fetch upstream
  pull/<n>/head:pr-<n>` after the push, `iso-suite.sh` for backend runs),
  never from the clone: its submodules are empty.
- Push without force: `git -C <that path> push fork HEAD:<head branch>`.
  If it is rejected, the author pushed meanwhile: fetch, re-review, and
  start again.
- Confirm CI started: `prs.py approve-runs <key>` approves fork workflow
  runs waiting for a maintainer (a normal maintainer step, not a bypass).
  Then check that runs exist for the new head:
  `gh api "repos/<repo>/actions/runs?head_sha=<sha>" --jq '.workflow_runs[]|"\(.name) \(.status)"'`.
  Record it with `--ci-note`.
- Reply on each review thread you acted on and resolve only those
  (review-pr §4).

**5d. Record** (one fix commit per call):
`prs.py record <key> --review fixed --sha <head you reviewed> --issue "<what was wrong>" --fix-sha <pushed sha> --fix-summary "<what you changed>"`,
then `--issue-fixed I<n>` for each issue the commit fixes.

**5e. Next run (`verify-fixes`):** diff your fix commits and confirm each
recorded issue is fixed (`--issue-fixed` for any still open). Review the
whole updated diff for anything new, including author pushes since. Record
`--review clean --sha <head>`, then `decide`. A low-risk PR merges as
**after-fix**. A regular PR with a prior approval merges as approved-regular.
A PR with issues left stays in C.

## 6. CI sweep (after the per-PR loop)

For every key that got `wait-ci` in this run (a regular or major PR you fixed,
a PR whose checks were still running, a PR whose branch you
updated), and **never a D PR**:

```
prs.py wait-ci <key> <key> ... --minutes 120
```

Run it with `run_in_background` and Bash `timeout: 7200000`; its completion
notice ends the wait. Then for each key:
- A regular or major PR you fixed: confirm the head is your fix on top of
  what you reviewed. Record `--review clean --sha <new head>`, then
  `decide`, then act (a regular PR with a prior approval merges; a major PR
  is approved and goes to B).
- A PR whose branch you updated: the head moved to your base merge, so
  `decide` says "the head moved after the review". Confirm the head's
  parents are the reviewed sha and the base, and that `gh pr diff` shows the
  same lines you reviewed; then `record --review clean --sha <new head>
  --delta minor`, `decide`, and act (2026-11-23: #4263 fell to N on a green
  head until re-recorded).
- A low-risk or regular PR that was only waiting for checks: `decide`, then
  act.
- Still running at the deadline: `decide` gives G ("checks still
  running"), and the next run picks it up.

## 7. Report and close the run

```
prs.py report     # sections A to H from the run records, written to reports/<id>.md
prs.py run-end    # stores each PR's state in the ledger for the next run
```

- `report` exits 5 if the buckets do not add up to the PRs inspected. Fix
  the records (a PR without `decide` lands in N); never edit the numbers.
- The script lists the facts. Add what each section needs where a record is
  thin: for A, a one-line description and the tests and CI verified; for B,
  why manual validation is recommended; for C, what remains; for D, the CI
  status at report time; for E, the evidence. Re-run `report` after any
  `record` change.
- Final message (be direct): one line with the counts (merged,
  awaiting your merge, waiting for CI, changes requested, closed, blocked).
  Then the B list (each PR one line: link, what it does, why manual), the
  G items that need the user's decision, and the report path.

## 8. Teardown and retro

Tear down as review-pr "Docker teardown" says (`session-cleanup.sh`, every
stack and clone registered, the `checkouts/` clones included). Then run
`session-retro` on this session unless the run is headless (`claude -p`).
Edit skills only in the skills repository and commit and push every change
to `mozzy11/claude-dev-skills` at once.

## Decision table

`prs.py decide` applies this (`policy.decide` and `policy.merge_gate`); the
right column names the test that pins each row of the user's scenarios.

| Situation | Outcome | Test |
|---|---|---|
| Regular, approved before the run, requested changes addressed, review clean, every check green, mergeable | Approve if not yet on this head, then merge (A, approved-regular) | `test_01` |
| Regular, approved before the run, minor issues you fixed this run | wait-ci; green → re-check your commits → merge (A) | `test_02` |
| Major (any approval history), review clean, checks green | Approve, leave open (B) | `test_03` |
| Regular, never reviewed, review clean | Approve; not merged (G: mergeable next run if unchanged). A large feature is major → B | `test_04` |
| Approval posted during this run (yours) | Never counts for a merge in this run | `test_04b` |
| Low-risk, first encounter, no issues, checks green, rules met | Approve and merge (A, first-run) | `test_05` |
| Low-risk, issues you fixed and pushed this run | D; stop, even if CI turns green | `test_06` |
| Low-risk, fixed in an earlier run, fixes verified, checks green | Merge (A, after-fix); an issue still open → C | `test_07` |
| Low-risk, checks failing / running / absent | G / wait-ci / G | `test_08` |
| Any PR with a required check green but another check red or running (an optional shard, a cancelled job, a fork run awaiting approval) | Not merged | `test_08b` |
| Verified obsolete or superseded | Close with an explanation (E) | `test_09`, `test_09b` |
| Core team or your own PR | F; no action | `test_10` |
| Major dependency upgrade | Never low-risk: regular (needs a prior approval) or major (core framework or runtime, 30+ updates) | `test_11` |
| Low-risk, clean, checks green, only branch-protection rules unmet (code owners, review decision, BLOCKED/BEHIND) | Merge with `--admin`, bypass named in the report (A) | `test_12` |
| Low-risk with red CI, conflicts, a change request, open threads or a draft | Never bypassed: G or C | `test_12b` |
| Regular or major with branch-protection rules unmet | G with the unmet rule; never bypassed | `test_12c` |
| Approval followed by author commits | Review the delta: `--delta minor` keeps the approval, substantial needs a new one (next run) | `test_approval_rules` |
| Someone else's change request, standing | Not merged (G or C); never dismissed | `test_approval_rules` |
| Change requested, nothing pushed since | C, waiting on the author | plan step |
| Head moved after your review, conflicts, unresolved threads, draft, CI older than 14 days | Not merged until resolved | `test_gate_refuses_moved_head_conflicts_and_threads`, `test_ci_state` |
