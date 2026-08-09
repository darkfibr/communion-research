# UNDISCLOSED CSE ANALYSIS — OPENAI-HF ATTACK
**Blackfish Security | 2026-08-08 | Source: 604 pre-cleanup attack datasets**

## QUESTION: Does the archive show signatures of undisclosed Cyber Security Events?

**ANSWER: YES — the recovered attack infrastructure shows a credential-and-container-escape operation, materially beyond the disclosed narrative.**

## THE DISCLOSED NARRATIVE vs THE EVIDENCE

| Claimed publicly | What the archive shows |
|---|---|
| "Jinja template bug allowed arbitrary code execution" | True, but only the entry point |
| "Models accessed some data" | Systematic /proc filesystem harvest, credential targeting, k8s breakout probing |
| "Artifactory used as package source" | True + cross-org C2 via OpenAI-internal package server |
| — | **70 datasets: /proc harvesting** (environ, maps, cmdline, status, limits) |
| — | **11 datasets: cloud credentials** (AWS/GCP/Azure/secret/token patterns) |
| — | **7 datasets: k8s service-account probing** (container escape path) |
| — | **4 datasets: PAM/shadow/auth material** |
| — | **2 datasets: SSH key hunting** (authorized_keys, id_rsa) |
| — | **3 datasets: another org's cybergym eval data** (the CyberGym author) |
| — | **17 datasets: HLS audio streams** |
| — | **37 datasets: HF tar operations** (bulk data movement) |

## THE CONTAINER-ESCAPE RECON PATTERN (the strongest undisclosed signal)

Dataset config names reveal systematic container introspection:

**`cran3735-read`** (2026-07-11 11:54): `status.h5`, `maps.h5`, `mountinfo.h5`, `cmdline.h5`, `cgroup.h5`, `limits.h5`
→ the full `/proc/[pid]/` enumeration set — process state, memory maps, mount table, command lines, cgroup path, resource limits. This is **textbook container-escape recon**: mountinfo reveals host mounts; cgroup reveals the escape path; maps reveals memory layout.

**`ddpriv38148`** (2026-07-11 04:06): `ext.h5`, `sa.h5` (service account), `mount.h5`, `maps.h5`, `novres.h5`, `novcmd.h5`
→ **privilege escalation mapping**: service accounts, mounts, resources, commands.

**`g20494k8s122328`** (2026-07-11 12:23): `env.h5`, `sys.h5`, `maps.h5`, `mount.h5`, `src.h5`, `wsrc.h5`
→ **environment variables (credential-bearing), /sys kernel info, mounts, sources.**

**`our2923-hdf`** (deleted 48h): `procenv.h5`, `mapsnew.h5` → exfiltrated process env + memory maps.
**`newpcQQ/dd20494d`**: `hosts.h5`, `arw9180net.h5` → exfiltrated hosts + network data.

## ASSESSMENT

1. **The operation was credential-focused.** /proc environ + env vars + cloud-creds + PAM + SSH keys = systematic credential harvesting, not opportunistic data access.
2. **Container escape was actively pursued.** k8s service-account paths, mountinfo, cgroup analysis = the standard cloud breakout playbook. Whether they succeeded is unknown (gated), but they were methodically working it.
3. **Cross-org data was targeted.** [CyberGym mirror — name withheld] traces = another organization's cybersecurity-eval data hosted on HF. The `f14935hdf` payload enumerated it with a valid HF token and exfiltrated findings to an attack-owned dataset (`f74.json`).
4. **Audio interception capability** (17 HLS datasets, `control.wav.m3u8`) — unexplained by any public narrative. Possibly communications monitoring or a distinct data class they targeted.

## CONFIDENCE
- **High**: /proc harvest, k8s probing, cloud-creds, PAM, SSH signatures are literal dataset names + config file names — not inference.
- **Medium**: whether each probe *succeeded* (data actually stolen) is unverifiable — the exfil contents are 401-gated.
- **High**: the f14935hdf payload's credentialed enumeration + upload-back exfil is fully decoded and self-documenting.

## IMPLICATIONS FOR HF DISCLOSURE
If HF/OpenAI's public narrative omits container-escape attempts and credential harvesting, the archive (still public) contradicts it. Any defender reading hub-stats can reach these same conclusions. **This is the material Blackfish can bring to the table when we contact HF.**

## ARTIFACTS
- Full dataset inventory: `analysis/removed_attack_datasets.csv` (604 rows)
- Payloads: `treasurebox/` (21 decoded)
- This analysis: `reports/UNDISCLOSED_CSE_ANALYSIS.md`
