---
name: dev-updates
description: Weekly developer update for Slack. Collects what the user did in the last week from GitHub (merged, open and reviewed PRs across every repository), Jira (issues they moved) and Confluence (pages they wrote), adds any pointers the user gives for work outside those tools, and hands back a three-to-five bullet message that pastes into Slack as is, with links wrapped in text. Trigger: "dev updates", "get me last week's updates", "weekly update", "slack update", "what did I do last week".
---

# Dev updates: last week's work, ready for Slack

The user posts a short update to the team's Slack channel, usually before or
after the weekly dev call. This skill gathers the evidence, summarizes it the
way the user wants, and returns text they copy and paste. **Never ask the user
anything**; decide, state the window used in one line, and deliver.

## 0. Where things live

- GitHub, through `gh` (authenticated as the user, login `mozzy11`): every
  repository, found with `gh search prs`, never one repository at a time.
- Jira and Confluence, through the Atlassian MCP tools (`searchJiraIssuesUsingJql`,
  `searchConfluenceUsingCql`; get the cloud id from `getAccessibleAtlassianResources`
  first). If the MCP reports that it needs authorization, say so in one line of the
  reply and continue with GitHub only: the Jira keys are in the PR titles anyway.
- Slack is never written to. The user pastes the text; post it only when they say
  "post it", and then as a draft.

## 1. The window

- Default: the seven days ending today.
- "Last week" on a Monday or Tuesday: the previous calendar week, Monday to Sunday.
- A range the user names wins over both.

State the window once in the reply, outside the Slack text, as "Window: Mon 9 to
Sun 16 Nov". Dates in `gh` queries are `YYYY-MM-DD`.

## 2. Collect (at most two tool calls in parallel)

GitHub, three queries in one Bash call:

```bash
S=<start> ; E=<end>
gh search prs --author=mozzy11 --merged --merged-at "$S..$E" --limit 100 \
  --json repository,number,title,url,closedAt \
  --jq '.[] | "\(.closedAt[:10]) \(.repository.nameWithOwner)#\(.number) \(.title) \(.url)"' | sort
gh search prs --author=mozzy11 --state=open --updated ">=$S" --limit 50 \
  --json repository,number,title,url,isDraft \
  --jq '.[] | "\(.repository.nameWithOwner)#\(.number) draft=\(.isDraft) \(.title) \(.url)"'
gh search prs --reviewed-by=mozzy11 --updated ">=$S" --limit 50 \
  --json repository,number,title,url,author \
  --jq '.[] | select(.author.login != "mozzy11") | "\(.repository.nameWithOwner)#\(.number) by \(.author.login): \(.title)"'
```

Jira, one JQL: `(assignee = currentUser() OR reporter = currentUser()) AND updated >= "<start>" ORDER BY updated DESC`
with fields summary, status, issuetype, parent, resolutiondate. Confluence, one CQL:
`contributor = currentUser() AND type = page AND lastmodified >= "<start>" ORDER BY lastmodified DESC`.

Then add what the user said in their message: pointers to work outside these
tools (a call, a deployment, a document elsewhere) become their own bullet,
in the user's words, tightened.

## 3. Summarize

Group the evidence into three to five bullets, in this order when present:

1. **Bugs**: one bullet, summarized by area, never enumerated. Read the areas off
   the PR title scopes (`fix(dates)`, `fix(order-entry)`) and name them in plain
   words: "Fixed a batch of bugs across order entry, results, validation and
   reports on develop". No ticket keys, no counts unless the user asks.
2. **Features**: one bullet per theme, not per PR. Several slices of one epic are
   one phrase ("more slices of the QC runs and multi-level validation work").
   A feature that matters on its own (a new integration, a new module) gets its
   own bullet with what it does for the lab in one sentence.
3. **Docs**: what changed for the reader, with the page linked.
4. **Integrations and setup repositories**: new or updated setup repositories,
   version bumps, in one bullet.
5. **Reviews**: "Reviewed N community PRs (areas)" only when the count is
   material (five or more); otherwise leave it out.

Open PRs are "in progress" and go into the bullet of their theme, never a
separate list. Anything the window does not cover is left out.

## 4. Format, exactly

- Plain text, no code fences, no headers, no bold. Bullets use "•".
- An opening line only when the user asks for one (an apology for missing the
  call, context for the team), in their words, tightened.
- Every PR, repository or page is a link wrapped in text, written as a Markdown
  link: `[the GOFR registration PR](https://github.com/...)`. The chat panel
  renders it as a hyperlink, and a copy from the rendered panel pastes into
  Slack with the link intact. Never a bare URL, never "#5041", never a repo slug.
- Three to five bullets, each one sentence, about twenty words. "Very brief"
  means three.
- The final reply is the message and nothing else: no "Written for" line, no
  window line, no notes about sources or housekeeping, no closing sentence.
  The user selects the whole reply and pastes it; any extra line lands in
  Slack. If something must be said (a source needed authorization, the window
  used), say it in a short text message before the last tool call, never in
  the final reply.

Example of the shape (links shortened here):

```
Hi all, apologies for missing the dev call, I'm not feeling well. Quick update on last week:

• Fixed a batch of bugs across order entry, results, validation and reports on develop.
• Streamlined the docs: all external integrations now live under one [External Integrations](https://...) section on the wiki, with a guide per integration.
• New integration: OpenELIS can now register itself as a facility in GOFR, so a single GOFR instance can track multiple OpenELIS instances ([PR](https://...), [setup repo](https://...)).
```

## 5. Corrections

A correction from the user (fewer bullets, a different opening line, a
different link style) applies to this message and to every later run: update
this skill in the skills repository and commit it, as the retro would.
