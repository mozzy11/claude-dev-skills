# UI regression checklist (Playwright MCP)

Everything here is driven through the real browser against the running stack
at `https://localhost/` with the Playwright MCP tools. SQL and the REST API
serve setup and supporting verification only; a workflow counts as tested
when its meaningful operations were completed through the UI and the saved
state was read back in the UI (reopened page, related page); SQL or the API
may confirm it as well but never replace the UI read-back.

## Working with the Playwright MCP

- Check it is alive first: `browser_tabs` (list). If the call fails or hangs,
  the UI phases are BLOCKED; record that, never substitute another mechanism
  and call it Playwright.
- Login: navigate to `https://localhost/login`, `browser_snapshot`, fill the
  user name (`#loginName`) and password (`#password`; do not use a label
  locator, the show-password toggle matches too), click the primary **Login**
  button (the first submit button on the page is the User Manual link).
  Credentials: `rt.sh creds`. If the app forces a password change, do it and
  store the new value with `rt.sh state set ui.admin_password <value>`.
  Sessions die whenever the webapp container is recreated: log in again after
  the upgrade.
- Explore before testing: open every top-level menu and note the routes that
  exist on the running version (the development build has routes the release
  lacks, and menu names change). The front end's route table lives in
  `App.jsx` of the application, but the running menu is what counts; read the
  `menu` table (`rt.sh psql "select element_id, action_url, is_active from
  menu order by presentation_order"`) when a page is hard to find.
- Prefer `browser_snapshot` refs, roles, labels and visible text over CSS.
  Use `browser_fill_form` for forms, `browser_select_option` for native
  selects, click Carbon checkbox/radio/toggle **labels** (the inputs are
  visually hidden). The header has its own Search button: scope to the main
  region when a form also has one.
- Evidence: `browser_take_screenshot` with an absolute `filename` under
  `release-reports/<run>/screenshots/<phase>-<workflow>-<step>.png`;
  `browser_console_messages` (level error) and `browser_network_requests`
  after each workflow; copy anything the MCP wrote elsewhere with
  `rt.sh screenshots <dir>`.
- `browser_run_code_unsafe` is for short read-backs only (status text, table
  rows). Never end such a script on an action that navigates and then read
  the response body; it can hang the MCP for 30 minutes. Put navigating
  actions last and read state in the next call. A dirty form raises a
  `beforeunload` dialog that blocks the next navigation: handle it with
  `browser_handle_dialog`.
- Patient name fields drop digits; use letters-only names and carry the run
  stamp in the national id.
- Legacy order entry (`/SamplePatientEntry`) creates analyses on submit; the
  newer clinical order flow (`/order/clinical/enter`) stores only sample type
  requests until the Collect step, so for results the order must be collected
  first. The unified results route may redirect `/AccessionResults` to
  `/Results` ("Search by lab number").
- Record every test in `release-reports/<run>/ui/test-log.md` as it happens:
  `| id | workflow | test case | expected | actual | status | evidence |
  severity | in previous release? |`.

## Statuses

PASS, FAIL, BLOCKED (environment or MCP prevented it), NOT TESTED (ran out
of scope or time; say why), NOT APPLICABLE (the running deployment has no such
feature or menu). Never PASS without completing the operation.

## Baseline on the previous release (Phase 4, brief)

Login; Patient entry opens and finds Patient A; Add Order opens and finds
Order 1 (sample type, tests shown); Results by lab number shows Order 1's
results; Validation page opens and lists or shows the validated result;
Reports menu opens one report page; Admin menu opens Test Management. One
screenshot per step. Any failure here is a baseline fact: investigate whether
it is environmental or an application defect of the release, and carry it
into the "in previous release?" column later.

## Regression on the development build (Phase 9)

Run the retrieval checks of `data-integrity.md` first (pre-existing records
through the UI), then the workflows below. Create new records with a `RT<run>-
NEW` stamp so pre-migration and post-migration data stay distinguishable.

### Priorities: test everything, the core in depth

Everything the running build exposes is tested, but not to the same depth.

- **Tier 1, core functionalities (sections 1 to 9): exhaustive.** Patient
  entry, order entry, result entry, multi-component and multi-sample-type
  tests (ranges, terminology, reflex, alerts, calculated; section 4b, extra
  emphasis), validation, reports, reflex and
  calculated tests, test catalogue management, and the admin management pages
  (users and roles, organisations, providers, and the other management
  pages listed in section 9). Every case listed below is run, every
  applicable edge case of the generic list at the end is run on top of them,
  and each case is run on both pre-migration (release-created) records and
  new records. A Tier 1 case is never skipped for time: if the run is long,
  it is long. Anything not run is NOT TESTED with the reason, and an untested
  Tier 1 case lowers the overall status.
- **Tier 2, everything else (section 10): breadth.** Every remaining menu
  item opens without console or 5xx errors, its main list or search works,
  and one create or edit on a demonstration record succeeds where it is safe.
- Order of work: Tier 1 first, in the order listed, then Tier 2. Time spent
  follows production risk: data written by labs every day (patients, orders,
  results, validation) comes first.
- For every Tier 1 case: drive it in the UI, save, read it back in the UI
  (reopen, and check the related page: order vs results vs validation vs
  report), screenshot, `browser_console_messages` and
  `browser_network_requests` after the case, one row in `ui/test-log.md`.

### Edge-case matrix applied to every Tier 1 form

Run each of these on every Tier 1 create and edit form, in addition to the
section's own cases (record NOT APPLICABLE with the reason when a case
cannot apply to that form):

1. All fields valid, then save, reopen, every field shown as entered.
2. Each required field left empty, one at a time: inline error, no save, the
   other entered values kept.
3. Invalid formats: letters in numbers and dates, wrong date format, invalid
   email or phone, special characters, leading and trailing spaces.
4. Boundaries: minimum and maximum lengths, maximum length plus one, zero,
   negative, very large numbers, decimal precision, dates on today, in the
   future, far in the past, on leap day.
5. Duplicates: the same identifier or name as an existing record (pre- and
   post-migration).
6. Unicode and accented names (French and other locale characters), and the
   page in a second locale if the build ships one.
7. Edit an existing pre-migration record, save, reopen; then edit it again
   (second save on the same record).
8. Cancel or navigate away with unsaved changes (dialog), refresh mid-form,
   browser back and forward.
9. Double submit (save clicked twice quickly): exactly one record.
10. Search: exact hit, partial hit, case variations, no hit (clean empty
    state), search with an empty term.
11. Permissions: a user without the role cannot open or save it (section 9
    creates the restricted users).
12. State after an error: fix the field that failed and save; the record
    saves correctly with no leftovers from the failed attempt.

### 1. Patient entry and management (Tier 1)

- Create a patient with every field (names, gender, birth date, national id,
  other identifiers, phone, email, address hierarchy levels, health region,
  education, marital status, nationality, emergency contact): save, reopen by
  national id and by last name, every field as entered.
- Minimal patient (required fields only).
- Birth date variants: exact date, estimated age in years, months, days;
  newborn (today), a future date (refused), a 120-plus-year age (warning or
  refusal, record the behaviour).
- Name rules: digits dropped or refused (record it), hyphens, apostrophes,
  accents, a single-letter name, a very long name.
- Duplicate national id and duplicate name plus birth date: warning or
  refusal, and what happens on override.
- Search by every search field the page has (id, names, birth date, gender,
  phone), alone and combined, hits and misses; pre-migration patients found
  by every field they hold.
- Edit a pre-migration patient (phone, address, identifier), save, reopen;
  the patient's existing orders still link to them.
- Patient history / patient results page for a patient with orders and for
  one without.
- Patient merge, if present: merge two run patients, both orders end up on
  the survivor, the other is no longer searchable.
- Patient created inside order entry (section 2) appears in patient search.

### 2. Order entry (Tier 1)

For each entry flow the running build exposes (`/SamplePatientEntry`,
`/order/clinical/*`, `/order/vector`, `/order/environmental`, generic sample,
electronic orders), run every case:

- New order for an existing patient: one sample type, two tests, save;
  reopen by accession number; sample, tests and patient linked (shown on the
  order, results and patient pages).
- New order for a new patient created in the flow.
- Panels: order a panel; its tests appear; order a panel plus a single test
  that is also in the panel (no duplicate analysis).
- Several sample types in one order, each with its own tests.
- Tests offered per sample type: only the mapped tests are offered; an
  inactive test or sample type is not offered.
- Requester (provider) and site (organisation): pick existing ones, including
  pre-migration ones and ones created in section 9; a required requester
  left empty.
- Dates and times: collection and reception today, in the past, in the
  future (refused), reception before collection (refused or warned).
- Lab number: generated, manual (if allowed), duplicate (refused), wrong
  format (refused), the next generated number after the upgrade does not
  collide with pre-migration numbers.
- Priority, program, questionnaire / additional order fields, if present.
- Required fields: no sample type, no test, no patient, one at a time.
- Collect step (clinical flow): collect, then the order reaches results;
  an uncollected order does not.
- Modify order: add a test, remove a test with no result, try to remove one
  with a result (refused), cancel a sample, add a sample; reopen each time.
- Labels / barcodes print from the order (the PDF opens).
- Vector and environmental: their specific fields (site, species, trap,
  location, observations from the loaded metadata), and the dashboard or
  report that lists them.
- Non-conforming event or sample rejection from order entry, if present.

### 3. Pathology, immunohistochemistry, cytology (Tier 1 where present)

For each dashboard that exists (`/PathologyDashboard`,
`/ImmunohistochemistryDashboard`, `/CytologyDashboard`): the list opens; an
order with the matching sample type appears (create one via order entry with a
pathology or cytology sample type if the catalogue has it); open the case
view; fill the required fields of each status in turn, save, reopen; attempt
an invalid transition (skip a required step); the patient and order
information on the case matches; the case report generates. Record NOT
APPLICABLE where the catalogue has no such sample types.

### 4. Result entry (Tier 1)

- Find work: by lab number, by patient, by test section work plan, by test,
  by date range; pre-migration orders and new ones.
- Numeric: inside the normal range; below and above it (flag shown); at
  exactly the low and high limits; in the critical range (critical flag or
  alert); outside the valid range (warning or refusal); decimals beyond the
  test's significant digits (rounded or refused, record which); zero;
  negative where meaningless.
- Ranges by patient: the same test for a male and a female patient, a child
  and an adult (age- and sex-specific ranges applied, including ranges the
  metadata loaded).
- Qualitative (dictionary) results, multi-select results, free text,
  titre-type results if any; a result component (multi-component test) if
  configured.
- Letters in a numeric result, an empty save, a result for only some tests
  of the order.
- Units shown as configured; result notes added and visible later.
- Save, navigate away, return: values, units, flags, ranges persist; the
  order page and patient results page show the same values.
- Edit a saved, unvalidated result; correct a validated result where the
  build allows (status returns to validation, history kept).
- Referral of a test to another lab, if present.
- Results for a cancelled sample or an uncollected order: refused or hidden,
  no server error.
- Analyzer results import page opens (if present); the CSV / harness flow only
  when the stack has the analyzer configuration.
- Console and network: no 5xx on any save.

### 4b. Multi-component and multi-sample-type tests (Tier 1, extra emphasis)

The user asked for extra emphasis here (2026-10-19). Use at least one
multi-component test (one test whose result has several components, each
with its own unit, range and code) and at least one multi-sample-type test
(one test orderable on two or more sample types, for example serum and
plasma, or blood and urine, with different ranges per sample type). Take them
from the metadata the run loaded, the pre-migration catalogue, and one of
each created through Test Management in section 9; run every case below on
each, and on pre-migration and new orders.

Numeric validation ranges:
- Each component has its own normal, critical and valid range, unit and
  significant digits; a value inside, below, above, at each limit and outside
  the valid range on each component flags only that component.
- The same test on each sample type applies that sample type's range (a
  value normal on one sample type is flagged on the other); age and sex bands
  per sample type and per component.
- A component with no range configured shows no false flag; an empty
  component on save (required or allowed, as configured).
- Editing a range in Test Management changes the flag on new results only;
  existing results keep their recorded range.

Terminology:
- Each component and each sample-type variant shows and stores its own code
  (LOINC or the configured terminology); the codes survive the upgrade
  unchanged; codes loaded from the terminology metadata are applied.
- The codes reach the outputs: the patient report and, if the build exposes
  FHIR, the Observation for each component carries its component code (read
  it through the UI's FHIR or export view where present, the API only as
  support).

Reflex tests:
- A rule conditioned on one component fires only on that component's value;
  a rule conditioned on a test for one sample type does not fire for the
  other sample type unless configured to; boundary values of each condition.
- The reflexed test is added to the right sample of a multi-sample order.

Alerts:
- A critical value on one component raises the critical alert or
  notification the build offers (results page flag, validation marker, Alerts
  module entry, delivery notification where configured), names the
  component, and clears or is acknowledged as the build intends; a normal
  value raises none.

Calculated tests:
- A calculation using components as operands (or producing a component)
  computes the right value with the right unit and rounding; a calculation
  using the same test on two sample types takes the operand from the right
  sample; a missing component operand gives a clear message, no wrong value.

End to end, for each test: order (both sample types in one order, then
separately), result every component, validate (per component where the build
allows: accept one component, reject another), report (every component with
its own unit, range, flag and code; the right sample type named), and the
patient results page shows the same.

### 5. Result validation (Tier 1)

- Validation by test section, by lab number range, by test date (each route
  present): the new results and pre-migration unvalidated results are listed.
- Accept one; reject one with a note; hold or retest one; accept all on a
  page; save; reopen: every status persisted, and the results page and the
  patient report show the right state.
- Abnormal and critical results are marked on the validation page.
- Validate nothing selected; re-validate an already validated result; a
  result edited after validation returns to validation.
- Reflex and calculated results (sections 7 and 8) appear for validation
  with their source results.
- Permission: a user without the validation role cannot open or save
  validation (section 9).

### 6. Reports (Tier 1)

- Patient report by lab number and by patient for: a pre-migration validated
  order, a new validated order, a partially validated order (unvalidated
  results not printed or marked), a corrected result; the PDF opens and its
  text holds the right values, units, ranges and flags (read the text with
  the PDF helper).
- Each routine report the menu offers (patient status, aggregate, statistics,
  TAT, audit trail, non-conformity, vector, export / CSV): a date range
  covering the run, one matching nothing (empty handled), an invalid range
  (end before start, refused), the largest range allowed.
- Report print queue and label printing.
- Reports in the second locale if the build ships one.

### 7. Reflex tests (Tier 1)

- The list opens; pre-migration rules display with their conditions and
  actions intact; rules loaded from metadata display.
- Create a rule on a demonstration test (numeric condition, then a dictionary
  condition), save, reopen, edit, deactivate, reactivate.
- Fire it: enter the triggering result, the reflex test is added to the
  order; enter a non-triggering result, nothing is added; the boundary value
  of the condition.
- Invalid rules: no condition, no action, a test not valid for the sample
  type, a rule referring to itself; expect refusal.
- A deactivated rule does not fire.

### 8. Calculated tests (Tier 1)

- The list opens; pre-migration calculations display intact.
- Create a calculation on demonstration tests (operands, operators,
  constants), save, reopen, edit, deactivate.
- Fire it: enter the operand results, the calculated value appears and is
  correct (check the arithmetic and rounding); a missing operand (no value or
  a clear message); a division by zero; operand units.
- Invalid calculations: no operand, an unknown test, a malformed formula;
  expect refusal.

### 9. Test catalogue and admin management (Tier 1)

Test catalogue management:
- View a pre-migration test and a metadata-loaded test: every attribute
  (names, localisations, section, sample types, result type, units, ranges,
  dictionary answers, LOINC / codes, panels, active, orderable, sort order)
  intact after the upgrade.
- Create a test through the full wizard (each result type the build offers),
  save, then order it, result it and validate it end to end.
- Edit a test: name, section, sample type mapping, ranges (age and sex
  bands, critical and valid limits), dictionary answers, active flag; each
  change visible in order and result entry.
- Required fields and invalid configurations (no sample type, no result type,
  overlapping or inverted ranges, duplicate name): refused.
- Panels, sample types, test sections, units of measure, result limits:
  create, edit, deactivate one each; the change shows in order entry.

Admin management pages:
- **Users and roles:** create a user with each role combination the build
  offers (at least receptionist only, results only, validation, admin);
  required fields, weak password, duplicate login name (record whether it is
  refused or silently ignored), expiry date; log in as each new user and
  confirm the menu and the pages match the roles and refused pages are
  refused; edit, deactivate, a deactivated user cannot log in; pre-migration
  users still log in with their passwords.
- **Organisations:** create with type and address, search, edit, deactivate;
  duplicate name; required fields; the organisation is offered in order
  entry (site / referring lab); pre-migration organisations intact.
- **Providers:** create with all fields, search, edit, deactivate; duplicate;
  required fields; the provider is offered as requester in order entry and
  printed on the report; pre-migration providers intact.
- **Other management pages:** dictionary (create, edit, category), site
  information and branding (a non-destructive change, then revert), menu
  configuration, programs, questionnaires, reflex and calculated (sections 7
  and 8), external connections (the pre-migration one opens and its secret
  still works), barcode and label configuration, result reporting
  configuration, NCE types and categories, analyzer configuration, EQA
  programmes, localisation / translations, catalog import and unresolved
  references: each opens, lists, and one create or edit with save and reopen.

### 10. Everything else (Tier 2)

Walk the remaining menu: sample management / sample edit, sample reception
and rejection, work plans (by test, panel, priority, section), quality
control pages, storage, inventory, analyzers, EQA / QA pages, audit trail,
notebook, dashboards, data export, and anything the menu shows that is not
above. For each: the page opens without console or 5xx errors; the main list
or search works; one create or edit on a demonstration record where it is
safe; document what was not tested and why.

### Generic edge cases (all tiers)

Pre-migration vs post-migration data on every page; consistency between
related pages (order vs results vs validation vs report); persistence after
navigation; unexpected but valid combinations (two sample types, many tests,
long notes); wrong combinations (test not for sample type); empty result
sets; console errors; failed requests that affect function. Document rather
than run anything destructive to shared configuration.

## Failure record

For every FAIL: workflow, steps, expected, actual, screenshot path, console
error, failed request (method, URL, status), webapp log excerpt (`docker logs`
around the timestamp), database evidence (query and rows) where relevant,
severity, and whether the same steps failed on the previous release in the
baseline (if not tried there, say "not checked on the previous release").
