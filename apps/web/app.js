import {calculate, validateDatabase} from "./solver.mjs";
import {
  BRANCH_LABELS,
  BRANCH_ORDER,
  COUNTRY_LABELS,
  buildVisualTreeHighlight,
  buildVisualTreeLayout,
  renderTreeMarkup,
} from "./visual-tree.mjs";
import {
  attachTreeAbResult,
  buildTreeAbSelectionHighlight,
  buildVehicleSearchIndex,
  changeTreeZoom,
  clampTreeScrollPosition,
  connectionGeometry,
  createTreeAbState,
  findVehicleSearchEntry,
  panScrollPosition,
  pointerMovementExceedsThreshold,
  resetTreeAbState,
  searchVehicleIndex,
  selectedDirectEdgeIds,
  selectedVehicleDetails,
  setTreeAbEndpoint,
  treeAbMatchesLayout,
  treeAbTreeKey,
  treeResultPresentation,
} from "./visual-tree-interaction.mjs";

const $ = id => document.getElementById(id);
const format = value => new Intl.NumberFormat("de-DE").format(value);
const fallbackLabel = value => value
  .replace(/^country_/, "")
  .replaceAll("_", " ")
  .replace(/\b\p{L}/gu, character => character.toLocaleUpperCase("de-DE"));
let database;
let currentTreeLayout = null;
let currentTreeHighlight = null;
let vehicleSearchIndex = [];
let selectedTreeVehicleId = null;
let treeZoom = 1;
let panState = null;
let treeRenderSequence = 0;
let resizeFrame = 0;
let treeAbState = createTreeAbState();

function vehicles() { return database?.vehicles || []; }

function setOptions(select, items, label = value => value.name ?? value) {
  select.replaceChildren(...items.map(value => new Option(label(value), value.id ?? value)));
}

function refreshBranches({preserveSelection = false} = {}) {
  const previousBranch = preserveSelection ? $("branch").value : null;
  const branches = [...new Set(vehicles()
    .filter(vehicle => vehicle.countryId === $("country").value)
    .map(vehicle => vehicle.branchId))].sort();
  setOptions($("branch"), branches.map(id => ({
    id,
    name: BRANCH_LABELS[id] ?? fallbackLabel(id),
  })));
  if (previousBranch && branches.includes(previousBranch)) $("branch").value = previousBranch;
  refreshVehicles({preserveSelection});
}

function refreshVehicles({preserveSelection = false} = {}) {
  const previousStart = preserveSelection ? $("start").value : null;
  const previousTarget = preserveSelection ? $("target").value : null;
  const list = vehicles()
    .filter(vehicle => vehicle.countryId === $("country").value
      && vehicle.branchId === $("branch").value && !vehicle.hiddenResearch)
    .sort((a, b) => a.rank - b.rank || a.order - b.order || a.name.localeCompare(b.name));
  const title = vehicle => `Rang ${vehicle.rank} · ${vehicle.name || vehicle.id}`;
  setOptions($("start"), [{id: "", name: "Forschungsbaum"}, ...list],
    vehicle => vehicle.id ? title(vehicle) : vehicle.name);
  setOptions($("target"), [{id: "", name: "Ziel wählen"}, ...list],
    vehicle => vehicle.id ? title(vehicle) : vehicle.name);
  if (previousStart && list.some(vehicle => vehicle.id === previousStart)) {
    $("start").value = previousStart;
  }
  if (previousTarget && list.some(vehicle => vehicle.id === previousTarget)) {
    $("target").value = previousTarget;
  } else if (!preserveSelection && list.length) {
    $("target").value = list.at(-1).id;
  }
}

function load(raw) {
  database = validateDatabase(raw);
  vehicleSearchIndex = buildVehicleSearchIndex(database);
  const countries = [...new Set(vehicles().map(vehicle => vehicle.countryId))].sort();
  setOptions($("country"), countries.map(id => ({
    id,
    name: COUNTRY_LABELS[id] ?? fallbackLabel(id),
  })));
  refreshBranches();
  $("target").value = "";
  treeAbState = resetTreeAbState();
  refreshTreeSelectors();
  $("status").textContent = `${database.gameVersion} · ${format(vehicles().length)} Fahrzeuge`;
  $("tree-search-count").textContent = `${format(vehicleSearchIndex.length)} Fahrzeuge indexiert`;
  renderSearchResults("");
  renderTreeAbState();
  if (!$("tree-view").hidden) refreshVisualTree({resetNavigation: true});
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

function setSearchResultsOpen(open) {
  $("tree-search-results").hidden = !open;
  $("tree-search-input").setAttribute("aria-expanded", String(open));
}

function renderSearchResults(query) {
  const container = $("tree-search-results");
  container.replaceChildren();
  const results = searchVehicleIndex(vehicleSearchIndex, query);
  if (!query.trim()) {
    setSearchResultsOpen(false);
    return;
  }
  if (!results.length) {
    const empty = document.createElement("p");
    empty.className = "tree-search-empty";
    empty.textContent = "Keine Fahrzeuge gefunden.";
    container.append(empty);
    setSearchResultsOpen(true);
    return;
  }
  for (const entry of results) {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "tree-search-result";
    option.dataset.searchVehicleId = entry.vehicle_id;
    option.setAttribute("role", "option");
    const name = document.createElement("strong");
    name.textContent = entry.name;
    const context = document.createElement("span");
    context.textContent = `${entry.country_label} · ${entry.branch_label} · Rang ${entry.rank}`;
    const identity = document.createElement("span");
    identity.textContent = `ID: ${entry.vehicle_id}`;
    option.append(name, context, identity);
    container.append(option);
  }
  setSearchResultsOpen(true);
}

function detailRow(label, value, className = "") {
  const row = document.createElement("div");
  if (className) row.className = className;
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = value;
  row.append(term, detail);
  return row;
}

function renderSelectedVehicleDetails(vehicleId) {
  const details = selectedVehicleDetails(database, currentTreeLayout, vehicleId);
  const container = $("tree-selection-details");
  const empty = $("tree-selection-empty");
  container.replaceChildren();
  if (!details) {
    container.hidden = true;
    empty.hidden = false;
    $("tree-selection-actions").hidden = true;
    return;
  }
  const folderMembership = details.group_id
    ? `${details.group_index + 1} von ${details.folder_declared_member_count} (Darstellungsmetadatum)`
    : "–";
  const folderData = details.folder_data_incomplete
    ? `Unvollständig · ${details.folder_missing_member_count} deklarierte Mitglieder nicht verfügbar`
    : details.group_id ? "Vollständig im produktiven Datensatz" : "–";
  container.append(
    detailRow("Fahrzeug", details.name),
    detailRow("Nation", details.country),
    detailRow("Fahrzeugart", details.branch),
    detailRow("Rang", String(details.rank)),
    detailRow("RP", format(details.rp)),
    detailRow("SL", format(details.sl)),
    detailRow("Folder/Gruppe", details.group_id || "–"),
    detailRow("Folder-Position", folderMembership),
    detailRow(
      "Folder-Daten",
      folderData,
      details.folder_data_incomplete ? "folder-data-incomplete" : "",
    ),
    detailRow("Sichtbarkeit", details.hidden_research ? "Hidden (Altbestand)" : "Normal sichtbar"),
    detailRow(
      "Status",
      details.partial_unresolved ? "Partial / unresolved" : "Vollständig dargestellt",
      details.partial_unresolved ? "partial-unresolved" : "",
    ),
  );
  empty.hidden = true;
  container.hidden = false;
  $("tree-selection-actions").hidden = false;
}

function vehicleLabel(vehicleId, emptyLabel = "Nicht gewählt") {
  if (!vehicleId) return emptyLabel;
  const vehicle = vehicles().find(item => item.id === vehicleId);
  return vehicle?.name || vehicleId;
}

function setTreeAbMessage(message, tone = "") {
  const element = $("tree-ab-message");
  element.textContent = message;
  element.className = `tree-ab-message${tone ? ` ${tone}` : ""}`;
}

function renderTreeAbState() {
  $("tree-ab-start").textContent = vehicleLabel(treeAbState.startId);
  $("tree-ab-target").textContent = vehicleLabel(treeAbState.targetId);
  $("tree-calculate").disabled = !(treeAbState.startId && treeAbState.targetId);
  $("tree-reset").disabled = !(treeAbState.startId || treeAbState.targetId || treeAbState.result);
  $("tree-details-calculator").hidden = !treeAbState.result;
  const summary = $("tree-result-summary");
  if (!treeAbState.result) {
    summary.hidden = true;
    return;
  }
  const presentation = treeResultPresentation(database, treeAbState.result);
  $("tree-result-route").textContent = `${presentation.start_name} → ${presentation.target_name}`;
  $("tree-result-values").textContent = `${format(presentation.vehicle_count)} Fahrzeuge · ${format(presentation.total_rp)} RP · ${format(presentation.total_sl)} SL · ${format(presentation.total_ge)} GE`;
  const status = presentation.calculation_status === "partial" ? "Partial / unresolved" : "Complete";
  const fallback = treeAbState.fallbackReason ? " · Sichtbarer Legacy-Fallback" : "";
  $("tree-result-meta").textContent = `${status} · Legacy-Ergebnis${fallback} · Details im Rechner`;
  summary.hidden = false;
}

function setCalculatorTree(countryId, branchId, startId = null, targetId = null) {
  $("country").value = countryId;
  refreshBranches();
  $("branch").value = branchId;
  refreshVehicles();
  if (startId && [...$("start").options].some(option => option.value === startId)) {
    $("start").value = startId;
  }
  if (targetId && [...$("target").options].some(option => option.value === targetId)) {
    $("target").value = targetId;
  } else {
    $("target").value = "";
  }
}

function syncCalculatorFromTreeState() {
  const vehicleId = treeAbState.targetId || treeAbState.startId;
  const vehicle = vehicles().find(item => item.id === vehicleId);
  if (!vehicle) return;
  setCalculatorTree(
    vehicle.countryId,
    vehicle.branchId,
    treeAbState.startId,
    treeAbState.targetId,
  );
}

function updateTreeAbFromCalculator() {
  let next = resetTreeAbState();
  if ($("start").value) next = setTreeAbEndpoint(database, next, "start", $("start").value);
  if ($("target").value) next = setTreeAbEndpoint(database, next, "target", $("target").value);
  treeAbState = next;
  renderTreeAbState();
}

function resetTreeAb({message = "A/B-Auswahl zurückgesetzt."} = {}) {
  treeAbState = resetTreeAbState();
  currentTreeHighlight = null;
  $("start").value = "";
  $("target").value = "";
  renderTreeAbState();
  setTreeAbMessage(message);
  if (!$("tree-view").hidden) {
    void refreshVisualTree({selectVehicleId: selectedTreeVehicleId});
  }
}

function setSelectedTreeEndpoint(role) {
  if (!selectedTreeVehicleId) return;
  try {
    treeAbState = setTreeAbEndpoint(database, treeAbState, role, selectedTreeVehicleId);
    syncCalculatorFromTreeState();
    renderTreeAbState();
    setTreeAbMessage(
      `${vehicleLabel(selectedTreeVehicleId)} ist jetzt ${role === "start" ? "Start A" : "Ziel B"}.`,
      "success",
    );
    void refreshVisualTree({selectVehicleId: selectedTreeVehicleId});
  } catch (error) {
    setTreeAbMessage(error.message, "error");
  }
}

function clearTreeSelection() {
  for (const card of $("tree-content").querySelectorAll(".tree-vehicle.selected, .tree-vehicle.search-target")) {
    card.classList.remove("selected", "search-target");
    card.setAttribute("aria-pressed", "false");
  }
  selectedTreeVehicleId = null;
  renderSelectedVehicleDetails(null);
  requestAnimationFrame(drawConnections);
}

function jumpToTreeVehicle(vehicleId, {focus = true} = {}) {
  const escaped = CSS.escape(vehicleId);
  const cards = $("tree-content").querySelectorAll(`[data-vehicle-id="${escaped}"]`);
  if (cards.length !== 1) throw new Error(`Fahrzeugkarte nicht eindeutig: ${vehicleId}`);
  const card = cards[0];
  card.scrollIntoView({behavior: "smooth", block: "center", inline: "center"});
  if (focus) card.focus({preventScroll: true});
  return card;
}

function selectTreeVehicle(vehicleId, {fromSearch = false, jump = false, focus = false} = {}) {
  const card = $("tree-content").querySelector(`[data-vehicle-id="${CSS.escape(vehicleId)}"]`);
  if (!card) return false;
  clearTreeSelection();
  selectedTreeVehicleId = vehicleId;
  card.classList.add("selected");
  card.classList.toggle("search-target", fromSearch);
  card.setAttribute("aria-pressed", "true");
  renderSelectedVehicleDetails(vehicleId);
  requestAnimationFrame(drawConnections);
  if (jump) jumpToTreeVehicle(vehicleId, {focus});
  return true;
}

function setTreeZoom(nextZoom, {preserveCenter = true} = {}) {
  const viewport = $("tree-viewport");
  const previous = treeZoom;
  treeZoom = nextZoom;
  $("visual-tree").style.zoom = String(treeZoom);
  $("tree-zoom-value").textContent = `${Math.round(treeZoom * 100)} %`;
  if (preserveCenter && previous !== treeZoom) {
    const factor = treeZoom / previous;
    viewport.scrollLeft = (viewport.scrollLeft + viewport.clientWidth / 2) * factor
      - viewport.clientWidth / 2;
    viewport.scrollTop = (viewport.scrollTop + viewport.clientHeight / 2) * factor
      - viewport.clientHeight / 2;
  }
  scheduleTreeGeometryRefresh();
}

function clampTreeViewportScroll() {
  const viewport = $("tree-viewport");
  const next = clampTreeScrollPosition(
    {left: viewport.scrollLeft, top: viewport.scrollTop},
    viewport,
  );
  if (next.left !== viewport.scrollLeft || next.top !== viewport.scrollTop) {
    viewport.scrollTo({...next, behavior: "auto"});
  }
}

function scheduleTreeGeometryRefresh() {
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => {
    clampTreeViewportScroll();
    drawConnections();
  });
}

function resetTreeNavigation() {
  clearTreeSelection();
  setTreeZoom(1, {preserveCenter: false});
  $("tree-viewport").scrollTo({left: 0, top: 0, behavior: "auto"});
}

async function activateSearchResult(vehicleId) {
  const entry = findVehicleSearchEntry(vehicleSearchIndex, vehicleId);
  if (!entry) return;
  $("tree-search-input").value = entry.name;
  setSearchResultsOpen(false);
  const changed = $("tree-country").value !== entry.country_id
    || $("tree-branch").value !== entry.branch_id;
  if (changed && (treeAbState.startId || treeAbState.targetId || treeAbState.result)) {
    treeAbState = resetTreeAbState();
    $("start").value = "";
    $("target").value = "";
    renderTreeAbState();
    setTreeAbMessage("A/B-Auswahl wegen Forschungsbaumwechsel zurückgesetzt.");
  }
  $("tree-country").value = entry.country_id;
  $("tree-branch").value = entry.branch_id;
  showView("tree", {refresh: false});
  if (changed || !currentTreeLayout
    || currentTreeLayout.country_id !== entry.country_id
    || currentTreeLayout.branch_id !== entry.branch_id) {
    await refreshVisualTree({
      resetNavigation: true,
      selectVehicleId: vehicleId,
      selectFromSearch: true,
    });
  } else {
    selectTreeVehicle(vehicleId, {fromSearch: true, jump: true, focus: true});
  }
}

function calculatorInput({startId = $("start").value || null, targetId = $("target").value} = {}) {
  const convertibleText = $("convertible-rp").value.trim();
  return {
    startId,
    targetId,
    progress: {
      vehicles: {[targetId]: {researchedRp: Number($("partial-rp").value) || 0}},
      ownedGe: Number($("owned-ge").value) || 0,
      convertibleRp: convertibleText === "" ? null : Number(convertibleText),
    },
    slDiscount: Number($("discount").value),
    optimizeFor: $("optimize").value,
  };
}

async function executeCalculation({origin}) {
  const input = origin === "tree"
    ? calculatorInput({startId: treeAbState.startId, targetId: treeAbState.targetId})
    : calculatorInput();
  const authoritativeTreeState = treeAbState;
  if (origin === "tree") syncCalculatorFromTreeState();
  else updateTreeAbFromCalculator();
  if (origin === "tree") treeAbState = authoritativeTreeState;
  if (!treeAbState.targetId) throw new Error("Bitte Ziel B auswählen.");
  const result = calculate(database, input);
  const presentation = treeResultPresentation(database, result);
  treeAbState = attachTreeAbResult(treeAbState, result, {
    userResultSource: "legacy",
    calculationStatus: presentation.calculation_status,
    fallbackReason: presentation.calculation_status === "partial"
      ? "known_partial_legacy_fallback" : null,
  });
  render(result);
  renderTreeAbState();
  setTreeAbMessage(
    presentation.calculation_status === "partial"
      ? "Legacy-Ergebnis ist partial; der sichtbare Fallback-Status bleibt erhalten."
      : "Legacy-Ergebnis erfolgreich im Forschungsbaum dargestellt.",
    presentation.calculation_status === "partial" ? "" : "success",
  );
  const resultTreeKey = treeAbTreeKey(database, treeAbState);
  if (resultTreeKey) {
    const [countryId, branchId] = resultTreeKey.split("/");
    $("tree-country").value = countryId;
    $("tree-branch").value = branchId;
  }
  if (!$("tree-view").hidden) {
    await refreshVisualTree({selectVehicleId: selectedTreeVehicleId || treeAbState.targetId});
  }
  return result;
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

async function refreshVisualTree({
  resetNavigation = false,
  selectVehicleId = null,
  selectFromSearch = false,
} = {}) {
  if (!database) return;
  if (resetNavigation) resetTreeNavigation();
  const sequence = ++treeRenderSequence;
  const countryId = $("tree-country").value;
  const branchId = $("tree-branch").value;
  $("tree-status").textContent = "Layout wird aufgebaut …";
  try {
    const layout = await buildVisualTreeLayout(database, {countryId, branchId});
    if (sequence !== treeRenderSequence) return;
    let highlight = layout ? buildTreeAbSelectionHighlight(layout, treeAbState) : null;
    let hasSolverHighlight = false;
    if (layout && treeAbState.result && treeAbMatchesLayout(database, treeAbState, layout)) {
      const presentation = treeResultPresentation(database, treeAbState.result);
      highlight = await buildVisualTreeHighlight(layout, treeAbState.result, {
        userResultSource: treeAbState.userResultSource,
        calculationStatus: treeAbState.calculationStatus,
        fallbackReason: treeAbState.fallbackReason,
        unresolvedVehicleIds: presentation.partial_vehicle_ids,
      });
      hasSolverHighlight = true;
    }
    if (sequence !== treeRenderSequence) return;

    currentTreeLayout = layout;
    currentTreeHighlight = highlight;
    const visualTree = $("visual-tree");
    visualTree.classList.toggle("has-highlight", hasSolverHighlight);
    visualTree.style.setProperty("--active-columns", layout
      ? String(Math.max(...layout.columns) + 1) : "1");
    $("tree-content").innerHTML = renderTreeMarkup(layout, highlight);
    updateTreeHeader(layout, countryId, branchId);
    requestAnimationFrame(() => {
      drawConnections();
      if (selectVehicleId) {
        selectTreeVehicle(selectVehicleId, {
          fromSearch: selectFromSearch,
          jump: selectFromSearch,
          focus: selectFromSearch,
        });
      }
    });
  } catch (error) {
    if (sequence !== treeRenderSequence) return;
    currentTreeLayout = null;
    currentTreeHighlight = null;
    $("visual-tree").classList.remove("has-highlight");
    $("tree-content").innerHTML = renderTreeMarkup(null);
    $("tree-status").textContent = `Fehler: ${error.message}`;
    $("tree-connections").replaceChildren();
    clearTreeSelection();
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
  const selectedDirect = new Set(selectedDirectEdgeIds(currentTreeLayout, selectedTreeVehicleId));
  const fragment = document.createDocumentFragment();
  svg.setAttribute("viewBox", `0 0 ${origin.width} ${origin.height}`);
  for (const edge of currentTreeLayout.edges) {
    const from = rectangles.get(edge.source_vehicle_id);
    const to = rectangles.get(edge.target_vehicle_id);
    if (!from || !to) continue;
    const {x1, y1, x2, y2, middle} = connectionGeometry(origin, from, to);
    const edgeId = `${edge.source_vehicle_id}->${edge.target_vehicle_id}`;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1} ${middle}, ${x2} ${middle}, ${x2} ${y2}`);
    const edgeClasses = ["tree-edge"];
    if (required.has(edgeId)) edgeClasses.push("required");
    if (selectedDirect.has(edgeId)) edgeClasses.push("selected-direct");
    path.setAttribute("class", edgeClasses.join(" "));
    path.dataset.edgeId = edgeId;
    fragment.append(path);
  }
  svg.replaceChildren(fragment);
}

function showView(view, {refresh = true} = {}) {
  const treeActive = view === "tree";
  $("calculator-view").hidden = treeActive;
  $("tree-view").hidden = !treeActive;
  $("calculator-tab").classList.toggle("active", !treeActive);
  $("tree-tab").classList.toggle("active", treeActive);
  $("calculator-tab").setAttribute("aria-selected", String(!treeActive));
  $("tree-tab").setAttribute("aria-selected", String(treeActive));
  if (!treeActive) {
    syncCalculatorFromTreeState();
    if (treeAbState.result) render(treeAbState.result);
  }
  if (treeActive && refresh) refreshVisualTree({selectVehicleId: selectedTreeVehicleId});
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

$("country").addEventListener("change", () => {
  refreshBranches();
  updateTreeAbFromCalculator();
});
$("branch").addEventListener("change", () => {
  refreshVehicles();
  updateTreeAbFromCalculator();
});
$("start").addEventListener("change", updateTreeAbFromCalculator);
$("target").addEventListener("change", updateTreeAbFromCalculator);
$("calculator-tab").addEventListener("click", () => showView("calculator"));
$("tree-tab").addEventListener("click", () => showView("tree"));
const changeTreeExplicitly = () => {
  treeAbState = resetTreeAbState();
  setCalculatorTree($("tree-country").value, $("tree-branch").value);
  renderTreeAbState();
  setTreeAbMessage("A/B-Auswahl wegen Forschungsbaumwechsel zurückgesetzt.");
  void refreshVisualTree({resetNavigation: true});
};
$("tree-country").addEventListener("change", changeTreeExplicitly);
$("tree-branch").addEventListener("change", changeTreeExplicitly);
$("tree-set-start").addEventListener("click", () => setSelectedTreeEndpoint("start"));
$("tree-set-target").addEventListener("click", () => setSelectedTreeEndpoint("target"));
$("tree-reset").addEventListener("click", () => resetTreeAb());
$("tree-calculate").addEventListener("click", async () => {
  try { await executeCalculation({origin: "tree"}); }
  catch (error) { setTreeAbMessage(error.message, "error"); }
});
$("tree-details-calculator").addEventListener("click", () => showView("calculator"));
$("tree-search-input").addEventListener("input", event => {
  renderSearchResults(event.target.value);
});
$("tree-search-input").addEventListener("keydown", event => {
  if (event.key === "ArrowDown") {
    const firstResult = $("tree-search-results").querySelector("button");
    if (firstResult) {
      event.preventDefault();
      firstResult.focus();
    }
  } else if (event.key === "Escape") {
    setSearchResultsOpen(false);
  }
});
$("tree-search-results").addEventListener("keydown", event => {
  if (event.key === "Escape") {
    setSearchResultsOpen(false);
    $("tree-search-input").focus();
  }
});
$("tree-search-results").addEventListener("click", event => {
  const result = event.target.closest("[data-search-vehicle-id]");
  if (result) void activateSearchResult(result.dataset.searchVehicleId);
});
$("tree-zoom-out").addEventListener("click", () => {
  setTreeZoom(changeTreeZoom(treeZoom, "out"));
});
$("tree-zoom-reset").addEventListener("click", () => {
  setTreeZoom(changeTreeZoom(treeZoom, "reset"));
});
$("tree-zoom-in").addEventListener("click", () => {
  setTreeZoom(changeTreeZoom(treeZoom, "in"));
});
$("tree-content").addEventListener("click", event => {
  const card = event.target.closest(".tree-vehicle[data-vehicle-id]");
  if (card) selectTreeVehicle(card.dataset.vehicleId, {focus: true});
});
$("tree-content").addEventListener("keydown", event => {
  const card = event.target.closest(".tree-vehicle[data-vehicle-id]");
  if (card && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    selectTreeVehicle(card.dataset.vehicleId, {focus: true});
  }
});

const treeViewport = $("tree-viewport");
treeViewport.addEventListener("pointerdown", event => {
  if (!event.isPrimary
    || (event.pointerType === "mouse" && event.button !== 0)
    || event.target.closest(".tree-vehicle, button, input, select, a")) return;
  panState = {
    pointerId: event.pointerId,
    active: false,
    x: event.clientX,
    y: event.clientY,
    left: treeViewport.scrollLeft,
    top: treeViewport.scrollTop,
  };
});
treeViewport.addEventListener("pointermove", event => {
  if (!panState || panState.pointerId !== event.pointerId) return;
  if (!panState.active) {
    if (!pointerMovementExceedsThreshold(
      {x: panState.x, y: panState.y},
      {x: event.clientX, y: event.clientY},
    )) return;
    panState.active = true;
    treeViewport.setPointerCapture(event.pointerId);
    treeViewport.classList.add("is-panning");
  }
  const next = panScrollPosition(
    panState,
    {x: panState.x, y: panState.y},
    {x: event.clientX, y: event.clientY},
  );
  const clamped = clampTreeScrollPosition(next, treeViewport);
  treeViewport.scrollLeft = clamped.left;
  treeViewport.scrollTop = clamped.top;
  event.preventDefault();
});
const stopTreePan = event => {
  if (!panState || panState.pointerId !== event.pointerId) return;
  if (panState.active && treeViewport.hasPointerCapture(event.pointerId)) {
    treeViewport.releasePointerCapture(event.pointerId);
  }
  panState = null;
  treeViewport.classList.remove("is-panning");
};
treeViewport.addEventListener("pointerup", stopTreePan);
treeViewport.addEventListener("pointercancel", stopTreePan);
treeViewport.addEventListener("lostpointercapture", stopTreePan);
$("database-file").addEventListener("change", async event => {
  try { load(JSON.parse(await event.target.files[0].text())); }
  catch (error) { alert(error.message); }
});

window.addEventListener("resize", scheduleTreeGeometryRefresh);
window.addEventListener("orientationchange", scheduleTreeGeometryRefresh);
if ("ResizeObserver" in window) {
  const treeResizeObserver = new ResizeObserver(scheduleTreeGeometryRefresh);
  treeResizeObserver.observe(treeViewport);
  treeResizeObserver.observe($("visual-tree"));
}
$("calculate").addEventListener("click", async () => {
  try { await executeCalculation({origin: "calculator"}); }
  catch (error) { alert(error.message); }
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
