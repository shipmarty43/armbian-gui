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
  add(box, "p", names[model.profile]);
  if (model.rows.length) {
    const table = add(box, "table", "");
    const heading = table.createTHead().insertRow();
    const live = id === "live";
    for (const label of ["CS", "Устройство", "Вывод", "Запрос, Гц", "Предел DT, Гц",
                         ...(live ? ["Linux", "Блокировка"] : [])]) add(heading, "th", label);
    const body = table.createTBody();
    for (const row of model.rows) {
      const tr = body.insertRow();
      for (const value of [row.cs, row.device, row.pin ? row.pin + " / " + row.pad : "—",
                           row.requested_hz, row.ceiling_hz,
                           ...(live ? [row.endpoint || "Не привязан", row.lock] : [])])
        add(tr, "td", value);
    }
  }
  for (const [cs, hz] of Object.entries(model.parked || {}))
    add(box, "p", "CS" + cs + " · сохранено " + hz + " Гц");
}
function controls() {
  el("profile").disabled = busy;
  el("refresh").disabled = busy;
  el("preview").disabled = busy || !state;
  if (el("apply")) el("apply").disabled = busy || !plan || !plan.changed;
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
  state = await api("");
  render("live", state.live);
  render("current", state.current);
  if (["shared", "single", "off"].includes(state.current.profile)) el("profile").value = state.current.profile;
}
async function run(action) {
  busy = true; controls();
  el("feedback").textContent = "Проверка…";
  try {
    if (action === "preview") {
      plan = await api(action, {profile: el("profile").value});
      render("candidate", plan.candidate);
      el("feedback").textContent = plan.changed ? "" : "Профиль уже выбран.";
    } else {
      if (action === "apply") await api(action, {profile: el("profile").value, token: plan.token});
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
run("refresh");
