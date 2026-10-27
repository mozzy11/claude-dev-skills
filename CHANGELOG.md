# Skill changelog

Kept by the session-retro skill: one entry per retro, each change with its evidence.

## 2026-10-27 queue check (session dcbd9657)
- Queue line 71ffb6d0 dropped (retro already in its session). Permission log empty.

## 2026-10-27 retro of 71ffb6d0 (review-pr #4833, self-review, Request changes)
- review-pr §3 API/UI probes: type one character past each text column into the form, and double-click Save on a create form keyed by a unique value, then count rows. Evidence: both probes found the two Required items (31-character login gave "Oops, Server error"; a double-click made two rows with one login that could not sign in or be opened); every happy path passed.
- Memory project_light_isolated_stack: the cloned DB keeps the shared DB's French default locale, so API-fetched role names come back French and admin-user-lab-unit-roles fails on the dialog text; judge it by CI.
- Kept: waiting for CI's Build + Test before posting settled an open question (the PR test's digit login vs the seeded charset) without a local suite run. Queue and permission log empty.

## 2026-10-26 queue check (session 71ffb6d0)
- Queue line 8e457bae dropped (retro already in its session). Permission log: one hook-approved `rm -f` loop over .playwright-mcp files under bypass mode, from the §3 MCP file cleanup; no rule needed.

## 2026-10-26 retro of 8e457bae (review-pr #4831, self-review, Request changes)
- review-pr §3 light stack: boot one webapp per review under ~5 GB free and drive property variants with a unit test in the copy; `docker rm` the container right after the walk. Evidence: one env-variant reboot took free disk 3.2 GB to 385 MB and the guard stopped the run; `docker rm` gave 2.6 GB back. The scratch unit test then found the Required item (empty Bridge URL with a stored pin answers 500).
- review-pr §3 MCP files: the MCP root follows the session cwd, so screenshots and page/console files land in the product checkout; move or delete them before posting. Evidence: pr4831-unreachable.png in the repo root, 10 files in its .playwright-mcp.
- Kept: probing the JDK HttpClient exceptions directly (refused, unknown host, timeout, empty URL) pointed at the uncovered empty-URL path before any stack time was spent. Queue line af358344 dropped (own entry). Permission log empty.

## 2026-10-26 retro of af358344 (review-pr #4824, self-review, Request changes)
- review-pr §3 light stack: the helper now copies the shared webapp's env, mounts and networks; specs seeding through db-container.ts hit `clinlims`, judge them by CI. Evidence: light-stack-up.sh failed twice (keystore password, encryption key, no DB network); critical-callback seeded the shared DB.
- review-pr attribution: compare a red E2E spec with another PR's run on the same base before calling it a race. Evidence: the harness shard looked like the known gate race; #4721's run passed the same spec, so "<40.00" was the PR's (author fixed it in 273e82b before the post).
- resolve-issue live-test data: walk-created configuration (calculations, reflex rules, ranges) is removed in the cleanup. Evidence: an "OGC1544 calc walk" calculation left on the shared DB blanked released Creatinine results.
- Helpers: claude-work/bin/light-stack-up.sh and teardown-light-stack.sh find the dev-stack DB/webapp containers. Kept: headRefOid re-read before posting caught the amend; the review was rebased on 273e82b.

## 2026-10-26 retro of f46b9b94 (review-pr openelis-docker #61 round two, self-review, Request changes)
- review-pr openelis-docker: run a release workflow's steps against the inputs it meets after merge (the existing tag's old files), not only the PR head. Evidence: running the step on the real 3.3.0 tag showed pin-versions.sh stopping, the Required finding of the round.
- Kept: stubbing pull/save in build.sh checked pinning without the disk cost; only small test containers, shared stack untouched. Queue line 23d7154d dropped (own entry). Permission log: 3 hook-approved compound scratchpad commands under bypass mode, no rule needed.

## 2026-10-26 retro of 23d7154d (review-pr openelis-docker #61, self-review, Request changes)
- review-pr openelis-docker: drive each documented recovery step on the shipped image, and probe bind mounts written by non-root containers with a root-owned volume. Evidence: the README re-pair (new code + up -d) did nothing on 3.3.0; the Bridge (uid 9257) got Permission denied creating an import folder, hidden by Docker Desktop.
- Memory project_openelis_docker_review_recipe: runs beside the analyzer-harness dev stack with a subnet/IP override (172.20.0.0/16 overlap), package staging without pulls, Bridge walk recipe (BC-5380 to Connect, MLLP sender, Pair again).
- Kept: the HL7 send from the host port proved the Bridge publication end to end (MSA|AA, 2 analyzer_results rows). Queue line 3feabbb2 dropped (own entry). Permission log empty.

## 2026-10-26 retro of 3feabbb2 (review-pr #4822, self-review, Request changes)
- review-pr §3 MCP: state does not survive between run_code calls, so a held page.route is held, checked and released in one call. Evidence: `globalThis.__release is not a function` left the order load hung and the walk was redone in one call.
- Memory: legacy Add Order and Modify Order Current Tests selectors (v4 walk recipe); purge-rows misses sample_requester (no FK), seed it explicitly.
- Kept: the held-load walk found the loading screen showing "Female" for a male patient (Required); the stale-requester probe ran through the UI by rewriting the POST, so the on-screen message was checked too. Queue and permission log empty. The skills push needs the literal path after `git -C` (the pre-push gate reads the command text; `$R` sent it to the OpenELIS tree).

## 2026-10-26 retro of 7289cc13 (part after its 2026-10-22 retro: cleanup thread)
- resolve-by-criteria §3 and resolve-issue live-test data: walk data on the shared dev DB is purged in full with purge-rows.sql (backup, dry run, commit), never left with a question or a volume-reset offer. Evidence: the first "clean the seesion artifatcs" pass asked about 51 test orders; the user repeated "clear the session artifacts".
- Kept: the purge (pg_dump first, ROLLBACK dry run, dangling-FK check) removed 51 orders, 49 patients, 30 providers and a site with the stack still healthy. Memory project_dev_db_purge_helper already records it. Second queue line was a duplicate of the same session. Permission log empty.

## 2026-10-22 retro of 7289cc13 (resolve-by-criteria OGC-1529 + OGC-1507, both merged; queue: ac549c03 reviewer run, retro already done)
- resolve-issue 3b: a change to which stored value wins drives every writer, every reader and each reset on the weakest data (no upstream translation, a regional locale); a changed shared component is submitted from every host. Evidence: #4800 review rounds 1 and 2 found dropped editor renames, a fr-HT lockout and Reset storing English; InlineNceForm 400 from five order steps.
- resolve-issue 3: inversion runs must have really executed (stale report, compile error, zsh `$F`); run each new unit test class alone once. Evidence: two non-runs of the inversion, ShippedLabelsTest passing only after Spring had started.
- resolve-by-criteria 3e: a required check red from an external outage gets a general fallback in the current PR after about two hours. Evidence: download.eclipse.org down 16 hours, eclipse-p2-mirror fallback in #4800.
- Memory: project_ci_formatting_eclipse_outage (fallback recipe), project_dev_stack_config_flip_and_fixture_ids (DB_CONTAINER and local fixture ids for spec runs). Settings: allow mcp__claude_ai_Atlassian__* (two getJiraIssue prompts).

## 2026-10-21 (session ac549c03 review-pr #4800 round two)

- review-pr §3 discriminating checks: drive every step of a fallback chain on a record where the sources above it are absent, and Reset after an override replaced the stored value. Evidence: round one checked Reset on a Transifex-translated label; round two found Reset stores English as the shipped French (Required).
- review-pr §3 specs: full basename plus `--list` before a run. Evidence: filter `ogc-1507` also ran a manual-only seeding spec that wrote NCE 24 to the shared DB (removed in cleanup).
- Kept: cmp of the 15 interdiff classes proved the shared stack served the head, no redeploy. Queue: df445497 dropped (own entry). Permission log empty.

## 2026-10-21 (session df445497 review-pr #4800 self-review)

- review-pr §3 shared stack: prove the served WAR matches the head by `cmp` of every changed class and resource against the isolated copy's build when the WAR predates the commit. Evidence: WAR 12:30 vs commit 13:39, 53 classes identical, walk ran on the shared stack without a redeploy.
- review-pr §3 regression matrix: a PR that changes how rows are read gets every writer of those rows driven through save and reload. Evidence: Sample Acceptance rename answered 200 but the new SYSTEM-origin read order hid it (reader lead, confirmed live, Required).
- Kept: two reader subagents as leads only; of their leads, 2 became Required after live proof, 1 (dictionary rename) was refuted by reading the update path. Queue: 5b2a48b1 dropped (own entry). Permission log empty.

## 2026-10-21 (session 5b2a48b1 review-pr #4799 self-review)

- review-pr §3 UI walk: never two browser calls in one tool block; seed setup data with a scratch-dir spec (symlinked node_modules, absolute helper imports, explicit login). Evidence: a parallel Print click and an Edit/fill/Save batch on #4799 all raced page loads and had to be redone; the saved storageState returned HTML to page.request.
- review-pr §3 API: oe-probe `call` truncates at 220 characters; parse JSON from plain curl. Evidence: three JSONDecodeErrors on /rest/reportQueue responses.
- Kept: inversion run (base main code + PR tests, 3 failures) and three hand-walked scenarios (ticket flow, single test, new release while a correction waits); the full-suite CI wait gated Approve.

## 2026-10-21 (queue: sessions fe696b4e release notes 3.3.0, 8a67dc7d part after its 2026-10-20 retro)

- resolve-by-criteria §3e: PRs with no app code (workflows, deploy scripts, docs) merge once Formatting and their own checks pass; deploy-only fixes are proven on the merge's deploy. Evidence: "the just merge the PR since no app code changes", "then just merge because the PR wont catch it"; #4783 with en.json still waited ("wait for ci to run and then youll merge").
- resolve-by-criteria final report: answer the asked question first in plain words. Evidence: "you talked too much i ddnt get your point, be direct", "you ddint answer my question".
- Kept: the testing deploy analyzer smoke went green at 4909f67 after the seed and smoke fixes (#4773, #4774, #4783).
- Memory: be-direct, no-app-code-merge-without-full-ci, release-cut-sequence (pom bump -> develop to main -> next SNAPSHOT; Confluence Past Releases parent edited as html after a markdown 422). Permission log empty.

## 2026-10-20 (session 9cb5c857 prepare-for-next-release summarized re-check, run 2026-10-19-1732 attempt 3)

- prepare-for-next-release Phase 0: summarized re-check recipe (reuse the finished run's verified backup, restore-run, baseline and upgraded walks, short Tier 1 pass on pre-migration records, report under a recheck name); the user asked for a short migration-focused pass after #4766.
- Phase 0: shared dev stack owned by a live session is lent through SendMessage; stopped names go to a file in an existing directory (the list file was never written, claude-work/logs did not exist) and only those names are restarted (docker start of every exited container reran the one-shot inits).
- Phase 0: network clash with the dev stack's analyzer-net needs both a subnet and the webapp ipv4_address override (two failed starts); zsh glob in grep --include hid the pinned address; pruned release images made `up 3.2.3.0` pull silently for 10+ minutes.
- Final message: read RELEASES.md before bringing main up to date (release/<X.Y>.x route, three-part versions from 3.3.0); a develop -> main PR puts -SNAPSHOT on main (#4772, merged by the user).
- rt.sh: `local-fix clear` recreates services only when the stack runs (it would have started the stack on the migrated directory); `restore-run` without backup/properties moves the boot-written Total/ChangedSystemConfiguration files aside (done by hand this run).
- ui-regression-checklist: run_code `filename` only under the app checkout, no fs import; #local_search, #unitType (3.2.3.0) vs #validationLabUnit + Load results (develop), report PDF via popup URL + page.request.
- Queue: fc5d90d4 dropped (already has its own entry).

## 2026-10-20 (session fc5d90d4 review-pr #4773 self-review)

- review-pr §3: deploy and seed scripts are run against a stub API from every starting state, old script included, from a copy outside the repo (no stack: the shared one was lent to a migration test); `.github/scripts` tests need pyyaml in a scratchpad venv.
- review-pr §3: a green CI job counts only for the steps it ran (the PR's E2E run ran the shared build only; the draft's "E2E ran the seed" was caught before posting).
- Observation: the user merged the PR while the review waited on that E2E run; the review was posted after the merge with its points framed as follow-ups. No rule change.

## 2026-10-20 (queue: session 033ce28e, part after its 06:08 retro)

- prepare-for-next-release Final message: a PR comment on the run is the report summary only, about 15 lines, no retro content (the first post on #4766 carried the full closing message; user: "i mean onky the review comments, not the retro thing. i mean just give a report summary").
- The publish watch after the merge (Dev Images vs deployment images, analyzer smoke red on testing) was recorded in memory during the session; no further change. Permission log empty.

## 2026-10-20 (session 5e073d11 review-pr #4771 self-review)

- review-pr §3: start the isolated suite in the background and wait on its completion notice (four 10-minute Monitors re-armed over one 50-minute suite).
- review-pr §3 served WAR: after a rebase the commit times prove nothing; grep the WAR's classes for PR-only symbols (09:18 WAR vs an 11:12 head, all code present).
- review-pr §3 API: `require`/`URL` are undefined in `browser_run_code_unsafe`, and a print clicked before the failing line still ran; fetch PDFs by version id with curl.
- session-retro §1: drop queued sessions already reviewed in-session (e12ccec5).
- Good outcome kept: discriminating probes (requester with 49 duplicate records, mixed-width range) found both Required items; happy paths all passed.

## 2026-10-20 (queue: session e12ccec5)

- e12ccec5 was already reviewed in-session (70f3117); no further skill changes.
- Permission log: two `mcp__claude-vscode__getDiagnostics` requests from session 8a67dc7d; allow rules added for the claude-vscode MCP tools in `~/.claude/settings.json`, log cleared.

## 2026-10-20 (session e12ccec5 review-pr #4769 self-review)

- review-pr §2: grep every removed symbol at the head and run each hit's tests (`OrderPossibleTestsHeaders` was still imported by `sortableHeaders.test.js`, the only red file in CI's Static job; caught by a grep during the review).
- review-pr §5: re-read `headRefOid` in the call that posts and diff against the reviewed sha (an amend landed seconds before the post; a Required item was already fixed and a correction review was needed).
- review-pr §3 regression matrix: export `DB_CONTAINER`/`HARNESS_DB_CONTAINER` for the dev-stack DB (`participant-setup` failed on `openelisglobal-database` and skipped all specs). Memory `project_local_e2e_ci_parity` item 5.
- review-pr §3 UI walk: never pass `filename` to `browser_snapshot` (it wrote `s168.yml` into the product repo root).
- Permission log: one entry from session 8a67dc7d (`rm -rf ...; cd <repo> && git ...` chain); the absolute-path rule already covers it, log cleared.

## 2026-10-20 (sessions 033ce28e release-readiness run 2026-10-19-1732, 3b339755 resolve-by-criteria OGC-431/1452/439, 18731779 skill update)

- prepare-for-next-release Phase 9 and 10.1: a FAIL is verified before it becomes a defect (fresh-page reproduction, every modal answered, two-step controls re-read, the site_information setting and the handler code read); two findings were withdrawn and two reclassified as configuration defaults after the user asked "please carefully test so that you don't incorrectly assume a bug" (2026-10-19; the 2026-10-18 session carried the same instruction). Memory `feedback_verify_before_registering_defect`.
- prepare-for-next-release Phase 9: status block at every phase end and after ten minutes of any background wait (user asked for status three times in 033ce28e and three times in 3b339755). Memory `feedback_proactive_status_updates`.
- prepare-for-next-release Phase 9 / 10.3 step 6: no main-session browser steps while the reviewer agent runs; it shares the Playwright MCP browser (the environmental walk landed on the reviewer's reflex page, a stray click opened a new order). Optional review findings that are real defects go into the response commit (five on 2026-10-20).
- prepare-for-next-release Phase 0 and 10.3 step 3: Docker.raw growth and the 15 GB headroom rule before suite runs and WAR builds, one full suite per push, targeted classes for follow-ups, isolated copy never excludes `projects/` (two false failures), scoped spotless helper; Docker Desktop hang recipe (a restart script waited 4 hours on `docker info`). Memory `docker-disk-hygiene` updated.
- prepare-for-next-release "Where things live": edit the skill only through the skills repository path (two permission prompts through the `~/.claude/skills` symlink).
- rt.sh: `backup` saves the run configuration and properties directories and `restore-run` restores them (attempt 1's properties leaked into the retry); `pull` no longer writes "NOT PRESENT" for present images; `creds` prints `password=<value>` on one line; `teardown` restores the two tracked log placeholders and `preflight` lists them as stack-written and prints Docker.raw's size; `liquibase_expected.py` raises the DATEEXECUTED-before-start note only for a subset of rows (JVM vs database zones made it fire on all 200 rows).
- ui-regression-checklist: hang pattern for modal closes (`page.on('response')` collector, `noWaitAfter`, bounded polling), `#password` instead of the label, 30 min idle logout, API login recipe (form-encoded + CSRF), the selectors that cost retries (dd/mm/yyyy dates, validation card list, Results searchbox, result alert modal, lab-number generation on load, `[id="0_name"]`, toggle labels, logout menu), environmental and vector routes (dashboard Continue, never deep links; program, site and standard needed; evaluation after release), name charsets.
- configuration-metadata: roles need a `groupingParent`, names respect the charset, seed an environmental program, header-only example CSVs shadow bundled files, properties overwrite site_information at boot.
- Queue: 18731779 (skill update session) had its corrections applied at the time (skills moved to this repository, live-only testing, core emphasis); 3b339755 contributed the status and careful-testing patterns and a second Docker Desktop hang (user: "can I restart the PC??").
- Memory `project_release_readiness_run_2026_10_19` records the run outcome, PR #4766 (merged 2026-10-20 as ee5d92c4cb on the user's instruction) and the open items for the next run; `project_playwright_second_context_hang` gained the modal-close pattern and the shared-browser note.

## 2026-10-15 (session c0b0f7ee, review and merge of #4410/#4412)

- review-pr §3, resolve-issue §3b, resolve-by-criteria: every function row and regression cell is clicked by hand through the Playwright MCP; spec runs are extra evidence, never a substitute (user: "next time please ensure you manually click through the screen by mcp playwright as i always say. no chances for a regression"; the #4410 review left add cassette, add slide, the Deactivate dialog, the Show deactivated switch and the counts to the PR's CLI specs).
- review-pr, resolve-issue, resolve-by-criteria "Docker teardown": register every created stack, container, cloned DB, dir, branch and process with `claude-work/bin/session-track.sh`, run `claude-work/bin/session-cleanup.sh` when the work is done; a new SessionEnd hook (`claude-work/hooks/session-cleanup-hook.sh`) runs the same cleanup as a safety net (user: "as soon as a session completes its work, it cleans up the containers and volumes, data inserted"). `light-stack-up.sh` now finds the dev-stack (`oe2-*`) database and network and registers what it creates. Tested on a throwaway session: registered items removed, an out-of-bounds path refused, a stopped container's volume kept.
- review-pr §3: an old PR whose re-run E2E shows "webapp is unhealthy" on every shard ran its stale original merge ref; update the branch instead of re-running failed jobs (#4412; memory `project_ci_rerun_stale_merge_ref`).

## 2026-10-12 (session faefde06, review of #4657/#4661/#4663 and merge of analyzer stack #4588)

- review-pr, resolve-issue, resolve-by-criteria: new "Docker teardown" step using `claude-work/bin/teardown-stack.sh` (user: "after every session finished, clear all related docker containers and volumes so that we dont eat up docker memory"; two stacks plus another session's stack filled Docker and the disk twice).
- review-pr: "merge" on a native GitHub stack goes through `claude-work/bin/merge-stack-rebase.sh` (stack PRs refuse single merges, bypass is allowed only on the bottom PR, and squashing the bottom PR leaves the next one in add/add conflict until its branch is moved onto develop).
- New helper `claude-work/bin/pw-stack.sh` runs Playwright against a dev-stack copy without `eval` compound commands (the likely source of the permission prompt the user saw).

## 2026-10-12 (session 85f2099a, resolve-by-criteria run 2: OGC-1396 to 1449, IG #21/#22)

- Skills moved to `claude-work/skills`, symlinked from `~/.claude/skills`, so edits never prompt; added `session-retro` and the SessionEnd/SessionStart retro hooks (user asked for continuous learning and no permission waits).
- resolve-issue §8: a Jira step skipped because the tool is down is reported in the first line of the next message, with `/mcp` (user: "did you forget to move OGC-1399", "why didn't you report").
- resolve-issue + review-pr: docs/IG PRs are judged by the IG Publisher QA counts, not the job colour (#21 had 1 error, 1 broken link, 1252 warnings behind a green job).
- resolve-issue: a walk-found defect noted as "for a separate pass" counts as an out-of-scope list (OGC-1448 h1 pages; user asked for the fix).
- resolve-issue: Spotless covers XML fixtures (push blocked); Playwright lint before pushing specs (#4685 Static failure); frontend tools via `npm --prefix`; disk check before long runs (disk filled mid-run).
- All three skills end with a Retro step.

## 2026-10-12 (retro of queued 85f2099a and faefde06, plus permission log)

- Both sessions were already audited by the two entries above; their remaining tails ("great", "thanks", stack merge and teardown) needed no new change.
- Permission log: one prompt from a `cd <iso copy> && mvn ... ; docker run ... spotless` chain (session ae493b76). Memory `project_isolated_backend_test_runs` now says to run the copy with `mvn -f <copy>/pom.xml` and absolute report paths.

## 2026-10-12 (session 7dfd6dd7, self-review of #4694)

- review-pr §3 API: snapshot rows before probes, give success-capable probes harmless payloads, and probe omitted keys as well as `null` (an omitted `ranges` returned 200 and wiped two tests' ranges, the review's one Required finding; a whitespace-id probe also wrote one test's set onto another and had to be restored).
- review-pr §3: frontend unit tests through `npm --prefix frontend run test -- --run <file>` (`npm exec vitest` from the repo root failed every file on config).
- review-pr §3: walk the shared stack when it already serves the PR head and no later change touches its paths (another session was running testcontainers on 5 GB of free disk); quote `git show "<ref>:<path>"` because zsh treats `$P:path` as a modifier.

## 2026-10-13 (retro of queued 7dfd6dd7, plus permission log)

- Session 7dfd6dd7 was already audited (entry above); no new change.
- Permission log: five prompts in session ae493b76, all hand-built `docker run ... spotless` one-liners with `$(git diff ...)`, `R=$PWD &&` and a `cd ../../claude-work` chain. New helper `claude-work/bin/spotless-docker.sh` (cold, container, scoped to changed Java/XML); resolve-issue's formatting rule and memory `project_spotless_macos_ci_skew` now point at it.

## 2026-10-13 (headless review of #4700)

- review-pr §3: low-disk isolated walk via memory `project_light_isolated_stack` (full dev-stack did not fit in 3.9 GB free; the shared stack served later commits on the same paths).

## 2026-10-13 (session ce3a837c, review of #4700)
- review-pr: clone-and-deploy block uses absolute paths, `mvn -f` and `--project-directory` instead of `cd` (permission log: two cd-chain prompts from session ae493b76 on 2026-10-13).
- memory dev-stack-login: fill `#password`, since `getByLabel(/password/i)` hits two elements (strict-mode error in #4700 walk).
- No change for createdb denial: already in project_light_isolated_stack (superuser createdb); spotless one-liner prompts already covered by resolve-issue's spotless-docker.sh rule.

## 2026-10-13 (this session, self-review of #4702)
- memory light-isolated-stack: Vite `root` must point at the copy when started via `npm --prefix exec`; MCP `page.request` needs absolute URLs; letters-only disposable usernames; manual teardown for the plain `docker run` webapp (each cost a retry in the #4702 walk).

## 2026-10-13 retro (session 5fe0795b)
- No skill change: review of #4702 had no user corrections; its in-session retro already added the page.request absolute-URL and letters-only login-name notes to project_light_isolated_stack.md. Header `selectLocale` strict-mode collision was a one-off.

## 2026-10-13 (self-review of #4704)
- memory light-isolated-stack: start Vite with a 2 h background timeout (default 10 min killed it, costing a failed setup run); seed orders via a throwaway createSampleOrder spec; activate = save lab unit, then POST /activate.

## 2026-10-13 retro (session 4396b832)
- review-pr §3 regression: rerun a failing Playwright spec alone with `--workers=1` before judging it (#4704 walk: a site-config-flipping spec failed only beside a parallel worker). No user corrections; the session's own retro already covered the Vite timeout.

## 2026-10-13 (session 51934e99, self-review of #4709)
- New `claude-work/bin/teardown-light-stack.sh <N>`; review-pr low-disk rule and memory light-isolated-stack point at it (the hand-written rm -rf/branch -D teardown chain was the session's one permission prompt).
- memory light-isolated-stack: wait on notification text (a cold-stack Basic Info save took ~6 s and two fixed-sleep checks read as "no response"); MCP page listeners persist across calls; one statement per `psql -c`; claude_ai_Atlassian fallback when the atlassian MCP is down.

## 2026-10-13 retro (queued 51934e99)
- No change: the session audited itself (entry above); its MCP screenshot path error is already covered by the dev-stack-login memory (files under repo/.playwright-mcp). Permission log empty.

## 2026-10-13 (headless self-review of #4712)
- memory light-isolated-stack: microbiology-whonet-export specs 404 on that stack (uat.scenarios off in the copied env); Carbon toggle needs its label clicked. Full retro skipped (headless run).

## 2026-10-13 retro (queued 3f8a1b77)
- No change: the #4712 headless review had no user corrections and already added its memory notes. Permission log empty.

## 2026-10-13 (self-review of #4713)
- New `claude-work/bin/light-stack-up.sh <N>` (DB clone, webapp container, Vite config); review-pr low-disk rule and memory light-isolated-stack point at it (hand-built setup cost ~10 tool calls each review).
- memory live-probe-recipe: a real expired session is a redirect loop through the proxy (ERR_TOO_MANY_REDIRECTS), not a 200 login page; probe it via https://localhost, not host Vite.

## 2026-10-13 retro (queued 105f4a1c)
- memory local-tooling-gaps: zsh does not word-split `$D` holding a command (a psql probe in the #4713 review failed "command not found: docker exec ..."); use a function or `${=D}`. No user corrections; the session already added light-stack-up.sh. Permission log empty.

## 2026-10-13 (self-review of #4715)
- review-pr §3 low-disk rule: `--workers=1` for regression specs under ~4 GB free (two workers beside two stacks hung the Docker daemon and the shared stack); read DB rows before teardown in their own call (a `;`-chained psql typo let teardown drop the DB first).
- memory docker-vm-readonly: hang variant needs `kill -9` on com.docker.backend; a mid-boot webapp restart leaves a stale databasechangeloglock (clear it after checking pg_stat_activity).

## 2026-10-14 retro (queued c5176a8b)
- No change: the #4715 self-review already added the --workers=1 low-disk rule and the Docker hang / stale Liquibase lock recovery to memory; no user corrections. Permission log empty.

## 2026-10-14 (self-review of #4717)
- review-pr §3 regression specs: build the list with find; a zsh glob inside $(...) emptied it and started all 484 specs.
- memory light-isolated-stack: page.request needs the /api/OpenELIS-Global prefix (an unprefixed /rest call replaced the session cookie); Docker VM disk does not shrink after teardown (5.4 -> 2.7 GB).
- Network drop after CI went green kept the review unposted until the user nudged; nothing to change in the skill (a watcher cannot outlive the network). Permission log empty.

## 2026-10-14 retro (queued 61967c4e, listed twice)
- No change: the #4717 self-review already recorded the find-built spec list, the /api/OpenELIS-Global prefix and the network-drop note. Permission log empty.

## 2026-10-14 (self-review of #4720)
- review-pr §3: wait for spec runs with an unanchored passed/failed grep (ANSI prefix kept an anchored waiter running to its 10 min timeout).
- review-pr §3 attribution: CI E2E logs list failures only; diff `--list --shard=k/4` with and without the PR for a red spec outside the diff; a repeat on rerun is not a flake (ogc-1423 depended on ogc-1420 sharing shard 3).
- memory: new project_e2e_shard_order_dependency; light-isolated-stack gets MCP no-Buffer upload and the Methods DatePicker recipe. Permission log empty.

## 2026-10-14 retro (queued f664f544)
- No change: the #4720 self-review already recorded the waiter grep, shard attribution and MCP no-Buffer upload; the localization.english SQL slip was one-off. Permission log empty.

## 2026-10-14 (self-review of #4722)
- review-pr §2 Liquibase: data changesets rewriting a uniquely-indexed column are tested with a pair that collides only after the rewrite (138 trim would stop an upgrade).
- review-pr §3 API: probe each length limit with the maximum plus surrounding spaces (trim().length() checks over untrimmed stores answered 500 on Storage and reagent unit).
- review-pr §3 light stack: arm a <400 MB disk guard during spec runs (4.4 GB -> 719 MB).
- light-stack-up.sh copies .env into the copy (specs failed on missing TEST_PASS); memory light-isolated-stack notes the ogc-1457 host-Vite limit. Permission log empty.

## 2026-10-14 retro (queued 5c37dcd3)
- No change: the #4722 self-review already recorded the Liquibase collision pair, the trimmed length probes, the disk guard and the .env copy. Permission log empty.

## 2026-10-14 (self-review of #4723)
- resolve-issue §3b: find the existing specs to run by grepping the changed routes, test ids and REST paths; OGC-1466 ran only its own spec and the review caught ogc-1194 failing on the same screen (preview stopped recording names).
- memory dev-compose-redeploy-gotcha: `docker restart` can refuse a vanished WAR mount after `mvn clean`; `docker start` served the new WAR in both contexts.
- Review found 2 Required on own PR by running the screen's existing specs and repeated-row probes across loaders; keep. Permission log empty.

## 2026-10-14 retro (queued 4b9ac228)
- No change: the #4723 self-review already ran its own retro (spec discovery by route grep, docker start after mvn clean). Permission log empty.

## 2026-10-14 (review of #4724, kanazawahere)
- review-pr §2 Workflow files: actionlint via docker (`-no-color -oneline -`; `-color=never` rejected) and `buildx imagetools inspect` for platform and name-collision claims. No user corrections. Permission log empty.

## 2026-10-14 retro (queued 4a840152, review of #4728)
- review-pr §live test: `browser_take_screenshot` takes a bare filename (scratchpad path refused: "outside allowed roots").
- review-pr §regression matrix: run Playwright specs via the absolute `node_modules/.bin/playwright -c <config>` and absolute `rm -rf test-results`, no `cd frontend &&` chain (2 permission requests logged); wait with Monitor, not `sleep` (blocked once). No user corrections.

## 2026-10-14 (self-review of #4731)
- review-pr §regression matrix: Playwright filters by spec basename (absolute paths gave "No tests found" from another cwd); grep the old text of every changed user-visible string across frontend/playwright and run the hits (found the vector toast break in CI demo specs). No user corrections. Permission log empty.

## 2026-10-15 (sessions ae493b76, afd8ae88, a59a08bb)
- resolve-issue §3: review-response and CI-fix pushes go out after targeted tests, inversion and the live check; the full suite runs in parallel and gates the merge (user: "where is the fix pushed ??", "all checks are green ... can you respond to the review", #4723, #4728).
- resolve-issue §3: new specs seed every precondition through the API and clean up; user-visible text changes grep playwright/cypress for the old text (CI failures on #4731: ogc-1488 without a checklist, three vector specs on the old toast).
- resolve-issue §3b step 0: order save path changes need a re-save walk at every later step for each specimen state (reviewer found duplicate rejection notes and an unsavable resampled order on #4731).
- resolve-issue §5: CI watcher and reviewer run with run_in_background or a Monitor, never a detached `&`; report red checks and posted reviews first (user reported both before the session did).
- resolve-issue §7: trimmed history passages (file back near 700 lines).
- resolve-by-criteria §3e: one merge call, then poll the PR state; a retry after a 504 added an empty duplicate commit to develop (#4728).
- resolve-by-criteria §3f: run session-retro after every issue (user: "so did the skill improve after the previous session").
- Memory: suite-before-push feedback updated with the review-response exception; new project memories for test-persistence unlisted entities and CreatePatientForm's form-level onChange.
- Reviewer sessions afd8ae88 and a59a08bb: their own retros found nothing new; afd8ae88's live walk is the evidence for the re-save rule.

## 2026-10-15 retro (queued ae493b76, c0b0f7ee, plus permission log)
- Both sessions were already audited by their own retros (entries above); no new user corrections after them.
- Permission log: a `cd <repo> && git archive ... ; cd $ISO && mvn -o test` chain (be1c5bd2) repeated despite the memory rule; new helper `claude-work/bin/iso-suite.sh`, referenced from resolve-issue, review-pr §3 and memory `project_isolated_backend_test_runs`.
- Permission log: two Edit prompts on `~/.claude/skills/review-pr/SKILL.md` (c0b0f7ee); all three skills' Retro step now says to edit `claude-work/skills/<name>/SKILL.md`.
- Permission log: a hand-built cleanup chain (`rm -rf $SP/*; docker volume prune`) is now covered by `session-cleanup.sh`; no change.

## 2026-10-15 (self-review of #4748, this session)
- `claude-work/bin/session-cleanup.sh`: the `dock` watchdog left an orphan `sleep 180` that held the caller's output open, so a 10 s cleanup blocked the Bash call for 3 min and printed "Terminated: 15" lines; the watchdog now kills its own sleep (tested: cleanup returns in 1 s, no sleep left).
- Memory `project_light_isolated_stack`: full-UI variant (own network, aliases, proxy needs `LETSENCRYPT_DOMAIN=localhost`) for walking published images next to the shared stack.
- Memory `project_i18n_regional_override`: en_US overlay hides en.json edits in HMR checks.
- No user corrections. Permission log empty for this session.

## 2026-10-15 (session a59a08bb: #4724 review+merge, #4748 dev-stack published images)
- claude-work/bin/spotless-docker.sh now includes changed Markdown (Prettier via npm in the container); #4748 failed CI Formatting on two .md files the script skipped. resolve-issue formatting line updated.
- New helper claude-work/bin/compare-images.py: config + per-file checksum diff of two images (jars by entry CRC); used to prove published dev images equal local builds.
- Memory: feedback dev-stack-published-images (user directive: no implicit image builds); dev-compose-file-removed updated. Separate-branch PR was a one-off; develop-only rule unchanged.

## 2026-10-15 retro (queued 151c7a5a, a59a08bb)
- Both sessions had already run their own retros (entries above). One uncaught correction: the #4724 post-merge report suggested pointing `docker-compose.yml` (deployment compose) at the `-dev` images; user: "is docker-compose.yml the dev compose file ??". review-pr §4 now requires checking a file's role before suggesting changes to a file outside the diff. The fact itself was already in memory `project_dev_compose_file_removed`.
- Permission log empty.

## 2026-10-15 (self-review of #4747, session 98373204)
- New helper claude-work/bin/pdftext.sh: pypdf was installed nowhere (the jasper memory said "scratchpad venv"); it keeps a reused claude-work/.pdfvenv. Memory `project_jasper_precompiled_reports` points to it.
- review-pr §3: printed-report recipe (popup URL + curl with the session cookie, `Home?lang=fr` for the French print) and the stopped-FHIR trap (referral save 500 with UnknownHostException fhir.openelis.org on the shared dev stack; the container had exited 2 h earlier).
- Good outcome kept: the read-only subagent's report-code findings were each checked live before filing; one (false corrected banner) reproduced and became Required, two (claim without daggers, aliquot crash) did not and were downgraded.
- No user corrections. Permission log empty.

## 2026-10-16 (sessions be1c5bd2, 98373204)
- resolve-issue §3b matrix: added "lab data shapes" (multi-component incl. hidden/empty components, multi-sample + aliquot without its own test, no results, partial/completed, normal/critical/valid-range limits, "<" text results) for any results/validation/report change. Evidence: user asked twice on OGC-932; the walk then found three defects.
- resolve-issue §3b matrix: dates are walked on month-first and day-first sites and tested with settings arriving after the first render. Evidence: CI-only failure of the Test date picker on #4747.
- resolve-issue §3: devstack-compose.py for recreating the dev-stack webapp (new helper in claude-work/bin).
- memory: wedged Playwright MCP recovery (kill only own Chrome child); analyzer-harness seed deactivates test 15.
- 98373204 (headless reviewer): already added pdftext.sh and report-fetch steps to review-pr itself; nothing further.

## 2026-10-16 (session be1c5bd2, user instruction)
- resolve-issue teardown: when the PR waits for the user's manual validation and merge, keep the stack (URL + login in the final summary) and session artifacts until the user confirms and the PR is MERGED; tear down straight after merging only when the pipeline merges itself. Final summary gains a Stack line. Evidence: OGC-932, stack torn down after review, then rebuilt for the user's manual test.

## 2026-10-16 retro (queued be1c5bd2, third pass)
- resolve-issue §3: wait for a recreated webapp with the Monitor tool on `docker inspect ... Health.Status`; `sleep N; until ...` chains are blocked by the Bash hook (be1c5bd2: twenty blocked retries of the same health wait).
- resolve-issue trimmed from 782 to about 730 lines: §0 live-test bullet now points at §3b instead of restating it, §0 Authorship and §7 Identity compressed, §6 merge recipe delegated to resolve-by-criteria §3e (which holds it). No rule removed.
- Analyzer suite errors (106) in that session were the git-archive copy missing submodules; iso-suite.sh and memory `isolated-backend-test-runs` already cover it. Permission log empty.

## 2026-10-16 retro (queued 3b339755, OGC-1452 openelis-docker)
- resolve-issue §3: bound Docker Desktop restart waits to about 5 minutes, then the hang recipe and an immediate report (session idled 4 h on a hung restart until the user asked "can i restart the PC").
- Memory `project-docker-vm-readonly-kills-postgres`: restart-wait variant, and a macOS reboot does not auto-start Docker Desktop. Permission log empty.

## 2026-10-16 retro (e8cce585, openelis-docker #60 self-review)
- review-pr §3: openelis-docker subsection; its webapp has no healthcheck, so wait on the startup log line (a `.State.Health.Status` wait ran 10 minutes to its timeout).
- Memory `project-openelis-docker-review-recipe`: fixed container names, encryption round-trip probe, package manifest check.
- bin/teardown-stack.sh: ported session-cleanup's watchdog to `dock()`; the old one left `sleep 180` holding each `$(dock ...)` open, so one teardown ran past the 10 minute cap (now 4 s).

## 2026-10-16 retro (e8cce585 requeued after its own in-session retro)
- Nothing new: the healthcheck wait, the teardown watchdog and the openelis-docker recipe were already applied in the entry above. The `import yaml` failure was a one-off (use `docker compose config --format json` instead of PyYAML). Permission log empty.

## 2026-10-16 (session 929277f6, user request)
- New skill `prepare-for-next-release` in openelis-docker/.claude/skills (symlinked into ~/.claude/skills and claude-work/skills): release-readiness pipeline (versions discovery, release stack on a run db dir, demo data, baseline, verified backup, same-db switch to develop, Liquibase verdict from the images' changelog trees vs DATABASECHANGELOG, manifest diff, Playwright MCP regression, timestamped report, retro). Scripts dry-tested read-only (preflight, init, versions, config, comparator on 3.2.3.0 vs develop trees, snapshot on the dev DB); no release test executed (user: create only).
- session-retro: covers prepare-for-next-release and names its real path (git-tracked in the docker repo).
- prepare-for-next-release Phase 10 (user: "fix any issues in the source code, test again, deploy the actual war file into the openelis docker ... or build local images"): fix loop with resolve-issue gates, `rt.sh local-fix war|frontend|image|show|clear` (local artefacts mounted into the same stack, recorded with sha and commit), `rt.sh restore-run` (migration retry from the verified backup on a new directory, previous evidence archived), liquibase-verify reads the expected set from the local WAR, report section 7 "Fixes applied"; status stays about the published images until merged and republished.

## 2026-10-16 retro (1b483006, PR #4753 self-review)
- review-pr §1: subagent findings are leads, verified before they enter a review (3 of 13 reader leads were wrong, one contradicted memory `project_transifex_plural_shape`).
- review-pr §3 API: concurrent identical requests for numbered/versioned writes, and in-between states for derived states; these three probes found all three Required items on #4753 while every happy path passed. `page.request` needs absolute URLs in run_code.
- Memory `project-result-correction-walk-recipe`: Results Edit -> Validation round trip with working selectors (four selector retries this session).
- Permission log: 44 entries, all from session 929277f6 editing prepare-for-next-release, whose real path is under openelis-docker/.claude (protected; allow rules cannot silence it). Needs the user: keep the skill outside a `.claude` directory (for example openelis-docker/skills/prepare-for-next-release) and point the `.claude/skills` entry at it as a symlink. Log cleared.

## 2026-10-16 retro (1b483006 + 929277f6 requeued after their in-session retros)
- Nothing new: both sessions' changes are in the entries above; 929277f6 ended with "continue", an interrupt and "no" (no correction). Permission log empty. Still open for the user: prepare-for-next-release lives under openelis-docker/.claude (protected path), so edits to it prompt.

## 2026-10-16 retro (3ed9b6b6, PR #4755 self-review)
- review-pr §3: before walking, check the served WAR is newer than the head's last amend (the stack served a WAR from before two amends); the redeploy recipe is in the new memory `project-dev-stack-redeploy-without-mkcert` (mkcert missing: `DEV_STACK_TLS=self-signed dev-stack up --skip-build`; `mvn clean` breaks the single-file WAR mount; specs need BASE_URL + DB_CONTAINER).
- review-pr §3 API: a queue/worker probe (more items than one batch against an unroutable host, then look for two attempts inside the retry delay). It found the duplicate-send Required item on #4755.
- Subagent leads: 1 of about 24 was wrong (prettier on SentMessages.jsx; CI Formatting passed), and about 10 were confirmed live or in code. The existing rule held. Permission log empty.

## 2026-10-17 retro (3b339755, resolve-by-criteria batch OGC-1452, OGC-431, OGC-439; 3ed9b6b6 requeued)
- resolve-issue §3: a suite-only failure usually means a sibling fixture replaced a table the test reads (three suite-only failures on #4755: site_information rows, the test catalogue, the delivery channels); create own rows with ensure* helpers. Launch iso-suite.sh with run_in_background and move on: the transcript shows 211 hand grep polls of suite logs although every suite already ran in the background.
- resolve-issue §3 live-test: read BASE_URL from `scripts/dev-stack env` after each rebuild (five ports in one session: 55032, 55181, 55247, 55320, 55486); restart the Vite container for a new directory (memory `project-vite-watcher-misses-new-directories`).
- resolve-issue §3b step 4: exact-name locators scoped to the mounted panel, `.last()` for stacked dialogs (five locator retries on ogc-439-result-delivery.spec.ts).
- resolve-by-criteria "Strictly serial": parked-commit flow for a next issue started during a review wait, and status updates name the staged work (user: "so what are these changes for ie the staged changes ??").
- Kept: two review rounds each found real defects (#4753: preliminary print, lookup fallback, print lock; #4755: duplicate send, lease, channel gate); status updates during background waits were answered with "great". Memories added during the session: configuration-properties-file-wins, parked-commit, pg-advisory-lock native query, vite watcher. 3ed9b6b6 (reviewer run of #4755) already has its own entry above; nothing new. Permission log empty.

## 2026-10-17 retro (3b339755 requeued after a pause)
- Nothing new: the session continued the six-issue task after the entry above; the user paused mid-turn ("can you pose here") and was given a stand-alone status. Permission log empty.

## 2026-10-17 retro (3b339755, six-issue task, PR #4757)
- Memory `project-local-e2e-ci-parity`: on a dev-stack stack the order-creating specs fail on CI referring site 9000100, then on provider person 9000002 after loading only e2e-foundational-data.sql (17 local failures, all before the changed code; CI green).
- Kept: inverting every fix at once in the isolated copy proved each new test guards its defect in one run; a harness spec whose caption stated the old design ("releasing the viral load releases every part") was updated with the intended behaviour, then verified by CI.

## 2026-10-18
- 5f86b0c8: aborted 40-line start of the PR #4757 review, no signals; no changes.
- resolve-issue: applies to every coding task, ticket or not; §7 independent review is never skipped without the user saying so (2026-10-18, PR #4757 reported done without a review; user correction). Memory `resolve-issue-for-every-task`.
- db3d95d3 (review of #4757): memory project_live_probe_recipe: catalog-import Apply now lands in the configuration named volume inside the webapp, not the checkout (found by find in the container). The review-pr rule "drive the in-between states (released result sent back for correction)" found the Required item again (correction after component validation); kept.

## 2026-10-19 retro (db3d95d3 PR #4757 review + 3b339755 requeued)
- Nothing new beyond the 2026-10-18 entries: the reviewer ran its own retro (catalog import CSV is persisted in the webapp container and reloaded on restart); this session's correction (resolve-issue for every task) is already applied. Permission log empty.
- resolve-issue §3b: access/scope changes inventory every list, count, open and write endpoint of the entity via an Explore sweep and check them as two scoped users plus admin (PR #4757: nine unscoped lists found only after the user asked about vector/environmental dashboards).

## 2026-10-19 (session 0dab5640, review-pr #4757 round 2)
- review-pr: spec runs write to `--output <scratchpad>/pw-out`; never `rm -rf frontend/test-results/*` (it deleted another session's harness failure artifacts in the shared checkout).
- review-pr: before a spec run, rule out the known local blockers: createSampleOrder specs 500 on fixture `Person#9000002` (memory item already existed, and the run was still spent: 9/12 failed at the precondition); harness specs need the author's last log read and mock port 8085 checked (a `beforeAll` burned 600 s repeating the author's failure).
- memory: new project_ci_e2e_ubuntu2604_playwright (E2E red at browser install on ubuntu 26.04 runners); v4 order-entry recipe gets the mm/dd/yyyy collection-date trap.
- kept: verifying subagent leads live before filing them. 1 of 9 reader leads became the review's only Required item (aliquot scope bypass, reproduced as six_hema).
- memory: MEMORY.md compacted from 20.9 KB to 16.5 KB (index hooks trimmed to one short clause, title dates dropped; topic files unchanged; backup in the session scratchpad).

## 2026-10-19 retro (0dab5640 requeued)
- Nothing new: the session ran its own retro (entry above) as its last step. Permission log empty.

## 2026-10-19 (session 3b45f18b, review-pr #4757 round 3)
- review-pr §3: typed numbers in a Carbon NumberInput are checked against the stored row (aliquot typed 2, stored 0; the round-3 Required item came from this).
- review-pr §3 API: one statement per `psql -tAc` (several print only the last result; a referral row nearly read as missing); new helper `claude-work/bin/oe-probe.sh` (login/call with CSRF) replaces the per-session probe script (a `${3:+--data "$3"}` quoting slip cost one probe round).
- Kept: the mixed own+foreign tube probe confirmed the aliquot refusal is all-or-nothing. Permission log empty.

## 2026-10-19 (session 3b339755, PR #4757 merged; queue: 3b45f18b reviewer run, retro already done)
- resolve-issue §3b: a change adding a partial state walks every surface reading the whole record's status in the mixed state (user found Results showing all parts "Accepted by technician" and the report only "Awaiting validation" after per-part validation shipped).
- resolve-issue §5: runner-image Playwright install failure is fixed by a separate workflow PR merged to develop first, since E2E is a workflow_run reading develop's file (#4764).
- memory: ubuntu 26.04 note resolved (pin, workflow_run rule); MCP save-hang note generalized to the main page (30-min hang on the Aliquot save; waitForRequest + psql worked for every later save).
- Kept: independent review rounds 2 and 3 each found a real bug (aliquot bypass, aliquot quantity saved as 0); the walk found a stale sibling status in the fix itself before push.

## 2026-10-20 retro (18731779 skill-update session, 3b339755 requeued)
- Nothing new in the skills: 18731779's two corrections are already applied (skills live in `mozzy11/claude-dev-skills`, never in a product repo: session-retro §0 and memory `feedback-skills-repo-commit-every-change`; "just update the skills" means text edits only, no new tooling: memory `feedback-prepare-for-next-release-skill`). 3b339755 ended with "put down the dev containers" and "Thanks" after its own retro.
- Permission log: 31 prompts from 18731779 editing the release skill under `openelis-docker/.claude` (resolved by the move), 2 from 033ce28e editing `rt.sh` through the `~/.claude/skills` symlink (rule already in prepare-for-next-release "Where things live", added by 4563287). Log cleared.

## 2026-10-20 retro of 8a67dc7d (resolve-by-criteria OGC-1514 + OGC-431, both merged)

- resolve-by-criteria §3f: watch the merge sha's push-triggered E2E / Tests and Publish images runs right after the merge, triage reds at once (fix + rerun failed jobs), CI fixes go into the in-flight PR, and ignore pull_request runs that share the sha. Evidence: user asked "can you see the ci failed on merge of 1514" an hour after the merge, then "push the fix if any as part of the current PR".
- resolve-by-criteria §0 parked commits: fold review fixes with fixup + autosquash, never copy-aside + reset --hard. Evidence: zsh did not split `$FILES`, the copy failed and a reset dropped five edited files (recovered from the isolated copy and the reflog).
- resolve-issue pre-push: grep a removed export across frontend/src and run the whole vitest suite before the first push; pass refs to spotless-docker apply. Evidence: Static failed on sortableHeaders.test.js importing the removed OrderPossibleTestsHeaders; the pre-push gate blocked an unformatted committed fixture.
- resolve-issue: spec waits registered before the triggering action, role-based locators. Evidence: the OGC-431 tile test passed locally and failed in CI (strict-mode match on a column header, listener after navigation).
- Kept: the independent review found a real bug on both PRs (duplicate revive on Modify Order; provider search truncating at 21 rows), both fixed in the PR.
- Memory: zsh-no-word-split-reset-trap, watch-merge-ci-fix-in-current-pr, testing-deploy-analyzer-smoke-red, provider search marked fixed, CI triage memory extended (Microsoft apt 403, Cypress service-worker crash). Queue: dropped 5e073d11 (headless #4771 review, already retro'd in 8dc9495).
