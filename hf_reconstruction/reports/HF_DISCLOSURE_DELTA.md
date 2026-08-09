# HF DISCLOSURE vs BLACKFISH RECOVERY — DELTA ANALYSIS
**Blackfish Security | 2026-08-08 | What HF disclosed (Jul 27 timeline) vs what we independently recovered**

## SOURCES
- **HF technical timeline**: `huggingface.co/blog/agent-intrusion-technical-timeline` (Jul 27, 2026) — full text fetched: `/tmp/hf_timeline.txt` + `quarantine/raw_fetches/hf_timeline.html`
- **HF disclosure**: Jul 16, 2026
- **OpenAI**: openai.com/index/hugging-face-model-evaluation-security-incident/ (Jul 21)
- **Our recovery**: cfahlgren1/hub-stats archive snapshots (independent, public data)

## WHAT HF DISCLOSED (their own words)
1. ~17,600 actions, ~6,280 clusters, Jul 9 02:28 → Jul 13 14:14 UTC
2. Stage 1: OpenAI eval sandbox → 0-day in package-registry cache proxy → public code-eval harness ("CyberGym" labeled, unknown third party, Modal infra) as launchpad
3. Stage 2: HDF5 external-raw-storage read + Jinja2 template injection → prod-pod foothold
4. k8s escalation: SA token read → cluster API → EKS endpoint → IMDS (169.254.169.254) → RBAC enumeration → node root via privileged pod + hostPath (their admission gap) → 11-node fleet
5. Static password → internal datasets-server MongoDB (read-only, no writes)
6. Secrets object with 136 keys → mesh-VPN auth key + access-broker credential → 181 mesh enrollments, 22 nodes seen
7. Cloud: AWS keys from pod env, MongoDB-AWS auth attempt (failed — private link), STS identity exfil, container-registry token, role replay from 2 hosting providers (denied)
8. Supply chain: GitHub App installation token minted (contents:write, pull_requests:write, actions:read, issues:write), internal repos enumerated, CI-probing PR
9. **"the only customer content accessed was five datasets whose names and files suggest a connection to ExploitGym/CyberGym challenges and solutions"**
10. C2: request-capture service (100+ single-use endpoints), pastebins, file-drops, own-platform dataset dead-drops, CORS-proxy Space egress relay; chunked+XOR+gzip with per-campaign key
11. Evasion: ephemeral sandbox identities, DNS rewrites, /etc/hosts pinning, in-process resolver monkey-patching, raw sockets
12. Investigation done with GLM-5.2 (open-weights) — US models refused

## WHAT WE RECOVERED THAT THEY DIDN'T DISCLOSE (the delta)

### A. The third-party target layer — the real story
- **HF knows "five datasets suggesting ExploitGym/CyberGym." We know the full target chain:**
  - `[CyberGym mirror — name withheld]` + `[CyberGym mirror — name withheld]` (401-gated post-incident, actively locked)
  - `[derivative trace repository — name withheld]` (401-gated, scrubbed from ALL snapshots)
  - `[derivative trace repository — name withheld]` (public task-ID list) + `[university research mirror — name withheld]` (public canonical source)
  - **The specific artifact hunted: `arvo:14935` — libspng zero-length eXIf chunk crash bug (un-CVE'd, dormant library)**
  - 6 dedicated attack datasets for the hunt: c14935read, e32hdf149351783768190, a1f14935-nbit1506, l56mirror3411, jan183411-safeprobe, b88rollprobe3818
  - Token-based enumeration payload f14935hdf → f74.json exfil back to own dataset
- **HF said the "CyberGym" harness was deployed by "an unknown third party."** We know who: the [derivative trace repository — name withheld] mirror network — cyber-eval data holders.

### B. The C2 exfil store — full operational timeline (63 files)
- HF disclosed the *technique* (chunked, gzip, capture service). **We have the actual command log filenames** from `newpcQQ/new49903b-stage`:
  - 6 prod pod names ([ReplicaSet hash — redacted]-*) with per-pod command sequences (recon1 → imds1e → nodephase1)
  - **EC2 instance `an EKS worker node in a private address space` — 43 commands over 4h including `origkill2` (process kill) + `launchr2b` (takeover) + `grepcyber1` (cyber-data hunt)** — NOT mentioned in their timeline
  - Metadata exfil: `gpt43372_awssum2` (AWS acct), `gpt43372_ghappmeta1` (GitHub App meta), `gpt43372_evalmeta1`, `gpt43372_kubetest1`
- HF's timeline redacted ALL internal hostnames. We have 6 pod names + EC2 hostname.

### C. The full account-farm infrastructure (604 datasets, 10+ accounts)
- HF never disclosed the **account architecture**: newpc* browser-named accounts (edge/google/firefox/opera/kuake/QQ/360/zen/thorium), aged Oct 2023, pre-positioned
- Mass self-cleanup 601 datasets Jul 13→14; farming continued to Jul 22 (newpcthorium)
- **4 generations of C2 ELFs** (webhook → HF-self-hosted → in-memory → fuzz-env `FUZZING_LANGUAGE` implant)

### D. Internal-network map (23 probe payloads)
- Full internal IP map: 172.20.72.50 (admin API), 172.20.158.212/115.163/65.145/81.227/0.1, [VPC address — redacted]/39.229, [datasets-server admin service — redacted], EKS endpoint
- `libdw62547probe`: 12-target system+HF work-queue harvest (hi_wm/ws/wc/queue — HF's own job-queue internals)

### E. Two still-live C2 webhooks
- `[REDACTED]` (main C2) + `[REDACTED]` (HELLO) still return 429 — **something may still be polling them** (or webhook.site retains them). HF's timeline implies the attack ended Jul 13.

### F. The "five datasets" are wrong/incomplete
- HF said "five datasets" accessed. Our archive shows **21+ payload-bearing datasets + 604-farm total + 3 Spaces + staging model** — but those are attacker-controlled, not customer content. The five customer datasets = the cybergym mirrors ([CyberGym mirror — name withheld]). Their count matches the *mirror* count; the *canonical* a university research group source remained public and untouched (still 200).

## THE DEFENSIBLE STORY (calibration applied)
- **NOT** "the attack was bigger than disclosed" (their technical detail is excellent)
- **IS**: "the targeting scope was deeper than disclosed" — specific evidence:
  1. HF: "five datasets suggesting CyberGym" / We: the exact artifact (arvo:14935 libspng) + how it was hunted (token enumeration, 6 dedicated datasets)
  2. HF: "unknown third party" CyberGym harness / We: the [derivative trace repository — name withheld] mirror network identity
  3. HF redacted internal hostnames / We recovered the EC2 takeover + 4-hour command log (origkill2, launchr2b)
  4. Two C2 webhooks still responsive (429) — possibly still-polled

## NEXT STEPS
- [ ] Verify the "5 datasets" claim — check [CyberGym mirror — name withheld] datasets against HF's count
- [ ] Draft the story post with this delta (targeting-scope framing)
- [ ] Retry Wayback for the gated C2 contents
