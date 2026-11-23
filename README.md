# claude-dev-skills

Claude Code skills used for OpenELIS Global development, organised by the
project they work on.

| Project | Skill | What it does | Trigger |
|---|---|---|---|
| [OpenELIS-Global-2](https://github.com/DIGI-UW/OpenELIS-Global-2) | [resolve-issue](openelis-global/resolve-issue/SKILL.md) | Jira issue end to end: implement with tests, live UI and API test on the dev stack, draft PR, CI, independent review | `resolve issue <key or link>` |
| OpenELIS-Global-2 | [review-pr](openelis-global/review-pr/SKILL.md) | Maintainer-style PR review, deployed and tested through the UI and the API | `review PR <link>` |
| OpenELIS repositories | [review-all-prs](openelis-global/review-all-prs/SKILL.md) | Sweeps every open PR in the OpenELIS repositories: leaves the core team's PRs alone, merges clean low-risk maintenance on the first run and previously approved regular PRs, approves major PRs for a manual merge, closes verified obsolete ones, reports A to H; never bypasses branch protection | `review all PRs` |
| OpenELIS-Global-2 | [resolve-by-criteria](openelis-global/resolve-by-criteria/SKILL.md) | Batch Jira resolution from a filter, one issue at a time, merged after review | `resolve by criteria <criteria>` |
| [openelis-docker](https://github.com/DIGI-UW/openelis-docker) | [prepare-for-next-release](openelis-docker/prepare-for-next-release/SKILL.md) | Release readiness: last release upgraded to develop on the same database, Liquibase and metadata migration evidence, Playwright MCP regression, fixes, detailed report | `prepare for next release` |
| all | [session-retro](shared/session-retro/SKILL.md) | Audits finished sessions and improves the skills and memory | `retro` |
| all | [dev-updates](shared/dev-updates/SKILL.md) | Last week's work from GitHub, Jira and Confluence as a short Slack update, links wrapped in text, ready to paste | `dev updates` |

`CHANGELOG.md` records every change the retro or a skill update made.

## Layout

```
openelis-global/   skills for the OpenELIS-Global-2 application repository
openelis-docker/   skills for the openelis-docker deployment repository
shared/            skills used across projects
```

Skills are kept here, not inside the product repositories.

## Install

```bash
git clone https://github.com/mozzy11/claude-dev-skills.git
cd claude-dev-skills
./install.sh
```

`install.sh` links every `<project>/<skill>` folder into `~/.claude/skills/<skill>`,
so Claude Code finds the skills from any directory and edits made here take
effect at once. It replaces existing links and leaves real folders alone.

The skills carry paths from the author's machine (checkouts under
`~/Desktop/DEV/Projects/OpenELIS/`); adjust the "Where things live" section of
a skill to your own layout. `prepare-for-next-release` reads the openelis-docker
checkout from `OE_RT_REPO` or the current directory.
