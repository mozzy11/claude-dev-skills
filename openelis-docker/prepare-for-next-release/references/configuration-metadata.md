# Configuration metadata: loading and migration

## Why

The deployment ships metadata as files: `configs/configuration/backend/<domain>/`
is mounted at `/var/lib/openelis-global/configuration/backend`, and every
`DomainConfigurationHandler` in the WAR reads its own domain at start-up
(`ConfigurationInitializationService`). `develop` usually adds handlers
(domains) and changes existing ones. A release is ready only when:

- everything the release loaded is still there and correct after the
  migration,
- every domain the develop build adds can be loaded on the **upgraded**
  database (not a fresh one), with its references to release-era records
  resolving,
- the develop loaders read the release-era files again without duplicates,
  lost links or errors.

A healthy start-up proves none of this: a file that fails to load is logged
and skipped, and the application boots anyway.

## How the loader behaves (verify against the source at the develop ref)

- Order: handlers run by `getLoadOrder()` (lower first). The develop boot
  logs `Loading configuration handlers in order: <domain>(<order>), ...`.
- Files: per domain, the filesystem folder wins over the WAR's bundled
  `classpath:configuration/<domain>/`; the two are never merged. Domains that
  share a folder (for example `address-hierarchy`, `compliance-standards`)
  split it by `getFileMatcher()`; the lower load order claims a file first.
  With `OPENELIS_CONFIGURATION_INSTANCE_ID` set, `<domain>/<instance>/` is
  used instead of the base files when it has any.
- Checksums: after a file loads successfully, its SHA-256 is written to
  `<config dir>/<domain>-checksums.properties`. An unchanged file is skipped
  on the next boot (`... unchanged (checksum matches). Skipping.`). A failed
  file keeps no checksum and is retried at every boot.
- Log lines (stdout, so `docker logs`):
  `Successfully loaded <domain> configuration: <file>`,
  `Failed to load <domain> configuration from file: <file>` (stack follows),
  `Failed to load configuration for domain: <domain>`.
- Develop also records each load in `configuration_import_run` and queues
  names it could not resolve in `unresolved_reference` (status column).
- Forced reload (develop, admin): `POST /rest/configuration/domains/reload`
  with `{"domains": [], "force": true}` (CSRF token from
  `/api/OpenELIS-Global/session`); the response lists every file as
  processed, skipped or error.

## 1. Isolate the run's configuration directory (before `up <release>`)

The compose file mounts `./configs/configuration` read-write, so the loader
writes checksum files into the docker repository. Leftover checksums from the
host's own deployment or an earlier run make the loader skip every file, and
the run then tests nothing; checksums written by the run would also leak into
the next one.

1. Copy `configs/configuration/` to `release-test/runs/<run>/configuration/`
   without any `*-checksums.properties`.
2. Add the mount to the run's `compose.override.yml`, under the application
   service: `- <absolute run configuration dir>:/var/lib/openelis-global/configuration`
   (compose merges volumes by container path, so it replaces the repository
   mount). `$RT config <tag>` must still validate.
3. After `up`, `docker inspect` the webapp's mounts: the configuration source
   must be the run directory. Record it in `state.json` (`$RT state set
   config_dir <path>`).

The checksum files then belong to the run and carry over the switch exactly as
they would in production.

## 2. Inventory the loaders and the metadata (Phase 1)

In the application checkout, without touching its working tree:

- `git -C <app> grep -l -E 'implements DomainConfigurationHandler|extends AbstractCatalogCsvHandler' <ref> -- src/main/java`
  for the develop ref (the commit the develop image was built from when known,
  otherwise `DIGI-UW/develop`) and for the release tag.
- For each handler: domain (`getDomainName`, constants included), matcher /
  extension, load order, required columns.

Write `env/config-inventory.md`:

| domain | release handler | develop handler (matcher, order) | files in the run configuration | example metadata in the app repo |
|---|---|---|---|---|

Mark domains new in develop, removed in develop, files no develop handler
reads, and develop domains with no file. Example metadata lives in the app
repository under `volume/configuration/backend/<domain>/`,
`src/main/resources/configuration/<domain>/`, `docs/configuration/` and the
handlers' unit-test resources.

## 3. Complete the metadata set (Phase 1, before `up <release>`)

Every develop domain must have at least one file in the run configuration:

- Release domains: keep the deployment's files as they are (they are what
  production has).
- Domains new in develop with no file in the deployment: add a small valid
  file, copied from the app repository's example where one exists, otherwise
  written from the handler's required columns. Its references must point at
  records the other files or the demonstration data create (tests, sample
  types, sections, dictionary entries), so cross-domain resolution is
  exercised. Put the run stamp `RT<run>` in free-text names.
- Put the new-domain files in place before the release boots: the release has
  no handler for them and must ignore them (confirm: no load line and no
  checksum file for those domains after the release boot). The develop boot on
  the migrated database then loads them for the first time, which is the
  production path.
- Note every file the run wrote or changed in `db/demo-manifest.md` (section
  "Configuration metadata"), with its source (copied verbatim / adapted /
  hand-written). Those files are test data and are the first suspects when a
  loader complains (see "test data or defect" in SKILL.md, Phase 10).
- A develop domain with no example in the deployment repository is also a
  deployment finding when the repository ships examples for comparable
  domains: fix it in Phase 10.5 (PR to openelis-docker).

## 4. Verify the load at every boot

Run after the release boot (Phase 2), the develop boot (Phase 6), every
migration retry, and every WAR remount. Save `db/config-load-<label>.md`:
for each file of each domain the running tag has a handler for:

| status | meaning |
|---|---|
| LOADED | `Successfully loaded` line this boot and the stored checksum equals `shasum -a 256 <file>` |
| UNCHANGED | `checksum matches` line, stored checksum equals the file |
| FAILED | `Failed to load ... from file` line (copy the stack excerpt) |
| STALE | stored checksum differs from the file and the file was not re-read |
| NOT SEEN | the file is in a handled domain but has no log line and no checksum (wrong folder, extension or matcher, classpath fallback, instance-id shadowing) |
| NO FILE | develop handler with no file (should not remain after step 3) |

Then the database and the UI:

- For every file, query that its records exist (by the file's keys: test
  names, panel names, dictionary entries, sample types, roles, ranges, rule
  names) with the expected active flag, localisation and links.
- Develop: the latest `configuration_import_run` rows, and every open
  `unresolved_reference` row. An open reference that one of the run's files
  should satisfy is a defect (loader, ordering, or the file).
- **Through Playwright MCP**, open the admin page for every loaded domain
  (Test Management, panels, sample types, dictionary, roles, result limits,
  reflex and calculated rules, test sections, locales, address hierarchy,
  questionnaires, NCE types and categories, compliance standards, vector
  species and trap types, EQA programmes, site branding and information,
  catalog import / unresolved references, whatever the running build has)
  and confirm at least one record from each file is shown as loaded, and
  usable where it applies (a loaded test appears in order entry for its
  sample type; a loaded range applies to a result). Screenshot each into
  `screenshots/config-<label>-<domain>.png`. Log, checksum and SQL evidence
  supports the UI check; it never replaces it.

Verdict YES only when nothing is FAILED, STALE or NOT SEEN, no relevant
unresolved reference is open, the records are in the database and every
domain was confirmed in the UI. Otherwise NO (or INCONCLUSIVE when the UI
check could not run), and the reason goes to the defect register.

## 5. Prove the metadata migrates (Phases 7 and 8)

1. The `before` / `after` snapshots cover the metadata tables. Release-era
   metadata must keep its ids, names, active flags, localisations and links
   (test to sample type and section, panel items, result limits, dictionary
   categories, reflex and calculated rules, roles to modules) unless a named
   changeset intends the change.
2. The develop boot normally skips the release-era files (UNCHANGED): that is
   the production path, and it is correct only if the migrated rows are
   right, which step 1 checks.
3. After `snapshot after`, force a reload on the upgraded database (the
   endpoint above, response saved to `db/config-reload-forced.json`), then
   `$RT snapshot after-reload` and `$RT compare after after-reload`. Expect no
   new duplicates, no lost links and no errors; any change must be what the
   develop loader legitimately updates (name it). Re-check the admin pages of
   the changed domains through Playwright MCP.
4. Edit one release-era file in a way the release format allows (for example a
   display name), boot or reload, and confirm the update lands on the existing
   record (no second record) in the UI.

A loader that fails, duplicates or loses links on the upgraded database is an
application defect (fixed on the dev server, Phase 10.3). A metadata table
broken by a changeset is a migration defect (Phase 10.2). A bad file the run
wrote is test data (Phase 10.1).

## Retries

`backup` copies the run configuration directory, with the checksums the
release wrote, to `backup/configuration/`. Before every `switch develop` after
`restore-run`, restore it (`rsync -a --delete backup/configuration/
release-test/runs/<run>/configuration/`), so the retry starts from the
release's configuration state as well as its database.
