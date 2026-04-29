# Chaofan Shou X Thread Notes, 2026-04-22 to 2026-04-29

This file summarizes a Tikhub scrape of public X posts by Chaofan Shou (`@Fried_rice`) from 2026-04-22 through 2026-04-29 UTC.

The local scrape was run from `/data/service/tikhub/chaofan_after_2026_04_22/` and cross-checked with both Tikhub timeline and search endpoints. The scrape found 5 posts in this window, all on 2026-04-23.

To avoid republishing a long third-party prompt verbatim, this file stores links, metadata, short excerpts, and paraphrased notes. See `prompts/chromium-agentflow-kimi-chaofan-inspired.md` for an original reusable template based on the public thread.

## Sources

- Main thread: https://x.com/Fried_rice/status/2047183251308175726
- AgentFlow reply: https://x.com/Fried_rice/status/2047183252977521102
- Model/provider reply: https://x.com/Fried_rice/status/2047183254592377046
- Prompt reply: https://x.com/Fried_rice/status/2047183257675202560
- GPU cost reply: https://x.com/Fried_rice/status/2047191722577543355
- Paper: https://arxiv.org/abs/2604.20801
- AgentFlow repository: https://github.com/berabuddies/agentflow

## Scrape Summary

| Time UTC | Tweet ID | Link | Notes |
| --- | --- | --- | --- |
| 2026-04-23 05:18:16 | `2047183251308175726` | https://x.com/Fried_rice/status/2047183251308175726 | Announces Kimi K2.5 plus evolved harness results against browser vulnerabilities and links the AgentFlow paper. |
| 2026-04-23 05:18:16 | `2047183252977521102` | https://x.com/Fried_rice/status/2047183252977521102 | Says AgentFlow was open sourced and used for graph-based multi-agent vulnerability discovery. |
| 2026-04-23 05:18:17 | `2047183254592377046` | https://x.com/Fried_rice/status/2047183254592377046 | Credits MiniMax M2.5 and compares it with Kimi K2.5 and Opus 4.6 for this task. |
| 2026-04-23 05:18:18 | `2047183257675202560` | https://x.com/Fried_rice/status/2047183257675202560 | Shares a long evolved Chromium prompt. The prompt emphasizes deep Chromium targets, sanitizer-backed crash definitions, external Chromium launch with CDP, deduplication, and reproducible artifact logging. |
| 2026-04-23 05:51:56 | `2047191722577543355` | https://x.com/Fried_rice/status/2047191722577543355 | Brief reply about GPU cost. |

## Short Excerpts

- "Chinese LLMs can hack better than state-sponsored hackers"
- "$20k for gpu"

## Operational Takeaways

The public thread and paper suggest the important ingredients are:

1. Use AgentFlow as a graph harness rather than a single-agent loop.
2. Fan out many isolated workers across browser subsystems.
3. Give workers strict ownership boundaries and shared deduplication files.
4. Treat sanitizer output as the core success signal.
5. Reject JavaScript exceptions, assertion-only crashes, and non-memory UBSAN noise.
6. Launch Chromium externally and connect via CDP so sanitizer logs and child processes can be managed directly.
7. Require reruns and minimal reproducer artifacts before logging a crash.
8. Let outer-loop optimization evolve prompts, tools, graph topology, and retry loops.

## Local Scrape Verification

The local structured scrape contained these IDs:

```text
2047183251308175726
2047183252977521102
2047183254592377046
2047183257675202560
2047191722577543355
```

