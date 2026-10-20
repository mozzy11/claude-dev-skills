---
name: session-retro
description: Audit finished Claude Code sessions and improve the user's skills (resolve-issue, review-pr, resolve-by-criteria, prepare-for-next-release, session-retro itself) and memory from what actually happened, so every next session is better. Runs at the start of a session when the retro queue has entries, as the last step of each of those skills, and on "retro" / "run the retro" / "audit my sessions".
---

# Session retro: learn from each finished session

Every finished session leaves evidence: what the user corrected, what failed,
what had to be redone, what stalled. This skill turns that evidence into
durable improvements of the skills and memory, so the same friction does not
happen twice. It is the only place where the skills change on their own.

**Never ask the user anything.** Decide, apply, and report in a few lines.
Do not weaken a gate (tests, live checks, review, merge rules) to save time:
an improvement makes the work better or faster, never sloppier.

## 0. Where things live

- Skills: the skills repository
  `/Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills`
  (GitHub `mozzy11/claude-dev-skills`), one folder per project:
  `openelis-global/{resolve-issue,review-pr,resolve-by-criteria}`,
  `openelis-docker/prepare-for-next-release` (its `SKILL.md`,
  `references/*.md` and `scripts/` are all fair game; every run of it ends
  with this retro), `shared/session-retro`. Edit them there, never through
  `~/.claude/skills/<name>` (symlinks made by the repo's `install.sh`; the
  protected `~/.claude` path prompts). Skills never go inside a product
  repository (OpenELIS-Global-2, openelis-docker): the user corrected this on
  2026-10-19.
- Every skill change is committed and pushed to `mozzy11/claude-dev-skills`
  right away (`git -C <skills repo> add -A && git commit && git push`),
  author mozzy11, no AI attribution, one commit per retro or per skill
  update with a short message naming the skills and the why.
- Retro queue: `/Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/claude-work/retro-queue.jsonl`,
  one JSON line per finished session (`session_id`, `transcript_path`, `cwd`,
  `reason`, `ended_at`), appended by the SessionEnd hook.
- Changelog: `/Users/mosesmutesasira/Desktop/DEV/Projects/claude-dev-skills/CHANGELOG.md`.
- Signal extractor: `scripts/retro_signals.py` next to this file.
- Memory: the project memory directory named in the system prompt
  (`MEMORY.md` index plus one file per fact).
- Permission log: `/Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/claude-work/permission-log.jsonl`,
  one line per permission request, written by the PermissionRequest hook
  (which approves it) and the Notification `permission_prompt` hook.

## 1. Pick the sessions

- Started from the SessionStart reminder or "retro": every line of the queue.
- Called as the last step of another skill: the current session
  (`~/.claude/projects/<project>/<session-id>.jsonl`, newest file) plus the
  queue.
- Skip sessions under 20 transcript lines, and headless reviewer runs
  (`claude -p ... review-pr`) unless their review was later corrected.
- A queued session whose id already heads a CHANGELOG entry had its retro
  in-session: drop its line without re-reading the transcript (2026-10-20,
  e12ccec5 was queued by the SessionEnd hook after its own retro).

## 2. Extract the signals

```
python3 <skill-dir>/scripts/retro_signals.py <transcript.jsonl> [more.jsonl ...]
```

It prints, per session: the user's own messages (with the assistant text just
before each), tool errors and blocked calls (hook blocks, permission
rejections, ENOSPC, timeouts), commands retried with the same intent, CI or
review failures followed by fix commits, MCP disconnects, Monitor expiries,
and long gaps where the user waited. Read the transcript itself around any
signal you act on; the extractor finds candidates, it does not judge.

## 2b. Permission requests (the user wants 100% autonomous sessions)

Read the permission log. For each entry remove the cause so it never asks
again, then clear the log:
- an ordinary command or file outside protected paths: add a matching allow
  rule to `~/.claude/settings.json` (`Bash(<prefix> *)`, `Edit(//<path>/**)`);
- a protected path (`.claude`, `.git`, `.mvn`, `.vscode`, shell configs,
  `.npmrc`, `.mcp.json`; allow rules never silence these): change the skill or
  helper so the work happens elsewhere (skills, hooks and work files live in
  `claude-work`; temp files in the scratchpad), and name the remaining case in
  the report;
- a `cd <dir>; cmd` chain: rewrite the skill's command with absolute paths,
  `git -C`, `npm --prefix`, `mvn -f`.
The hook already approved the request; the fix is so that it is not needed.

## 3. Classify each signal

| Kind | Example | Action |
|---|---|---|
| User correction or complaint | "why didn't you report?", "did you forget...", "you said X but..." | A rule in the skill that governs that step, plus a feedback memory |
| Repeated failure with a known fix | push blocked by spotless on a fixture; lint failed in CI only | A check added to the skill's pre-push / gate step |
| Environment or tool trap | MCP down, disk full, cwd-relative tests, stale WAR | A project memory with the recipe; a skill line only if the skill drives that step |
| Wasted time | waiting on a 30 min monitor that could have been bounded; re-reading the same files | A shorter or reordered procedure in the skill |
| Good outcome worth keeping | user said "great", a review found a real bug | Keep the rule that produced it; note it in the changelog |
| One-off, no pattern | a flaky test that passed on rerun | Nothing |

A signal needs evidence (quote the transcript line) before it changes a
skill. Two sessions showing the same friction is stronger than one.

## 4. Apply the improvements

- Edit the skill where the step lives, in its own words and structure: add or
  sharpen the rule at the step, with a dated note of the evidence in one line
  (for example "(2026-10-12: Jira down at PR open, user asked why it was not
  reported)"). Prefer changing an existing rule to appending a new one.
- Keep the skills short: merge duplicates, delete rules that no longer apply,
  and keep each SKILL.md under about 700 lines. A rule nobody can find does
  not help.
- Memory: update the matching memory file (or add one) and its MEMORY.md line,
  following the memory rules in the system prompt.
- Helper scripts (ci-watch.py, fhirget.sh, hooks) live in claude-work; fix
  them there.
- Append to `CHANGELOG.md`: date, session id(s), each change in one line with
  its evidence.
- Remove the processed lines from the queue.
- Never add AI attribution, never use em dashes, never ask for confirmation.

## 5. Report

Three to six lines: sessions reviewed, the changes made (skill and rule),
and anything that needs the user (for example a setting only they can change).
If nothing needed changing, say so in one line.
