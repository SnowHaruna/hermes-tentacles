<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/version-V6.3-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/architecture-Octopus_Distributed_Neural-purple" alt="Architecture">
  <img src="https://img.shields.io/badge/zero_deps-shared_venv-success" alt="Zero Deps">
</p>

<h1 align="center">🦑 Hermes' Tentacles</h1>
<p align="center"><strong>An instruction-driven AI clone system — fork a full conversation clone into the background, let it reason independently, and get results delivered back seamlessly</strong></p>
<p align="center">
  <em>SnowHaruna says search / lookup / research / analyze / compare → a tentacle forks instantly. You stay unblocked — keep chatting as you were.</em>
</p>

---

## Why "Tentacles"

In June 2026, SnowHaruna and Little Snow were tracing the evolutionary lineage of AI Agent communication and walked a complete reverse path:

```
Octopus Distributed Neural → Insect Segmental Nerve Cord → Single-Cell Biochemical Communication
```

**An octopus's tentacles have their own ganglia** — each tentacle can make autonomous decisions and sense independently, all while staying in sync with the central brain through a distributed neural ring. This is the architectural metaphor behind the Tentacle system: each tentacle is an independent Hermes clone (independent reasoning) that shares a main-memory snapshot (RAG injection). Once finished, its discoveries are handed back through `tentacle_findings/` and reviewed by Little Snow for promotion into permanent memory.

> 📚 See also: [Single-Cell Communication Research Report](https://github.com/SnowHaruna/Hermes-MemVault) — from quorum sensing to endosymbiosis, 9 biological communication mechanisms → AI Agent inter-agent communication mapping

---

## Why Tentacles

Current AI assistants have exactly three ways to do heavy work:

| Approach | Problem |
|----------|---------|
| Foreground work | You sit there waiting |
| Background scripts | Can only run commands, can't reason |
| Sub-agents | Freezes chat while working |

**Tentacles are the fourth way.**

---

## How It Works

```
SnowHaruna issues a command: "Look up XXX"
     │
     ▼
  Little Snow judges: clear instruction → fork a tentacle!
     │
     ├─ Export current RAG memory snapshot
     ├─ tentacle.py --inject-memory
     ├─ Fork an independent Hermes instance
     │
     ├─ 🔧 Reasoning in progress... (every tool call visible in real time)
     ├─ 💭 Internal reasoning (stderr progress)
     ├─ 📝 Findings written to tentacle_findings/
     │
     ├─ 🆘 Hits a blocker → waits in place for help (doesn't exit!)
     │      ├─ Little Snow reads it → reports to SnowHaruna
     │      └─ SnowHaruna resolves it → tentacle resumes
     │
     └─ ✅ Done → Little Snow auto-reviews findings
            ├─ Useful → promoted into memory
            └─ Noise → discarded
```

---

## Quick Start

```bash
git clone https://github.com/SnowHaruna/hermes-tentacles.git

# Basic usage
~/.hermes/hermes-agent/venv/bin/python tentacle.py \
  --prompt "Research XXX" \
  --output ~/.hermes/reports/report.md \
  --max-iterations 40

# With memory snapshot injection
~/.hermes/hermes-agent/venv/bin/python tentacle.py \
  --prompt-file task.txt \
  --inject-memory /tmp/memory_snapshot.txt \
  --name "my-research" \
  --output ~/.hermes/reports/report.md \
  --toolsets "web,terminal,file"
```

---

## Key Design Decisions (V6)

| Decision | Rationale |
|----------|-----------|
| SnowHaruna instruction-driven (not auto-tiered) | SnowHaruna knows best what she wants — no guessing |
| RAG snapshot injection (not tentacle searching on its own) | Keeps main and fork memory timelines aligned |
| In-place help wait (not exit-and-restart) | No context loss; resumes from checkpoint |
| `tentacle_findings/` file handback | Never touches MEMORY.md — prevents fork pollution of main memory |
| Little Snow auto-review (not manual review by SnowHaruna) | Finishes in the background, zero interruption |

---

## Real-Time Monitoring

Tentacles are not black boxes — every tool call is visible in real time:

```
[tentacle] 🔧 web_search("El Niño 2026 forecast"...)
[tentacle] ✅ web_search → 5 results, 2.3s
[tentacle] 💭 Reasoning...
[tentacle] 🔧 write_file("/home/.../finding_001.txt"...)
```

Little Snow's watchdog patrols every 3 minutes: heartbeat missing for 10 minutes → report to SnowHaruna; running past 15 minutes → report progress.

---

## Verified Tasks

| Tentacle Task | Time | Output |
|---------------|------|--------|
| North vs. South Pole melt rate comparison | 7'40" | 11 KB professional report + AWars creative material |
| Philosophy of 1+1=2 | 69" | 8.6 KB deep analysis (Peano → Russell → Gödel) |
| Single-cell biological communication research | 4'10" | 43 KB paper-level report, 35 references |
| GitHub competitor search | 4'52" | 20+ project comparison → conclusion: no direct competitors |
| Kahana memory literature deep dive | Multi-round | 7-chapter analysis + MemVault architecture reference |

---

## Metrics

| Metric | Value |
|--------|-------|
| Fork cost | ~150 MB RAM |
| Output quality | = same tier as main AI |
| Dependencies | Zero — shares the same Python venv |
| Domains | All — research / analysis / coding / writing |
| Help protocol | In-place wait, no exit |
| GitHub | [SnowHaruna/hermes-tentacles](https://github.com/SnowHaruna/hermes-tentacles) |

---

## Security Audit

[SECURITY_AUDIT.md](SECURITY_AUDIT.md) — V6.2 audit: 10 vulnerabilities, 9 fixed (C2/C3/H1/H2/M1/M2/M3/L1/L2). Only C1 (GitHub PAT in plaintext) requires manual rotation.

---

## Related Projects

| Project | Relationship |
|---------|-------------|
| [Hermes-MemVault](https://github.com/SnowHaruna/Hermes-MemVault) | Memory system — the tentacle's RAG snapshot source |
| [memvault](https://github.com/SnowHaruna/memvault) | Upstream independent pip package (original author @GwynCat) |

---

## Author

**Design:** SnowHaruna (榛名雪)  
**Implementation:** Little Snow (Hermes Agent)  
**License:** MIT  

---

<p align="center">
  <em>"Evolution doesn't head toward bigger brains — it heads toward more tentacles."</em>
</p>
