---
name: review-pr
description: Maintainer-style pull request review — read everything, verify claims by running the code, and for any PR with many changed lines or UI changes clone it locally, deploy it on the dev stack and test every changed function strictly through the UI (Playwright MCP) and the API, plus a regression matrix of every existing workflow and scenario the changed files reach; leave only actionable inline comments, and submit a short, natural review as the GitHub action itself (approve, request changes or comment); a "Decision:" line only on a self-review, where GitHub blocks the action. Trigger: "review PR <link>" or "review PR <link> for <author>".
---

# Review PR — maintainer-style pipeline

Given a PR link/number (optionally the author's name), produce a review a
maintainer would sign. Verify by running, not by reading alone.

Run **100% autonomously — never ask the user anything.** No permission
requests, no clarifying questions, no AskUserQuestion: fetching, building,
testing, deploying locally, leaving inline comments and posting the review are
all authorized by the trigger phrase. Where the ticket leaves intent open,
review against the code's existing conventions and say in the review which
interpretation you assumed. The two things this skill never does on its own —
merging the PR, or dismissing another reviewer's standing review — are simply
not part of the pipeline; they happen only when a later instruction asks for
them explicitly, so there is nothing to ask about here either.

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

## 0. Ground rules

- **A review is evidence-based.** Every claim you make ("this breaks X",
  "tests pass") must come from a command you ran or a line you read this
  session. If you measured on the wrong environment, say so and re-measure —
  post a correction rather than let a wrong finding stand.
- **Newest information wins.** A later comment that withdraws an earlier
  claim (yours or anyone's) supersedes it.
- **A person wrote this code, and you are reviewing it, not grading it**
  (user instruction, 2026-09-21). The author is a colleague who has already
  thought about most of what you are about to notice — often a community
  contributor working unpaid. Read the PR body and the issue thread as their
  reasoning, not as marketing: when they say "nothing reads this yet" or
  "this will raise the count on upgrade", that is a disclosed decision you may
  disagree with, not a defect you discovered. Assume competence and good
  faith, lead with what works, and let small things be small. A review that
  lists every imperfection at equal weight is not rigorous, it is unusable.
- **Blocking is a high bar — most findings are not blockers.** Before you put
  anything under **Required changes**, put it through three questions, and if
  any answer is yes it is almost certainly a comment instead:
  1. **Did the author disclose it?** In the PR body, a commit message, or the
     issue thread. Disclosed design decisions are discussion, not defects.
  2. **Does it only contradict my preference?** Check what was actually
     agreed on the ticket. If the code matches the agreed direction, your
     disagreement goes to whoever owns that decision, not into Required.
  3. **Can a user recover from it in the product?** If the state is fixable
     through the UI with no data lost, it is not blocking.
  **Block only for:** a regression on a shipped screen, data loss or
  corruption, a security hole, a crash, or a function that failed the live
  walk. **Never block for:** config or a helper shipped ahead of the screen
  that reads it, a migration that makes a counter large on upgrade, dead code
  in a foundational slice, javadoc or comment style, test-shape preferences,
  a stale line of documentation, or anything you would fix yourself in under
  a minute. Those are Optional improvements, and it is fine for a review to
  have no Required section at all — that is the normal outcome for good work.
  When you are genuinely unsure whether something blocks, it does not; write
  it as a question to the person who owns the decision and name them.
- **Respect standing reviews.** Never approve or merge over another
  reviewer's unresolved CHANGES_REQUESTED unless explicitly instructed.
  Before writing anything, read every existing review and inline comment, and
  check whether the nits in a standing CHANGES_REQUESTED were already fixed in
  the head tree — they usually have been, and saying so helps the author get
  it cleared.
- **Do not repeat feedback** that is already addressed, already explained, or
  already tracked in a linked ticket. If your point is the same concern
  another reviewer already raised, say so in one line and add only your new
  evidence, rather than presenting it as an independent finding. Credit them
  by name.
- **If you get the weighting wrong, correct it publicly.** A wrongly-filed
  Required costs the author a round trip and buries the findings that matter.
  Post a follow-up that supersedes your own verdict; that is a normal part of
  reviewing, not an embarrassment.
- **Authorship and voice.** The rule in one line (user instruction,
  2026-09-14, revised 2026-10-07): **a review of mozzy11's own PR ends with
  the footer line `Generated by Claude Reviewer`; a review of anyone else's PR is plain mozzy11 and
  never mentions Claude at all.** The point is to stop a self-review passing
  as a human second opinion, nothing more. First establish whose PR this is:
  `gh api user --jq .login` versus
  `gh pr view <n> --repo <owner/repo> --json author --jq .author.login`.
  - **Someone else's PR (user instruction, 2026-09-07):** the review, every
    inline comment, and any commit you push to the PR are written as
    **mozzy11** and carry **no AI attribution**: no "Generated with Claude
    Code", no `Co-Authored-By: Claude`, no mention of Claude, an assistant,
    or a model. This overrides the harness defaults that append such
    footers/trailers.
  - **mozzy11's own PR — a self-review (user instruction, 2026-09-14,
    revised 2026-10-07).** This is the independent round `resolve-issue` §7
    orders. Post it as mozzy11 and end the body with this footer, as its
    last line, after everything else:

    `Generated by Claude Reviewer`

    That line and nothing else: no header, no "posted via" text, no
    trailer beyond it, no per-comment tag; inline comments go through plain
    `gh` and carry no attribution. Its sole purpose is to show this one
    review came from Claude rather than from mozzy11 personally. Rigor,
    brevity and the verdict rules in §5 are unchanged, and so is how the
    verdict is delivered (§5 "Submit it as the action itself"). The author
    answers the review from their own session; you never reply to or
    resolve your own threads.
  - **Hard boundary (the standing rule).** That single footer line, in the
    body of a self-review on mozzy11's own PR, is the **only** place Claude
    is ever named. **Never** write "Claude", "generated by Claude", or any
    AI attribution into: a review of anyone else's PR, a PR title or
    description, a commit message, an inline review comment, an issue or PR
    comment, or a Jira comment. Everything mozzy11's account signs is
    mozzy11's.
- **Short enough to read in a minute.** Findings, not narrative: the reader
  should get your overall take and the blocking items from the first five
  lines. Evidence is a link or a one-line "ran X → Y", never a
  pasted log.

## 1. Read the full context

- PR description, every commit, every changed file, all existing comments and
  reviews (yours from earlier sessions included), linked Jira/FRS, CI status.
- **Effective diff, not raw diff**: for branches carrying merge commits,
  review `git diff <base>...<head>` — GitHub's Files-changed view equals this;
  the commit list does not.
- Fetch the branch locally into a **worktree** for anything beyond trivial
  reading; never review a large PR purely from the web diff. For a PR with
  many changed lines, or any UI change, the worktree is also what you build,
  deploy and live-test (§3): reading such a PR is not reviewing it.
- On large PRs, **fan out subagents for the read-heavy half** (one per
  subsystem/dimension, reporting file:line findings only) and keep the main
  context for verification and judgment. Prefer the GitHub/Atlassian MCP
  tools over ad-hoc curl for structured PR/issue data. A subagent finding
  is a lead, not a finding: it enters the review only after a live probe,
  a memory or your own read confirms it (#4753, 2026-10-16: 3 of 13 reader
  leads were wrong, among them a Transifex plural shape that memory
  `project_transifex_plural_shape` lists as uploading fine).

## 2. Structural checks that have caught real problems here

Run these before reading logic:

- **Submodule pointers**: for each changed gitlink, check ancestry both ways
  (`git merge-base --is-ancestor`). A pointer that is an *ancestor* of the
  base branch's is a **rewind** — it silently reverts other people's work.
- **Liquibase**: changeset filename/number collisions against the base branch,
  duplicate `(id, author)` pairs, orphaned files, includes that don't resolve,
  and whether reruns are guarded (`preConditions onFail="MARK_RAN"`). Two
  changesets redeclaring the same CHECK constraint = last-writer-wins.
  A data changeset that rewrites a column under a unique index (trim, lower)
  must survive two rows that collide only after the rewrite: insert such a
  pair in `BEGIN; ... ROLLBACK;` and run its SQL (#4722, 2026-10-14: 138
  checked against stored trimmed codes only, so `' X'` + `'X '` stopped the
  upgrade).
- **Workflow files** (`.github/`): for each change, answer "what runs
  differently on the default branch after merge?" — especially anything
  touching image publish names/tags. Prove default-branch equivalence by
  executing the guard logic, not by eyeballing it. Lint with
  `git show <ref>:<file> | docker run --rm -i rhysd/actionlint:latest -no-color -oneline -`
  (not installed locally; `-color=never` is rejected), then `docker rmi` it.
  For image publishing, check platforms and name collisions with
  `docker buildx imagetools inspect <image:tag>` (#4724, 2026-10-14).
- **Schema/constraint interplay**: new writes against columns with unique
  indexes or NOT NULL constraints; entity graphs with versioned
  (`optimistic-lock`) mappings fed from caches.
- **Spring wiring**: new service→service edges can close construction cycles
  that only detonate under a different bean-creation order (fix: `@Lazy` on
  the new edge, verified by the full suite, not a single test).
- **Removed symbols**: for every export, class or method the diff deletes,
  `grep -rn <name> frontend/src src` at the head and run each hit's tests
  (#4769, 2026-10-20: `OrderPossibleTestsHeaders` was still imported by
  `sortableHeaders.test.js`, the only red file in CI's Static job).

## 3. Verify by running

- Build the merged/head tree; run the full backend suite in an **isolated
  copy** via `claude-work/bin/iso-suite.sh <repo> <sha> <copy> <log>` (never
  in-repo: IDE rebuilds corrupt `target/`; never a `cd <copy> && mvn` chain),
  and the frontend suite with `npm --prefix frontend run test`.
  Start it with Bash `run_in_background` right after the read and let its
  completion notice end the wait; a Monitor caps at 10 minutes, and on #4771
  (2026-10-20) four re-armed Monitors covered one 50-minute suite.
- A test that fails after you did inversion-style experiments may be running
  **stale bytecode** — rerun in a clean copy before believing it.
- **Live test: mandatory when the PR is cross-stack, behavior-facing, or
  large.** Decide from the effective diff, not the description. A live test
  through the Playwright MCP (UI) **and** the API is **required** when any
  of these hold:
  - files change under both `frontend/` and the backend (`src/main/java`,
    `src/main/resources`, Liquibase changesets, `pom.xml`);
  - a user-visible flow changes (a screen, a form, a validation, a REST
    endpoint a screen calls), whatever the file count;
  - **the PR carries many lines of change** (user instruction, 2026-09-21):
    as a guide, more than about 200 changed lines, more than about 8 files,
    or more than one screen touched, and **any UI change beyond a one-line
    fix**. That is where an integration mismatch hides between two green
    test suites, and reading a large diff is not reviewing it.
  For such a PR the review is **never** submitted from the web diff alone:
  the PR is **cloned locally, built, deployed on the dev stack and tested
  strictly, function by function, through the UI and the API**, and the
  verdict follows what the browser and the API showed. A PR that only
  touches docs, CI, or an isolated pure function may skip it; say so in the
  review. A seed or deploy script that calls the REST API still gets run:
  copy it out of the repo (so the repo's `.env` cannot point it at a real
  stack), serve a small stub of the endpoints it calls, and run it from each
  starting state, the old script included, comparing the logged writes
  (#4773, 2026-10-20: five states plus the old seed, no stack needed while
  the shared one was lent out). `.github/scripts` tests need `pyyaml`: run
  them from a scratchpad venv, or three modules fail to import.
- **A green CI job counts only for the steps it ran.** Path filters skip
  jobs: read the run's job list before citing it as evidence (#4773: "03 -
  E2E" ran Detect Changes and Shared Build only, and the draft had claimed
  its seed step).
- **Any change YOU author is live-tested end to end before you push it
  (user instruction, 2026-09-23 — the rule broken most often, and the one
  the user has had to repeat).** Reviewing someone else's code and pushing
  your own fix onto their branch are different acts: the moment you write a
  line, the whole live-test gate applies to *your* line, with no exemption
  for size, layer or "obviously safe". A one-line fix, a SQL expression, a
  Hibernate mapping, a formatter change — all of it.
  - **List the blast radius before you push, not the part you set out to
    fix.** Every screen, report, dashboard, export, scheduled job and
    endpoint that reads or writes what you touched goes on the list, and
    every one of them is driven through the Playwright MCP on the dev stack
    (plus the API where it lives server-side). Derive the list from what the
    code reaches — grep the callers — not from what you were thinking about.
  - **Verifying a layer in isolation proves that layer only.** A SQL
    expression checked in `psql`, a helper covered by a unit test, a green
    suite: none of these is evidence that the screen using it works, and
    none may stand in for driving that screen. If you changed a query the
    dashboard runs, you open the dashboard.
  - **Missing fixture data is not a reason to skip a surface.** Create the
    order, the sampling site, the threshold, the critical range — through
    the UI or the API — and then exercise the screen. Only when that is
    genuinely impossible do you say so **in the message that accompanies the
    push**, naming the surface as unverified. Never discover the gap because
    the user asked.
  - **Make every check discriminating** (the pattern the user confirmed on
    #4380, 2026-09-23: "you should always do this"). An input whose expected
    outcome could also arise without the code under test proves nothing:
    `6.5×10¹` and plain `65` both produced 66, so a fresh order with
    `8.5×10¹` → `86.0` was needed. For every rule, threshold or branch, drive
    **one value that must trigger it and one that must not** (`9.5×10¹` fired
    the `> 90` reflex and alert, `8.5×10¹` fired neither and got the Abnormal
    flag). A claim about an engine stands only when **the UI row, the
    database row and the audit row agree** (here the `notifications` table
    logs each reflex, calculation and alert firing). Use fresh records on
    distinct parents when a table is keyed per patient or per order, so a
    stale binding cannot pass for a result. When the live run contradicts an
    earlier claim of yours, the claim was wrong: correct it in the same
    thread.
- **The served WAR must match the head.** Compare the WAR's time with the
  head's last amend (`git reflog`); if older, redeploy per memory
  `project-dev-stack-redeploy-without-mkcert` (`mvn clean` breaks the
  single-file WAR mount, and `dev-stack up` needs mkcert or
  `DEV_STACK_TLS=self-signed`). On #4755 (2026-10-16) the stack served a
  WAR from before two amends. After a rebase or reset every commit carries
  the amend time, so the times prove nothing: unzip the PR's classes and
  `grep -rla <new method or message key>` them (#4771, 2026-10-20: a 09:18
  WAR held all of an 11:12 head's code).
- **Shared stack already serving the PR (check first).** When the PR head
  is already on local develop and deployed, and `git diff <head> HEAD` shows
  that no later commit or working-tree change touches the PR's files or
  methods, walk the shared stack: confirm both contexts carry a PR-only
  symbol (`grep -c <newMethod>` on the class in `OpenELIS-Global` and
  `api#OpenELIS-Global`). This avoids a second stack while another session
  runs testcontainers on 5 GB of free disk (#4694, 2026-10-12). Use
  `git show "<ref>:<path>"` quoted: in zsh `$P:path` is a modifier.
- **Low disk, later commits on the PR's paths:** use memory
  `project_light_isolated_stack` (cloned DB in the shared Postgres, one extra
  webapp container, host Vite) instead of `dev-stack up`; it fit in 4 GB free
  next to another session's stack (#4700, 2026-10-13). After `git archive`
  and the WAR build, `claude-work/bin/light-stack-up.sh <N>` clones the DB,
  starts the webapp and writes the Vite config (#4713); tear it down with
  `claude-work/bin/teardown-light-stack.sh <N>`.
  Under ~4 GB free, run the regression specs with `--workers=1`: two
  workers next to two stacks hung the Docker daemon and took the shared
  stack down (#4715, 2026-10-13; recovery in memory
  `project_docker_vm_readonly_kills_postgres`). Read the DB rows you need
  before teardown, in a call of their own.
  While specs run, arm a background guard that kills the run under 400 MB
  free (`df -m /`): a light-stack review fell from 4.4 GB to 719 MB
  (#4722, 2026-10-14).
- **How to clone and deploy the PR head.**

  ```bash
  N=<pr-number>
  git fetch upstream "pull/$N/head:pr-$N"
  W="$(dirname "$PWD")/OpenELIS-pr-$N"
  git worktree add "$W" "pr-$N"
  mvn -f "$W/pom.xml" clean install -DskipTests -Dmaven.test.skip=true
  # Take over the shared dev stack from the worktree: same project name, so the
  # fixed-name containers are recreated with THIS tree's WAR and frontend/src.
  # Absolute paths only, never `cd` (a cd chain prompts; 2026-10-13 log).
  docker compose -p openelis-global-2 --project-directory "$W" \
    -f "$W/dev.docker-compose.yml" up -d \
    --force-recreate oe.openelis.org frontend.openelis.org
  ```

  `docker compose ls` shows the project name if it differs; it defaults to
  the lower-cased directory name of the main checkout. Restart the proxy
  service, then confirm the served build via
  `WEB-INF/classes/build.properties` and, for anything the PR removes,
  `unzip -l target/*.war | grep <Class>`. The recreated front-end container
  may 500 on `/src/index.jsx` because the dev image's `node_modules` lag
  `package.json`: that is the image, not the PR. Run `npm ci` inside the
  container and restart Vite; if the PR adds a dependency, add it with
  `npm install --no-save <dep>` the same way. After that, never recreate the
  front-end container again for a WAR change. If a long-lived volume trips an `onFail="HALT"` data gate,
  recreate the volume before concluding the PR is broken. When the review
  is done, recreate the stack from the main checkout and remove the worktree
  (`git worktree remove`), so the next session finds develop deployed and
  the disk clean.
- **Then test it, carefully, function by function.**
  - **Build two inventories from the effective diff before clicking
    anything**, and write them into the review notes as checklists: the
    *surface inventory* (every screen, menu entry, column, filter, field,
    modal, dialog, drawer, notification, empty and error state the diff
    touches, plus other screens reading the same data) and the *function
    inventory* (every function the PR adds or alters, in user terms, each
    with the action that exercises it, the expected on-screen result, the
    request it should send and the persisted state it should leave). One
    function is one row.
  - **Every row is clicked by hand through the Playwright MCP; a spec run
    never replaces one** (user instruction, 2026-10-15, after the #4410
    review left add cassette, add slide, the Deactivate dialog, the Show
    deactivated switch and the counts to the PR's own specs run from the CLI:
    "manually click through the screen by mcp playwright as i always say, no
    chances for a regression"). Running the Playwright specs is extra
    evidence on top of the hand walk, never instead of it, and that includes
    the author's own specs for the feature. A row only counts as exercised
    once you drove it yourself in the MCP browser and checked the screen,
    the request and the stored row. This applies equally to the rows of a
    fix you push onto the PR and to the regression matrix cells.
  - **UI through the Playwright MCP** (`browser_navigate`, `browser_click`,
    `browser_type`, `browser_select_option`, `browser_snapshot`,
    `browser_console_messages`, `browser_network_requests`,
    `browser_take_screenshot`): log in with the `.env` test credentials and
    walk every row, one action at a time (snapshot, act, snapshot, compare
    with the expected result), never chaining actions and checking only the
    end state. Cover create *and* edit paths, every modal in both states
    (fresh, and opened on an existing record), every field round-tripped
    through a save and a reload, happy path and negative paths (invalid
    input, empty required field, duplicate, cancel, boundary value), each
    conditional branch forced to render, both sides of any role or config
    gate, empty states, and the flows adjacent to the change. Read the
    console and network panes after each step; a 4xx/5xx or a React error
    is a finding even when the screen looks right. Give
    `browser_take_screenshot` a bare filename: the MCP writes only under
    `claude-work` and `claude-work/.playwright-mcp`, and a scratchpad path is
    refused (#4728, 2026-10-14). Never pass `filename` to `browser_snapshot`:
    it wrote `s168.yml` into the product repo root (#4769, 2026-10-20).
  - **Regression matrix, on every live-tested PR** (user instruction,
    2026-09-26: as much live UI testing through the Playwright MCP as
    possible, every case scenario related to the changed files, so the PR
    breaks no existing workflow). Build it exactly as `resolve-issue` §3b
    describes: per changed file its consumers (grep imports and callers up
    to the screens, reports, exports and jobs), per consumer its workflows
    including the ones the PR description never mentions, per workflow its
    scenarios (happy, negative, lanes and variants, empty / existing /
    legacy data, roles and config gates on and off). Where the expected
    outcome is not obvious, drive the scenario on `upstream/develop` first
    so a change in behavior is attributable. Walk every cell in the
    browser, run the existing Playwright specs for those screens against
    the stack (rerun a failure alone with `--workers=1` before calling it:
    specs that flip site config clash when run in parallel, 2026-10-13
    #4704). Build the spec list with `find <dir> -name <spec>.spec.ts`, never a
    glob inside `$(...)`: in zsh a non-matching glob aborts the substitution,
    the list comes out empty and all 484 core-app specs start (#4717,
    2026-10-14), and record consumer -> workflow -> scenario -> expected ->
    observed. A difference the PR does not claim is a regression finding.
    Wait for the run's end with an unanchored `grep -aE '[0-9]+ (passed|failed) \('`:
    the line reporter prefixes ANSI codes, so `^\s*N passed` never matched and
    the waiter ran to its timeout (#4720, 2026-10-14). Run specs without a
    `cd frontend && ...` chain (each one raised a permission request, #4728):
    `<repo>/frontend/node_modules/.bin/playwright test -c <repo>/frontend/playwright.config.ts ...`
    with `--output <scratchpad>/pw-out`. Never `rm -rf <repo>/frontend/test-results/*`:
    the checkout is shared, and on #4757 (2026-10-19) that deleted another
    session's failure artifacts. Before a run, rule out the known local
    blockers instead of spending the run on them:
    - On a dev-stack DB, specs that order through
      `createSampleOrder`/`orderTests` answer 500 on fixture provider
      `Person#9000002` (memory `project_local_e2e_ci_parity` item 4). Load the
      fixtures first, or judge those specs by CI.
    - For harness specs, read the author's latest run log in
      `claude-work/missions` and `curl -sk localhost:8085` (the analyzer mock).
      On #4757, `beforeAll` analyzer activation burned 600 s, the same failure
      the author's log already showed, and port 8085 refused.
    - Seeding setups (`participant-auth.setup.ts`) `docker exec` the DB by
      name: export `DB_CONTAINER` and `HARNESS_DB_CONTAINER` as
      `$COMPOSE_PROJECT_NAME-db.openelis.org-1` (from `scripts/dev-stack env`),
      or every spec is skipped behind a failed setup (#4769, 2026-10-20).

    Wait with Monitor, never a foreground `sleep` (the harness blocks it). Pass
    spec basenames as filters (`ogc-1483 ogc-1488`), not absolute paths: run
    from another cwd, absolute paths matched nothing ("No tests found", #4731).
    For every user-visible string the PR changes (toast, label, error text),
    grep the old text in `frontend/playwright` (helpers and demo specs too)
    and run each hit: #4731 changed a save toast that a vector seed helper
    and two CI demo specs still waited for.
  - **Typed numbers round-trip to the row.** After saving a number typed
    into a Carbon `NumberInput`, read the stored value: a handler that
    clamps state leaves the input showing the typed value (#4757,
    2026-10-19: aliquot typed 2, stored 0, on a tube with no quantity).
  - **API** with the session cookie + `X-CSRF-Token` (the `csrf` field of
    `GET /api/OpenELIS-Global/session`; `source claude-work/bin/oe-probe.sh`
    gives `login <user> <pass>` and `call <METHOD> <path> [json]`, pointed
    at the dev-stack BASE_URL): one call per function row that
    lives server-side, including the edge inputs the PR claims to handle
    and the invalid input each validation must reject. Assert the status,
    the body and the persisted row (a GET or `psql` in the database
    container, one statement per `psql -tAc`: with several it prints only
    the last result, which once read as "no row"). A 200 is not proof; the row is. Snapshot the rows first
    and compare after each probe, and give every probe that might succeed
    a payload that is harmless if it does (each test's own data): on #4694
    an "omitted field" probe returned 200 and wiped two tests' ranges, and
    a later probe wrote one test's set onto another (2026-10-12). Also
    probe an omitted key, not only `null`: Jackson keeps a DTO's
    `= new ArrayList<>()` default, so the null check never fires.
    For every length limit, also send the maximum with spaces around it:
    a check on `trim().length()` over an untrimmed store passes it and the
    column answers 500 (#4722, 2026-10-14: Storage text, reagent unit).
    For a numbered or versioned write (version N+1, a sequence per
    parent), fire two identical requests with `Promise.all`; for a state
    the PR derives (printed, amended, partial), drive the in-between
    states too (a released result sent back for correction, a batch that
    mixes ready and pending records). On #4753 (2026-10-16) these three
    probes found all three Required items; the happy paths all passed.
    For a queue, outbox or scheduled worker, queue more items than one
    batch against a slow target (an unroutable host such as
    `10.255.255.1`) and watch for two attempts on one item within less
    than the retry delay: the WAR runs two workers in one JVM, and on
    #4755 (2026-10-16) a 120 s lease over a 20-row batch let both send
    the same message.
    Inside `browser_run_code_unsafe`, `page.request` needs absolute URLs, and
    `require` and `URL` are undefined: a print clicked before such a line
    still happened (#4771). Fetch PDFs with curl by version id instead.
  - **Printed reports:** click Generate in the MCP, take the `ReportPrint?...`
    URL from the popup, fetch it with `curl -k -b JSESSIONID=<from
    context.cookies()>` and read it with `claude-work/bin/pdftext.sh` (page
    count, size, text). The UI language switch calls `Home?lang=fr`, so the
    same cookie prints the French report. A referral save that answers 500
    with `UnknownHostException: fhir.openelis.org` in the log means the
    stack's FHIR container is stopped: start it, walk, stop it again (#4747,
    2026-10-15).
  - Frontend unit tests: `npm --prefix frontend run test -- --run <file>`;
    `npm --prefix frontend exec vitest` runs from the caller's directory,
    misses the vitest config and fails every file (2026-10-12).
  - For a new config property, assert the key the server publishes on
    `/rest/configuration-properties`; for a Liquibase changeset, assert the
    `databasechangelog` row and the object it creates. Use a throwaway DB
    volume for fresh-boot/migration verification; leave shared data as found.
  Record expected vs observed for every row. A live result that contradicts
  the PR's tests is a finding: the mock agreed with the author. The review's
  verification line names what was walked and gives both tallies
  (functions inventoried / exercised / passed; regression scenarios listed
  / walked / passed); any row or cell not exercised is named as
  unverified. If the stack cannot be brought up, say so explicitly and do
  not Approve. A required live test that was skipped, or a function that
  failed live, rules out Approve.
- A PR last pushed days ago whose CI was re-run fails E2E with
  `container openelisglobal-webapp is unhealthy` on every shard: the re-run
  built its original merge ref, an old webapp against today's service
  images. Compare with other E2E runs of the same hour; if theirs are
  healthy, `gh pr update-branch <n>` and approve the new fork runs instead
  of re-running failed jobs (#4412, 2026-10-15).
- Attribute every failure: introduced by the PR, pre-existing on the base
  (prove with a base-branch run or blob comparison), or environmental.
  CI E2E logs print failing specs only, so a spec missing from a green log
  proves nothing. A PR that adds or removes a spec reshuffles the shards: for
  a red spec outside the diff, diff `playwright test --list --shard=k/4`
  with and without the PR (git archive both refs, symlinked node_modules) to
  find the spec it used to share a shard with (#4720, 2026-10-14: ogc-1423
  relied on ogc-1420 refreshing a cached list; memory
  `project_e2e_shard_order_dependency`). A failure that repeats on a rerun of
  the failed jobs is not a flake.

### openelis-docker pull requests

Run the PR's own compose on fresh volumes with non-default `.env` values and
build the package; recipe in memory `project-openelis-docker-review-recipe`.
Its webapp has no healthcheck: wait on the "Server startup in" log line, not
`.State.Health.Status` (2026-10-16, #60: a health wait ran 10 minutes to its
timeout).

### Docs and IG pull requests

For the FHIR IG repo, a green build job is not enough: read the IG Publisher
QA line in the build log (`Errors: N, Warnings: N, Info: N, Broken Links: N`)
and compare it with the last clean build on main. Errors or broken links are
Required; new warnings need an explanation. Check every changed profile
comment and every removed Known Issue against the code on develop
(2026-10-12: #21 shipped 1 error and 1 broken link behind a green job).

## 4. Inline comments

- Only where actionable and anchored to a specific line: what's wrong, why it
  matters (failure scenario), and the expected shape of the fix when useful.
- Short, direct, respectful — **at most three sentences per comment**, plain
  words, one code snippet only when it shows the fix. No style nits unless
  they materially affect correctness, readability, or consistency with the
  file's own conventions.
- **Write to the person, about the code.** State what you observed and the
  consequence, and leave the fix to them unless the shape is genuinely
  useful. Where something is a judgement call rather than a defect, ask
  ("worth confirming with X?") instead of instructing. Never imply
  carelessness, never pile on once a point is made, and do not leave a
  comment whose only content is that you would have written it differently.
- **A suggestion about a file outside the diff** (a follow-up, a "gap remains")
  names that file's role only after checking it: who runs it, which docs
  point at it, which workflow consumes it. (2026-10-15: #4724 follow-up said to
  point `docker-compose.yml`, the deployment compose, at `-dev` images; user:
  "is docker-compose.yml the dev compose file ??", a correction was posted.)
- **Budget your comments.** Ten inline notes on one PR reads as a takedown
  however politely each is worded. Keep the ones that change what someone
  does; drop the rest, or roll several small ones into a single line in
  Optional improvements.
- If you also push fixes to the PR (only when asked or when it's your role on
  that PR), reply to each thread with what you did — and never resolve
  threads you didn't act on.

## 5. Submit the review

Write it the way a colleague would: a short opening sentence in plain words,
then the findings. The `Decision:` line and the footer line exist only in
the self-review case from §0; drop both entirely when reviewing someone
else's PR as mozzy11.

```
Decision: Approve / Request changes / Comment   <- self-review only

[One or two plain sentences: your overall take, e.g. "Walked this end to
end and it holds up, nice work." or "Mostly there, but the save path
drops the collector name, details below."]

Summary:
- [Most important point]
- [Most important point]

Required changes:
- [Only blocking items, if any]

Optional improvements:
- [Only genuinely useful non-blocking items, if any]

Generated by Claude Reviewer   <- self-review only
```

- **The footer is for self-reviews only, without exception** (user
  instruction, 2026-10-07). A review of anyone else's PR never carries it,
  or anything else hinting at Claude, an assistant or a template: it should
  read as a natural review written by mozzy11.

- **A verdict label only where the action is impossible** (user
  instruction, 2026-10-07). On someone else's PR, never write "Decision:
  ...", "Verdict:", "Status:" or any similar line, in the body or an inline
  comment: the GitHub action you take is the verdict, and the body just
  reads like normal review comments. Only on a self-review, where GitHub
  blocks approve and request-changes, does the body open with
  `Decision: Approve`, `Decision: Request changes` or `Decision: Comment`
  (see below).
- Keep it tight: **Summary ≤ 5 bullets, one line each**; Required and
  Optional lists only when non-empty (drop the heading otherwise). The whole
  review should fit on one screen.
- Verdict rules, applied only after the three blocking questions in §0:
  **Request changes** for a regression on a shipped screen, data loss or
  corruption, a security hole, a crash, missing tests on changed behaviour,
  or **any function that failed the live UI/API walk** — and only when the
  item survives those three questions. **Comment** for everything else that
  is worth saying, including disclosed design decisions you would argue
  differently, polish, and questions for whoever owns the ticket; this is the
  common verdict and it is not a soft option. **Approve** when you have
  verified, not assumed, that CI is green, nothing blocking remains, and,
  where §3 required a live test, every row of the function inventory was
  exercised in the browser and via the API and passed, and every cell of
  the regression matrix was walked with no unexplained change from develop. A required live test
  that was skipped or could not be completed never yields Approve.
- **Before you submit, re-read your own Required section and cut it down.**
  For each item ask whether you would genuinely hold a colleague's work over
  it. If the honest answer is no, move it to Optional. An empty Required
  section on a well-built PR is the expected result, not a failure to find
  anything.
- **Say what works, first and specifically.** Open the Summary with what you
  verified working, named concretely, before any concern. The author needs to
  know their work was actually exercised, and a reader needs the shape of the
  PR before its rough edges.
- One line on what you verified by execution vs. by reading (for a
  live-tested PR: the functions walked and the tally inventoried / exercised
  / passed), and what you could not verify (inaccessible repos/logs/
  environments). No pasted output.
- No signature of any kind on someone else's PR (§0 Authorship). In the
  self-review case the only attribution is the `Generated by Claude
  Reviewer` footer, as the last line; inline comments carry no tag.
- **Submit it as the action itself** (user instruction, 2026-10-07). On
  someone else's PR the verdict is the review event, never a line of text:
  - Request changes → `gh pr review <n> --repo <owner/repo>
    --request-changes --body-file <file>`
  - Approve → `gh pr review <n> --repo <owner/repo> --approve --body-file
    <file>`
  - Comment → `gh pr review <n> --repo <owner/repo> --comment --body-file
    <file>`
  Inline comments ride along in the same review (pending review via the
  API, then submit it with the matching `event`: `REQUEST_CHANGES`,
  `APPROVE` or `COMMENT`). Read `headRefOid` again in the same call that
  posts, and if it moved past the sha you reviewed, diff the two and fix the
  body first: on #4769 (2026-10-20) an amend landed seconds before the post,
  a Required item was already fixed, and a correction review was needed.
- **Self-review exception, forced by GitHub.** GitHub refuses approve and
  request-changes on your own PR (422 "Can not approve/request changes on
  your own pull request"), so on mozzy11's own PR submit with `--comment`
  (event `COMMENT`) and put the verdict in the body's first line as
  `Decision: Approve`, `Decision: Request changes` or `Decision: Comment`,
  with the `Generated by Claude Reviewer` footer as the last line. Do not
  try the other events first on a self-review; you already know they fail.
  If GitHub ever refuses the action on someone else's PR for another
  reason, the same fallback applies: comment event plus the `Decision:`
  line, but **never** the footer; that review is still plain mozzy11.
- **Tell the caller in your final message.** End your session output with
  one plain line naming the verdict you applied (approved / requested
  changes / commented) so a calling pipeline can read it from the log.
- Merging afterwards is a separate, explicitly-instructed act — never part of
  the review itself. When told "merge", bypass rules and merge at once (see
  memory `merge-means-now-admin-bypass`). A PR in a native GitHub stack
  (`gh api repos/<o>/<r>/pulls/<n> --jq .stack` is set) can only merge with
  everything below it: run `claude-work/bin/merge-stack-rebase.sh` (records
  heads, moves each next branch onto develop past its squashed parent,
  merge-async with `bypass_rules`, bottom-up).

## Docker teardown (always, before the retro)

Docker here has 7.6 GB and is shared with other sessions, so every stack this
session started is removed before it ends (user instruction, 2026-10-12):
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
- Report the teardown in the final message (projects removed, containers
  left = 0, free disk).

## Retro (always, after the review is posted)

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
