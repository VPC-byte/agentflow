const state = {
  runId: null,
  pipeline: null,
  runs: [],
  nodes: {},
  selectedNodeId: null,
  eventSource: null,
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function parseYamlNodes(text) {
  const matches = [...text.matchAll(/^\s*-\s*id:\s*(.+)$/gm)];
  return matches.map((match) => match[1].trim());
}

function topoLevels(nodes) {
  const levels = {};
  const map = Object.fromEntries(nodes.map((node) => [node.id, node]));
  function depth(id) {
    if (levels[id] !== undefined) return levels[id];
    const deps = map[id]?.depends_on || [];
    levels[id] = deps.length ? 1 + Math.max(...deps.map(depth)) : 0;
    return levels[id];
  }
  nodes.forEach((node) => depth(node.id));
  return levels;
}

function renderGraph() {
  const container = document.getElementById("graph");
  container.innerHTML = "";
  if (!state.pipeline?.nodes?.length) {
    container.innerHTML = '<p class="small">Run a pipeline to render the DAG.</p>';
    return;
  }
  const nodes = state.pipeline.nodes;
  const levels = topoLevels(nodes);
  const levelGroups = {};
  nodes.forEach((node) => {
    const level = levels[node.id] || 0;
    levelGroups[level] ||= [];
    levelGroups[level].push(node);
  });
  const width = Math.max(800, (Object.keys(levelGroups).length + 1) * 220);
  const height = Math.max(400, nodes.length * 130);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "graph-lines");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  container.appendChild(svg);

  const positions = {};
  Object.entries(levelGroups).forEach(([level, group]) => {
    group.forEach((node, index) => {
      positions[node.id] = { x: Number(level) * 220 + 30, y: index * 130 + 30 };
    });
  });

  nodes.forEach((node) => {
    for (const dependency of node.depends_on || []) {
      const from = positions[dependency];
      const to = positions[node.id];
      if (!from || !to) continue;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M ${from.x + 180} ${from.y + 38} C ${from.x + 210} ${from.y + 38}, ${to.x - 30} ${to.y + 38}, ${to.x} ${to.y + 38}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "#334155");
      path.setAttribute("stroke-width", "2");
      svg.appendChild(path);
    }
  });

  nodes.forEach((node) => {
    const position = positions[node.id];
    const result = state.nodes[node.id] || { status: "pending" };
    const div = document.createElement("div");
    div.className = `graph-node ${result.status || "pending"} ${state.selectedNodeId === node.id ? "selected" : ""}`;
    div.style.left = `${position.x}px`;
    div.style.top = `${position.y}px`;
    div.innerHTML = `
      <h3>${node.id}</h3>
      <p>${node.agent} · ${result.status || "pending"}</p>
      <p class="small">${node.model || "default model"}</p>
    `;
    div.onclick = () => {
      state.selectedNodeId = node.id;
      renderGraph();
      renderDetail();
    };
    container.appendChild(div);
  });
}

function renderRuns() {
  const container = document.getElementById("runs");
  container.innerHTML = state.runs.map((run) => `
    <div class="run-item">
      <h3>${run.pipeline.name}</h3>
      <div class="small">${run.id}</div>
      <div class="small">Status: ${run.status}</div>
      <button data-run-id="${run.id}">Open</button>
    </div>
  `).join("");
  container.querySelectorAll("button[data-run-id]").forEach((button) => {
    button.onclick = async () => {
      const run = await api(`/api/runs/${button.dataset.runId}`);
      state.runId = run.id;
      state.pipeline = run.pipeline;
      state.nodes = run.nodes;
      document.getElementById("run-status").textContent = run.status;
      renderGraph();
      renderDetail();
      connectStream(run.id);
    };
  });
}

function renderDetail() {
  const detail = document.getElementById("detail");
  const selected = state.selectedNodeId && state.nodes[state.selectedNodeId];
  document.getElementById("selected-node").textContent = state.selectedNodeId || "None";
  if (!selected) {
    detail.innerHTML = '<p class="small">Select a node to inspect its output and parsed JSONL trace.</p>';
    return;
  }
  const traces = selected.trace_events || [];
  detail.innerHTML = `
    <div class="trace-item">
      <h4>Status</h4>
      <div class="small">${selected.status}</div>
      <div class="small">Exit code: ${selected.exit_code ?? "-"}</div>
      <div class="small">Success: ${selected.success ?? "-"}</div>
    </div>
    <div class="trace-item">
      <h4>Final output</h4>
      <div class="output-box">${escapeHtml(selected.output || "")}</div>
    </div>
    <div class="trace-item">
      <h4>Success checks</h4>
      <div class="output-box">${escapeHtml((selected.success_details || []).join("\n"))}</div>
    </div>
    ${traces.map((trace) => `
      <div class="trace-item">
        <h4>${trace.title}</h4>
        <div class="small">${trace.kind} · ${trace.timestamp}</div>
        <pre>${escapeHtml(trace.content || JSON.stringify(trace.raw || {}, null, 2))}</pre>
      </div>
    `).join("")}
  `;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function applyEvent(event) {
  if (event.type === "run_started") {
    document.getElementById("run-status").textContent = "running";
  }
  if (event.node_id && !state.nodes[event.node_id]) {
    state.nodes[event.node_id] = { node_id: event.node_id, trace_events: [], status: "pending" };
  }
  if (event.type === "node_started" && event.node_id) {
    state.nodes[event.node_id].status = "running";
  }
  if (event.type === "node_trace" && event.node_id) {
    state.nodes[event.node_id].trace_events ||= [];
    state.nodes[event.node_id].trace_events.push(event.data.trace);
  }
  if ((event.type === "node_completed" || event.type === "node_failed") && event.node_id) {
    Object.assign(state.nodes[event.node_id], {
      status: event.type === "node_completed" ? "completed" : "failed",
      exit_code: event.data.exit_code,
      success: event.data.success,
      output: event.data.output,
      final_response: event.data.final_response,
      success_details: event.data.success_details,
    });
  }
  if (event.type === "node_skipped" && event.node_id) {
    state.nodes[event.node_id].status = "skipped";
  }
  if (event.type === "run_completed") {
    document.getElementById("run-status").textContent = event.data.status;
  }
  renderGraph();
  renderDetail();
}

function connectStream(runId) {
  if (state.eventSource) state.eventSource.close();
  state.eventSource = new EventSource(`/api/runs/${runId}/stream`);
  state.eventSource.onmessage = (message) => applyEvent(JSON.parse(message.data));
}

async function refreshRuns() {
  state.runs = await api("/api/runs");
  renderRuns();
}

document.getElementById("load-example").onclick = async () => {
  const data = await api("/api/examples/default");
  document.getElementById("pipeline-input").value = data.yaml;
};

document.getElementById("run-pipeline").onclick = async () => {
  const yaml = document.getElementById("pipeline-input").value;
  const run = await api("/api/runs", { method: "POST", body: JSON.stringify({ yaml }) });
  state.runId = run.id;
  state.pipeline = run.pipeline;
  state.nodes = run.nodes;
  state.selectedNodeId = state.pipeline.nodes?.[0]?.id || null;
  document.getElementById("run-status").textContent = run.status;
  renderGraph();
  renderDetail();
  connectStream(run.id);
  await refreshRuns();
};

document.getElementById("refresh-runs").onclick = refreshRuns;
refreshRuns().catch((error) => {
  document.getElementById("runs").innerHTML = `<div class="small">${escapeHtml(error.message)}</div>`;
});
