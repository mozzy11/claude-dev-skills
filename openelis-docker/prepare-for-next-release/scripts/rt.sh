#!/usr/bin/env bash
# Release-test driver for the prepare-for-next-release skill.
#
# Runs the openelis-docker deployment (docker-compose.yml of this repository)
# under a dedicated compose project with every application image pinned to one
# tag and the database on a run-specific data directory, so the deployment's
# own configs/database/data and any other stack on the host are never touched.
#
# Every subcommand is idempotent and reads/writes release-reports/<run>/state.json,
# so an interrupted run can be inspected (`resume`) and continued safely.
# Nothing here ever deletes a database directory, runs `down -v`, or edits
# DATABASECHANGELOG.
#
# Usage: rt.sh <subcommand> [args]   (run `rt.sh help`)
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
# The openelis-docker checkout under test: OE_RT_REPO, else the git checkout of
# the current directory, else the default local clone.
DEFAULT_REPO="$HOME/Desktop/DEV/Projects/OpenELIS/openelis-docker/openelis-docker"
if [ -z "${OE_RT_REPO:-}" ]; then
  top=$(git rev-parse --show-toplevel 2>/dev/null || true)
  if [ -n "$top" ] && [ -f "$top/docker-compose.yml" ] && grep -q openelis "$top/docker-compose.yml" 2>/dev/null; then
    OE_RT_REPO=$top
  else
    OE_RT_REPO=$DEFAULT_REPO
  fi
fi
REPO=$OE_RT_REPO
[ -f "$REPO/docker-compose.yml" ] || { printf 'ERROR: %s has no docker-compose.yml; set OE_RT_REPO to the openelis-docker checkout\n' "$REPO" >&2; exit 1; }
PROJECT=${OE_RT_PROJECT:-oe-release-test}
REPORTS="$REPO/release-reports"
RUNS="$REPO/release-test/runs"
CURRENT="$REPORTS/.current-run"
BASE_COMPOSE="$REPO/docker-compose.yml"
GITHUB_APP_REPO=${OE_RT_GITHUB_APP_REPO:-DIGI-UW/OpenELIS-Global-2}
GITHUB_DOCKER_REPO=${OE_RT_GITHUB_DOCKER_REPO:-DIGI-UW/openelis-docker}
TAB=$(printf '\t')

say()  { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
now()  { date '+%Y-%m-%dT%H:%M:%S%z'; }

# Run a command with a time cap (docker calls can hang when the daemon is
# unhappy; see the Docker hygiene notes). Usage: dock <seconds> cmd...
dock() {
  local cap=$1; shift
  "$@" & local p=$!
  ( trap 'kill $s 2>/dev/null; exit 0' TERM; sleep "$cap" & s=$!; wait $s; kill $p 2>/dev/null ) </dev/null >/dev/null 2>&1 &
  local w=$!
  wait $p; local rc=$?
  kill $w 2>/dev/null; wait $w 2>/dev/null
  return $rc
}

# ---------- run directory and state ----------
run_id() { [ -f "$CURRENT" ] && cat "$CURRENT" || true; }
run_dir() {
  local id; id=$(run_id)
  [ -n "$id" ] || die "no current run; start with: rt.sh init"
  printf '%s' "$REPORTS/$id"
}
state_file() { printf '%s/state.json' "$(run_dir)"; }

state_get() {
  python3 -I - "$(state_file)" "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
v = d
for part in sys.argv[2].split('.'):
    v = v.get(part) if isinstance(v, dict) else None
    if v is None: break
if v is None: print('')
elif isinstance(v, (dict, list)): print(json.dumps(v))
else: print(v)
PY
}

state_set() {
  python3 -I - "$(state_file)" "$1" "$2" <<'PY'
import json, sys
p, key, raw = sys.argv[1:4]
d = json.load(open(p))
try: val = json.loads(raw)
except Exception: val = raw
cur = d
parts = key.split('.')
for part in parts[:-1]:
    cur = cur.setdefault(part, {})
cur[parts[-1]] = val
json.dump(d, open(p, 'w'), indent=2, sort_keys=True)
PY
}

state_log() {
  python3 -I - "$(state_file)" "$(now)" "$*" <<'PY'
import json, sys
p, ts, msg = sys.argv[1:4]
d = json.load(open(p))
d.setdefault('events', []).append({'at': ts, 'msg': msg})
json.dump(d, open(p, 'w'), indent=2, sort_keys=True)
PY
  say "[$(now)] $*"
}

# ---------- compose ----------
override_file() { printf '%s/compose.override.yml' "$(run_dir)"; }

# compose <tag> <compose args...>: the deployment's own compose file plus the
# run's override (and the local-fix override once a fix is deployed), under
# the dedicated project name.
compose() {
  local tag=$1; shift
  local lf=""; [ -f "$(run_dir)/compose.local-fix.yml" ] && lf="$(run_dir)/compose.local-fix.yml"
  OE_RT_TAG="$tag" OE_RT_DB_DATA="$(state_get db_data_dir)" \
    docker compose -p "$PROJECT" --project-directory "$REPO" \
      -f "$BASE_COMPOSE" -f "$(override_file)" ${lf:+-f "$lf"} "$@"
}

WAR_IN_IMAGE=${OE_RT_WAR_PATH:-/usr/local/tomcat/webapps/OpenELIS-Global.war}
HTML_IN_IMAGE=${OE_RT_FRONTEND_HTML:-/usr/share/nginx/html}

current_tag() { local t; t=$(state_get current_tag); [ -n "$t" ] && printf '%s' "$t" || state_get release_tag; }

svc() { state_get "services.$1"; }
cid() { compose "$(current_tag)" ps -q "$(svc "$1")" 2>/dev/null | head -1; }

psql_in_db() {
  # psql_in_db <args...>  (as clinlims on the clinlims database, tab separated)
  local c; c=$(cid db); [ -n "$c" ] || die "database container is not running"
  docker exec -i "$c" psql -X -At -F "$TAB" -v ON_ERROR_STOP=1 -U clinlims -d clinlims "$@"
}

# ---------- helpers ----------
base_config_json() {
  docker compose --project-directory "$REPO" -f "$BASE_COMPOSE" config --format json 2>/dev/null
}

hub_tag_info() {
  # hub_tag_info <repo> <tag> -> "<last_updated> <digest>" or "MISSING"
  python3 -I - "$1" "$2" <<'PY'
import json, sys, urllib.request
repo, tag = sys.argv[1:3]
if '/' not in repo: repo = 'library/' + repo
try:
    d = json.load(urllib.request.urlopen(f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}", timeout=20))
    print(d.get('last_updated', '')[:19], d.get('digest') or '', ' '.join(sorted({i.get('architecture','') for i in d.get('images', [])})))
except Exception as e:
    print('MISSING', str(e)[:80])
PY
}

require_tools() {
  local missing=""
  for t in docker python3 curl unzip lsof git; do command -v "$t" >/dev/null 2>&1 || missing="$missing $t"; done
  [ -z "$missing" ] || die "missing tools:$missing"
}

# ---------- subcommands ----------
cmd_help() {
  cat <<EOF
rt.sh subcommands (project $PROJECT, repo $REPO)
  preflight              inspect git, docker, ports, memory, disk, conflicting containers, isolation guard
  sync                   fast-forward the docker repo to upstream/main when the tree is clean (never resets)
  init [--new]           create release-reports/<run>/ (state, override file, db data dir) and make it current
  resume                 print the current run's state and the next safe step
  versions               discover the latest official release and the develop tags; check the registry
  config <tag>           validate and save the resolved compose config for <tag>
  pull <tag>             pull the application images for <tag>
  up <tag>               guarded start: db first, wait for it, then the rest
  wait [seconds]         wait for db ready, webapp started, health 200, frontend 200 (exit 4 = still waiting)
  status                 containers, images, digests, state
  verify-running <tag>   assert every pinned container runs <tag> (image id + registry digest) on the run's db dir
  logs <label>           save docker logs of every service to logs/<service>-<label>.log
  psql "<sql>"           run SQL as clinlims (tab separated)
  sql-file <file>        run a SQL file as clinlims
  snapshot <label>       db/manifest-<label>.json + db/databasechangelog-<label>.tsv
  compare <a> <b>        db/manifest-diff-<a>-<b>.md from two snapshots
  backup                 pg_dump (custom format) + globals into backup/, then verify-backup
  verify-backup          pg_restore --list and a restore into a scratch database, then drop it
  switch <tag>           guarded upgrade: new db container, pre-upgrade snapshot, then the application
  liquibase-verify       expected vs applied changesets, exectypes, checksums, lock, log scan -> db/liquibase-verdict.md
  creds                  the application login and the DEFAULT_PW the compose file sets (never put it in a report)
  screenshots <dir>      copy screenshots newer than the run start into screenshots/
  report-skeleton        write release-reports/openelis-release-readiness-<run>.md from the template
  state get <k> | set <k> <v> | log "<msg>"
  stop | start           compose stop / start (containers kept)
  teardown [--volumes]   compose down without -v; --volumes needs OE_RT_CONFIRM_VOLUMES=yes; the db dir is never deleted
Fix loop (after defects were found):
  local-fix war <path>        mount a locally built WAR over the webapp's WAR and recreate the webapp
  local-fix frontend <dir>    mount a local front-end build (vite dist) over the nginx html root
  local-fix image <svc> <img> run a locally built image for one service
  local-fix show | clear      show or remove the local overrides (clear recreates the services from the images)
  restore-run                 new database directory restored from the verified backup (release state), previous
                              attempt's evidence archived; then: rt.sh switch <develop>, wait, liquibase-verify
EOF
}

cmd_preflight() {
  require_tools
  local f=/dev/null
  if [ -n "$(run_id)" ] && [ -d "$REPORTS/$(run_id)" ]; then mkdir -p "$REPORTS/$(run_id)/env"; f="$REPORTS/$(run_id)/env/preflight-$(date +%H%M%S).txt"; fi
  preflight_body 2>&1 | tee "$f"
}

preflight_body() {
  say "== prepare-for-next-release preflight $(now)"
  say "repo: $REPO"
  say "-- git"
  git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "$REPO is not a git checkout"
  say "branch: $(git -C "$REPO" branch --show-current)  head: $(git -C "$REPO" rev-parse --short HEAD)"
  git -C "$REPO" remote -v | sed 's/^/remote: /'
  dock 60 git -C "$REPO" fetch --all --prune --tags >/dev/null 2>&1 || warn "git fetch failed (offline?)"
  local dirty; dirty=$(git -C "$REPO" status --porcelain | grep -v '^?? release-reports/\|^?? release-test/\|^?? .claude/' || true)
  if [ -n "$dirty" ]; then say "uncommitted changes (preserved, never reset):"; printf '%s\n' "$dirty" | sed 's/^/  /'; else say "working tree: clean"; fi
  for ref in upstream/main origin/main; do
    if git -C "$REPO" rev-parse -q --verify "$ref" >/dev/null 2>&1; then
      say "vs $ref: ahead $(git -C "$REPO" rev-list --count "$ref"..HEAD) behind $(git -C "$REPO" rev-list --count HEAD.."$ref")"
    fi
  done
  say "last commits:"; git -C "$REPO" log --oneline -5 | sed 's/^/  /'
  say "-- docker"
  dock 20 docker info --format 'engine {{.ServerVersion}} {{.OSType}}/{{.Architecture}} mem {{.MemTotal}} cpus {{.NCPU}}' 2>/dev/null || die "docker daemon not answering within 20 s (see the Docker hang recipe)"
  docker compose version 2>/dev/null | head -1
  say "-- compose file: $BASE_COMPOSE"
  local cfg; cfg=$(base_config_json) || die "docker compose config failed on the base file"
  local cfgf; cfgf=$(mktemp); printf '%s' "$cfg" > "$cfgf"
  python3 -I - "$cfgf" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for name, s in d["services"].items():
    ports = ",".join(f"{p.get('published','')}->{p.get('target','')}" for p in s.get("ports", []))
    vols = [v for v in s.get("volumes", []) if v.get("target") == "/var/lib/postgresql/data"]
    pg = f" PGDATA<-{vols[0].get('source')}" if vols else ""
    print(f"  {name:<24} {s.get('image',''):<48} container={s.get('container_name','')} ports={ports}{pg}")
PY
  say "-- isolation guard"
  python3 -I - "$REPO" "$cfgf" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[2]))
names = set(d["services"])
bad = []
for name, s in d["services"].items():
    env = s.get("environment") or {}
    blob = " ".join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else " ".join(env)
    for m in re.finditer(r"jdbc:postgresql://([^:/\s]+)", blob):
        if m.group(1) not in names: bad.append(f"{name}: datasource host {m.group(1)} is not a compose service")
    for v in s.get("volumes", []):
        if v.get("target") == "/var/lib/postgresql/data" and v.get("type") == "bind" and not str(v.get("source", "")).startswith(sys.argv[1]):
            bad.append(f"{name}: database data dir {v.get('source')} is outside the repository")
print("ISOLATED LOCAL ENVIRONMENT: " + ("yes" if not bad else "NO"))
for b in bad: print("  " + b)
PY
  rm -f "$cfgf"
  say "-- existing deployment database directory (never touched by this skill)"
  if [ -f "$REPO/configs/database/data/PG_VERSION" ]; then say "  configs/database/data: present, PG_VERSION $(cat "$REPO/configs/database/data/PG_VERSION"), modified $(stat -f '%Sm' "$REPO/configs/database/data")"; else say "  configs/database/data: absent or empty"; fi
  say "-- containers that would clash (fixed container_name values of the compose file)"
  local clash=0
  for n in $(printf '%s' "$cfg" | python3 -I -c 'import json,sys; [print(s.get("container_name","")) for s in json.load(sys.stdin)["services"].values() if s.get("container_name")]'); do
    local info; info=$(dock 20 docker ps -a --filter "name=^${n}$" --format '{{.Names}} {{.Image}} {{.Status}} project={{.Label "com.docker.compose.project"}}')
    if [ -n "$info" ]; then
      case "$info" in *"project=$PROJECT"*) say "  $info (this skill's project, fine)";; *) say "  CLASH: $info"; clash=1;; esac
    fi
  done
  [ $clash = 0 ] && say "  none"
  say "-- published ports"
  for p in $(printf '%s' "$cfg" | python3 -I -c 'import json,sys; print(" ".join(sorted({str(p.get("published")) for s in json.load(sys.stdin)["services"].values() for p in s.get("ports",[]) if p.get("published")})))'); do
    local l; l=$(lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $1"("$2")"}' | sort -u | tr '\n' ' ')
    if [ -n "$l" ]; then say "  $p: IN USE by $l"; else say "  $p: free"; fi
  done
  say "-- other running containers and their memory (Docker total above)"
  local stats; stats=$(dock 30 docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' 2>/dev/null | grep -v "openelisglobal-\|external-fhir-api\|oe-certs\|autoheal-oe" || true)
  if [ -n "$stats" ]; then printf '%s\n' "$stats" | sed 's/^/  /'; else say "  none"; fi
  local engine_mem; engine_mem=$(dock 20 docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
  python3 -I - "$stats" "$engine_mem" <<'PY'
import re, sys
def gib(s):
    m = re.match(r"([\d.]+)([KMG]i?B)", s.strip())
    if not m: return 0.0
    v, u = float(m.group(1)), m.group(2)[0]
    return v / 1024 / 1024 if u == "K" else v / 1024 if u == "M" else v
used = total = 0.0
for ln in sys.argv[1].splitlines():
    parts = ln.split()
    if len(parts) >= 4 and parts[2] == "/":
        used += gib(parts[1]); total = gib(parts[3])
if total == 0.0:
    try: total = float(sys.argv[2]) / 1024 / 1024 / 1024
    except (IndexError, ValueError): total = 0.0
room = total - used
print(f"  other containers use {used:.1f} GiB of {total:.1f} GiB; room for the release stack (about 4 GiB): {'yes' if room >= 4.5 else 'NO, stop or free memory first'}")
PY
  say "-- disk"
  df -h / | awk 'NR==2{print "  free on /: "$4" ("$5" used)"}'
  dock 60 docker system df 2>/dev/null | sed 's/^/  /'
  say "-- tools: gh $(command -v gh >/dev/null && gh auth status >/dev/null 2>&1 && echo ok || echo 'absent or not logged in (GitHub API falls back to anonymous curl)')"
}

cmd_sync() {
  local dirty; dirty=$(git -C "$REPO" status --porcelain | grep -v '^?? release-reports/\|^?? release-test/\|^?? .claude/' || true)
  [ -z "$dirty" ] || { warn "working tree has local changes; not syncing (they are preserved):"; printf '%s\n' "$dirty"; return 2; }
  dock 60 git -C "$REPO" fetch upstream --tags >/dev/null 2>&1 || dock 60 git -C "$REPO" fetch origin --tags >/dev/null 2>&1 || die "fetch failed"
  local ref=upstream/main; git -C "$REPO" rev-parse -q --verify "$ref" >/dev/null 2>&1 || ref=origin/main
  if git -C "$REPO" merge --ff-only "$ref" >/dev/null 2>&1; then say "fast-forwarded to $ref ($(git -C "$REPO" rev-parse --short HEAD))"; else warn "cannot fast-forward to $ref (local commits diverge); left as is"; return 2; fi
}

cmd_init() {
  require_tools
  local existing; existing=$(run_id)
  if [ -n "$existing" ] && [ -f "$REPORTS/$existing/state.json" ] && [ "${1:-}" != "--new" ]; then
    local ph; ph=$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1])).get("phase",""))' "$REPORTS/$existing/state.json")
    case "$ph" in
      reported|torn-down) ;;
      *) say "run $existing is current (phase: $ph). Use 'rt.sh resume' to continue it, or 'rt.sh init --new' to start another."; return 2;;
    esac
  fi
  local id; id=$(date '+%Y-%m-%d-%H%M')
  local dir="$REPORTS/$id"
  mkdir -p "$dir"/{env,logs,db,backup,screenshots,ui} "$RUNS/$id/db-data"
  printf '%s' "$id" > "$CURRENT"
  local cfg; cfg=$(base_config_json) || die "docker compose config failed"
  printf '%s' "$cfg" > "$dir/env/compose-config-base.json"
  # Discover the services, the pinned images and the database data mount from the deployment itself.
  python3 -I - "$cfg" "$dir" "$RUNS/$id/db-data" "$PROJECT" "$REPO" "$id" "$(now)" <<'PY'
import json, sys
cfg, run_dir, db_data, project, repo, run_id, ts = sys.argv[1:8]
d = json.loads(cfg)
services = {}
pinned = []
db_service = app = fhir = frontend = proxy = None
app_repo = None
for name, s in d["services"].items():
    image = s.get("image", "")
    repo_name, _, tag = image.rpartition(":")
    env = s.get("environment") or {}
    envd = env if isinstance(env, dict) else {e.split("=",1)[0]: e.split("=",1)[1] if "=" in e else "" for e in env}
    if any(v.get("target") == "/var/lib/postgresql/data" for v in s.get("volumes", [])):
        db_service = name
    if "DEFAULT_PW" in envd and "datasource.url" in " ".join(f"{k}={v}" for k, v in envd.items()):
        app, app_repo = name, repo_name
    if any(k.startswith("FHIR_DATASOURCE") for k in envd):
        fhir = name
    if repo_name.endswith("-frontend"): frontend = name
    if repo_name.endswith("-proxy"): proxy = name
    if tag == "develop":
        pinned.append({"service": name, "repo": repo_name, "container_name": s.get("container_name", "")})
if not (db_service and app):
    sys.exit("could not identify the database and application services from the compose file")
lines = ["# Generated by rt.sh init for run %s. Pins every image the deployment publishes under" % run_id,
         "# the :develop tag (the same set build.sh and the release workflow pin) to OE_RT_TAG, and",
         "# puts the database on this run's own data directory. Nothing else is overridden.",
         "services:"]
for p in pinned:
    lines.append(f"  {p['service']}:")
    lines.append(f"    image: {p['repo']}:${{OE_RT_TAG:?set by rt.sh}}")
    if p["service"] == db_service:
        lines.append("    volumes:")
        lines.append("      - ${OE_RT_DB_DATA:?set by rt.sh}:/var/lib/postgresql/data")
if db_service not in [p["service"] for p in pinned]:
    lines += [f"  {db_service}:", "    volumes:", "      - ${OE_RT_DB_DATA:?set by rt.sh}:/var/lib/postgresql/data"]
open(f"{run_dir}/compose.override.yml", "w").write("\n".join(lines) + "\n")
state = {
    "run_id": run_id, "created_at": ts, "phase": "initialized", "project": project, "repo": repo,
    "db_data_dir": db_data, "override_file": f"{run_dir}/compose.override.yml",
    "release_tag": None, "develop_tag": "develop", "current_tag": None,
    "app_image_repo": app_repo, "pinned": pinned,
    "services": {"db": db_service, "app": app, "fhir": fhir, "frontend": frontend, "proxy": proxy},
    "backup": {"path": None, "verified": False}, "snapshots": [], "events": [],
}
json.dump(state, open(f"{run_dir}/state.json", "w"), indent=2, sort_keys=True)
print(f"run {run_id} initialised in {run_dir}")
print(f"  database data dir: {db_data}")
print(f"  services: db={db_service} app={app} fhir={fhir} frontend={frontend} proxy={proxy}")
print("  pinned images: " + ", ".join(p["repo"] for p in pinned))
PY
  state_log "run initialised"
}

cmd_resume() {
  local dir; dir=$(run_dir)
  say "run: $(run_id)  dir: $dir"
  python3 -I - "$dir/state.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for k in ("phase", "release_tag", "develop_tag", "current_tag", "db_data_dir", "upgrade_started_at"):
    print(f"  {k}: {d.get(k)}")
print(f"  backup: {d.get('backup')}")
print(f"  snapshots: {d.get('snapshots')}")
print("  last events:")
for e in d.get("events", [])[-8:]: print(f"    {e['at']} {e['msg']}")
PY
  local dd; dd=$(state_get db_data_dir)
  if [ -f "$dd/PG_VERSION" ]; then say "  db data dir: initialised (PG_VERSION $(cat "$dd/PG_VERSION"))"; else say "  db data dir: EMPTY (no database yet)"; fi
  say "  containers of project $PROJECT:"
  dock 20 docker ps -a --filter "label=com.docker.compose.project=$PROJECT" --format '    {{.Names}} {{.Image}} {{.Status}}' || true
  local ph; ph=$(state_get phase)
  say "  next safe step for phase '$ph':"
  case "$ph" in
    initialized) say "    rt.sh versions, then rt.sh pull <release> and rt.sh up <release>";;
    release-up) say "    create demonstration data, rt.sh snapshot before, baseline UI test";;
    demo-data|baseline-tested) say "    rt.sh backup (then rt.sh switch <develop>)";;
    backed-up) say "    rt.sh switch develop (the database must still hold the demonstration data)";;
    upgrading) say "    the upgrade was interrupted: read logs, rt.sh wait, rt.sh liquibase-verify; never re-run 'up <release>' on this database";;
    upgraded) say "    rt.sh liquibase-verify, rt.sh snapshot after, rt.sh compare before after, then the UI regression";;
    upgrade-failed) say "    diagnose from logs/ and db/; do not restart repeatedly; fix in the source (phase 10), rt.sh local-fix war <war>, rt.sh restore-run, rt.sh switch <develop>";;
    fixing) say "    deploy the fix (rt.sh local-fix ...); migration defect: rt.sh restore-run then switch/wait/liquibase-verify; otherwise re-run the failed checks";;
    integrity-checked|regression-tested) say "    write the report (rt.sh report-skeleton), then rt.sh teardown";;
    reported|torn-down) say "    finished; rt.sh init --new for another run";;
    *) say "    unknown phase";;
  esac
}

cmd_versions() {
  local dir; dir=$(run_dir)
  local latest
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    latest=$(dock 60 gh api "repos/$GITHUB_APP_REPO/releases/latest" --jq '[.tag_name, .published_at, .html_url, (.prerelease|tostring), (.draft|tostring)] | @tsv' 2>/dev/null)
    recent=$(dock 60 gh api "repos/$GITHUB_APP_REPO/releases?per_page=6" --jq '.[] | [.tag_name, .published_at, (if .prerelease then "prerelease" else "release" end), (if .draft then "draft" else "published" end)] | @tsv' 2>/dev/null)
  else
    latest=$(curl -s -m 30 "https://api.github.com/repos/$GITHUB_APP_REPO/releases/latest" | python3 -I -c 'import json,sys; d=json.load(sys.stdin); print("\t".join([d.get("tag_name",""), d.get("published_at",""), d.get("html_url",""), str(d.get("prerelease")), str(d.get("draft"))]))')
    recent=$(curl -s -m 30 "https://api.github.com/repos/$GITHUB_APP_REPO/releases?per_page=6" | python3 -I -c 'import json,sys; [print("\t".join([r.get("tag_name",""), r.get("published_at",""), "prerelease" if r.get("prerelease") else "release", "draft" if r.get("draft") else "published"])) for r in json.load(sys.stdin)]')
  fi
  local tag; tag=$(printf '%s' "$latest" | cut -f1)
  [ -n "$tag" ] || die "could not determine the latest release of $GITHUB_APP_REPO"
  say "latest official release of $GITHUB_APP_REPO: $tag ($(printf '%s' "$latest" | cut -f2))"
  if [ -n "${OE_RT_RELEASE_TAG:-}" ] && [ "$OE_RT_RELEASE_TAG" != "$tag" ]; then
    say "OE_RT_RELEASE_TAG=$OE_RT_RELEASE_TAG overrides the latest release (testing an upgrade from an older release); it is still checked on the registry below"
    tag=$OE_RT_RELEASE_TAG
  fi
  say "recent releases (GitHub 'latest' excludes prereleases and drafts):"; printf '%s\n' "$recent" | sed 's/^/  /'
  say "develop tag used by $BASE_COMPOSE: $(python3 -I -c 'import json,sys; print(", ".join(sorted({p["repo"]+":develop" for p in json.load(open(sys.argv[1]))["pinned"]})))' "$dir/state.json")"
  say "registry check (Docker Hub):"
  local ok=1 json="{"
  json="$json\"release_tag\": \"$tag\", \"develop_tag\": \"develop\", \"checked_at\": \"$(now)\", \"images\": {"
  local first=1
  for repo in $(python3 -I -c 'import json,sys; print(" ".join(p["repo"] for p in json.load(open(sys.argv[1]))["pinned"]))' "$dir/state.json"); do
    local r d
    r=$(hub_tag_info "$repo" "$tag"); d=$(hub_tag_info "$repo" develop)
    say "  $repo:$tag -> $r"
    say "  $repo:develop -> $d"
    case "$r" in MISSING*) ok=0;; esac
    [ $first = 1 ] || json="$json,"; first=0
    json="$json\"$repo\": {\"$tag\": \"$r\", \"develop\": \"$d\"}"
  done
  json="$json}}"
  printf '%s\n' "$json" > "$dir/env/versions.json"
  local dr; dr=$(dock 60 gh api "repos/$GITHUB_DOCKER_REPO/releases/tags/$tag" --jq '.tag_name + " " + .published_at' 2>/dev/null || true)
  say "openelis-docker release for $tag: ${dr:-none}"
  if [ $ok = 1 ]; then
    state_set release_tag "$tag"; state_log "versions: release $tag, develop tag develop, all release images on the registry"
  else
    state_log "versions: release $tag but at least one image tag is missing on the registry"; return 1
  fi
}

cmd_config() {
  local tag=${1:?tag}; local dir; dir=$(run_dir)
  compose "$tag" config > "$dir/env/compose-config-$tag.yml" || die "compose config invalid for $tag"
  compose "$tag" config --images | sort -u > "$dir/env/images-$tag.txt"
  say "config valid for $tag; images:"; sed 's/^/  /' "$dir/env/images-$tag.txt"
}

cmd_pull() {
  local tag=${1:?tag}; local dir; dir=$(run_dir)
  cmd_config "$tag" >/dev/null || exit 1
  state_log "pull $tag started"
  compose "$tag" pull 2>&1 | tail -20
  [ "${PIPESTATUS[0]}" = 0 ] || die "pull failed for $tag"
  for i in $(cat "$dir/env/images-$tag.txt"); do
    say "  $i -> $(docker image inspect "$i" --format '{{.Id}} {{join .RepoDigests ","}}' 2>/dev/null || echo 'NOT PRESENT')"
  done | tee "$dir/env/digests-$tag.txt"
  state_log "pull $tag finished"
}

wait_db() {
  local cap=${1:-300} t=0 c
  while [ $t -lt "$cap" ]; do
    c=$(cid db)
    if [ -n "$c" ] && docker exec "$c" pg_isready -h 127.0.0.1 -U clinlims -d clinlims -q 2>/dev/null \
       && docker exec "$c" psql -X -At -U clinlims -d clinlims -c 'select 1' >/dev/null 2>&1; then
      say "database ready after ${t}s"; return 0
    fi
    sleep 5; t=$((t+5))
  done
  warn "database not ready after ${cap}s"; return 4
}

cmd_up() {
  local tag=${1:?tag}; local dir; dir=$(run_dir)
  local rel dev ph dd; rel=$(state_get release_tag); dev=$(state_get develop_tag); ph=$(state_get phase); dd=$(state_get db_data_dir)
  [ -n "$rel" ] || die "run 'rt.sh versions' first (release tag unknown)"
  if [ "$tag" = "$dev" ] && [ ! -f "$dd/PG_VERSION" ]; then
    die "refusing: 'up $dev' on an empty database directory would be a fresh develop install, not an upgrade. Use 'rt.sh switch $dev' after the release database exists and is backed up."
  fi
  if [ "$tag" = "$dev" ] && [ "$ph" != "upgrading" ] && [ "$ph" != "upgraded" ]; then
    die "refusing: use 'rt.sh switch $dev' (it checks the backup and takes the pre-upgrade snapshot)"
  fi
  if [ "$tag" = "$rel" ]; then
    case "$ph" in upgrading|upgraded|upgrade-failed|integrity-checked|regression-tested|reported)
      [ "${OE_RT_ALLOW_DOWNGRADE:-}" = yes ] || die "refusing: the database has been migrated by $dev; starting $rel on it is a downgrade (set OE_RT_ALLOW_DOWNGRADE=yes only if you know why)";;
    esac
  fi
  cmd_config "$tag" >/dev/null || exit 1
  state_set current_tag "$tag"
  state_log "up $tag: starting certs + database first"
  compose "$tag" up -d "$(svc db)" || die "compose up (database) failed"
  wait_db 420 || die "database did not become ready; see: docker logs $(cid db)"
  state_log "up $tag: starting the remaining services"
  compose "$tag" up -d || die "compose up failed"
  [ "$tag" = "$rel" ] && [ "$ph" = initialized ] && state_set phase release-up
  say "started; now: rt.sh wait"
}

cmd_wait() {
  local cap=${1:-540} t=0 app dir; dir=$(run_dir); app=$(svc app)
  wait_db 120 || return 4
  local c started
  while [ $t -lt "$cap" ]; do
    c=$(cid app)
    if [ -z "$c" ]; then warn "application container not found"; return 4; fi
    started=$(docker inspect -f '{{.State.StartedAt}}' "$c")
    local log; log=$(docker logs --since "$started" "$c" 2>&1)
    if printf '%s' "$log" | grep -qE 'MigrationFailedException|ValidationFailedException|liquibase\.exception|Error creating bean with name .liquibase|Context \[[^]]*\] startup failed|Waiting for changelog lock'; then
      if printf '%s' "$log" | grep -qE 'MigrationFailedException|ValidationFailedException|Error creating bean with name .liquibase|startup failed'; then
        say "FATAL startup/migration error in the application log:"; printf '%s' "$log" | grep -nE 'MigrationFailedException|ValidationFailedException|liquibase\.exception|Error creating bean|startup failed|Reason:' | head -20
        state_log "wait: fatal startup error detected"; return 3
      fi
      printf '%s' "$log" | grep -c 'Waiting for changelog lock' | xargs -I{} say "changelog lock wait seen {} times (stale lock from a killed boot?)"
    fi
    if printf '%s' "$log" | grep -q 'Server startup in'; then
      local h hb f
      h=$(curl -sk -m 10 -o /tmp/oe-rt-health.$$ -w '%{http_code}' https://localhost/api/OpenELIS-Global/health 2>/dev/null); hb=$(cat /tmp/oe-rt-health.$$ 2>/dev/null); rm -f /tmp/oe-rt-health.$$
      f=$(curl -sk -m 10 -o /dev/null -w '%{http_code}' https://localhost/ 2>/dev/null)
      if [ "$h" = 200 ] && printf '%s' "$hb" | grep -q UP && [ "$f" = 200 ]; then
        local fh; fh=$(curl -sk -m 10 -o /dev/null -w '%{http_code}' http://localhost:8081/fhir/metadata 2>/dev/null)
        say "ready after ${t}s: health=$h ($hb) frontend=$f fhir-metadata=$fh"
        say "tomcat: $(printf '%s' "$log" | grep -o 'Server startup in .*' | tail -1)"
        state_log "wait: application healthy (health $h, frontend $f, fhir $fh)"; return 0
      fi
      say "tomcat up, health=$h frontend=$f (t=${t}s)"
    fi
    sleep 10; t=$((t+10))
  done
  warn "not ready after ${cap}s (exit 4 = call wait again; the log so far is in docker logs $(cid app))"; return 4
}

cmd_status() {
  local dir; dir=$(run_dir)
  say "run $(run_id) phase $(state_get phase) release=$(state_get release_tag) develop=$(state_get develop_tag) current=$(current_tag)"
  local lf; lf=$(state_get local_fix); [ -n "$lf" ] && [ "$lf" != "{}" ] && say "  local fix overrides: $lf"
  dock 30 docker ps -a --filter "label=com.docker.compose.project=$PROJECT" --format '  {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || true
  local c; c=$(cid db)
  [ -n "$c" ] && say "  db data mount: $(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Source}}{{end}}{{end}}' "$c")"
  [ -n "$c" ] && say "  databasechangelog rows: $(psql_in_db -c 'select count(*) from databasechangelog' 2>/dev/null || echo '?')"
}

cmd_verify_running() {
  local tag=${1:?tag}; local dir; dir=$(run_dir); local rc=0
  local out="$dir/env/running-$tag.txt"; : > "$out"
  while IFS="$TAB" read -r service repo; do
    local c; c=$(compose "$tag" ps -q "$service" 2>/dev/null | head -1)
    if [ -z "$c" ]; then say "  $service: NOT RUNNING" | tee -a "$out"; rc=1; continue; fi
    local cimg iid eid digests
    cimg=$(docker inspect -f '{{.Config.Image}}' "$c"); iid=$(docker inspect -f '{{.Image}}' "$c")
    eid=$(docker image inspect "$repo:$tag" -f '{{.Id}}' 2>/dev/null); digests=$(docker image inspect "$repo:$tag" -f '{{join .RepoDigests ","}}' 2>/dev/null)
    local hub; hub=$(python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["images"].get(sys.argv[2],{}).get(sys.argv[3],"").split(" ")[1] if " " in d["images"].get(sys.argv[2],{}).get(sys.argv[3],"") else "")' "$dir/env/versions.json" "$repo" "$tag" 2>/dev/null)
    local verdict=OK
    [ "$cimg" = "$repo:$tag" ] || verdict="WRONG IMAGE ($cimg)"
    [ "$iid" = "$eid" ] || verdict="$verdict; container image id != local $repo:$tag"
    if [ -n "$hub" ] && ! printf '%s' "$digests" | grep -q "$hub"; then verdict="$verdict; local digest not the registry digest $hub"; fi
    local mounts; mounts=$(docker inspect -f '{{range .Mounts}}{{.Destination}}<-{{.Source}} {{end}}' "$c" | tr ' ' '\n' | grep -E "^($WAR_IN_IMAGE|$HTML_IN_IMAGE)<-" | tr '\n' ' ')
    [ -n "$mounts" ] && verdict="$verdict + LOCAL FIX mounted: $mounts"
    say "  $service: $cimg id=${iid:7:12} digests=$digests -> $verdict" | tee -a "$out"
    case "$verdict" in OK*) ;; *) rc=1;; esac
  done < <(python3 -I -c 'import json,sys; [print(p["service"]+"\t"+p["repo"]) for p in json.load(open(sys.argv[1]))["pinned"]]' "$dir/state.json")
  local c; c=$(cid db)
  if [ -n "$c" ]; then
    local src; src=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Source}}{{end}}{{end}}' "$c")
    if [ "$src" = "$(state_get db_data_dir)" ]; then say "  database data dir: $src (this run's) OK" | tee -a "$out"; else say "  database data dir: $src is NOT this run's $(state_get db_data_dir)" | tee -a "$out"; rc=1; fi
  fi
  [ $rc = 0 ] && state_log "verify-running $tag: all pinned containers run $tag" || state_log "verify-running $tag: MISMATCH (see env/running-$tag.txt)"
  return $rc
}

cmd_logs() {
  local label=${1:?label}; local dir; dir=$(run_dir); local tag; tag=$(current_tag)
  for s in $(compose "$tag" config --services 2>/dev/null); do
    compose "$tag" logs --no-color --timestamps "$s" > "$dir/logs/$s-$label.log" 2>&1
    say "  logs/$s-$label.log ($(wc -l < "$dir/logs/$s-$label.log" | tr -d ' ') lines)"
  done
  state_log "logs saved with label $label"
}

cmd_psql() { psql_in_db -c "${1:?sql}"; }
cmd_sql_file() { psql_in_db -f /dev/stdin < "${1:?file}"; }

cmd_snapshot() {
  local label=${1:?label}; local dir; dir=$(run_dir); local c; c=$(cid db); [ -n "$c" ] || die "database container is not running"
  python3 -I "$HERE/db_snapshot.py" snapshot --psql "docker exec -i $c psql -X -At -v ON_ERROR_STOP=1 -U clinlims -d clinlims" --out "$dir/db/manifest-$label.json" --label "$label" || die "snapshot failed"
  psql_in_db -c "select id, author, filename, md5sum, exectype, orderexecuted, to_char(dateexecuted,'YYYY-MM-DD HH24:MI:SS'), coalesce(contexts,''), coalesce(labels,''), coalesce(deployment_id,'') from databasechangelog order by orderexecuted" > "$dir/db/databasechangelog-$label.tsv"
  say "  db/manifest-$label.json, db/databasechangelog-$label.tsv ($(wc -l < "$dir/db/databasechangelog-$label.tsv" | tr -d ' ') changelog rows)"
  python3 -I - "$(state_file)" "$label" <<'PY'
import json, sys
p, label = sys.argv[1:3]
d = json.load(open(p)); s = d.setdefault("snapshots", [])
label in s or s.append(label)
json.dump(d, open(p, "w"), indent=2, sort_keys=True)
PY
  state_log "snapshot $label taken"
}

cmd_compare() {
  local a=${1:?before} b=${2:?after}; local dir; dir=$(run_dir)
  python3 -I "$HERE/db_snapshot.py" compare "$dir/db/manifest-$a.json" "$dir/db/manifest-$b.json" --out "$dir/db/manifest-diff-$a-$b.md" || { state_log "compare $a $b: differences or failures found (db/manifest-diff-$a-$b.md)"; return 1; }
  state_log "compare $a $b: written to db/manifest-diff-$a-$b.md"
}

cmd_backup() {
  local dir; dir=$(run_dir); local c; c=$(cid db); [ -n "$c" ] || die "database container is not running"
  local tag ts f g; tag=$(current_tag); ts=$(date +%Y%m%d-%H%M%S); f="$dir/backup/clinlims-$tag-$ts.dump"; g="$dir/backup/globals-$tag-$ts.sql"
  state_log "backup started ($f)"
  docker exec "$c" pg_dump -U postgres -Fc clinlims > "$f" || die "pg_dump failed"
  docker exec "$c" pg_dumpall -U postgres --globals-only > "$g" || die "pg_dumpall --globals-only failed"
  [ -s "$f" ] || die "backup file is empty"
  say "  $f ($(du -h "$f" | cut -f1)) sha256 $(shasum -a 256 "$f" | cut -c1-16)"
  say "  $g ($(du -h "$g" | cut -f1))"
  state_set backup.path "$f"; state_set backup.globals "$g"; state_set backup.verified false
  cmd_verify_backup
}

cmd_verify_backup() {
  local dir; dir=$(run_dir); local c; c=$(cid db); local f; f=$(state_get backup.path)
  [ -s "$f" ] || die "no backup file recorded"
  local scratch=clinlims_rt_check
  docker cp "$f" "$c:/tmp/rt-check.dump" || die "docker cp failed"
  local entries; entries=$(docker exec "$c" pg_restore -l /tmp/rt-check.dump | grep -c '^[0-9]')
  say "  pg_restore --list: $entries archive entries"
  docker exec "$c" psql -X -U postgres -c "drop database if exists $scratch" >/dev/null
  docker exec "$c" psql -X -U postgres -c "create database $scratch" >/dev/null || die "could not create the scratch database"
  docker exec "$c" pg_restore -U postgres -d "$scratch" --no-owner --no-privileges --exit-on-error /tmp/rt-check.dump > "$dir/backup/restore-check.log" 2>&1
  local rc=$?
  local live scr
  live=$(docker exec "$c" psql -X -At -U postgres -d clinlims -c "select (select count(*) from information_schema.tables where table_schema='clinlims')||' tables, '||(select count(*) from clinlims.patient)||' patients, '||(select count(*) from clinlims.sample)||' samples, '||(select count(*) from clinlims.databasechangelog)||' changesets'")
  scr=$(docker exec "$c" psql -X -At -U postgres -d "$scratch" -c "select (select count(*) from information_schema.tables where table_schema='clinlims')||' tables, '||(select count(*) from clinlims.patient)||' patients, '||(select count(*) from clinlims.sample)||' samples, '||(select count(*) from clinlims.databasechangelog)||' changesets'" 2>/dev/null)
  docker exec "$c" psql -X -U postgres -c "drop database if exists $scratch" >/dev/null
  docker exec "$c" rm -f /tmp/rt-check.dump
  say "  live:     $live"; say "  restored: $scr (pg_restore exit $rc)"
  { say "verified at $(now)"; say "file: $f"; say "archive entries: $entries"; say "live: $live"; say "restored: $scr"; say "pg_restore exit: $rc"; } > "$dir/backup/restore-check.txt"
  if [ $rc = 0 ] && [ "$live" = "$scr" ]; then
    state_set backup.verified true; state_set backup.verified_at "$(now)"
    local ph; ph=$(state_get phase); case "$ph" in release-up|demo-data|baseline-tested) state_set phase backed-up;; esac
    state_log "backup verified: restore into $scratch matched the live counts"
  else
    state_log "backup verification FAILED (exit $rc, counts differ); see backup/restore-check.log"; return 1
  fi
}

cmd_switch() {
  local tag=${1:?tag}; local dir; dir=$(run_dir)
  local dev dd; dev=$(state_get develop_tag); dd=$(state_get db_data_dir)
  [ "$tag" = "$dev" ] || warn "switching to '$tag', which is not the recorded develop tag '$dev'"
  [ "$(state_get backup.verified)" = True ] || [ "$(state_get backup.verified)" = true ] || die "refusing: no verified backup (rt.sh backup first)"
  [ -f "$dd/PG_VERSION" ] || die "refusing: the database directory is empty; nothing to upgrade"
  [ -f "$dir/db/manifest-before.json" ] || die "refusing: no 'before' snapshot (rt.sh snapshot before)"
  cmd_config "$tag" >/dev/null || exit 1
  local old; old=$(current_tag)
  state_log "switch $old -> $tag: recording the running images"
  cmd_verify_running "$old" >/dev/null 2>&1 || warn "pre-switch verification of $old had mismatches (see env/running-$old.txt)"
  state_set phase upgrading; state_set current_tag "$tag"
  state_log "switch: recreating the database container with the $tag image on the same data directory"
  compose "$tag" up -d --no-deps "$(svc db)" || die "compose up (database) failed"
  wait_db 420 || die "database not ready after the image switch; see docker logs"
  local src; src=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Source}}{{end}}{{end}}' "$(cid db)")
  [ "$src" = "$dd" ] || die "the new database container mounts $src, not $dd"
  cmd_snapshot pre-upgrade || die "pre-upgrade snapshot failed"
  python3 -I "$HERE/db_snapshot.py" compare "$dir/db/manifest-before.json" "$dir/db/manifest-pre-upgrade.json" --out "$dir/db/manifest-diff-before-pre-upgrade.md" >/dev/null 2>&1 \
    && say "  demonstration data present before the migration (before == pre-upgrade)" \
    || warn "before and pre-upgrade snapshots differ: read db/manifest-diff-before-pre-upgrade.md before continuing"
  state_set upgrade_started_at "$(psql_in_db -c "select to_char(now(),'YYYY-MM-DD HH24:MI:SS')")"
  state_log "switch: starting the $tag application against the existing database (migration begins now)"
  compose "$tag" up -d || die "compose up failed"
  say "started; now: rt.sh wait 540 (repeat while it exits 4), then rt.sh logs develop-boot and rt.sh liquibase-verify"
}

extract_changelogs() {
  # extract_changelogs <image> <dest-dir>  -> prints the directory holding liquibase/
  local image=$1 dest=$2
  mkdir -p "$dest"
  local c; c=$(docker create "$image" 2>/dev/null) || { warn "docker create $image failed (pulled?)"; return 1; }
  local war="/usr/local/tomcat/webapps/OpenELIS-Global.war"
  if ! docker cp "$c:$war" "$dest/app.war" 2>/dev/null; then
    war=$(docker run --rm --entrypoint sh "$image" -c 'ls /usr/local/tomcat/webapps/*.war 2>/dev/null | grep -v ROOT | head -1')
    docker cp "$c:$war" "$dest/app.war" || { docker rm "$c" >/dev/null; return 1; }
  fi
  docker rm "$c" >/dev/null
  unzip -q -o "$dest/app.war" 'WEB-INF/classes/liquibase/*' -d "$dest" || return 1
  rm -f "$dest/app.war"
  printf '%s' "$dest/WEB-INF/classes"
}

extract_changelogs_from_war() {
  # extract_changelogs_from_war <war file> <dest-dir> -> prints the directory holding liquibase/
  local war=$1 dest=$2
  mkdir -p "$dest"
  unzip -q -o "$war" 'WEB-INF/classes/liquibase/*' -d "$dest" || return 1
  printf '%s' "$dest/WEB-INF/classes"
}

# ---------- fix loop: local artefacts into the same stack ----------
local_fix_py() {
  # local_fix_py <action> [args...]: mutate state.local_fix and render compose.local-fix.yml
  python3 -I - "$(state_file)" "$(override_file | sed 's/compose.override.yml$/compose.local-fix.yml/')" "$WAR_IN_IMAGE" "$HTML_IN_IMAGE" "$@" <<'PY'
import json, sys
state_p, out_p, war_in, html_in, action, *args = sys.argv[1:]
d = json.load(open(state_p))
lf = d.get("local_fix") or {}
svcs = d["services"]
if action == "war":
    lf["war"], lf["war_sha256"], lf["war_commit"], lf["war_built"] = args[0], args[1], args[2], args[3]
elif action == "frontend":
    lf["frontend_dir"], lf["frontend_commit"] = args[0], args[1]
elif action == "image":
    lf.setdefault("images", {})[args[0]] = args[1]
elif action == "clear":
    lf = {}
d["local_fix"] = lf
json.dump(d, open(state_p, "w"), indent=2, sort_keys=True)
lines = ["# Local fix overrides generated by rt.sh local-fix. Mounted or substituted artefacts built",
         "# from the application source; the published image tags stay as the run override pins them.",
         "services:"]
per = {}
if lf.get("war"):
    per.setdefault(svcs["app"], {}).setdefault("volumes", []).append(f"{lf['war']}:{war_in}")
if lf.get("frontend_dir") and svcs.get("frontend"):
    per.setdefault(svcs["frontend"], {}).setdefault("volumes", []).append(f"{lf['frontend_dir']}:{html_in}:ro")
for s, img in (lf.get("images") or {}).items():
    per.setdefault(s, {})["image"] = img
for s, spec in per.items():
    lines.append(f"  {s}:")
    if "image" in spec:
        lines.append(f"    image: {spec['image']}")
    if spec.get("volumes"):
        lines.append("    volumes:")
        for v in spec["volumes"]:
            lines.append(f"      - {v}")
if per:
    open(out_p, "w").write("\n".join(lines) + "\n")
    print("affected services: " + " ".join(per))
else:
    import os
    if os.path.exists(out_p): os.remove(out_p)
    print("no local fix overrides")
PY
}

cmd_local_fix() {
  local dir; dir=$(run_dir); local sub=${1:-show}; [ $# -gt 0 ] && shift
  local tag; tag=$(current_tag)
  case "$sub" in
    war)
      local w; w=$(cd "$(dirname "${1:?path to the WAR}")" && pwd)/$(basename "$1"); [ -f "$w" ] || die "no such WAR: $w"
      local top sha="unknown"; top=$(git -C "$(dirname "$w")" rev-parse --show-toplevel 2>/dev/null || true)
      [ -n "$top" ] && sha="$(git -C "$top" rev-parse --short HEAD)-$([ -n "$(git -C "$top" status --porcelain)" ] && echo dirty || echo clean)"
      local affected; affected=$(local_fix_py war "$w" "$(shasum -a 256 "$w" | cut -c1-16)" "$sha" "$(stat -f '%Sm' "$w")")
      state_log "local-fix: WAR $w (sha $(state_get local_fix.war_sha256), commit $sha) mounted over $WAR_IN_IMAGE in $(svc app)"
      compose "$tag" up -d --force-recreate --no-deps "$(svc app)" || die "could not recreate $(svc app)"
      say "webapp recreated with the local WAR; now: rt.sh wait (or rt.sh restore-run first for a migration retry)";;
    frontend)
      local f; f=$(cd "${1:?front-end build dir}" && pwd); [ -f "$f/index.html" ] || die "$f has no index.html (run the front-end build first)"
      local top sha="unknown"; top=$(git -C "$f" rev-parse --show-toplevel 2>/dev/null || true)
      [ -n "$top" ] && sha="$(git -C "$top" rev-parse --short HEAD)-$([ -n "$(git -C "$top" status --porcelain)" ] && echo dirty || echo clean)"
      local_fix_py frontend "$f" "$sha" >/dev/null
      state_log "local-fix: front-end build $f (commit $sha) mounted over $HTML_IN_IMAGE in $(svc frontend)"
      compose "$tag" up -d --force-recreate --no-deps "$(svc frontend)" || die "could not recreate $(svc frontend)";;
    image)
      local s=${1:?service} i=${2:?image:tag}
      docker image inspect "$i" >/dev/null 2>&1 || die "image $i is not present locally (build it first)"
      local_fix_py image "$s" "$i" >/dev/null
      state_log "local-fix: service $s runs local image $i ($(docker image inspect "$i" -f '{{.Id}}' | cut -c8-19))"
      compose "$tag" up -d --force-recreate --no-deps "$s" || die "could not recreate $s";;
    clear)
      local affected; affected=$(state_get local_fix)
      local_fix_py clear >/dev/null
      state_log "local-fix cleared (was: $affected); services recreated from the images"
      compose "$tag" up -d || die "compose up failed";;
    show)
      cat "$dir/compose.local-fix.yml" 2>/dev/null || say "no local fix overrides"
      say "state.local_fix: $(state_get local_fix)";;
    *) die "local-fix: war <path> | frontend <dir> | image <service> <image> | show | clear";;
  esac
}

cmd_restore_run() {
  local dir; dir=$(run_dir); local rel; rel=$(state_get release_tag); local f; f=$(state_get backup.path)
  case "$(state_get backup.verified)" in True|true) ;; *) die "refusing: no verified backup to restore from";; esac
  [ -s "$f" ] || die "backup file missing: $f"
  local prev n; prev=$(state_get restore_attempts); n=$(( ${prev:-0} + 1 ))
  mkdir -p "$dir/db/attempt-$n" "$dir/logs/attempt-$n"
  cp "$dir"/db/manifest-pre-upgrade.json "$dir"/db/manifest-after*.json "$dir"/db/databasechangelog-pre-upgrade.tsv "$dir"/db/databasechangelog-after-upgrade.tsv "$dir"/db/liquibase-verdict.* "$dir"/db/manifest-diff-*.md "$dir/db/attempt-$n/" 2>/dev/null
  cp "$dir"/logs/*-develop-boot.log "$dir/logs/attempt-$n/" 2>/dev/null
  state_log "restore-run: attempt $n; the previous attempt's evidence is copied to db/attempt-$n and logs/attempt-$n"
  compose "$(current_tag)" stop >/dev/null 2>&1
  local old new; old=$(state_get db_data_dir); new="$RUNS/$(run_id)/db-data-retry-$n"; mkdir -p "$new"
  python3 -I - "$(state_file)" "$old" <<'PY'
import json, sys
p, old = sys.argv[1:3]
d = json.load(open(p)); d.setdefault("db_data_dir_history", []).append(old)
json.dump(d, open(p, "w"), indent=2, sort_keys=True)
PY
  state_set db_data_dir "$new"; state_set restore_attempts "$n"; state_set current_tag "$rel"; state_set upgrade_started_at ""; state_set phase backed-up
  state_log "restore-run: previous database directory kept at $old (migrated state, evidence); new directory $new"
  compose "$rel" up -d --no-deps "$(svc db)" || die "could not start the $rel database image on $new"
  wait_db 420 || die "database not ready on the new directory"
  local c; c=$(cid db)
  docker cp "$f" "$c:/tmp/rt-restore.dump" || die "docker cp failed"
  docker exec "$c" psql -X -U postgres -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='clinlims' and pid<>pg_backend_pid()" >/dev/null
  docker exec "$c" dropdb -U postgres --if-exists clinlims || die "dropdb failed"
  docker exec "$c" createdb -U postgres -O clinlims clinlims || die "createdb failed"
  docker exec "$c" pg_restore -U postgres -d clinlims --exit-on-error /tmp/rt-restore.dump > "$dir/backup/restore-attempt-$n.log" 2>&1 || die "pg_restore failed; see backup/restore-attempt-$n.log"
  docker exec "$c" rm -f /tmp/rt-restore.dump
  cmd_snapshot "before-retry$n" || die "snapshot after restore failed"
  if python3 -I "$HERE/db_snapshot.py" compare "$dir/db/manifest-before.json" "$dir/db/manifest-before-retry$n.json" --out "$dir/db/manifest-diff-before-before-retry$n.md" >/dev/null 2>&1; then
    state_log "restore-run: restored database matches the 'before' manifest"
  else
    warn "restored database differs from the 'before' manifest: read db/manifest-diff-before-before-retry$n.md before continuing"
  fi
  say "release database restored on $new with the $rel database image. Next: rt.sh switch $(state_get develop_tag) (the local fix, if any, is still mounted), rt.sh wait, rt.sh logs develop-boot-retry$n, rt.sh liquibase-verify"
}

cmd_start() { compose "$(current_tag)" start; state_log "stack started"; }

cmd_liquibase_verify() {
  local dir; dir=$(run_dir)
  local repo rel dev; repo=$(state_get app_image_repo); rel=$(state_get release_tag); dev=$(current_tag)
  [ -f "$dir/db/databasechangelog-pre-upgrade.tsv" ] || [ -f "$dir/db/databasechangelog-before.tsv" ] || die "no pre-upgrade changelog export"
  local before="$dir/db/databasechangelog-pre-upgrade.tsv"; [ -f "$before" ] || before="$dir/db/databasechangelog-before.tsv"
  say "exporting DATABASECHANGELOG after the upgrade"
  psql_in_db -c "select id, author, filename, md5sum, exectype, orderexecuted, to_char(dateexecuted,'YYYY-MM-DD HH24:MI:SS'), coalesce(contexts,''), coalesce(labels,''), coalesce(deployment_id,'') from databasechangelog order by orderexecuted" > "$dir/db/databasechangelog-after-upgrade.tsv" || die "changelog export failed"
  psql_in_db -c "select id, locked, coalesce(to_char(lockgranted,'YYYY-MM-DD HH24:MI:SS'),''), coalesce(lockedby,'') from databasechangeloglock" > "$dir/db/databasechangeloglock-after-upgrade.tsv"
  local oldroot newroot lwar; lwar=$(state_get local_fix.war)
  say "extracting the changelog tree from $repo:$rel"
  oldroot=$(extract_changelogs "$repo:$rel" "$dir/db/changelogs-$rel") || die "could not extract changelogs from $repo:$rel"
  if [ -n "$lwar" ] && [ -f "$lwar" ]; then
    say "a local WAR is deployed: expected set taken from $lwar (commit $(state_get local_fix.war_commit)), not from $repo:$dev"
    rm -rf "$dir/db/changelogs-local-war"; newroot=$(extract_changelogs_from_war "$lwar" "$dir/db/changelogs-local-war") || die "could not extract changelogs from $lwar"
    state_log "liquibase-verify: expected changesets from the local WAR $lwar"
  else
    say "extracting the changelog tree from $repo:$dev"
    newroot=$(extract_changelogs "$repo:$dev" "$dir/db/changelogs-$dev") || die "could not extract changelogs from $repo:$dev"
  fi
  local applog; applog=$(ls -t "$dir"/logs/"$(svc app)"-*.log 2>/dev/null | head -1)
  python3 -I "$HERE/liquibase_expected.py" \
    --old-root "$oldroot" --new-root "$newroot" \
    --before "$before" --after "$dir/db/databasechangelog-after-upgrade.tsv" \
    --lock "$dir/db/databasechangeloglock-after-upgrade.tsv" \
    --contexts "${OE_RT_LIQUIBASE_CONTEXTS:-default}" \
    ${applog:+--log "$applog"} \
    --upgrade-started "$(state_get upgrade_started_at)" \
    --out-json "$dir/db/liquibase-verdict.json" --out-md "$dir/db/liquibase-verdict.md"
  local rc=$?
  say "verdict written to db/liquibase-verdict.md (exit $rc; 0 = YES, 2 = NO, 3 = INCONCLUSIVE)"
  case $rc in 0) state_set phase upgraded; state_log "liquibase-verify: YES";; 2) state_set phase upgrade-failed; state_log "liquibase-verify: NO";; *) state_log "liquibase-verify: INCONCLUSIVE";; esac
  return $rc
}

cmd_creds() {
  local tag; tag=$(current_tag)
  local pw; pw=$(compose "$tag" config --format json 2>/dev/null | python3 -I -c 'import json,sys; d=json.load(sys.stdin); s=d["services"][sys.argv[1]]; e=s.get("environment") or {}; print((e.get("DEFAULT_PW") if isinstance(e,dict) else next((x.split("=",1)[1] for x in e if x.startswith("DEFAULT_PW=")),"")) or "")' "$(svc app)")
  say "login name: admin (the seeded administrator)"
  say "password: ${pw:-<DEFAULT_PW not set in the compose file>}  (from DEFAULT_PW in docker-compose.yml; if the UI forces a change on first login, record the new one with: rt.sh state set ui.admin_password <value>)"
  local changed; changed=$(state_get ui.admin_password); [ -n "$changed" ] && say "password changed during this run to: $changed"
  say "url: https://localhost/"
}

cmd_screenshots() {
  local src=${1:?dir}; local dir; dir=$(run_dir); local n=0
  local ref="$dir/compose.override.yml"; [ -f "$ref" ] || ref="$dir/state.json"
  while IFS= read -r f; do cp "$f" "$dir/screenshots/" && n=$((n+1)); done < <(find "$src" -maxdepth 2 -type f \( -name '*.png' -o -name '*.jpeg' -o -name '*.jpg' \) -newer "$ref" 2>/dev/null)
  say "copied $n screenshots into $dir/screenshots/"
}

cmd_report_skeleton() {
  local dir; dir=$(run_dir); local id; id=$(run_id)
  local out="$REPORTS/openelis-release-readiness-$id.md"
  [ -f "$out" ] && { say "$out exists; not overwriting"; return 0; }
  python3 -I - "$HERE/../references/report-template.md" "$out" "$dir/state.json" "$REPO" "$(git -C "$REPO" branch --show-current)" "$(git -C "$REPO" rev-parse HEAD)" "$(now)" <<'PY'
import json, sys
tpl, out, state_p, repo, branch, commit, ts = sys.argv[1:8]
s = json.load(open(state_p))
t = open(tpl).read()
subs = {"{{RUN_ID}}": s["run_id"], "{{DATE}}": ts, "{{RELEASE_TAG}}": str(s.get("release_tag")), "{{DEVELOP_TAG}}": str(s.get("develop_tag")),
        "{{REPO}}": repo, "{{BRANCH}}": branch, "{{COMMIT}}": commit, "{{BACKUP}}": str((s.get("backup") or {}).get("path")),
        "{{BACKUP_VERIFIED}}": str((s.get("backup") or {}).get("verified")), "{{DB_DATA_DIR}}": s.get("db_data_dir", ""),
        "{{IMAGES}}": "\n".join(f"- {p['repo']}:{s.get('release_tag')} -> {p['repo']}:{s.get('develop_tag')}" for p in s.get("pinned", []))}
for k, v in subs.items(): t = t.replace(k, v)
open(out, "w").write(t)
print(out)
PY
  state_log "report skeleton written: $out"
}

cmd_state() {
  case "${1:-}" in
    get) state_get "${2:?key}";;
    set) state_set "${2:?key}" "${3:?value}"; say "set $2";;
    log) shift; state_log "$*";;
    *) cat "$(state_file)";;
  esac
}

cmd_stop() { compose "$(current_tag)" stop; state_log "stack stopped (containers kept)"; }

cmd_teardown() {
  local dir; dir=$(run_dir); local tag; tag=$(current_tag)
  if [ "${1:-}" = "--volumes" ]; then
    [ "${OE_RT_CONFIRM_VOLUMES:-}" = yes ] || die "refusing --volumes without OE_RT_CONFIRM_VOLUMES=yes (named volumes hold the keystores and lucene index; the database directory $(state_get db_data_dir) is never deleted by this script)"
    compose "$tag" down --volumes --remove-orphans; state_log "teardown with named volumes removed"
  else
    compose "$tag" down --remove-orphans; state_log "teardown: containers and network removed, named volumes and the database directory kept"
  fi
  state_set phase torn-down
  say "database directory kept at $(state_get db_data_dir); backup at $(state_get backup.path)"
}

# Every subcommand except these needs a current run with a state file.
case "${1:-help}" in
  help|-h|--help|preflight|sync|init) ;;
  *) { [ -n "$(run_id)" ] && [ -f "$REPORTS/$(run_id)/state.json" ]; } || die "no current run; start with: rt.sh init (or rt.sh preflight first)";;
esac

case "${1:-help}" in
  help|-h|--help) cmd_help;;
  preflight) cmd_preflight;;
  sync) cmd_sync;;
  init) shift; cmd_init "$@";;
  resume) cmd_resume;;
  versions) cmd_versions;;
  config) shift; cmd_config "$@";;
  pull) shift; cmd_pull "$@";;
  up) shift; cmd_up "$@";;
  wait) shift; cmd_wait "$@";;
  status) cmd_status;;
  verify-running) shift; cmd_verify_running "$@";;
  logs) shift; cmd_logs "$@";;
  psql) shift; cmd_psql "$@";;
  sql-file) shift; cmd_sql_file "$@";;
  snapshot) shift; cmd_snapshot "$@";;
  compare) shift; cmd_compare "$@";;
  backup) cmd_backup;;
  verify-backup) cmd_verify_backup;;
  switch) shift; cmd_switch "$@";;
  liquibase-verify) cmd_liquibase_verify;;
  creds) cmd_creds;;
  screenshots) shift; cmd_screenshots "$@";;
  report-skeleton) cmd_report_skeleton;;
  state) shift; cmd_state "$@";;
  stop) cmd_stop;;
  start) cmd_start;;
  local-fix) shift; cmd_local_fix "$@";;
  restore-run) cmd_restore_run;;
  teardown) shift; cmd_teardown "$@";;
  *) die "unknown subcommand $1 (rt.sh help)";;
esac
