# Demonstration data and data-integrity verification

## Why

Production databases hold records written by the previous release. The
upgrade must keep them intact and usable, and migrations that transform data
(backfills, normalisations) must do what their changesets intend. A clean
development install proves none of that, so the release stack is seeded first
and the same records are checked after the upgrade.

## Demonstration data (created on the previous release, Phase 2)

Create a small, valid, traceable set. Use a run stamp in every identifier so
the records are unmistakable and the regression run cannot confuse them with
anything else: `RT<run-id digits>` (for example `RT20261016` and a sequence
number). Names must be letters only (the patient form strips digits), so put
the stamp in the national id, the external id, the subject number or a note.

Minimum set, in this order, through the UI with Playwright MCP unless noted:

| # | Record | How | Stable identifier to record |
|---|---|---|---|
| 1 | Patient A (adult, full demographics) | Patient entry page | national id `RT<run>-P1`, name |
| 2 | Patient B (minimal required fields) | Patient entry page | national id `RT<run>-P2` |
| 3 | Order 1 for Patient A: one sample type, two tests, one panel | Add Order (legacy `SamplePatientEntry` or the current order entry, whatever the running release offers) | accession number, test names, sample type |
| 4 | Order 2 for Patient B: another sample type, one test | same | accession number |
| 5 | Results for Order 1 (numeric and qualitative), saved | Results page by lab number | values entered |
| 6 | Validation of one Order 1 result (accepted), one left unvalidated | Validation page | which test was validated |
| 7 | Order 3 for Patient A left at "entered" (no results) | Add Order | accession number |
| 8 | Vector order and environmental order, if the running release has those menus; otherwise NOT APPLICABLE | their entry pages | accession numbers |
| 9 | One note on a sample (or patient) | Order/Results page note field | text contains the stamp |
| 10 | One external connection with basic auth (exercises encrypted secrets across the upgrade) | Admin, External Connections | name `RT<run>-conn` |
| 11 | One demonstration test or panel in the catalogue (inactive by default is fine) | Admin, Test Management | name contains the stamp |
| 12 | A multi-component test and a multi-sample-type test (per-component and per-sample-type ranges, codes, a reflex rule and a calculation using them), each ordered, resulted (one critical component) and validated | Test Management, order entry, results, validation; or the run's metadata files where the release UI cannot create them | test names, accession numbers, component values |

If the UI route for a record does not exist or cannot be driven reliably,
fall back to the application's own REST endpoints (the same ones the form
submits, with the CSRF token from `/api/OpenELIS-Global/session`) and say so
in the manifest. Use SQL only for lookups and verification, never to insert
domain records: the aim is data the application itself considers valid.

Keep the data consistent with the reference data the way the UI enforces it:
create in dependency order (catalogue and mappings before orders, orders
before results), order only tests mapped to the chosen sample type, enter
results the test's type and ranges accept, and match ages and sexes to the
ranges you rely on. Data that breaks these rules produces failures that are
not product defects (SKILL.md, Phase 10.1).

Write `release-reports/<run>/db/demo-manifest.md` as you go: one line per
record with its identifiers, the page used (or the REST fallback), and the
expected status, plus a "Configuration metadata" section listing every file
the run added or adapted (`references/configuration-metadata.md` step 3). Then
`rt.sh snapshot before` captures the whole database (every table count, the
business records keyed by stable identifiers, orphan checks, digests,
sequence positions).

## Checks after the upgrade (Phase 7)

1. `rt.sh snapshot after` and `rt.sh compare before after` produce
   `db/manifest-diff-before-after.md`. It reports:
   - table count changes (new tables and rows added by changesets are
     expected; a DECREASED count needs an explanation),
   - business records by stable key: VERIFIED, MISSING RECORDS or FIELDS
     CHANGED, with the changed fields listed (patients, identities, samples,
     sample items, analyses, results, notes, referrals, tests, panels, panel
     items, reflex and calculated test configuration, sample types, result
     limits, menus, users, roles, site information, organisations, providers,
     external connections, dictionary, observation history),
   - orphan checks on the core foreign keys (sample_human, sample_item,
     analysis, result, patient, panel_item, test_reflex, user roles) and
     samples without items / items without analyses,
   - id sequences behind max(id) (a classic cause of duplicate-key errors on
     the first insert after an upgrade),
   - the Liquibase row count and lock state.
2. For every difference, decide: intended by a changeset (name it; the
   `rt.sh liquibase-verify` output lists the applied changesets) or a defect.
   `fhir_uuid` backfills, menu rows, new configuration rows and new tables
   are the usual intended ones. A changed result `value`, accession number,
   national id, status, or a broken link is a CRITICAL defect.
3. Through the UI, on the development build, retrieve every demonstration
   record: patient search by national id and by name, order search by
   accession number, results by lab number (values and units shown as
   entered), validation page shows the validated status, the note is
   visible, the external connection opens with its name (and its secret is
   still usable: an edit/save round trip or a test-connection action if the
   page offers one), the catalogue entry opens. Screenshot each. Record
   PASS/FAIL per record in `ui/test-log.md`.
4. Insert new data after the upgrade (the regression run does): if the first
   insert into a table fails with a duplicate key, the sequence check above
   already names the table.

## Classification

- Lost, duplicated, orphaned or unusable pre-existing data: CRITICAL, release
  blocker, unless an explicitly intended and validated migration behaviour.
- Field transformations that match a changeset's intent: record as
  "expected transformation" with the changeset reference.
- Checks that could not be performed (table absent, UI route missing): list
  them under "not performed"; never count them as verified.
