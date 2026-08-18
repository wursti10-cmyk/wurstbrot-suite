const tree = document.getElementById("tree");
const svg = document.getElementById("connections");

const cssState = state => state.replaceAll("_", "-");

function vehicleNode(node, states) {
  const element = document.createElement("article");
  element.className = `vehicle ${states.map(cssState).join(" ")}`;
  element.dataset.vehicleId = node.vehicle_id;
  const name = document.createElement("strong");
  name.textContent = node.name;
  const details = document.createElement("small");
  const folder = node.group_id ? ` · ${node.group_id} #${node.group_index + 1}` : "";
  details.textContent = `${node.vehicle_id}${folder}`;
  element.append(name, details);
  return element;
}

function renderLayout(data) {
  const {layout, highlight, prototype: metadata} = data;
  document.getElementById("start-label").textContent = metadata.startLabel;
  document.getElementById("target-label").textContent = metadata.targetLabel;
  document.getElementById("source-label").textContent = highlight.user_result_source;
  document.getElementById("calculation-label").textContent = highlight.complete
    ? highlight.calculation_status
    : `${highlight.calculation_status} · nicht vollständig`;
  document.getElementById("status").textContent = `${layout.game_version} · ${layout.nodes.length} Fahrzeuge`;

  const columns = Math.max(...layout.columns) + 1;
  for (const rank of layout.ranks) {
    const band = document.createElement("section");
    band.className = "rank-band";
    const title = document.createElement("div");
    title.className = "rank-title";
    title.textContent = `Rang ${rank}`;
    const grid = document.createElement("div");
    grid.className = "rank-grid";
    grid.style.setProperty("--columns", columns);

    for (let column = 0; column < columns; column += 1) {
      const container = document.createElement("div");
      container.className = "tree-column";
      const nodes = layout.nodes
        .filter(node => node.rank === rank && node.column === column)
        .sort((left, right) => left.visual_slot - right.visual_slot);
      for (const node of nodes) {
        container.append(vehicleNode(node, highlight.node_states[node.vehicle_id]));
      }
      grid.append(container);
    }
    band.append(title, grid);
    tree.append(band);
  }

  requestAnimationFrame(() => drawConnections(layout, highlight));
}

function drawConnections(layout, highlight) {
  const origin = tree.getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${origin.width} ${origin.height}`);
  const required = new Set(highlight.required_edge_ids);
  for (const edge of layout.edges) {
    const source = tree.querySelector(`[data-vehicle-id="${CSS.escape(edge.source_vehicle_id)}"]`);
    const target = tree.querySelector(`[data-vehicle-id="${CSS.escape(edge.target_vehicle_id)}"]`);
    if (!source || !target) continue;
    const from = source.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    const x1 = from.left + from.width / 2 - origin.left;
    const y1 = from.bottom - origin.top;
    const x2 = to.left + to.width / 2 - origin.left;
    const y2 = to.top - origin.top;
    const middle = (y1 + y2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const edgeId = `${edge.source_vehicle_id}->${edge.target_vehicle_id}`;
    path.setAttribute("d", `M ${x1} ${y1} C ${x1} ${middle}, ${x2} ${middle}, ${x2} ${y2}`);
    path.setAttribute("class", required.has(edgeId) ? "edge required" : "edge");
    path.dataset.edgeId = edgeId;
    svg.append(path);
  }
}

fetch("germany-army.json")
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(renderLayout)
  .catch(error => {
    document.getElementById("status").textContent = `Fehler: ${error.message}`;
  });
