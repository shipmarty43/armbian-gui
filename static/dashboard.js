const node = id => document.getElementById(id);
function rows(id, data) {
  const list = node(id);
  list.replaceChildren();
  if (!data.length) list.textContent = 'Нет данных';
  for (const [label, value] of data) {
    const key = document.createElement('dt');
    const item = document.createElement('dd');
    key.textContent = label;
    item.textContent = value;
    list.append(key, item);
  }
}
async function refresh() {
  try {
    const response = await fetch('/api/status', {cache: 'no-store'});
    if (!response.ok) throw new Error(String(response.status));
    const s = await response.json();
    node('board').textContent = s.board || 'Состояние платы';
    node('kernel').textContent = 'Linux ' + s.kernel;
    rows('temperatures', Object.entries(s.temperatures).map(([key,t]) => [t.sensor || key, t.celsius + ' °C']));
    rows('batteries', Object.entries(s.batteries).map(([key,b]) => [key, [b.percent === null ? '—' : b.percent + '%', b.state].filter(Boolean).join(' · ')]));
    rows('fans', Object.entries(s.fans).map(([key,f]) => [key, [f.duty_percent === null ? '—' : f.duty_percent + '%', f.rpm === null ? 'нет данных об оборотах' : f.rpm + ' об/мин'].join(' · ')]));
    rows('interfaces', Object.entries(s.interfaces));
    rows('modules', s.modules.map(m => [m.name, m.loader_state || (m.errors.length ? m.errors.join(', ') : {selected:'Выбран в профиле', disabled:'Отключён'}[m.configuration])]));
    node('position').textContent = s.gps_location ? [s.gps_location.source, s.gps_location.latitude, s.gps_location.longitude].join(' · ') : 'Нет свежих координат';
    node('feedback').textContent = 'Обновлено ' + new Date().toLocaleTimeString();
  } catch (error) {
    node('feedback').textContent = 'Обновление недоступно (' + error.message + ').';
  } finally {
    window.setTimeout(refresh, 5000);
  }
}
refresh();

node('gpio-refresh').addEventListener('click', async () => {
  try {
    const response = await fetch('/api/gpio', {cache: 'no-store'});
    if (!response.ok) throw new Error(String(response.status));
    const {pins} = await response.json();
    rows('gpio', pins.map(p => [p.pin + ' · ' + p.name, [p.direction, p.used ? (p.consumer || 'занят') : 'свободен'].join(' · ')]));
  } catch (error) {
    node('gpio').textContent = 'Данные GPIO недоступны (' + error.message + ').';
  }
});
