"use strict";
const el = id => document.getElementById(id);
const names = {shared: "SX1262 + CC1101 + nRF24", single: "SX1262", off: "Выключен",
               external: "Другой маршрут SPI1", unknown: "Нет данных"};
let state, plan, busy = false;
function add(parent, tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  parent.append(node);
  return node;
}
function render(id, model) {
  const box = el(id);
  box.replaceChildren();
  const vendor = model.profile === "a733";
  add(box, "p", vendor ? (model.buses.join(", ") || "Контроллеры SPI выключены") : names[model.profile]);
  if (model.rows.length) {
    const table = add(box, "table", "");
    const heading = table.createTHead().insertRow();
    const live = id === "live";
    for (const label of [...(vendor ? ["SPI"] : []), "CS", "Устройство", "Вывод", vendor ? "Режим" : "Запрос, Гц", "Предел DT, Гц",
                         ...(live ? ["Linux"] : []), ...(live && !vendor ? ["Блокировка"] : [])]) add(heading, "th", label);
    const body = table.createTBody();
    for (const row of model.rows) {
      const tr = body.insertRow();
      for (const value of [...(vendor ? [row.bus] : []), row.cs, row.device, row.pin ? row.pin + " / " + row.pad : "—",
                           vendor ? row.mode : row.requested_hz, row.ceiling_hz ?? "—",
                           ...(live ? [row.endpoint || "Не привязан"] : []), ...(live && !vendor ? [row.lock] : [])])
        add(tr, "td", value);
    }
  }
  for (const [cs, hz] of Object.entries(model.parked || {}))
    add(box, "p", "CS" + cs + " · сохранено " + hz + " Гц");
}
function ownerNames(owners) {
  return owners.map(o => o.label).join(" + ") || "—";
}
function pinTable(id, labels, rows) {
  const box = el(id);
  box.replaceChildren();
  if (!rows.length) {
    add(box, "p", id === "changes" ? "Назначения контактов совпадают." : "Нет заявленных выводов.");
    return;
  }
  const table = add(box, "table", "");
  const heading = table.createTHead().insertRow();
  const functions = id === "pins" && state?.board === "Zero 3W";
  for (const label of ["Вывод", "GPIO", ...labels, ...(functions ? ["Доступные маршруты"] : [])]) add(heading, "th", label);
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const value of [row.pin, row.pad]) add(tr, "td", value);
    for (const owners of [row.before, row.after]) {
      const cell = add(tr, "td", owners ? ownerNames(owners) : "Нет данных");
      if (owners) cell.title = owners.map(o => o.path).join("\n");
      if (row.consumer && owners === row.before) add(cell, "small", "GPIO · " + row.consumer);
      if (owners && owners.length > 1) cell.className = "pin-conflict";
    }
    if (functions) add(tr, "td", row.functions?.join(" / ") || "—");
  }
}
function renderPins() {
  if (!state) return;
  const live = new Map(state.live.pins.map(row => [row.pin, row]));
  const rows = state.current.pins.map(row => ({...row, before: live.get(row.pin)?.owners, consumer: live.get(row.pin)?.gpio_consumer, after: row.owners}));
  pinTable("pins", [state.live.gpio_known ? "Сейчас (DT и GPIO)" : "Сейчас (DT, gpiochip недоступен)", "Следующая загрузка"], rows.filter(r =>
    el("all-pins").checked || r.before?.length || r.after.length || r.consumer));
}
function renderChoices() {
  const select = el("profile");
  const previous = select.value;
  select.replaceChildren();
  const groups = new Map();
  for (const item of state.choices) {
    if (!groups.has(item.group)) {
      const group = document.createElement("optgroup");
      group.label = item.group; select.append(group); groups.set(item.group, group);
    }
    add(groups.get(item.group), "option", item.label).value = item.id;
  }
  select.value = state.choices.some(item => item.id === previous) ? previous :
    (["single", "shared", "off"].includes(state.current.profile)
      ? state.current.profile : state.choices[0].id);
}
function controls() {
  el("profile").disabled = busy || !state;
  el("refresh").disabled = busy;
  el("preview").disabled = busy || !state;
  if (el("apply")) el("apply").disabled = busy || !plan || !plan.changed || !plan.token;
  if (el("undo")) el("undo").disabled = busy || !state || !state.undo;
  el("plan").hidden = !plan;
}
async function api(action, body) {
  const response = await fetch("/api/buses" + (action ? "/" + action : ""), body ? {
    method: "POST", headers: {"Content-Type": "application/json", "X-OPi-Panel": "1"},
    body: JSON.stringify(body)
  } : {});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || response.statusText);
  return result;
}
async function load() {
  plan = null;
  const previousBoard = state?.board;
  state = await api("");
  if (previousBoard !== state.board) el("all-pins").checked = state.board === "Zero 3W";
  el("board").textContent = "Orange Pi " + (state.board || "Zero 2W") + " · 40-контактная гребёнка";
  render("live", state.live);
  render("current", state.current);
  renderChoices();
  renderPins();
}
async function run(action, profile = el("profile").value) {
  if (busy) return;
  busy = true; controls();
  el("feedback").textContent = "Проверка…";
  try {
    if (action === "preview") {
      plan = await api(action, {profile});
      plan.target = profile;
      el("issues").replaceChildren();
      if (plan.issues.length) {
        add(el("issues"), "strong", "Применение заблокировано");
        for (const issue of plan.issues) add(el("issues"), "p", issue);
      }
      if (plan.alternative) {
        const offer = plan.alternative;
        const button = add(el("issues"), "button", "Предпросмотр · " + offer.label);
        button.type = "button";
        button.addEventListener("click", () => run("preview", offer.id));
      }
      if (plan.transition) add(el("issues"), "strong", plan.transition);
      for (const warning of plan.warnings) add(el("issues"), "p", warning);
      pinTable("changes", ["Было", "Запрошено"], plan.changes);
      el("candidate").replaceChildren();
      if (["SPI", "SPI1"].includes(el("profile").selectedOptions[0].parentElement.label)) render("candidate", plan.candidate);
      el("feedback").textContent = plan.changed ? "" : "Профиль уже выбран.";
    } else {
      if (action === "apply") await api(action, {profile: plan.target, token: plan.token});
      if (action === "undo") await api(action, {token: state.undo});
      await load();
      el("feedback").textContent = action === "refresh" ? "" : "Сохранено для следующей загрузки.";
    }
  } catch (error) {
    plan = null; state = null;
    el("feedback").textContent = error.message + " Обновите состояние.";
  } finally { busy = false; controls(); }
}
for (const name of ["refresh", "preview", "apply", "undo"])
  el(name)?.addEventListener("click", () => run(name));
el("profile").addEventListener("change", () => { plan = null; controls(); });
el("all-pins").addEventListener("change", renderPins);
run("refresh");
