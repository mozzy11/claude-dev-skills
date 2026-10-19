# Release safety and recovery rules

These rules bind every phase of the release test. `scripts/rt.sh` enforces the
ones it can; the rest are yours.

## The environment

- The application under test is the Docker deployment of this repository
  (`docker-compose.yml`, `.env`, `configs/`), run with the published images.
  Never build an image from the application source to stand in for a
  published one, and never test from the application checkout.
- The stack runs under the compose project `oe-release-test` with the run's
  override file, so named volumes are the run's own. The compose file's
  `container_name` values are fixed, so any other stack using those names or
  the published ports must be stopped (not removed) by whoever owns it before
  the run; `rt.sh preflight` lists the clashes.
- The database lives on `release-test/runs/<run>/db-data`, a directory created
  for the run. The deployment's own `configs/database/data` is never read,
  written, moved or deleted.
- Production guard: `rt.sh preflight` prints `ISOLATED LOCAL ENVIRONMENT`. If
  it says NO (a datasource host that is not a compose service, or a database
  directory outside the repository), stop and ask.
- Docker Desktop on this host has about 7.6 GiB for all containers and a
  release stack needs about 4 GiB. Never run it next to another OpenELIS
  stack or a testcontainers suite; `preflight` shows what else is running.

## Never

- `docker compose down -v`, `docker volume rm`, `docker volume prune` on this
  project while a run is in progress. `rt.sh teardown` never passes `-v`
  unless `--volumes` is given together with `OE_RT_CONFIRM_VOLUMES=yes`.
- Delete, move or overwrite a database data directory. The script has no code
  path that does; if a run must be discarded, the operator removes
  `release-test/runs/<run>` by hand.
- `git reset --hard`, `git checkout -- .`, `git clean` in this repository.
  Local changes are inspected and preserved; `rt.sh sync` only fast-forwards
  a clean tree.
- Edit `DATABASECHANGELOG` or `DATABASECHANGELOGLOCK`, run Liquibase
  `clearCheckSums`, `changelogSync`, `markNextChangeSetRan`, or hand-apply SQL
  so that a failed changeset looks applied. Clearing a stale lock is the one
  exception, and only when `pg_stat_activity` proves the locking session is
  gone and the lock time predates the current boot; record it as a recovery
  action.
- Edit the application source, its changelogs or the test data to make a
  failed check look passed. Defects are fixed in Phase 10 the proper way: a
  failing test, a general fix, the suites, a pull request, and a live
  re-verification through Playwright MCP (migration fixes in this stack from a
  local WAR, with the whole upgrade rerun; post-upgrade bugs on the dev
  server, then confirmed here). Correcting the run's own inconsistent test
  data is allowed only after a consistent record reproduced the case cleanly
  (SKILL.md, Phase 10.1). A shipped
  changeset that the previous release already applied is never edited in
  place (its checksum is recorded); guards go into a new changeset.
- Push a locally built image to Docker Hub, or retag a local build as a
  published tag. Local artefacts run only through `rt.sh local-fix`, which
  records their path, checksum and commit; the published `develop` tags come
  from the application's CI after the merge.
- Declare the release ready on the strength of a local fix. The status in the
  report is about the published images; a fix verified locally keeps it at
  NOT READY until merged and republished.
- Restart a failed upgrade boot repeatedly. One restart after a diagnosed
  environmental cause (database not ready, stale lock) is fine; after that,
  preserve the state and report. A migration retry after a fix goes through
  `rt.sh restore-run` (fresh directory from the verified backup), never
  through a restart on the half-migrated directory.
- Store a password in the report or in evidence files. `rt.sh creds` prints
  the login for your use only.

## Always

- Register the run with the session tracker so the SessionEnd cleanup knows
  about it, but as a `dir` only for the scratch extraction directories,
  never for the database directory or the backup:
  `claude-work/bin/session-track.sh dir <scratch path>`.
- Take evidence before changing state: `rt.sh logs <label>`,
  `rt.sh snapshot <label>`, `rt.sh verify-running <tag>`.
- Bound every wait. `rt.sh wait` caps itself (exit 4 means call it again),
  `rt.sh pull` can take long on a slow link (run it in the background and
  watch the tail of its output).
- When Docker stops answering (`docker ps` hangs), apply the hang recipe from
  memory (`kill -9` the `com.docker.backend` pid, then `open -a Docker`),
  wait for the database container to be healthy before the webapp, and if
  the webapp was killed mid-boot check `databasechangeloglock` before
  restarting it.
- Record every recovery action in `state.json` with `rt.sh state log "..."`
  and in the report's Environment section.

## Recovery

- Migration failed: keep the containers running (the failed boot's log is the
  evidence), `rt.sh logs develop-boot`, `rt.sh liquibase-verify`,
  `rt.sh snapshot after-failure`, `rt.sh compare before after-failure`. Decide
  whether the database is partially upgraded (new rows in `databasechangelog`
  but the verdict is NO). Then fix the changeset in the source (Phase 10),
  mount the rebuilt WAR, and retry from the release state with
  `rt.sh restore-run` + `rt.sh switch <develop>`: the half-migrated
  directory stays on disk as evidence, the retry runs on a new directory
  restored from the verified backup. Never restore the backup over the run
  database and never restart the webapp on the half-migrated directory
  hoping for a different result.
- Webapp dead because the database was not ready (log shows the datasource
  refusing connections at the liquibase bean, no changeset recorded): one
  `docker restart` of the webapp container after `rt.sh wait` confirms the
  database, then continue. Record it as an environmental event, not a defect.
- Stale changelog lock (`Waiting for changelog lock` in a loop, lock row older
  than the container start, no session holding it in `pg_stat_activity`):
  release it with `rt.sh psql "update databasechangeloglock set locked=false,
  lockgranted=null, lockedby=null where id=1"` and restart the webapp once.
- Docker daemon hang or VM read-only: see the Docker memory notes; after the
  daemon is back, `rt.sh status`, `rt.sh wait`, and re-verify running images
  before trusting any further evidence.

## Final state

The last message of a run states which tag is running (or that the stack is
stopped), where the database directory and the verified backup are, and
whether anything from another stack was stopped for the run and restarted.
