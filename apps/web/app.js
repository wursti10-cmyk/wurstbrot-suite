import {calculate, validateDatabase} from "./solver.mjs";

const $ = id => document.getElementById(id);
const format = value => new Intl.NumberFormat("de-DE").format(value);
let database;

function vehicles() { return database?.vehicles || []; }
function setOptions(select, items, label = value => value) {
  select.replaceChildren(...items.map(value => new Option(label(value), value.id ?? value)));
}
function refreshBranches() {
  const branches = [...new Set(vehicles().filter(v => v.countryId === $("country").value).map(v => v.branchId))].sort();
  setOptions($("branch"), branches); refreshVehicles();
}
function refreshVehicles() {
  const list = vehicles().filter(v => v.countryId === $("country").value && v.branchId === $("branch").value && !v.hiddenResearch).sort((a,b) => a.rank-b.rank || a.order-b.order || a.name.localeCompare(b.name));
  const title = v => `Rang ${v.rank} · ${v.name || v.id}`;
  setOptions($("start"), [{id:"",name:"Baumstart"}, ...list], v => v.id ? title(v) : v.name);
  setOptions($("target"), list, title); if (list.length) $("target").value = list.at(-1).id;
}
function load(raw) {
  database = validateDatabase(raw);
  const countries = [...new Set(vehicles().map(v => v.countryId))].sort();
  setOptions($("country"), countries); refreshBranches();
  $("status").textContent = `${database.gameVersion} · ${format(vehicles().length)} Fahrzeuge`;
}
function render(result) {
  $("summary").classList.remove("empty");
  $("summary").innerHTML = `<div class="metric"><strong>${format(result.totalGe)} GE</strong>benötigt</div><div class="metric"><strong>${format(result.totalRp)} RP</strong>noch offen</div><div class="metric"><strong>${format(result.totalSl)} SL</strong>Kaufkosten</div>`;
  $("explanation").innerHTML = result.lines.map(line => `<div class="vehicle"><span>${line.name}</span><span>${format(line.remainingRp)} RP · ${format(line.ge)} GE</span></div>`).join("") || "<p>Das Ziel ist bereits erreicht.</p>";
}

$("country").addEventListener("change", refreshBranches);
$("branch").addEventListener("change", refreshVehicles);
$("database-file").addEventListener("change", async event => { try { load(JSON.parse(await event.target.files[0].text())); } catch (error) { alert(error.message); } });
$("calculate").addEventListener("click", () => { try { render(calculate(database, {startId: $("start").value || null, targetId: $("target").value, partialRp: $("partial-rp").value, ownedGe: $("owned-ge").value, slDiscount: $("discount").value})); } catch (error) { alert(error.message); } });
$("copy").addEventListener("click", async () => { await navigator.clipboard.writeText(`${$("summary").innerText}\n${$("explanation").innerText}`); $("copy").textContent = "Kopiert"; setTimeout(() => $("copy").textContent = "Kopieren", 1200); });

fetch("../../data/samples/WT_Database_2.57.1.67.json").then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(load).catch(() => { $("status").textContent = "Bitte Datenbank auswählen"; });
if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("service-worker.js");
