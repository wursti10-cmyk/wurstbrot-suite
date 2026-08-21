export const LAYOUT_CONTRACT_VERSION = "visual-tech-tree-layout-v1";
export const HIGHLIGHT_CONTRACT_VERSION = "visual-tech-tree-highlight-v1";
export const FOLDER_UX_CONTRACT_VERSION = "visual-tech-tree-folder-ux-v1";

export const COUNTRY_LABELS = Object.freeze({
  country_usa: "USA",
  country_germany: "Deutschland",
  country_ussr: "UdSSR",
  country_britain: "Großbritannien",
  country_japan: "Japan",
  country_china: "China",
  country_italy: "Italien",
  country_france: "Frankreich",
  country_sweden: "Schweden",
  country_israel: "Israel",
});

export const BRANCH_LABELS = Object.freeze({
  army: "Panzer",
  aviation: "Flugzeuge",
  helicopters: "Hubschrauber",
  boats: "Küstenschiffe",
  ships: "Hochseeschiffe",
});

export const BRANCH_ORDER = Object.freeze([
  "army",
  "aviation",
  "helicopters",
  "boats",
  "ships",
]);

export const KNOWN_PARTIAL_VEHICLE_IDS = Object.freeze([
  "fiat_cr42",
  "fiat_g50_seria2",
  "fiat_g50_seria7as",
  "mc-202",
  "mc200_serie3",
  "mc200_serie7",
  "r2y2_kai",
  "r2y2_v1",
  "r2y2_v2",
  "sm_79_1936",
  "sm_79_1939",
  "sm_79_1941",
  "sm_79_1943",
  "sm_79_iar",
]);

const FIELD_EVIDENCE = Object.freeze({
  nation: {classification: "A", source: "normalized vehicles.countryId", confidence: "direct"},
  vehicleType: {
    classification: "A",
    source: "shop country branch container via vehicles.branchId",
    confidence: "direct",
  },
  rank: {classification: "A", source: "normalized vehicles.rank", confidence: "direct"},
  column: {
    classification: "B",
    source: "zero-based index of the source shop range column",
    confidence: "deterministic",
  },
  order: {
    classification: "B",
    source: "source shop order within a column",
    confidence: "deterministic",
  },
  predecessor: {
    classification: "B",
    source: "normalized predecessors (explicit reqAir or deterministic source sequence)",
    confidence: "deterministic",
  },
  successors: {
    classification: "B",
    source: "reverse index of normalized predecessors",
    confidence: "deterministic",
  },
  folder: {
    classification: "A",
    source: "normalized groups from source shop folders",
    confidence: "direct",
  },
  groupIndex: {
    classification: "B",
    source: "zero-based member index in the source shop folder",
    confidence: "deterministic",
  },
  hiddenResearch: {
    classification: "A",
    source: "normalized vehicles.hiddenResearch",
    confidence: "direct",
  },
  reqUnlock: {
    classification: "A",
    source: "normalized vehicles.reqUnlock",
    confidence: "direct",
  },
  visualSlot: {
    classification: "B",
    source: "rank/column-local sort by normalized order and vehicle id",
    confidence: "deterministic",
  },
});

const LIMITATIONS = Object.freeze([
  "premium_and_special_vehicles_are_filtered_by_the_existing_converter",
  "rankPosXY_and_fakeReqUnitPosXY_are_sparse_helicopter_metadata_and_not_layout_authority",
  "folder_membership_does_not_define_hidden_folder_acquisition_semantics",
  "reqUnlock_is_visible_evidence_and_never_an_invented_vehicle_edge",
]);

const partialVehicleIds = new Set(KNOWN_PARTIAL_VEHICLE_IDS);

function compareValues(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function compareVehicle(left, right) {
  return compareValues(Number(left.rank), Number(right.rank))
    || compareValues(Number(left.column || 0), Number(right.column || 0))
    || compareValues(Number(left.order || 0), Number(right.order || 0))
    || compareValues(left.id, right.id);
}

function pythonCanonicalJson(value, key = "") {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("Nicht-endliche Layoutzahl.");
    if (key === "order" && Number.isInteger(value)) return `${value}.0`;
    return String(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map(item => pythonCanonicalJson(item)).join(",")}]`;
  }
  const entries = Object.keys(value).sort().map(name => (
    `${JSON.stringify(name)}:${pythonCanonicalJson(value[name], name)}`
  ));
  return `{${entries.join(",")}}`;
}

async function fingerprint(payload) {
  if (!globalThis.crypto?.subtle) throw new Error("SHA-256 ist in diesem Browser nicht verfügbar.");
  const bytes = new TextEncoder().encode(pythonCanonicalJson(payload));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
}

export function availableTrees(database) {
  const trees = new Map();
  for (const vehicle of database.vehicles || []) {
    const key = `${vehicle.countryId}/${vehicle.branchId}`;
    trees.set(key, (trees.get(key) || 0) + 1);
  }
  return trees;
}

export function buildFolderMetadataSummary(database) {
  const vehicles = database?.vehicles || [];
  const vehicleIds = new Set(vehicles.map(vehicle => vehicle.id));
  const folders = Object.entries(database?.groups || {}).sort(([left], [right]) => (
    compareValues(left, right)
  )).map(([groupId, declaredMemberIds]) => {
    const presentMemberIds = declaredMemberIds.filter(vehicleId => vehicleIds.has(vehicleId));
    const missingMemberIds = declaredMemberIds.filter(vehicleId => !vehicleIds.has(vehicleId));
    return Object.freeze({
      group_id: groupId,
      declared_member_ids: Object.freeze([...declaredMemberIds]),
      present_member_ids: Object.freeze(presentMemberIds),
      missing_member_ids: Object.freeze(missingMemberIds),
      complete_in_normalized_data: missingMemberIds.length === 0,
      displayable: presentMemberIds.length > 0,
    });
  });
  return Object.freeze({
    contract_version: FOLDER_UX_CONTRACT_VERSION,
    folder_count: folders.length,
    present_member_count: folders.reduce(
      (total, folder) => total + folder.present_member_ids.length,
      0,
    ),
    missing_member_count: folders.reduce(
      (total, folder) => total + folder.missing_member_ids.length,
      0,
    ),
    incomplete_folder_count: folders.filter(folder => (
      folder.missing_member_ids.length > 0
    )).length,
    non_displayable_folder_count: folders.filter(folder => !folder.displayable).length,
    folders: Object.freeze(folders),
  });
}

export async function buildVisualTreeLayout(database, {countryId, branchId}) {
  const vehicles = (database.vehicles || [])
    .filter(vehicle => vehicle.countryId === countryId && vehicle.branchId === branchId)
    .sort(compareVehicle);
  if (!vehicles.length) return null;

  const vehicleIds = new Set(vehicles.map(vehicle => vehicle.id));
  const byId = new Map(vehicles.map(vehicle => [vehicle.id, vehicle]));
  const successors = new Map(vehicles.map(vehicle => [vehicle.id, []]));
  const edges = [];
  for (const vehicle of vehicles) {
    const predecessorId = (database.predecessors || {})[vehicle.id] || null;
    if (!predecessorId) continue;
    if (!vehicleIds.has(predecessorId)) {
      throw new Error(`Baumübergreifender Vorgänger: ${predecessorId} -> ${vehicle.id}`);
    }
    successors.get(predecessorId).push(vehicle.id);
    edges.push({
      source_vehicle_id: predecessorId,
      target_vehicle_id: vehicle.id,
      edge_type: "research_predecessor",
      evidence: "normalized_predecessors",
    });
  }

  const ranks = [...new Set(vehicles.map(vehicle => Number(vehicle.rank)))].sort((a, b) => a - b);
  const columns = [...new Set(vehicles.map(vehicle => Number(vehicle.column || 0)))].sort((a, b) => a - b);
  const visualSlots = new Map();
  for (const rank of ranks) {
    for (const column of columns) {
      vehicles
        .filter(vehicle => Number(vehicle.rank) === rank && Number(vehicle.column || 0) === column)
        .sort((left, right) => compareValues(Number(left.order || 0), Number(right.order || 0))
          || compareValues(left.id, right.id))
        .forEach((vehicle, slot) => visualSlots.set(vehicle.id, slot));
    }
  }

  const nodes = vehicles.map(vehicle => ({
    vehicle_id: vehicle.id,
    name: vehicle.name || vehicle.id,
    country_id: vehicle.countryId,
    branch_id: vehicle.branchId,
    rank: Number(vehicle.rank),
    column: Number(vehicle.column || 0),
    order: Number(vehicle.order || 0),
    visual_slot: visualSlots.get(vehicle.id),
    predecessor_id: (database.predecessors || {})[vehicle.id] || null,
    successor_ids: successors.get(vehicle.id)
      .sort((left, right) => compareVehicle(byId.get(left), byId.get(right))),
    group_id: vehicle.group || null,
    group_index: Number(vehicle.groupIndex || 0),
    hidden_research: Boolean(vehicle.hiddenResearch),
    req_unlock: String(vehicle.reqUnlock || ""),
    reserve: Boolean(vehicle.reserve),
    premium: Boolean(vehicle.premium),
    special: Boolean(vehicle.special),
    rp: Number(vehicle.rp || 0),
    sl: Number(vehicle.sl || 0),
  }));

  const folderMetadata = buildFolderMetadataSummary(database);
  const metadataByGroupId = new Map(folderMetadata.folders.map(folder => [folder.group_id, folder]));
  const groupIds = [...new Set(vehicles.map(vehicle => vehicle.group).filter(Boolean))].sort();
  const folders = groupIds.map(groupId => {
    const metadata = metadataByGroupId.get(groupId);
    const declared = [...(metadata?.declared_member_ids || [])];
    const present = declared.filter(vehicleId => vehicleIds.has(vehicleId));
    const missing = [...(metadata?.missing_member_ids || [])];
    return {
      group_id: groupId,
      declared_member_ids: declared,
      present_member_ids: present,
      missing_member_ids: missing,
      complete_in_normalized_data: missing.length === 0,
      visible_member_count: present.length,
      declared_member_count: declared.length,
      missing_member_count: missing.length,
    };
  });
  edges.sort((left, right) => compareValues(left.target_vehicle_id, right.target_vehicle_id)
    || compareValues(left.source_vehicle_id, right.source_vehicle_id));

  const base = {
    contract_version: LAYOUT_CONTRACT_VERSION,
    game_version: database.gameVersion,
    country_id: countryId,
    branch_id: branchId,
    flow_direction: "top_to_bottom",
    ranks,
    columns,
    nodes,
    edges,
    folders,
    evidence: FIELD_EVIDENCE,
    limitations: LIMITATIONS,
  };
  return {...base, fingerprint: await fingerprint(base)};
}

export async function buildVisualTreeHighlight(layout, result, options = {}) {
  const nodeIds = new Set(layout.nodes.map(node => node.vehicle_id));
  if (!nodeIds.has(result.targetVehicleId)) throw new Error("Das Solver-Ziel gehört nicht zum Layout.");
  if (result.startVehicleId && !nodeIds.has(result.startVehicleId)) {
    throw new Error("Der Solver-Start gehört nicht zum Layout.");
  }
  const required = new Set(result.requiredVehicleIds);
  const unknown = [...required].filter(vehicleId => !nodeIds.has(vehicleId));
  if (unknown.length) throw new Error(`Layoutfremde Solver-Fahrzeuge: ${unknown.join(", ")}`);

  const lineReasons = new Map(result.lines.map(line => [line.id, line.reason]));
  const directPath = new Set(result.lines
    .filter(line => line.reason === "direct_path")
    .map(line => line.id));
  const pathNodes = new Set(directPath);
  if (result.startVehicleId) pathNodes.add(result.startVehicleId);
  const unresolvedVehicles = [...new Set(options.unresolvedVehicleIds || [])].sort();
  const unresolvedFolders = [...new Set(options.unresolvedFolderIds || [])].sort();

  const nodeStates = {};
  for (const node of layout.nodes) {
    const states = [];
    if (node.vehicle_id === result.startVehicleId) states.push("start_a");
    if (node.vehicle_id === result.targetVehicleId) states.push("target_b");
    const reason = lineReasons.get(node.vehicle_id);
    states.push(reason ? `required_${reason}` : "not_required");
    if (node.group_id) states.push("folder_member");
    if (node.hidden_research) states.push("hidden_research");
    if (unresolvedVehicles.includes(node.vehicle_id)
      || unresolvedFolders.includes(node.group_id)) states.push("partial_unresolved");
    nodeStates[node.vehicle_id] = states;
  }
  const requiredEdgeIds = layout.edges
    .filter(edge => pathNodes.has(edge.source_vehicle_id) && directPath.has(edge.target_vehicle_id))
    .map(edge => `${edge.source_vehicle_id}->${edge.target_vehicle_id}`);
  const calculationStatus = options.calculationStatus || "complete";
  const fallbackReason = options.fallbackReason || null;
  const base = {
    contract_version: HIGHLIGHT_CONTRACT_VERSION,
    layout_fingerprint: layout.fingerprint,
    start_vehicle_id: result.startVehicleId,
    target_vehicle_id: result.targetVehicleId,
    user_result_source: options.userResultSource || "legacy",
    calculation_status: calculationStatus,
    fallback_reason: fallbackReason,
    complete: calculationStatus === "complete" && !fallbackReason
      && !unresolvedVehicles.length && !unresolvedFolders.length,
    node_states: nodeStates,
    required_edge_ids: requiredEdgeIds,
    unresolved_vehicle_ids: unresolvedVehicles,
    unresolved_folder_ids: unresolvedFolders,
  };
  return {...base, fingerprint: await fingerprint(base)};
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function romanRank(rank) {
  return ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"][rank]
    || String(rank);
}

function formatNumber(value) {
  return new Intl.NumberFormat("de-DE").format(value);
}

function renderVehicle(node, highlight) {
  const states = new Set(highlight?.node_states?.[node.vehicle_id] || ["not_required"]);
  if (node.group_id) states.add("folder_member");
  if (node.hidden_research) states.add("hidden_research");
  if (partialVehicleIds.has(node.vehicle_id)) states.add("partial_unresolved");
  const classes = [...states].map(state => state.replaceAll("_", "-")).join(" ");
  const badges = [];
  if (states.has("start_a")) badges.push("A · Start");
  if (states.has("target_b")) badges.push("B · Ziel");
  if (node.reserve) badges.push("Reserve");
  if (node.hidden_research) badges.push("Hidden");
  if (partialVehicleIds.has(node.vehicle_id)) badges.push("Partial");
  if (node.req_unlock) badges.push("Zusatzfreischaltung");
  const badgeMarkup = badges.length
    ? `<div class="vehicle-badges">${badges.map(label => `<span>${escapeHtml(label)}</span>`).join("")}</div>`
    : "";
  return `<article class="tree-vehicle ${classes}" data-vehicle-id="${escapeHtml(node.vehicle_id)}"`
    + ` data-rank="${node.rank}" data-column="${node.column}"`
    + `${node.group_id ? ` data-group-id="${escapeHtml(node.group_id)}"` : ""}`
    + ` role="button" tabindex="0" aria-pressed="false"`
    + ` aria-label="${escapeHtml(`${node.name}, Rang ${romanRank(node.rank)}`)}">`
    + `<strong>${escapeHtml(node.name)}</strong>`
    + `<span class="vehicle-rank">Rang ${romanRank(node.rank)}</span>`
    + `<dl><div><dt>RP</dt><dd>${formatNumber(node.rp)}</dd></div>`
    + `<div><dt>SL</dt><dd>${formatNumber(node.sl)}</dd></div></dl>`
    + badgeMarkup
    + "</article>";
}

function renderColumnNodes(nodes, folders, highlight) {
  const folderById = new Map(folders.map(folder => [folder.group_id, folder]));
  let markup = "";
  for (let index = 0; index < nodes.length;) {
    const node = nodes[index];
    if (!node.group_id) {
      markup += renderVehicle(node, highlight);
      index += 1;
      continue;
    }
    const members = [];
    while (index < nodes.length && nodes[index].group_id === node.group_id) {
      members.push(nodes[index]);
      index += 1;
    }
    const folder = folderById.get(node.group_id);
    const partial = members.some(member => partialVehicleIds.has(member.vehicle_id));
    const incompleteData = !folder?.complete_in_normalized_data;
    const visibleCount = folder?.visible_member_count ?? members.length;
    const countLabel = `${visibleCount} ${visibleCount === 1 ? "Fahrzeug" : "Fahrzeuge"}`;
    const accessibleStatus = [
      incompleteData ? "Folder-Daten unvollständig" : "Folder-Daten vollständig",
      partial ? "Partial / unresolved" : null,
    ].filter(Boolean).join(", ");
    const dataNotice = incompleteData
      ? `<p class="folder-data-notice">Folder-Daten unvollständig · ${folder.missing_member_count}`
        + ` ${folder.missing_member_count === 1 ? "deklariertes Mitglied" : "deklarierte Mitglieder"}`
        + " im Datensatz nicht verfügbar</p>"
      : "";
    const folderClasses = [
      "tree-folder",
      partial ? "partial-unresolved" : null,
      incompleteData ? "incomplete-data" : null,
    ].filter(Boolean).join(" ");
    markup += `<section class="${folderClasses}"`
      + ` data-folder-id="${escapeHtml(node.group_id)}" data-folder-reveal="always"`
      + ` role="group" aria-label="${escapeHtml(`Folder, ${countLabel}, ${accessibleStatus}`)}">`
      + '<div class="folder-header">'
      + '<span class="folder-label">Folder/Gruppe</span>'
      + `<span class="folder-count">${escapeHtml(countLabel)}</span>`
      + "</div>"
      + `<p class="folder-semantics">Gruppierung · keine Forschungsbeziehung</p>`
      + (partial ? '<p class="folder-state">Partial / unresolved</p>' : "")
      + dataNotice
      + members.map(member => renderVehicle(member, highlight)).join("")
      + "</section>";
  }
  return markup;
}

export function renderTreeMarkup(layout, highlight = null) {
  if (!layout) {
    return '<div class="tree-empty"><strong>Nicht verfügbar</strong>'
      + "<span>Für diese Nation und Fahrzeugart enthält die Datenbank keinen Forschungsbaum.</span></div>";
  }
  const columnCount = Math.max(...layout.columns) + 1;
  return layout.ranks.map(rank => {
    const columns = Array.from({length: columnCount}, (_, column) => {
      const nodes = layout.nodes
        .filter(node => node.rank === rank && node.column === column)
        .sort((left, right) => left.visual_slot - right.visual_slot);
      return `<div class="tree-column" data-column="${column}">`
        + renderColumnNodes(nodes, layout.folders, highlight)
        + "</div>";
    }).join("");
    return `<section class="tree-rank" data-rank="${rank}">`
      + `<div class="tree-rank-title"><span>Rang</span><strong>${romanRank(rank)}</strong></div>`
      + `<div class="tree-rank-grid" style="--tree-columns:${columnCount}">${columns}</div>`
      + "</section>";
  }).join("");
}
