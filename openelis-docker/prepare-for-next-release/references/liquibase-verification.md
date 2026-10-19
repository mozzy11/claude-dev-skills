# Liquibase migration verification

This is the central test. It answers one question with evidence:

> Did the current development version successfully upgrade the database
> created by the last officially released version? YES, NO or INCONCLUSIVE.

## How the application migrates

- The webapp runs Liquibase itself at Spring start-up (`SpringLiquibase` bean
  `liquibase`, changelog `classpath:liquibase/base-changelog.xml`, contexts
  from `spring.liquibase.contexts`, `default` unless the deployment sets it).
  There is no separate migration container or command.
- `base-changelog.xml` includes one `base.xml` per version directory plus
  feature files (qa, qc, upgrade). Some changesets carry `context` (ci or
  test data) and never run in `default`; two carry `runAlways`; several files
  set `logicalFilePath`, so the `FILENAME` recorded in `DATABASECHANGELOG` can
  differ from the physical path. `scripts/liquibase_expected.py` handles all
  of that by reading the trees that are actually inside the two images.
- The webapp has no wait-for-database: if the database is not accepting
  connections about 20 s after the container starts, the `liquibase` bean
  fails, the context dies and Tomcat stays up with a dead context. That is an
  environmental failure, not a migration failure; `rt.sh up` and `rt.sh
  switch` start the database first for that reason.
- A failed changeset throws `MigrationFailedException`; Spring then logs
  `Error creating bean with name 'liquibase'` and Tomcat logs
  `Context [...] startup failed`. Tomcat still prints `Server startup in`, and
  the health endpoint does not answer 200. Every changeset before the failed
  one stays applied: the database is then partially upgraded.

## Procedure (after `rt.sh switch <develop>` and `rt.sh wait`)

1. `rt.sh logs develop-boot` saves the logs of every service. The webapp log
   is the primary evidence; keep it even on success.
2. `rt.sh liquibase-verify` does, in order:
   - exports `DATABASECHANGELOG` and `DATABASECHANGELOGLOCK` after the boot,
   - extracts `WEB-INF/classes/liquibase/` from the release image and from the
     develop image (`docker create` + `docker cp` of the WAR, `unzip`), so the
     expected set comes from the images under test and not from a checkout,
   - computes the runnable changesets of each tree (contexts, dbms), the
     changesets that are new in develop, and compares them with the rows that
     appeared in `DATABASECHANGELOG` since the pre-upgrade export,
   - checks exectypes (`EXECUTED`, `MARK_RAN` are fine; `MARK_RAN` means a
     precondition chose to skip, listed so you can judge it), checksum changes
     on previously applied rows, lost rows, `ORDEREXECUTED` continuity, rows
     dated before the upgrade start, the lock row,
   - scans the webapp log for `MigrationFailedException`,
     `ValidationFailedException`, `liquibase.exception`, bean creation errors,
     context failures, lock waits, SQL errors, and counts `ran successfully`
     lines,
   - writes `db/liquibase-verdict.md` and `.json`; exit 0 = YES, 2 = NO,
     3 = INCONCLUSIVE.
3. Read the verdict file. Confirm it against the log yourself: open
   `logs/<app>-develop-boot.log`, find the first Liquibase line and the last,
   and the lines around any error. The script finds candidates; you judge.
4. Confirm the application is operational after the migration: `rt.sh wait`
   returned 0 (health 200 with `{"status":"UP"}`, front end 200), and a login
   through the UI works (Phase 7 covers it).
5. Record in the report: previous version, target tag, whether the same
   database directory was reused (`rt.sh verify-running <develop>` shows the
   mount), the counts from the verdict file, failed/skipped changesets with
   file, id, author, error and impact, and the YES/NO/INCONCLUSIVE answer.

## Interpreting results

| Observation | Meaning | Action |
|---|---|---|
| verdict YES, 0 missing, log has `Server startup in`, health 200 | the upgrade ran to completion | continue to data integrity |
| `MARK_RAN` rows | a precondition decided the change was not needed on this data | list them; fine unless the precondition hides a real failure (`onFail="MARK_RAN"` on a change that should have applied) |
| missing changesets, log shows `MigrationFailedException` with `Reason:` | a changeset failed; database partially upgraded | capture file/id/author/reason; classify (defect, unexpected data state, bad assumption about existing data, version mismatch, environment); NOT READY or BLOCKED |
| checksum changes on old rows, log `ValidationFailedException` | a shipped changeset was edited after the release applied it | release blocker unless the project intends `runOnChange` there |
| log shows connection refused at the liquibase bean, no new rows | database not ready at boot | environmental; one webapp restart, then re-verify |
| `Waiting for changelog lock` loop | stale lock from a killed boot | see safety-rules recovery; clear only with proof |
| new rows but health never 200, `startup failed` after Liquibase finished | migration done, application failed later (bean wiring, FHIR, properties) | still NOT READY; the cause is in the log after the last changeset |
| rows exist, no log available | evidence incomplete | INCONCLUSIVE; recover the log (`docker logs`) before judging |

## Retrying after a fix

A failed changeset is fixed in the application source (Phase 10 of
SKILL.md): a new guard changeset or a precondition, never an in-place edit of
a changeset the release already applied (its checksum is recorded and would
fail validation on every existing installation). Then:

1. build the WAR and `rt.sh local-fix war <war>` (the webapp is recreated
   with the WAR mounted; `verify-running` and the verdict file name it),
2. `rt.sh restore-run`: the half-migrated directory is kept as evidence, a
   new directory is initialised with the release database image and the
   verified backup is restored into it (schema, data, the release's
   `DATABASECHANGELOG`), snapshotted and compared with `before`,
3. `rt.sh switch <develop>`, `rt.sh wait`, `rt.sh logs develop-boot-retry<n>`,
   `rt.sh liquibase-verify`: the expected set is read from the local WAR's
   changelog tree, so the verdict is about the fix. Record both verdicts in
   the report: the published image's (NO) and the local fix's.

## What not to do

No `clearCheckSums`, `changelogSync`, manual `DATABASECHANGELOG` edits, no
editing of already-applied changesets, no repeated restarts hoping for a
different outcome, no restoring the backup over the run database to hide a
failure. The purpose is to find release problems and fix them properly, not
to get past them.
