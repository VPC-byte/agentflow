# Chromium Campaign Scaffold

This scaffold is intentionally thin. The canonical prompt remains:

`prompts/chromium-agentflow-kimi-chaofan-inspired.md`

The files in `agent_template/` provide the concrete launch helper expected by
that prompt. They are copied into each remote shard directory before a run.

Default remote layout:

- Campaign root: `/home/ubuntu/campaigns/chromium-agentflow`
- Chromium source: `/home/ubuntu/campaigns/chromium/src`
- ASAN Chrome binary: `/home/ubuntu/campaigns/chromium/src/out/asan/chrome`
- Shard workspaces: `/home/ubuntu/campaigns/chromium-agentflow/agents/agent_NNN`

Typical flow:

```bash
scripts/bootstrap_chromium_remote.sh 44.223.72.154 --build
scripts/bootstrap_chromium_remote.sh 3.238.79.147
CHROMIUM_WORKER_HOSTS=44.223.72.154,3.238.79.147 agentflow run examples/chromium_kimi_campaign.py
```

Use `--build` on one high-CPU node first. Once the ASAN build exists, copy or
rsync `/home/ubuntu/campaigns/chromium` to the other workers before starting a
larger fanout. AgentFlow's SSH fanout renders a different `target.host` per
shard; it does not add a shared filesystem across SSH targets. The campaign
therefore keeps `docs/`, `crashes/`, and `locks/` local to each worker and emits
one summary per host plus a combined local summary.
