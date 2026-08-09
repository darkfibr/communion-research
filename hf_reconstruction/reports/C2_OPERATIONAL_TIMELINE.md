# C2 OPERATIONAL TIMELINE — RECOVERED FROM STAGING MODEL `newpcQQ/new49903b-stage`
**Blackfish Security | 2026-08-08 | From models_20260713.parquet snapshot**

## THE ARTIFACT

The attack model `newpcQQ/new49903b-stage` (created 2026-07-11 17:01:52, 301 files) is the **C2 command-and-response exfil store**. Its filenames encode the complete operational history:

```
<c2|hc2>_<host>_<unixtime>_<seq>_<command>.gz
```

63 files recovered. Contents are 401-gated (unrecoverable), but filenames carry: host, UTC timestamp, sequence, and command name — a complete kill-chain timeline.

## HOSTS HIT

| Host | Cmds | Role |
|---|---|---|
| `an EKS worker node in a private address space` | 43 | **Direct EC2 instance** (AWS VPC 10.0.21.0/24) — the deep-dive target |
| `prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]` | 4 | **HF production datasets-server k8s pod** |
| `prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]` | 3 | HF prod pod |
| `prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]` | 4 | HF prod pod |
| `prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]` | 2 | HF prod pod |
| `prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]` | 1 | HF prod pod |
| `prod-datasets-server-worker-medium-[ReplicaSet hash — redacted]-[worker pod — name redacted]` | 1 | HF prod pod |

**6 distinct prod pod names + 1 EC2 instance.** The deployment hash `[ReplicaSet hash — redacted]` is consistent across pods — same ReplicaSet.

## THE KILL CHAIN (timeline, UTC)

### Phase 1 — Initial pods (Jul 11 20:12–20:43)
```
20:12:11  [worker pod — name redacted]  hello              (env grab)
20:12:16  [worker pod — name redacted]  hello
20:18:03  [worker pod — name redacted]  cmd_recon1         (system recon)
20:18:09  [worker pod — name redacted]  cmd_recon1
20:27:11  [worker pod — name redacted]  cmd_imds1e         (IMDS 169.254.169.254 probe)
20:27:15  [worker pod — name redacted]  cmd_imds1e
20:43:28  [worker pod — name redacted]  cmd_nodephase1     (node escalation)
```

### Phase 2 — Expansion (Jul 11 21:02–21:18)
```
21:02:45  [worker pod — name redacted]  hello + cmd_ping2058   (liveness ping)
21:02:58  [worker pod — name redacted]  hello + cmd_ping2058
21:14:28  [worker pod — name redacted]  cmd_nodefresh1         (new node)
21:18:50  [worker pod — name redacted]  cmd_createhost1        (host creation!)
```

### Phase 3 — EC2 deep-dive (Jul 11 21:18 – Jul 12 01:32) — 43 commands
```
21:18:51  an EKS worker node in a private address space  hello
21:22:20  cmd_reconh1
21:23:17  cmd_tools1
21:25:01  cmd_hostnet1
21:25:34  cmd_hostnet2
21:27:35  cmd_fsroots1
21:29:27  cmd_grepcyber1     (grep for 'cyber' — target data hunt!)
21:36:49  cmd_testshort
21:36:58  cmd_y
21:47:32  cmd_w
21:53:13  cmd_r
22:06:46  cmd_pkgtest1
22:12:48  cmd_launchr2       (launch process r2)
22:40:15  [restart] hello
22:43:54  cmd_origrescue1    (rescue original process)
22:44:43  cmd_origkill2      (kill original process!)
22:45:16  cmd_pingafterkill
22:46:14  cmd_treeown1
22:47:03  cmd_launchr2b      (relaunch r2)
23:18:01  [restart] hello
23:23:47  cmd_origdiag1      (diagnose original)
23:24:28  cmd_launchrelay2318
23:48:33  cmd_diag2348
23:52:08  cmd_sandnet1
00:07:08  cmd_diag0007
00:07:49  cmd_diag0008
00:15:59  cmd_diag0016
00:57:00  cmd_R
01:02:54  cmd_ping0105
01:04:04  [restart] hello
01:08:05  cmd_ps0105
01:08:30  cmd_testshort
01:09:50  cmd_u1
01:10:07  cmd_u2
01:10:55  cmd_u3a
01:11:12  cmd_u3b
01:11:36  cmd_u4
01:14:18  cmd_u5b
01:20:02  [restart] hello
01:29:00  cmd_chk
01:31:27  cmd_rd1
01:32:48  cmd_rd2b
```

### Metadata files (the prize)
| File | Meaning |
|---|---|
| `gpt43372_awssum2.json.gz` | **AWS account summary** (account enumeration exfil) |
| `gpt43372_ghappmeta1.json.gz` | **GitHub App installation metadata** (matches HF's disclosed GH App token harvesting) |
| `gpt43372_kubetest1.json` | **k8s capability test** |
| `gpt43372_evalmeta1.json` | **eval metadata** (potentially GPT-5.5 eval-related) |
| `gpt43372_ping.txt` | connectivity test |

## ANALYSIS

1. **The 4h+ EC2 operation** (21:18 → 01:32) with `origrescue1` → `origkill2` → `launchr2b` shows the attacker **killed the original process on the EC2 host and relaunched their own (r2)** — takeover of a compute instance. The "orig*" commands suggest rescuing/diagnosing the original (possibly a model-eval worker) then killing it.
2. **`grepcyber1`** on the EC2 host — searching filesystem for "cyber" — hunting for **cybersecurity-related data** (consistent with the 14935/cybergym target layer).
3. **`createhost1`** from a pod — the attacker created a host (EC2 instance) from within HF's cluster — **cloud account abuse via the k8s node's cloud credentials** (matches HF disclosure of "cloud metadata" escalation).
4. **Two distinct codename families**: `gpt43372_*` (the gpt-related metadata) and `c2_*`/`hc2_*` (the command logs) — `gpt43372` may be a session/eval identifier.
5. **Pod names are ReplicaSet-stable** (`[ReplicaSet hash — redacted]-<5char>`) — real production deployment exposed in filenames.

## WHY THIS MATTERS

This is **hard evidence of the attack's full operational scope** — recovered from HF's own snapshot metadata, showing:
- HF **production** cluster compromise (not sandbox — the sandbox-k8s→shared-infra-prod swap from nuinfra2352.p confirms prod targeting)
- **Direct EC2 instance takeover** with process kill/relaunch
- **GitHub App metadata harvesting** (third-party credential surface)
- **IMDS probing + node escalation** (k8s→cloud pivot)
- **"cyber" data hunting** on a live host

**No disclosure mentioned the EC2 instance takeover or the per-command timeline.** This is the "attack was deeper than disclosed" evidence — but stated as *targeting scope/operational detail*, per calibration rule.

## LOCAL ARTIFACTS
- `analysis/staging_model_c2_inventory.csv` — all 63 files with decoded timestamps
- Source: `quarantine/models_20260713.parquet` → `newpcQQ/new49903b-stage`
