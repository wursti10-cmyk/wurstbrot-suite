import {calculate, validateDatabase} from "./solver.mjs";
import {
  BRANCH_LABELS,
  BRANCH_ORDER,
  COUNTRY_LABELS,
  buildVisualTreeHighlight,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "./visual-tree.mjs";

const $ = id => document.getElementById(id);
const format = value => new Intl.NumberFormat("de-DE").format(value);
const fallbackLabel = value => value
  .replace(/^country_/, "")
  .replaceAll("_", " ")
  .replace(/\b\p{L}/gu, character => character.toLocaleUpperCase("de-DE"));
let database;
let currentTreeLayout = null;
let currentTreeHighlight = null;
let treeRenderSequence = 0;
let resizeFrame = 0;

function vehicles() { return database?.vehicles || []; }

function setOptions(select, items, label = value => value.name ?? value) {
  select.replaceChildren(...items.map(value => new Option(label(value), value.id ?? value)));
}

function refreshBranches() {
  const branches = [...new Set(vehicles()
    .filter(vehicle => vehicle.countryId === $("country").value)
    .map(vehicle => vehicle.branchId))].sort();
  setOptions($("branch"), branches.map(id => ({
    id,
    name: BRANCH_LABELS[id] ?? fallbackLabel(id),
  })));
  refreshVehicles();
}

function refreshVehicles() {
  const list = vehicles()
    .filter(vehicle => vehicle.countryId === $("country").value
      && vehicle.branchId === $("branch").value && !vehicle.hiddenResearch)
    .sort((a, b) => a.rank - b.rank || a.order - b.order || a.name.localeCompare(b.name));
  const title = vehicle => `Rang ${vehicle.rank} · ${vehicle.name || vehicle.id}`;
  setOptions($("start"), [{id: "", name: "Forschungsbaum"}, ...list],
    vehicle => vehicle.id ? title(vehicle) : vehicle.name);
  setOptions($("target"), list, title);
  if (list.length) $("target").value = list.at(-1).id;
}

function load(raw) {
  database = validateDatabase(raw);
  const countries = [...new Set(vehicles().map(vehicle => vehicle.countryId))].sort();
  setOptions($("country"), countries.map(id => ({
    id,
    name: COUNTRY_LABELS[id] ?? fallbackLabel(id),
  })));
  refreshBranches();
  refreshTreeSelectors();
  $("status").textContent = `${database.gameVersion} · ${format(vehicles().length)} Fahrzeuge`;
  if (!$("tree-view").hidden) refreshVisualTree();
}

function refreshTreeSelectors() {
  const countries = [...new Set(vehicles().map(vehicle => vehicle.countryId))].sort();
  const selectedCountry = countries.includes($("tree-country").value)
    ? $("tree-country").value
    : countries.includes("country_germany") ? "country_germany" : countries[0];
  setOptions($("tree-country"), countries.map(id => ({
    id,
    name: COUNTRY_LABELS[id] ?? fallbackLabel(id),
  })));
  $("tree-country").value = selectedCountry || "";

  const selectedBranch = BRANCH_ORDER.includes($("tree-branch").value)
    ? $("tree-branch").value : "army";
  setOptions($("tree-branch"), BRANCH_ORDER.map(id => ({id, name: BRANCH_LABELS[id]})));
  $("tree-branch").value = selectedBranch;
}

function treeDemoResult(countryId, branchId) {
  if (countryId !== "country_germany" || branchId !== "army") return null;
  const ids = new Set(vehicles().map(vehicle => vehicle.id));
  const startId = "germ_pzkpfw_VI_ausf_h1_tiger";
  const targetId = "germ_leopard_2a7v";
  if (!ids.has(startId) || !ids.has(targetId)) return null;
  return calculate(database, {
    startId,
    targetId,
    progress: {vehicles: {}, ownedGe: 0, convertibleRp: null},
    slDiscount: 0,
    optimizeFor: "ge",
  });
}

function updateTreeHeader(layout, countryId, branchId) {
  const country = COUNTRY_LABELS[countryId] ?? fallbackLabel(countryId);
  const branch = BRANCH_LABELS[branchId] ?? fallbackLabel(branchId);
  $("tree-heading").textContent = `${country} · ${branch}`;
  if (!layout) {
    $("tree-status").textContent = "In der geladenen Datenbank nicht verfügbar";
    $("tree-metrics").replaceChildren();
    return;
  }
  $("tree-status").textContent = `${layout.game_version} · stabiler VT.1-Layout-Contract`;
  const values = [
    `${format(layout.nodes.length)} Fahrzeuge`,
    `${layout.ranks.length} Ränge`,
    `${layout.columns.length} Spalten`,
    `${layout.folders.length} Folder`,
  ];
  $("tree-metrics").replaceChildren(...values.map(value => {
    const badge = document.createElement("span");
    badge.textContent = value;
    return badge;
  }));
}

async function refreshVisualTree() {
  if (!database) return;
  const sequence = ++treeRenderSequence;
  const countryId = $("tree-country").value;
  const branchId = $("tree-branch").value;
  $("tree-status").textContent = "Layout wird aufgebaut …";
  try {
    const layout = await buildVisualTreeLayout(database, {countryId, branchId});
    if (sequence !== treeRenderSequence) return;
    const result = layout ? treeDemoResult(countryId, branchId) : null;
    const highlight = result ? await buildVisualTreeHighlight(layout, result, {
      userResultSource: "legacy",
      calculationStatus: "complete",
    }) : null;
    if (sequence !== treeRenderSequence) return;

    currentTreeLayout = layout;
    currentTreeHighlight = highlight;
    $("tree-demo").hidden = !highlight;
    const visualTree = $("visual-tree");
    visualTree.classList.toggle("has-highlight", Boolean(highlight));
    visualTree.style.setProperty("--active-columns", layout
      ? String(Math.max(...layout.columns) + 1) : "1");
    $("tree-content").innerHTML = renderTreeMarkup(layout, highlight);
    updateTreeHeader(layout, countryId, branchId);
    requestAnimationFrame(drawConnections);
  } catch (error) {
    if (sequence !== treeRenderSequence) return;
    currentTreeLayout = null;
    currentTreeHighlight = null;
    $("tree-demo").hidden = true;
    $("tree-content").innerHTML = renderTreeMarkup(null);
    $("tree-status").textContent = `Fehler: ${error.message}`;
    $("tree-connections").replaceChildren();
  }
}

function drawConnections() {
  const svg = $("tree-connections");
  const tree = $("visual-tree");
  if (!currentTreeLayout || $("tree-view").hidden) {
    svg.replaceChildren();
    return;
  }
  const origin = tree.getBoundingClientRect();
  const elements = new Map([...tree.querySelectorAll("[data-vehicle-id]")]
    .map(element => [element.dataset.vehicleId, element]));
  const rectangles = new Map([...elements].map(([vehicleId, element]) => (
    [vehicleId, element.getBoundingClientRect()]
  )));
  const required = new Set(currentTreeHighlight?.required_edge_ids || []);
  const fragment = document.createDocumentFragment();
  svg.setAttribute("viewBox", `0 0 ${origin.width} ${origin.height}`);
  for (const edge of currentTreeLayout.edges) {
    const from = rectangles.get(edge.source_vehicle_id);
    const to = rectangles.get(edge.target_vehicle_id);
    if (!from || !to) continue;
    const x1 = from.left + from.width / 2 - origin.left;
    const y1 = from.bottom - origin.top;
    const x2 = to.left + to.width / 2 - origin.left;
    const y2 = to.top - origin.top;
    const middle = (y1 + y2) / 2;
    const edgeId = `${edge.source_vehicle_id}->${edge.target_vehicle_id}`;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1} ${middle}, ${x2} ${middle}, ${x2} ${y2}`);
    path.setAttribute("class", required.has(edgeId) ? "tree-edge required" : "tree-edge");
    path.dataset.edgeId = edgeId;
    fragment.append(path);
  }
  svg.replaceChildren(fragment);
}

function showView(view) {
  const treeActive = view === "tree";
  $("calculator-view").hidden = treeActive;
  $("tree-view").hidden = !treeActive;
  $("calculator-tab").classList.toggle("active", !treeActive);
  $("tree-tab").classList.toggle("active", treeActive);
  $("calculator-tab").setAttribute("aria-selected", String(!treeActive));
  $("tree-tab").setAttribute("aria-selected", String(treeActive));
  if (treeActive) refreshVisualTree();
}

function metric(value, label) {
  const box = document.createElement("div");
  box.className = "metric";
  const strong = document.createElement("strong");
  strong.textContent = value;
  box.append(strong, document.createTextNode(label));
  return box;
}

function render(result) {
  const summary = $("summary");
  summary.classList.remove("empty");
  summary.replaceChildren(
    metric(`${format(result.totalGe)} GE`, "benötigt"),
    metric(`${format(result.totalRp)} RP`, "noch offen"),
    metric(`${format(result.totalSl)} SL`, "Kaufkosten"),
  );

  const ranks = $("rank-requirements");
  ranks.replaceChildren();
  if (result.rankRequirements.length) {
    const heading = document.createElement("h3");
    heading.textContent = "Rangfreischaltungen";
    ranks.append(heading);
    for (const rank of result.rankRequirements) {
      const row = document.createElement("p");
      row.textContent = `Rang ${rank.rank + 1}: ${rank.availableAfter}/${rank.required}`;
      ranks.append(row);
    }
  }

  const explanation = $("explanation");
  explanation.replaceChildren();
  if (!result.lines.length) {
    const empty = document.createElement("p");
    empty.textContent = "Das Ziel ist bereits erreicht.";
    explanation.append(empty);
  }
  for (const line of result.lines) {
    const row = document.createElement("div");
    row.className = "vehicle";
    const name = document.createElement("span");
    name.textContent = `${line.name} · ${line.reason}`;
    const costs = document.createElement("span");
    costs.textContent = `${format(line.remainingRp)} RP · ${format(line.ge)} GE`;
    row.append(name, costs);
    explanation.append(row);
  }

  const warnings = $("warnings");
  warnings.replaceChildren();
  if (result.convertibleRpShortfall) {
    const warning = document.createElement("p");
    warning.textContent = `Fehlende Convertible RP: ${format(result.convertibleRpShortfall)}`;
    warnings.append(warning);
  }
  for (const message of result.warnings) {
    const warning = document.createElement("p");
    warning.textContent = `Warnung: ${message}`;
    warnings.append(warning);
  }
}

$("country").addEventListener("change", refreshBranches);
$("branch").addEventListener("change", refreshVehicles);
$("calculator-tab").addEventListener("click", () => showView("calculator"));
$("tree-tab").addEventListener("click", () => showView("tree"));
$("tree-country").addEventListener("change", refreshVisualTree);
$("tree-branch").addEventListener("change", refreshVisualTree);
$("database-file").addEventListener("change", async event => {
  try { load(JSON.parse(await event.target.files[0].text())); }
  catch (error) { alert(error.message); }
});

window.addEventListener("resize", () => {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(drawConnections);
});
$("calculate").addEventListener("click", () => {
  try {
    const convertibleText = $("convertible-rp").value.trim();
    const targetId = $("target").value;
    render(calculate(database, {
      startId: $("start").value || null,
      targetId,
      progress: {
        vehicles: {[targetId]: {researchedRp: Number($("partial-rp").value) || 0}},
        ownedGe: Number($("owned-ge").value) || 0,
        convertibleRp: convertibleText === "" ? null : Number(convertibleText),
      },
      slDiscount: Number($("discount").value),
      optimizeFor: $("optimize").value,
    }));
  } catch (error) { alert(error.message); }
});
$("copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText(
    `${$("summary").innerText}\n${$("rank-requirements").innerText}\n${$("explanation").innerText}\n${$("warnings").innerText}`,
  );
  $("copy").textContent = "Kopiert";
  setTimeout(() => { $("copy").textContent = "Kopieren"; }, 1200);
});

fetch("../../data/samples/WT_Database_2.57.1.67.json")
  .then(response => {
    if (!response.ok) throw new Error("Beispieldatenbank konnte nicht geladen werden.");
    return response.json();
  })
  .then(load)
  .catch(() => { $("status").textContent = "Bitte Datenbank auswählen"; });

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  navigator.serviceWorker.register("service-worker.js");
}
