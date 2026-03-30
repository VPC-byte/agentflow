const state = {
  runId: null,
  pipeline: null,
  runs: [],
  nodes: {},
  events: [],
  selectedNodeId: null,
  selectedArtifact: "output.txt",
  artifactCache: new Map(),
  eventSource: null,
  validationPipeline: null,
  detailAutoScroll: true,
  detailScrollNodeId: null,
  detailEventSignature: null,
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
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

function setBanner(message, kind = "success") {
  const banner = document.getElementById("banner");
  if (!message) {
    banner.className = "banner hidden";
    banner.textContent = "";
    return;
  }
  banner.className = `banner ${kind}`;
  banner.textContent = message;
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function formatDuration(run) {
  if (!run?.started_at || !run?.finished_at) return "-";
  return `${Math.max(0, Math.round((new Date(run.finished_at) - new Date(run.started_at)) / 1000))}s`;
}

function currentRun() {
  return state.runs.find((run) => run.id === state.runId) || null;
}

function topoLevels(nodes) {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const indegree = Object.fromEntries(nodes.map((node) => [node.id, 0]));
  const outgoing = Object.fromEntries(nodes.map((node) => [node.id, []]));
  const levels = {};

  nodes.forEach((node) => {
    for (const dependency of node.depends_on || []) {
      if (!nodeIds.has(dependency)) continue;
      indegree[node.id] += 1;
      outgoing[dependency].push(node.id);
    }
  });

  const queue = nodes.filter((node) => indegree[node.id] === 0).map((node) => node.id);
  while (queue.length) {
    const id = queue.shift();
    levels[id] = levels[id] ?? 0;
    for (const next of outgoing[id]) {
      levels[next] = Math.max(levels[next] ?? 0, levels[id] + 1);
      indegree[next] -= 1;
      if (indegree[next] === 0) queue.push(next);
    }
  }

  nodes.forEach((node) => {
    if (levels[node.id] !== undefined) return;
    const dependencyLevels = (node.depends_on || []).map((dependency) => levels[dependency] ?? 0);
    levels[node.id] = dependencyLevels.length ? Math.max(...dependencyLevels) + 1 : 0;
  });

  return levels;
}

const graphViewState = {
  cleanup: null,
  layoutSignature: null,
  positions: {},
  zoom: 1,
};

const GRAPH_STATUS_COLORS = {
  pending: "#8b949e",
  queued: "#8b949e",
  skipped: "#8b949e",
  running: "#d29922",
  retrying: "#d29922",
  completed: "#3fb950",
  failed: "#f85149",
  cancelled: "#f85149",
};

function graphLayoutSignature(nodes) {
  return JSON.stringify(nodes.map((node) => ({
    id: node.id,
    depends_on: node.depends_on || [],
    on_failure_restart: node.on_failure_restart || [],
  })));
}

function graphStatusColor(status) {
  return GRAPH_STATUS_COLORS[status] || GRAPH_STATUS_COLORS.pending;
}

function truncateGraphLabel(value, maxLength) {
  const text = String(value ?? "");
  return text.length > maxLength ? `${text.slice(0, Math.max(0, maxLength - 3))}...` : text;
}

function graphLayout(nodes) {
  const levels = topoLevels(nodes);
  const groups = {};
  let maxLevel = 0;

  nodes.forEach((node) => {
    const level = levels[node.id] || 0;
    groups[level] ||= [];
    groups[level].push(node);
    maxLevel = Math.max(maxLevel, level);
  });

  const nodeWidth = 220;
  const nodeHeight = 104;
  const levelGap = 156;
  const rowGap = 56;
  const margin = { top: 48, right: 72, bottom: 48, left: 48 };
  const maxGroupSize = Math.max(1, ...Object.values(groups).map((group) => group.length));
  const sceneWidth = Math.max(860, margin.left + (maxLevel + 1) * nodeWidth + maxLevel * levelGap + margin.right);
  const sceneHeight = Math.max(560, margin.top + maxGroupSize * nodeHeight + Math.max(0, maxGroupSize - 1) * rowGap + margin.bottom);
  const positions = {};

  Object.entries(groups).forEach(([levelText, group]) => {
    const level = Number(levelText);
    const columnHeight = group.length * nodeHeight + Math.max(0, group.length - 1) * rowGap;
    const startY = margin.top + Math.max(0, (sceneHeight - margin.top - margin.bottom - columnHeight) / 2);
    group.forEach((node, index) => {
      positions[node.id] = {
        x: margin.left + level * (nodeWidth + levelGap),
        y: startY + index * (nodeHeight + rowGap),
      };
    });
  });

  return { nodeWidth, nodeHeight, sceneWidth, sceneHeight, positions };
}

function updateTopMetrics() {
  document.getElementById("metric-total").textContent = state.runs.length;
  document.getElementById("metric-queued").textContent = state.runs.filter((run) => run.status === "queued").length;
  document.getElementById("metric-running").textContent = state.runs.filter((run) => ["running", "cancelling"].includes(run.status)).length;
}

function filteredRuns() {
  const query = document.getElementById("run-search").value.trim().toLowerCase();
  if (!query) return state.runs;
  return state.runs.filter((run) =>
    run.id.toLowerCase().includes(query) ||
    run.pipeline.name.toLowerCase().includes(query) ||
    run.status.toLowerCase().includes(query)
  );
}

function renderRuns() {
  const container = document.getElementById("runs");
  const runs = filteredRuns();
  if (!runs.length) {
    container.innerHTML = '<div class="small">No runs yet.</div>';
    return;
  }
  container.innerHTML = runs.map((run) => `
    <div class="run-item ${run.id === state.runId ? "active" : ""}">
      <h3>${escapeHtml(run.pipeline.name)}</h3>
      <div class="small mono">${run.id}</div>
      <div class="small">Status: ${escapeHtml(run.status)} · Started: ${escapeHtml(formatDate(run.started_at || run.created_at))}</div>
      <div class="small">Duration: ${escapeHtml(formatDuration(run))}</div>
      <div class="button-row" style="margin-top:0.65rem">
        <button data-open-run="${run.id}">Open</button>
      </div>
    </div>
  `).join("");

  container.querySelectorAll("button[data-open-run]").forEach((button) => {
    button.onclick = async () => {
      await openRun(button.dataset.openRun);
    };
  });
}

function renderGraph(pipelineNodes = null, nodeStatusMap = null) {
  const container = document.getElementById("graph");
  if (graphViewState.cleanup) {
    graphViewState.cleanup();
    graphViewState.cleanup = null;
  }

  container.style.padding = "0";
  container.innerHTML = "";

  const pipeline = state.pipeline || state.validationPipeline;
  const nodes = pipelineNodes || pipeline?.nodes || [];
  const nodeMap = nodeStatusMap || state.nodes;
  if (!nodes.length) {
    container.innerHTML = '<p class="small" style="padding:1rem">Validate or run a pipeline to render the DAG.</p>';
    return;
  }

  const layout = graphLayout(nodes);
  const signature = graphLayoutSignature(nodes);
  if (graphViewState.layoutSignature !== signature) {
    graphViewState.layoutSignature = signature;
    graphViewState.positions = {};
    graphViewState.zoom = 1;
    container.scrollLeft = 0;
    container.scrollTop = 0;
  }

  nodes.forEach((node) => {
    graphViewState.positions[node.id] ||= { ...layout.positions[node.id] };
  });
  Object.keys(graphViewState.positions).forEach((nodeId) => {
    if (!nodes.some((node) => node.id === nodeId)) delete graphViewState.positions[nodeId];
  });

  const ns = "http://www.w3.org/2000/svg";
  const rootStyles = getComputedStyle(document.documentElement);
  const primaryColor = rootStyles.getPropertyValue("--primary").trim() || "#38bdf8";
  const borderColor = rootStyles.getPropertyValue("--border").trim() || "#334155";
  const panelColor = rootStyles.getPropertyValue("--panel").trim() || "#111827";
  const textColor = rootStyles.getPropertyValue("--text").trim() || "#e5e7eb";
  const mutedColor = rootStyles.getPropertyValue("--muted").trim() || "#94a3b8";
  const badgeFill = "rgba(56, 189, 248, 0.14)";
  const badgeStroke = "rgba(56, 189, 248, 0.45)";
  const svg = document.createElementNS(ns, "svg");

  svg.setAttribute("viewBox", `0 0 ${layout.sceneWidth} ${layout.sceneHeight}`);
  svg.setAttribute("width", String(layout.sceneWidth * graphViewState.zoom));
  svg.setAttribute("height", String(layout.sceneHeight * graphViewState.zoom));
  svg.style.display = "block";
  svg.style.userSelect = "none";
  svg.style.webkitUserSelect = "none";
  svg.style.touchAction = "none";
  container.appendChild(svg);

  const defs = document.createElementNS(ns, "defs");
  const createMarker = (id, color) => {
    const marker = document.createElementNS(ns, "marker");
    marker.setAttribute("id", id);
    marker.setAttribute("viewBox", "0 0 10 10");
    marker.setAttribute("refX", "9");
    marker.setAttribute("refY", "5");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "8");
    marker.setAttribute("markerUnits", "strokeWidth");
    marker.setAttribute("orient", "auto");
    const arrow = document.createElementNS(ns, "path");
    arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
    arrow.setAttribute("fill", color);
    marker.appendChild(arrow);
    return marker;
  };
  defs.appendChild(createMarker("graph-arrow", borderColor));
  defs.appendChild(createMarker("graph-arrow-cycle", "#f85149"));
  svg.appendChild(defs);

  const background = document.createElementNS(ns, "rect");
  background.setAttribute("x", "0");
  background.setAttribute("y", "0");
  background.setAttribute("width", String(layout.sceneWidth));
  background.setAttribute("height", String(layout.sceneHeight));
  background.setAttribute("fill", "transparent");
  svg.appendChild(background);

  const edgesLayer = document.createElementNS(ns, "g");
  const nodesLayer = document.createElementNS(ns, "g");
  svg.appendChild(edgesLayer);
  svg.appendChild(nodesLayer);

  const nodeRefs = {};
  const edgeRefs = [];

  function scenePoint(event) {
    const rect = svg.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * layout.sceneWidth,
      y: ((event.clientY - rect.top) / rect.height) * layout.sceneHeight,
    };
  }

  function nodeBounds(nodeId) {
    const position = graphViewState.positions[nodeId] || layout.positions[nodeId];
    return {
      x: position.x,
      y: position.y,
      width: layout.nodeWidth,
      height: layout.nodeHeight,
    };
  }

  function forwardPath(fromId, toId) {
    const from = nodeBounds(fromId);
    const to = nodeBounds(toId);
    const startX = from.x + from.width;
    const startY = from.y + from.height / 2;
    const endX = to.x;
    const endY = to.y + to.height / 2;
    const direction = endX >= startX ? 1 : -1;
    const curve = Math.max(52, Math.abs(endX - startX) * 0.45);
    return `M ${startX} ${startY} C ${startX + direction * curve} ${startY}, ${endX - direction * curve} ${endY}, ${endX} ${endY}`;
  }

  function cyclePath(fromId, toId) {
    const from = nodeBounds(fromId);
    const to = nodeBounds(toId);
    const startX = from.x;
    const startY = from.y + from.height / 2;
    const endX = to.x + to.width;
    const endY = to.y + to.height / 2;
    const horizontalLift = Math.max(92, Math.abs(startX - endX) * 0.3);
    const verticalLift = Math.max(96, Math.abs(startY - endY) * 0.45 + 36);
    const controlY = Math.min(startY, endY) - verticalLift;
    return `M ${startX} ${startY} C ${startX - horizontalLift} ${controlY}, ${endX + horizontalLift} ${controlY}, ${endX} ${endY}`;
  }

  function updateNodePosition(nodeId) {
    const ref = nodeRefs[nodeId];
    const position = graphViewState.positions[nodeId];
    if (!ref || !position) return;
    ref.setAttribute("transform", `translate(${position.x} ${position.y})`);
  }

  function updateEdges(changedNodeId = null) {
    edgeRefs.forEach((edge) => {
      if (changedNodeId && edge.fromId !== changedNodeId && edge.toId !== changedNodeId) return;
      edge.path.setAttribute("d", edge.kind === "cycle" ? cyclePath(edge.fromId, edge.toId) : forwardPath(edge.fromId, edge.toId));
    });
  }

  function findNodeGroup(target) {
    let current = target;
    while (current && current !== svg) {
      if (current.dataset?.nodeId) return current;
      current = current.parentNode;
    }
    return null;
  }

  nodes.forEach((node) => {
    for (const dependency of node.depends_on || []) {
      if (!graphViewState.positions[dependency] || !graphViewState.positions[node.id]) continue;
      const edge = document.createElementNS(ns, "path");
      edge.setAttribute("fill", "none");
      edge.setAttribute("stroke", borderColor);
      edge.setAttribute("stroke-width", "2");
      edge.setAttribute("stroke-linecap", "round");
      edge.setAttribute("stroke-linejoin", "round");
      edge.setAttribute("marker-end", "url(#graph-arrow)");
      edgesLayer.appendChild(edge);
      edgeRefs.push({ fromId: dependency, toId: node.id, kind: "dependency", path: edge });
    }
  });

  nodes.forEach((node) => {
    for (const restartTarget of node.on_failure_restart || []) {
      if (!graphViewState.positions[restartTarget] || !graphViewState.positions[node.id]) continue;
      const edge = document.createElementNS(ns, "path");
      edge.setAttribute("fill", "none");
      edge.setAttribute("stroke", "#f85149");
      edge.setAttribute("stroke-width", "2");
      edge.setAttribute("stroke-dasharray", "8 6");
      edge.setAttribute("stroke-linecap", "round");
      edge.setAttribute("stroke-linejoin", "round");
      edge.setAttribute("marker-end", "url(#graph-arrow-cycle)");
      edgesLayer.appendChild(edge);
      edgeRefs.push({ fromId: node.id, toId: restartTarget, kind: "cycle", path: edge });
    }
  });

  updateEdges();

  let dragState = null;
  let suppressClick = false;

  nodes.forEach((node) => {
    const result = nodeMap[node.id] || { status: "pending" };
    const status = result.status || "pending";
    const statusColor = graphStatusColor(status);
    const badgeLabel = truncateGraphLabel(node.agent || "agent", 14);
    const badgeWidth = Math.max(64, badgeLabel.length * 7 + 24);
    const group = document.createElementNS(ns, "g");
    group.dataset.nodeId = node.id;
    group.style.cursor = "grab";

    const selection = document.createElementNS(ns, "rect");
    selection.setAttribute("x", "-4");
    selection.setAttribute("y", "-4");
    selection.setAttribute("width", String(layout.nodeWidth + 8));
    selection.setAttribute("height", String(layout.nodeHeight + 8));
    selection.setAttribute("rx", "20");
    selection.setAttribute("fill", "none");
    selection.setAttribute("stroke", primaryColor);
    selection.setAttribute("stroke-width", "2.5");
    selection.setAttribute("opacity", state.selectedNodeId === node.id ? "1" : "0");
    group.appendChild(selection);

    const card = document.createElementNS(ns, "rect");
    card.setAttribute("x", "0");
    card.setAttribute("y", "0");
    card.setAttribute("width", String(layout.nodeWidth));
    card.setAttribute("height", String(layout.nodeHeight));
    card.setAttribute("rx", "16");
    card.setAttribute("fill", panelColor);
    card.setAttribute("fill-opacity", "0.94");
    card.setAttribute("stroke", statusColor);
    card.setAttribute("stroke-width", "2.5");
    group.appendChild(card);

    const title = document.createElementNS(ns, "text");
    title.setAttribute("x", "16");
    title.setAttribute("y", "32");
    title.setAttribute("fill", textColor);
    title.setAttribute("font-size", "14");
    title.setAttribute("font-weight", "600");
    title.setAttribute("font-family", "Inter, ui-sans-serif, system-ui, sans-serif");
    title.textContent = truncateGraphLabel(node.id, 24);
    group.appendChild(title);

    const statusText = document.createElementNS(ns, "text");
    statusText.setAttribute("x", String(layout.nodeWidth - 16));
    statusText.setAttribute("y", "32");
    statusText.setAttribute("fill", statusColor);
    statusText.setAttribute("font-size", "11");
    statusText.setAttribute("font-weight", "700");
    statusText.setAttribute("text-anchor", "end");
    statusText.setAttribute("font-family", "Inter, ui-sans-serif, system-ui, sans-serif");
    statusText.textContent = truncateGraphLabel(status.toUpperCase(), 12);
    group.appendChild(statusText);

    const subtitle = document.createElementNS(ns, "text");
    subtitle.setAttribute("x", "16");
    subtitle.setAttribute("y", "58");
    subtitle.setAttribute("fill", mutedColor);
    subtitle.setAttribute("font-size", "11");
    subtitle.setAttribute("font-family", "Inter, ui-sans-serif, system-ui, sans-serif");
    subtitle.textContent = `Attempts ${(result.current_attempt || 0)}/${(node.retries || 0) + 1}`;
    group.appendChild(subtitle);

    const badge = document.createElementNS(ns, "rect");
    badge.setAttribute("x", "16");
    badge.setAttribute("y", "72");
    badge.setAttribute("width", String(badgeWidth));
    badge.setAttribute("height", "22");
    badge.setAttribute("rx", "11");
    badge.setAttribute("fill", badgeFill);
    badge.setAttribute("stroke", badgeStroke);
    badge.setAttribute("stroke-width", "1");
    group.appendChild(badge);

    const badgeText = document.createElementNS(ns, "text");
    badgeText.setAttribute("x", String(16 + badgeWidth / 2));
    badgeText.setAttribute("y", "87");
    badgeText.setAttribute("fill", primaryColor);
    badgeText.setAttribute("font-size", "11");
    badgeText.setAttribute("font-weight", "600");
    badgeText.setAttribute("text-anchor", "middle");
    badgeText.setAttribute("font-family", "Inter, ui-sans-serif, system-ui, sans-serif");
    badgeText.textContent = badgeLabel;
    group.appendChild(badgeText);

    nodeRefs[node.id] = group;
    updateNodePosition(node.id);

    group.addEventListener("click", () => {
      if (suppressClick) {
        suppressClick = false;
        return;
      }
      state.selectedNodeId = node.id;
      renderGraph();
      renderDetail();
    });

    nodesLayer.appendChild(group);
  });

  function stopDragging() {
    if (!dragState) return;
    svg.style.cursor = "default";
    if (nodeRefs[dragState.nodeId]) nodeRefs[dragState.nodeId].style.cursor = "grab";
    suppressClick = dragState.moved;
    if (dragState.moved) {
      window.setTimeout(() => {
        suppressClick = false;
      }, 0);
    }
    dragState = null;
  }

  function handleMouseDown(event) {
    if (event.button !== 0) return;
    const nodeGroup = findNodeGroup(event.target);
    if (!nodeGroup) return;
    const nodeId = nodeGroup.dataset.nodeId;
    if (!graphViewState.positions[nodeId]) return;
    const point = scenePoint(event);
    nodesLayer.appendChild(nodeGroup);
    dragState = {
      nodeId,
      startX: point.x,
      startY: point.y,
      originX: graphViewState.positions[nodeId].x,
      originY: graphViewState.positions[nodeId].y,
      moved: false,
    };
    svg.style.cursor = "grabbing";
    nodeGroup.style.cursor = "grabbing";
    event.preventDefault();
  }

  function handleMouseMove(event) {
    if (!dragState) return;
    const point = scenePoint(event);
    const dx = point.x - dragState.startX;
    const dy = point.y - dragState.startY;
    dragState.moved ||= Math.abs(dx) > 2 || Math.abs(dy) > 2;
    graphViewState.positions[dragState.nodeId] = {
      x: Math.max(24, Math.min(layout.sceneWidth - layout.nodeWidth - 24, dragState.originX + dx)),
      y: Math.max(24, Math.min(layout.sceneHeight - layout.nodeHeight - 24, dragState.originY + dy)),
    };
    updateNodePosition(dragState.nodeId);
    updateEdges(dragState.nodeId);
  }

  function handleMouseUp() {
    stopDragging();
  }

  function handleWheel(event) {
    event.preventDefault();
    const nextZoom = Math.max(0.6, Math.min(2.4, graphViewState.zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12)));
    if (nextZoom === graphViewState.zoom) return;
    const containerRect = container.getBoundingClientRect();
    const offsetX = event.clientX - containerRect.left + container.scrollLeft;
    const offsetY = event.clientY - containerRect.top + container.scrollTop;
    const logicalX = offsetX / graphViewState.zoom;
    const logicalY = offsetY / graphViewState.zoom;
    graphViewState.zoom = nextZoom;
    svg.setAttribute("width", String(layout.sceneWidth * graphViewState.zoom));
    svg.setAttribute("height", String(layout.sceneHeight * graphViewState.zoom));
    container.scrollLeft = Math.max(0, logicalX * graphViewState.zoom - (event.clientX - containerRect.left));
    container.scrollTop = Math.max(0, logicalY * graphViewState.zoom - (event.clientY - containerRect.top));
  }

  svg.addEventListener("mousedown", handleMouseDown);
  svg.addEventListener("wheel", handleWheel, { passive: false });
  window.addEventListener("mousemove", handleMouseMove);
  window.addEventListener("mouseup", handleMouseUp);

  graphViewState.cleanup = () => {
    svg.removeEventListener("mousedown", handleMouseDown);
    svg.removeEventListener("wheel", handleWheel);
    window.removeEventListener("mousemove", handleMouseMove);
    window.removeEventListener("mouseup", handleMouseUp);
  };
}

function renderRunMeta() {
  const run = currentRun();
  document.getElementById("run-status").textContent = run?.status || "idle";
  document.getElementById("run-meta").textContent = run
    ? `${run.pipeline.name} · created ${formatDate(run.created_at)} · duration ${formatDuration(run)}`
    : state.validationPipeline
      ? `Validated DAG: ${state.validationPipeline.name}`
      : "No run selected";
}

function upsertAttempt(nodeState, attemptNumber, patch) {
  if (!attemptNumber) return;
  nodeState.attempts ||= [];
  let attempt = nodeState.attempts.find((item) => item.number === attemptNumber);
  if (!attempt) {
    attempt = { number: attemptNumber };
    nodeState.attempts.push(attempt);
    nodeState.attempts.sort((left, right) => left.number - right.number);
  }
  Object.assign(attempt, patch);
}

async function fetchArtifact(nodeId, name) {
  if (!state.runId || !nodeId) return "";
  const cacheKey = `${state.runId}:${nodeId}:${name}`;
  if (state.artifactCache.has(cacheKey)) return state.artifactCache.get(cacheKey);
  const content = await api(`/api/runs/${state.runId}/artifacts/${nodeId}/${name}`);
  state.artifactCache.set(cacheKey, content);
  return content;
}

function ensureDetailEnhancements() {
  if (!document.getElementById("detail-enhancement-styles")) {
    const style = document.createElement("style");
    style.id = "detail-enhancement-styles";
    style.textContent = `
      .trace-stack {
        display: grid;
        gap: 0.85rem;
      }

      .trace-card {
        margin: 0;
        border: 1px solid rgba(48, 54, 61, 0.92);
        border-left: 4px solid var(--trace-accent, rgba(88, 166, 255, 0.82));
        border-radius: 14px;
        background: rgba(13, 17, 23, 0.72);
        overflow: hidden;
      }

      .trace-card[open] {
        background: rgba(17, 22, 29, 0.92);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2);
      }

      .trace-card.trace-card-error {
        border-left-color: rgba(248, 81, 73, 0.88);
      }

      .trace-card > summary {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        list-style: none;
        cursor: pointer;
        padding: 0.9rem;
      }

      .trace-card > summary::-webkit-details-marker {
        display: none;
      }

      .trace-card-body {
        padding: 0 0.9rem 0.9rem;
      }

      .trace-card-header {
        min-width: 0;
        flex: 1;
        display: flex;
        align-items: center;
        gap: 0.7rem;
        flex-wrap: wrap;
      }

      .trace-card-meta {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        flex-wrap: wrap;
      }

      .trace-tool-icon {
        width: 1.85rem;
        height: 1.85rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        font-size: 0.78rem;
        font-weight: 700;
        color: #f0f6fc;
        background: var(--trace-accent, rgba(88, 166, 255, 0.82));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
      }

      .trace-tool-icon-exec {
        --trace-accent: rgba(88, 166, 255, 0.82);
      }

      .trace-tool-icon-read {
        --trace-accent: rgba(63, 185, 80, 0.82);
      }

      .trace-tool-icon-write {
        --trace-accent: rgba(210, 153, 34, 0.86);
      }

      .trace-tool-icon-error {
        --trace-accent: rgba(248, 81, 73, 0.88);
      }

      .trace-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        min-height: 1.5rem;
        padding: 0.08rem 0.5rem;
        border: 1px solid rgba(139, 148, 158, 0.32);
        border-radius: 999px;
        background: rgba(139, 148, 158, 0.1);
        color: var(--muted);
        font-size: 0.71rem;
        line-height: 1.2;
        white-space: nowrap;
      }

      .trace-pill.trace-pill-success {
        border-color: rgba(63, 185, 80, 0.42);
        background: rgba(63, 185, 80, 0.12);
        color: #7ee787;
      }

      .trace-pill.trace-pill-failure {
        border-color: rgba(248, 81, 73, 0.42);
        background: rgba(248, 81, 73, 0.12);
        color: #ff7b72;
      }

      .trace-command-block {
        margin-top: 0.75rem;
        background: #0b0f14;
        border-color: rgba(88, 166, 255, 0.24);
      }

      .trace-json-key {
        color: #79c0ff;
      }

      .trace-json-value {
        color: #a5d6ff;
      }

      .trace-block {
        display: grid;
        gap: 0.45rem;
      }

      .trace-block + .trace-block {
        margin-top: 0.75rem;
      }

      .trace-subsection {
        margin-top: 0.75rem;
        border: 1px solid rgba(48, 54, 61, 0.82);
        border-radius: 12px;
        background: rgba(8, 11, 17, 0.55);
      }

      .trace-subsection > summary {
        cursor: pointer;
        list-style: none;
        padding: 0.68rem 0.85rem;
        color: var(--muted);
        font-size: 0.76rem;
      }

      .trace-subsection > summary::-webkit-details-marker {
        display: none;
      }

      .trace-subsection-body {
        padding: 0 0.85rem 0.85rem;
      }

      .trace-empty {
        padding: 0.9rem;
        border: 1px dashed rgba(48, 54, 61, 0.85);
        border-radius: 14px;
        color: var(--muted);
        font-size: 0.76rem;
      }
    `;
    document.head.appendChild(style);
  }

  const detail = document.getElementById("detail");
  if (detail && !detail.dataset.scrollTrackingBound) {
    detail.dataset.scrollTrackingBound = "true";
    detail.addEventListener("scroll", () => {
      state.detailAutoScroll = detail.scrollHeight - detail.scrollTop - detail.clientHeight < 32;
    });
  }
}

function formatElapsedSeconds(seconds) {
  if (!Number.isFinite(seconds)) return null;
  if (seconds < 1) return `${Math.max(1, Math.round(seconds * 1000))}ms`;
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes}m ${remainder}s`;
}

function maybeParseJson(value) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (!["{", "[", "\""].includes(trimmed[0])) return value;
  try {
    return JSON.parse(trimmed);
  } catch {
    return value;
  }
}

function isStructuredValue(value) {
  return value !== null && typeof value === "object";
}

function renderJsonMarkup(value) {
  const normalized = isStructuredValue(value) ? value : maybeParseJson(value);
  if (!isStructuredValue(normalized)) return escapeHtml(String(value ?? ""));
  const json = JSON.stringify(normalized, null, 2);
  const tokenPattern = /"(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(?=\s*:)|"(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  let result = "";
  let lastIndex = 0;
  for (const match of json.matchAll(tokenPattern)) {
    result += escapeHtml(json.slice(lastIndex, match.index));
    const token = match[0];
    const suffix = json.slice((match.index || 0) + token.length).trimStart().startsWith(":");
    const className = suffix && token.startsWith("\"") ? "trace-json-key" : "trace-json-value";
    result += `<span class="${className}">${escapeHtml(token)}</span>`;
    lastIndex = (match.index || 0) + token.length;
  }
  result += escapeHtml(json.slice(lastIndex));
  return result;
}

function renderPreBlock(value, className = "") {
  const normalized = maybeParseJson(value);
  const classes = ["output-box"];
  if (className) classes.push(className);
  const html = isStructuredValue(normalized) ? renderJsonMarkup(normalized) : escapeHtml(String(value ?? ""));
  return `<pre class="${classes.join(" ")}">${html}</pre>`;
}

function renderBlock(label, value, options = {}) {
  if (value === null || value === undefined || value === "") return "";
  const content = `<div class="trace-subsection-body">${renderPreBlock(value, options.className || "")}</div>`;
  if (options.collapsed) {
    return `
      <details class="trace-subsection"${options.open ? " open" : ""}>
        <summary>${escapeHtml(label)}</summary>
        ${content}
      </details>
    `;
  }
  return `
    <div class="trace-block">
      <div class="small">${escapeHtml(label)}</div>
      ${renderPreBlock(value, options.className || "")}
    </div>
  `;
}

function findNestedEntry(source, predicate, depth = 0) {
  const normalized = maybeParseJson(source);
  if (normalized !== source) return findNestedEntry(normalized, predicate, depth + 1);
  if (source === null || source === undefined || depth > 5) return null;
  if (Array.isArray(source)) {
    for (const item of source) {
      const found = findNestedEntry(item, predicate, depth + 1);
      if (found) return found;
    }
    return null;
  }
  if (typeof source !== "object") return null;
  for (const [key, value] of Object.entries(source)) {
    if (predicate(key, value)) return { key, value };
    const found = findNestedEntry(value, predicate, depth + 1);
    if (found) return found;
  }
  return null;
}

function extractToolName(trace) {
  const raw = trace?.raw || {};
  return raw.name ||
    raw.tool_name ||
    raw.toolName ||
    raw.item?.name ||
    raw.item?.tool_name ||
    raw.function?.name ||
    raw.payload?.function?.name ||
    raw.params?.name ||
    trace?.title?.replace(/^Tool call:\s*/i, "").trim() ||
    trace?.title ||
    "Tool";
}

function extractToolId(trace) {
  const raw = trace?.raw || {};
  return raw.id || raw.tool_use_id || raw.toolUseId || raw.item?.id || raw.item?.call_id || null;
}

function extractToolRef(trace) {
  const raw = trace?.raw || {};
  return raw.tool_use_id || raw.toolUseId || raw.id || raw.item?.tool_use_id || raw.item?.call_id || null;
}

function extractToolInput(trace) {
  const raw = trace?.raw || {};
  return raw.input ??
    raw.arguments ??
    raw.item?.arguments ??
    raw.item?.input ??
    raw.function?.arguments ??
    raw.payload?.function?.arguments ??
    raw.params?.arguments ??
    trace?.content ??
    null;
}

function extractToolOutput(trace) {
  const raw = trace?.raw || {};
  return raw.result ??
    raw.output ??
    raw.content ??
    raw.item?.output ??
    raw.item?.result ??
    raw.item?.content ??
    raw.item?.message ??
    raw.payload?.result ??
    raw.payload?.output ??
    raw.params?.result ??
    trace?.content ??
    null;
}

function extractCommand(value) {
  const entry = findNestedEntry(value, (key) => ["cmd", "command", "bash_command", "shell_command"].includes(String(key).toLowerCase()));
  return entry ? String(entry.value ?? "").trim() : "";
}

function extractDuration(value) {
  const entry = findNestedEntry(value, (key) =>
    ["duration", "duration_ms", "durationms", "elapsed", "elapsed_ms", "elapsedms", "latency_ms", "latencyms"].includes(String(key).toLowerCase())
  );
  if (!entry) return null;
  if (typeof entry.value === "string" && entry.value.trim()) return entry.value.trim();
  if (typeof entry.value === "number") {
    const key = entry.key.toLowerCase();
    return key.includes("ms") ? `${Math.round(entry.value)}ms` : formatElapsedSeconds(entry.value);
  }
  return null;
}

function extractExitCode(value) {
  const entry = findNestedEntry(value, (key) => ["exit_code", "exitcode", "returncode"].includes(String(key).toLowerCase()));
  if (!entry) return null;
  const numeric = Number(entry.value);
  return Number.isFinite(numeric) ? numeric : String(entry.value ?? "");
}

function extractTraceDuration(trace) {
  return extractDuration(trace?.raw) || extractDuration(trace?.content);
}

function extractTraceExitCode(trace) {
  const fromRaw = extractExitCode(trace?.raw);
  return fromRaw ?? extractExitCode(trace?.content);
}

function isErrorTrace(trace) {
  const raw = trace?.raw || {};
  const title = String(trace?.title || "").toLowerCase();
  const kind = String(trace?.kind || "").toLowerCase();
  return kind.includes("error") ||
    title.includes("error") ||
    raw.item?.type === "error" ||
    raw.error !== undefined ||
    trace?.source === "stderr";
}

function isToolUseTrace(trace) {
  return ["tool_use", "tool_call", "toolcall"].includes(trace?.kind);
}

function isToolResultTrace(trace) {
  return ["tool_result", "toolresult"].includes(trace?.kind);
}

function classifyToolType(name, isError = false) {
  if (isError) return "error";
  const lower = String(name || "").toLowerCase();
  if (["exec", "command", "bash", "shell", "terminal", "run"].some((token) => lower.includes(token))) return "exec";
  if (["write", "edit", "patch", "apply", "create", "update", "delete", "modify"].some((token) => lower.includes(token))) return "write";
  if (["read", "open", "find", "search", "list", "view", "fetch", "grep", "rg", "cat"].some((token) => lower.includes(token))) return "read";
  return "read";
}

function toolIcon(type) {
  if (type === "exec") return ">";
  if (type === "write") return "W";
  if (type === "error") return "!";
  return "R";
}

function traceTimestampMap(nodeId) {
  return state.events
    .filter((event) => event.node_id === nodeId && event.type === "node_trace")
    .map((event) => event.timestamp);
}

function buildTraceEntries(nodeId, traceEvents) {
  const timestamps = traceTimestampMap(nodeId);
  const entries = [];
  const pendingById = new Map();
  let lastPending = null;

  function attachResult(target, trace, timestamp) {
    if (!target) return false;
    target.result = extractToolOutput(trace);
    target.resultTrace = trace;
    target.timestamp = timestamp || target.timestamp;
    target.duration = target.duration || extractTraceDuration(trace);
    target.exitCode = target.exitCode ?? extractTraceExitCode(trace);
    return true;
  }

  traceEvents.forEach((trace, index) => {
    const timestamp = timestamps[index] || null;
    if (isToolUseTrace(trace)) {
      const toolName = extractToolName(trace);
      const type = classifyToolType(toolName);
      const entry = {
        key: `${trace.kind || "tool"}:${index}:${toolName}`,
        kind: "tool",
        type,
        label: toolName,
        title: toolName,
        trace,
        timestamp,
        duration: extractTraceDuration(trace),
        input: extractToolInput(trace),
        command: type === "exec" ? extractCommand(extractToolInput(trace)) : "",
        result: null,
        exitCode: extractTraceExitCode(trace),
      };
      entries.push(entry);
      const toolId = extractToolId(trace);
      if (toolId) pendingById.set(toolId, entry);
      lastPending = entry;
      return;
    }

    if (isToolResultTrace(trace)) {
      const toolRef = extractToolRef(trace);
      const matched = (toolRef && pendingById.get(toolRef)) || lastPending;
      if (attachResult(matched, trace, timestamp)) return;
    }

    if (trace?.kind === "command_output" && lastPending && lastPending.type === "exec") {
      const existing = lastPending.result ? `${String(lastPending.result).trimEnd()}\n${String(trace.content || "").trim()}` : trace.content;
      lastPending.result = existing;
      lastPending.timestamp = timestamp || lastPending.timestamp;
      return;
    }

    if (trace?.kind === "item_completed" && !isErrorTrace(trace) && lastPending) {
      lastPending.timestamp = timestamp || lastPending.timestamp;
      lastPending.duration = lastPending.duration || extractTraceDuration(trace);
      lastPending.exitCode = lastPending.exitCode ?? extractTraceExitCode(trace);
      if (!lastPending.result) lastPending.result = extractToolOutput(trace);
      return;
    }

    if (isErrorTrace(trace)) {
      entries.push({
        key: `${trace.kind || "error"}:${index}:${trace.title || "Error"}`,
        kind: "error",
        type: "error",
        label: extractToolName(trace),
        title: trace.title || "Error",
        trace,
        timestamp,
        duration: extractTraceDuration(trace),
        input: null,
        command: "",
        result: extractToolOutput(trace),
        exitCode: extractTraceExitCode(trace),
      });
      return;
    }

    entries.push({
      key: `${trace.kind || "event"}:${index}:${trace.title || trace.kind || "Trace event"}`,
      kind: "event",
      type: "read",
      label: trace.title || trace.kind || "Trace event",
      title: trace.title || trace.kind || "Trace event",
      trace,
      timestamp,
      duration: extractTraceDuration(trace),
      input: null,
      command: "",
      result: extractToolOutput(trace),
      exitCode: extractTraceExitCode(trace),
    });
  });

  return entries.slice(-25).reverse();
}

function renderTraceCard(entry) {
  const isError = entry.type === "error";
  const isOpen = isError || entry.open;
  const timestamp = entry.timestamp ? formatDate(entry.timestamp) : null;
  const exitCode = entry.exitCode;
  const exitBadgeClass = exitCode === null || exitCode === undefined
    ? ""
    : Number(exitCode) === 0
      ? "trace-pill-success"
      : "trace-pill-failure";
  const inputLabel = entry.trace?.kind === "tool_use" ? "Input JSON" : "Input";
  const outputLabel = entry.trace?.kind === "tool_use" ? "Result" : "Output";
  const inputBlock = entry.command
    ? `
      <div class="trace-block">
        <div class="small">Command</div>
        ${renderPreBlock(entry.command, "trace-command-block")}
      </div>
      ${renderBlock(inputLabel, entry.input, { collapsed: entry.trace?.kind === "tool_use" })}
    `
    : renderBlock(inputLabel, entry.input, { collapsed: entry.trace?.kind === "tool_use" });
  const outputBlock = renderBlock(outputLabel, entry.result, {
    collapsed: entry.trace?.kind === "tool_use" || !!entry.command || isError,
    open: isError,
  });
  const rawBlock = entry.kind === "event" ? renderBlock("Raw event", entry.trace?.raw || entry.trace?.content, { collapsed: true }) : "";

  return `
    <details class="trace-card trace-card-${entry.type}" data-trace-key="${escapeHtml(entry.key)}"${isOpen ? " open" : ""}>
      <summary>
        <span class="trace-tool-icon trace-tool-icon-${entry.type}">${toolIcon(entry.type)}</span>
        <span class="trace-card-header">
          <strong>${escapeHtml(entry.title)}</strong>
          <span class="trace-card-meta">
            ${entry.duration ? `<span class="trace-pill">${escapeHtml(entry.duration)}</span>` : ""}
            ${timestamp ? `<span class="small">${escapeHtml(timestamp)}</span>` : ""}
            ${exitCode !== null && exitCode !== undefined ? `<span class="trace-pill ${exitBadgeClass}">exit ${escapeHtml(String(exitCode))}</span>` : ""}
          </span>
        </span>
      </summary>
      <div class="trace-card-body">
        ${inputBlock}
        ${outputBlock}
        ${rawBlock}
      </div>
    </details>
  `;
}

function renderLifecycleEvent(event) {
  return `
    <div class="summary-card">
      <div><strong>${escapeHtml(event.type)}</strong></div>
      <div class="small">${escapeHtml(formatDate(event.timestamp))}</div>
      ${renderPreBlock(event.data || {})}
    </div>
  `;
}

async function renderDetail() {
  ensureDetailEnhancements();
  const detail = document.getElementById("detail");
  const previousScrollTop = detail.scrollTop;
  const openTraceKeys = new Set(Array.from(detail.querySelectorAll(".trace-card[open]")).map((card) => card.dataset.traceKey));
  const selectedNodeId = state.selectedNodeId;
  const selectedArtifact = state.selectedArtifact;
  const selected = selectedNodeId && state.nodes[selectedNodeId];
  document.getElementById("selected-node").textContent = selectedNodeId || "None selected";

  let nodeChanged = false;
  if (state.detailScrollNodeId !== selectedNodeId) {
    nodeChanged = true;
    state.detailScrollNodeId = selectedNodeId;
    state.detailAutoScroll = true;
    state.detailEventSignature = null;
  }

  if (!selected || !selectedNodeId) {
    detail.innerHTML = '<p class="small">Select a node to inspect its output, attempts, artifacts, and parsed timeline.</p>';
    return;
  }

  let artifactText = "";
  try {
    artifactText = await fetchArtifact(selectedNodeId, selectedArtifact);
  } catch {
    artifactText = selected.output || "";
  }
  if (state.selectedNodeId !== selectedNodeId || state.selectedArtifact !== selectedArtifact) return;

  const attemptRows = (selected.attempts || []).map((attempt) => `
    <div class="summary-card">
      <div><strong>Attempt ${attempt.number}</strong></div>
      <div class="small">Status: ${escapeHtml(attempt.status)} · Exit: ${escapeHtml(String(attempt.exit_code ?? "-"))}</div>
      <div class="small">Started: ${escapeHtml(formatDate(attempt.started_at))}</div>
      <div class="small">Finished: ${escapeHtml(formatDate(attempt.finished_at))}</div>
    </div>
  `).join("");

  const lifecycleEventRows = state.events.filter((event) => event.node_id === selectedNodeId && event.type !== "node_trace");
  const lifecycleEvents = lifecycleEventRows.slice(-12).reverse();
  const traceCards = buildTraceEntries(selectedNodeId, selected.trace_events || []);
  traceCards.forEach((entry) => {
    entry.open = openTraceKeys.has(entry.key);
  });
  const nextEventSignature = `${selectedNodeId}:${(selected.trace_events || []).length}:${lifecycleEventRows.length}`;
  const shouldAutoScroll = state.detailAutoScroll && state.detailEventSignature !== null && state.detailEventSignature !== nextEventSignature;

  detail.innerHTML = `
    <div class="summary-grid">
      <div class="summary-card"><div class="small">Status</div><strong>${escapeHtml(selected.status || "pending")}</strong></div>
      <div class="summary-card"><div class="small">Current attempt</div><strong>${escapeHtml(String(selected.current_attempt || 0))}</strong></div>
      <div class="summary-card"><div class="small">Exit code</div><strong>${escapeHtml(String(selected.exit_code ?? "-"))}</strong></div>
      <div class="summary-card"><div class="small">Success</div><strong>${escapeHtml(String(selected.success ?? "-"))}</strong></div>
    </div>
    <div class="trace-item">
      <h4>Attempts</h4>
      <div class="summary-grid">${attemptRows || '<div class="small">No attempts yet.</div>'}</div>
    </div>
    <div class="trace-item">
      <h4>Artifact: ${escapeHtml(selectedArtifact)}</h4>
      <div class="output-box">${escapeHtml(artifactText)}</div>
    </div>
    <div class="trace-item">
      <h4>Success checks</h4>
      <div class="output-box">${escapeHtml((selected.success_details || []).join("\n"))}</div>
    </div>
    <div class="trace-item">
      <h4>Trace Timeline</h4>
      <div class="trace-stack">
        ${traceCards.map((entry) => renderTraceCard(entry)).join("") || '<div class="trace-empty">No parsed tool or trace activity yet.</div>'}
      </div>
    </div>
    <div class="trace-item">
      <h4>Lifecycle Events</h4>
      ${lifecycleEvents.map((event) => renderLifecycleEvent(event)).join("") || '<div class="small">No node-specific lifecycle events yet.</div>'}
    </div>
  `;

  state.detailEventSignature = nextEventSignature;
  if (shouldAutoScroll) {
    window.requestAnimationFrame(() => {
      detail.scrollTop = detail.scrollHeight;
    });
  } else if (nodeChanged) {
    window.requestAnimationFrame(() => {
      detail.scrollTop = 0;
    });
  } else {
    window.requestAnimationFrame(() => {
      detail.scrollTop = previousScrollTop;
    });
  }
}

function applyEvent(event) {
  state.events.push(event);
  if (event.type === "run_queued") {
    const run = currentRun();
    if (run) run.status = "queued";
  }
  if (event.type === "run_started") {
    const run = currentRun();
    if (run) run.status = "running";
  }
  if (event.type === "run_cancelling") {
    const run = currentRun();
    if (run) run.status = "cancelling";
  }
  if (event.node_id && !state.nodes[event.node_id]) {
    state.nodes[event.node_id] = { node_id: event.node_id, trace_events: [], attempts: [], status: "pending", current_attempt: 0 };
  }
  if (event.type === "node_started" && event.node_id) {
    state.nodes[event.node_id].status = "running";
  }
  if (event.type === "node_retrying" && event.node_id) {
    state.nodes[event.node_id].status = "retrying";
    state.nodes[event.node_id].current_attempt = event.data.attempt || state.nodes[event.node_id].current_attempt;
    upsertAttempt(state.nodes[event.node_id], event.data.attempt, { status: "retrying" });
  }
  if (event.type === "node_trace" && event.node_id) {
    state.nodes[event.node_id].trace_events ||= [];
    state.nodes[event.node_id].trace_events.push(event.data.trace);
    const attempt = event.data.trace?.attempt;
    if (attempt) state.nodes[event.node_id].current_attempt = attempt;
  }
  if (["node_completed", "node_failed", "node_cancelled"].includes(event.type) && event.node_id) {
    const status = event.type === "node_completed" ? "completed" : event.type === "node_failed" ? "failed" : "cancelled";
    Object.assign(state.nodes[event.node_id], {
      status,
      exit_code: event.data.exit_code,
      success: event.data.success,
      output: event.data.output,
      final_response: event.data.final_response,
      success_details: event.data.success_details,
      current_attempt: event.data.attempt || state.nodes[event.node_id].current_attempt,
    });
    upsertAttempt(state.nodes[event.node_id], event.data.attempt, {
      status,
      exit_code: event.data.exit_code,
      output: event.data.output,
      success: event.data.success,
    });
  }
  if (event.type === "node_skipped" && event.node_id) {
    state.nodes[event.node_id].status = "skipped";
  }
  if (event.type === "run_completed") {
    const run = currentRun();
    if (run) run.status = event.data.status;
  }
  renderRunMeta();
  renderRuns();
  renderGraph();
  renderDetail();
}

function connectStream(runId) {
  if (state.eventSource) state.eventSource.close();
  state.eventSource = new EventSource(`/api/runs/${runId}/stream`);
  state.eventSource.onmessage = (message) => applyEvent(JSON.parse(message.data));
  state.eventSource.onerror = () => {
    if (state.eventSource) state.eventSource.close();
  };
}

async function refreshRuns() {
  state.runs = await api("/api/runs");
  updateTopMetrics();
  renderRuns();
  renderRunMeta();
}

async function openRun(runId) {
  const run = await api(`/api/runs/${runId}`);
  state.runId = run.id;
  state.pipeline = run.pipeline;
  state.nodes = run.nodes;
  state.selectedNodeId = state.selectedNodeId || state.pipeline.nodes?.[0]?.id || null;
  state.events = await api(`/api/runs/${runId}/events`);
  state.artifactCache.clear();
  renderRunMeta();
  renderRuns();
  renderGraph();
  await renderDetail();
  connectStream(run.id);
}

function pipelinePayload() {
  const pipelineText = document.getElementById("pipeline-input").value;
  const baseDir = document.getElementById("pipeline-base-dir").value.trim();
  return baseDir ? { pipeline_text: pipelineText, base_dir: baseDir } : { pipeline_text: pipelineText };
}

async function validatePipeline() {
  const response = await api("/api/runs/validate", { method: "POST", body: JSON.stringify(pipelinePayload()) });
  state.validationPipeline = response.pipeline;
  state.pipeline = null;
  state.nodes = {};
  state.runId = null;
  state.events = [];
  state.selectedNodeId = response.pipeline.nodes?.[0]?.id || null;
  renderRunMeta();
  renderGraph();
  await renderDetail();
  setBanner(`Pipeline validated: ${response.pipeline.name}`, "success");
}

async function runPipeline() {
  const run = await api("/api/runs", { method: "POST", body: JSON.stringify(pipelinePayload()) });
  state.validationPipeline = null;
  await refreshRuns();
  await openRun(run.id);
  setBanner(`Run queued: ${run.id}`, "success");
}

async function cancelRun() {
  if (!state.runId) return;
  await api(`/api/runs/${state.runId}/cancel`, { method: "POST" });
  setBanner(`Cancellation requested for ${state.runId}`, "success");
  await openRun(state.runId);
}

async function rerunRun() {
  if (!state.runId) return;
  const rerun = await api(`/api/runs/${state.runId}/rerun`, { method: "POST" });
  await refreshRuns();
  await openRun(rerun.id);
  setBanner(`Rerun queued: ${rerun.id}`, "success");
}

for (const button of document.querySelectorAll(".artifact-button")) {
  button.onclick = async () => {
    state.selectedArtifact = button.dataset.artifact;
    await renderDetail();
  };
}

document.getElementById("load-example").onclick = async () => {
  const data = await api("/api/examples/default");
  document.getElementById("pipeline-input").value = data.example;
  document.getElementById("pipeline-base-dir").value = data.base_dir || "";
  setBanner(null);
};

document.getElementById("validate-pipeline").onclick = () => validatePipeline().catch((error) => setBanner(error.message, "error"));
document.getElementById("run-pipeline").onclick = () => runPipeline().catch((error) => setBanner(error.message, "error"));
document.getElementById("cancel-run").onclick = () => cancelRun().catch((error) => setBanner(error.message, "error"));
document.getElementById("rerun-run").onclick = () => rerunRun().catch((error) => setBanner(error.message, "error"));
document.getElementById("refresh-runs").onclick = () => refreshRuns().catch((error) => setBanner(error.message, "error"));
document.getElementById("run-search").oninput = renderRuns;

refreshRuns()
  .then(async () => {
    if (state.runs[0]) await openRun(state.runs[0].id);
  })
  .catch((error) => setBanner(error.message, "error"));
