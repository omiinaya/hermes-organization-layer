# SonarQube Deployment + CI Integration Plan

**Goal:** Deploy SonarQube (community-script CT) and wire inline SonarQube analysis into the spacetime-× repos + recently-worked repos' GitHub Actions CI.

**Scope (locked with Omar):** spacetime-× set + recently-worked repos; inline SonarQube job per repo's existing workflow.

---

## Phase 1 — Deploy SonarQube server (community script) — DONE 09-13
- [x] Run `ct/sonarqube.sh` headless → **CT 104** (script chose 104), static **192.168.1.130/24**, gw .1, storage **Intel**, template **local**, Debian 13, 4 core/8GB/25GB. (`var_net=192.168.1.130/24`, live http OK)
- [x] Verify: `http://192.168.1.130:9000/` → **200**, service `sonarqube` active, java on :9000, `/api/system/status` **UP** (v26.9.0.129388).
- [x] Bootstrap admin: rotated default `admin/admin` → strong pw (vault `sonarqube-admin` `vault_1df6…`, shadowed /root/.sonar-admin-pw.tmp). Old admin:admin invalid.
- [x] Mint CI token `ci-analysis` `squ_0380…` (vault `sonarqube-ci-token` `vault_f675…`, shadowed /root/.sonar-ci-token.tmp).
- [ ] Verify CT 103 (github-runner) can reach :9000.

## Phase 2 — Enumerate target repos + CI workflows
- [ ] spacetime-× set: spacetime-ab, -air, -api, -cars, -crm, -drivers, -hardware-test, -jobs, -kanban, -llm, -memory, -mods, -rpm, -swarm, -tv, -wiki, -browser, -code(-plugins).
- [ ] Recently-worked (pushed 2026-09): filmforge, matrix-arrow, hermes-host-sentinel, hermes-matrix-rooms, team-gen, hermes-proxy-relay, legiontd2-overlay, hermes-thin-client, hermes-browser-relay, tor-pool, spacetime-llm, auto-fcc.
- [ ] For each: identify the primary build/test workflow + language/toolchain (for sonar-scanner/analyzer choice).

## Phase 3 — Wire inline SonarQube job per repo — IN PROGRESS
- [x] Built reusable workflow `somarqube.yml` in hermes-organization-layer (self-hosted `pve-scripts`, target `http://192.168.1.130:9000`, sonar-scanner CLI 6.2.1, JDK 21). Committed+pushed `ead94a7`.
- [x] Runner CT 103: installed `default-jre-headless` → OpenJDK 21 (sonar-scanner needs Java).
- [x] `spacetime-llm` — reusable-workflow call in `ci.yml` (job `sonarqube`), `SONAR_TOKEN` secret set, **E2E run 34801540640 queued/running**.
- [x] `spacetime-rpm` — inline job in `ci.yml`, YAML valid, secret set, committed+pushed `19ebca8`.
- [ ] Verify SonarQube shows analysis for spacetime-llm (+ rpm) after runs complete.
## Phase 3b — Public spacetime-× on local runners + Sonar (COMPLETE 09-14)
- [x] Privacy pivot: user chose to make the 6 public spacetime-× repos private + run CI on local self-hosted runners so the LAN SonarQube is reachable.
- [x] **Self-hosted runner per repo** registered on CT 103 (ab, crm, kanban, memory, tv, wiki) — all 6 **online**. Method: **fresh runner tarball** (NOT a copy of an already-registered dir — copies keep stale config and `config.sh` refuses "already configured"; the first script failed this exact way), `config.sh --unattended` + fresh registration token, copy `runsvc.sh` (unattended doesn't generate it), systemd unit per repo. Registration well: `/root/hermes-org/family/scripts/register-runner.sh`.
- [x] `SONAR_TOKEN` secret set on all 6.
- [x] Inline SonarQube job appended to each primary workflow (`ci.yml`/`test.yml`), self-hosted `pve-scripts`.
- [x] **Docker scanner** (`sonarsource/sonar-scanner-cli:latest`) instead of zip download — the `binaries.sonarsource.com` zip is **deterministically corrupt** on our runner (5/5 retries bad at `jre/lib/modules` / `libjvm.so`); Docker image pulls intact.
- [x] Dropped `sonar.branch.name` — Community Build has **no branch analysis** (paid Developer feature); single-branch (master) analysis works free.
- [x] Fixed tv `ci.yml` pre-existing parse-killer: `secrets.*` in a **job-level `if:`** (invalid → whole workflow never parsed). Moved to step guard.
- [x] **E2E PROVEN: all 6 projects landed on :9000** — spacetime-ab, -crm, -kanban, -memory, -tv, -wiki (verified via `/api/projects/search`).

### Gaps found & fixed (Sonar = part of every CI)
- Corrupt scanner zip (deterministic) → Docker image.
- `sonar.branch.name` unsupported on Community → removed (branch analysis = paid upgrade).
- tv job-level `secrets` `if` killed workflow parse → fixed.

## Phase 4 — Verify
- [ ] Run one representative workflow (e.g. spacetime-llm or hermes-organization-layer) → analysis reported on SonarQube :9000.
- [ ] Spot-check 2-3 more repos.
- [ ] Report quality results, token/perf notes.

## Phase 5 — Docs + ops (doctrine)
- [ ] Update pve-scripts-local skill: CT 130 sonarqube deployed, :9000, IP, how to re-run/update.
- [ ] Operator profile note (infra/sonarqube) once stable.