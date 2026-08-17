import {calculate, validateDatabase} from "./solver.mjs";

const $ = id => document.getElementById(id);
const format = value => new Intl.NumberFormat("de-DE").format(value);
const COUNTRY_LABELS = Object.freeze({
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
const BRANCH_LABELS = Object.freeze({
  army: "Panzer",
  aviation: "Flugzeuge",
  helicopters: "Hubschrauber",
  boats: "Küstenschiffe",
  ships: "Hochseeschiffe",
});
const fallbackLabel = value => value
  .replace(/^country_/, "")
  .replaceAll("_", " ")
  .replace(/\b\p{L}/gu, character => character.toLocaleUpperCase("de-DE"));
let database;

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
  $("status").textContent = `${database.gameVersion} · ${format(vehicles().length)} Fahrzeuge`;
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
$("database-file").addEventListener("change", async event => {
  try { load(JSON.parse(await event.target.files[0].text())); }
  catch (error) { alert(error.message); }
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
