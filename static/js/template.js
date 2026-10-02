/* EWOK template designer: edits a wallrender template (schema v1) and
   previews it through /api/template/preview. No framework; the template
   object is the single source of truth and the form is redrawn from it. */
(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // Preset sample devices come from the server (config.SAMPLE_DEVICES).
  const PRESETS = JSON.parse(document.getElementById('sampleDevices').textContent);
  const SAMPLE = PRESETS[0].values;
  // Device profiles come from wallrender (device_profiles.json).
  const DEVICES = JSON.parse(document.getElementById('deviceProfiles').textContent);

  const NEW_LAYERS = {
    text: () => ({ type: 'text', text: '{{device_name}}', box: { x: 0.1, y: 0.6, w: 0.8, h: 0.05 },
      size: 0.028, color: '#FFFFFF', align: 'center' }),
    qr: () => ({ type: 'qr', data: 'jamf-device:{{jss_id}}', box: { x: 0.35, y: 0.72, w: 0.3, h: 0.14 } }),
    image: () => ({ type: 'image', asset: '', box: { x: 0.35, y: 0.3, w: 0.3, h: 0.14 } }),
  };

  const state = {
    template: {
      schema_version: 1,
      name: 'Untitled template',
      canvas: { width: 1290, height: 2796 },
      background: { color: '#0B2545' },
      layers: [NEW_LAYERS.text(), NEW_LAYERS.qr()],
    },
    selected: 0,
    assets: [],
    values: SAMPLE,
    stress: false,
    guide: { device: '', orientation: 'portrait', screen: 'lock' },
    previewRole: null, // null: use the sample device's own values
    roleLabels: {}, // variant key -> the role as typed, for display
    lastImage: null,
  };

  // ── Preview ────────────────────────────────────────

  let previewTimer = null;
  let previewController = null;

  function schedulePreview() {
    $('.tpl-preview').classList.add('is-stale');
    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderPreview, 300);
  }

  function exportable() {
    // Drop editor-only blanks: an image layer with no asset yet is skipped.
    const t = JSON.parse(JSON.stringify(state.template));
    t.layers = t.layers.filter((l) => l.type !== 'image' || l.asset);
    if (t.roles) {
      ['empty', 'default'].forEach((k) => {
        if (t.roles[k] && !Object.keys(t.roles[k]).length) delete t.roles[k];
      });
    }
    return t;
  }

  async function renderPreview() {
    if (previewController) previewController.abort();
    previewController = new AbortController();
    setStatus('Rendering…');
    try {
      const resp = await fetch('/api/template/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template: exportable(), values: previewValues(), stress: state.stress,
          devices: pickedDevices(), screen: state.guide.screen,
        }),
        signal: previewController.signal,
      });
      const body = await resp.json();
      if (!resp.ok) {
        showWarnings(body.problems || [body.error || 'The preview failed.']);
        setStatus(resp.status === 400 ? 'Not rendered: the template has problems (listed below).'
          : 'Not rendered: an asset or value could not be used (listed below).');
        return;
      }
      const render = body.renders[0];
      const img = $('#previewImage');
      img.src = render.image;
      img.hidden = false;
      $('.tpl-preview').classList.remove('is-stale');
      showWarnings(render.warnings);
      showStress(body.renders.slice(1));
      state.lastImage = render.image;
      img.onload = () => {
        drawSafeAreas();
        drawDeviceGrid();
      };
      showWarnings(render.device_warnings, $('#deviceWarnings'),
        pickedDevices().length ? 'Fits every selected device.' : 'No devices selected.');
      setStatus(`Rendered ${state.template.canvas ? state.template.canvas.width + '×' + state.template.canvas.height : ''} with the sample device.`);
    } catch (err) {
      if (err.name !== 'AbortError') setStatus('Not rendered: could not reach EWOK.');
    }
  }

  function setStatus(text) {
    $('#previewStatus').textContent = text;
  }

  const STRESS_CAPTIONS = { long: 'Every value long', empty: 'Every value empty' };

  function showStress(renders) {
    const box = $('#stressRenders');
    box.hidden = !renders.length;
    box.replaceChildren();
    renders.forEach((r) => {
      const fig = document.createElement('figure');
      const cap = document.createElement('figcaption');
      cap.textContent = STRESS_CAPTIONS[r.label] || r.label;
      const img = document.createElement('img');
      img.src = r.image;
      img.alt = `Preview with ${(STRESS_CAPTIONS[r.label] || r.label).toLowerCase()}`;
      const ul = document.createElement('ul');
      ul.className = 'tpl-warnings';
      fig.append(cap, img, ul);
      box.append(fig);
      showWarnings(r.warnings, ul);
    });
  }

  function showWarnings(list, target, okText) {
    const ul = target || $('#warningList');
    ul.replaceChildren();
    if (!list.length) {
      const li = document.createElement('li');
      li.className = 'ok';
      li.textContent = okText || 'No warnings.';
      ul.append(li);
      return;
    }
    list.forEach((w) => {
      const li = document.createElement('li');
      // wallrender counts layers from 0; this page numbers them from 1.
      li.textContent = w.replace(/\blayer (\d+)/g, (m, n) => `layer ${Number(n) + 1}`);
      ul.append(li);
    });
  }

  // ── Canvas and background ──────────────────────────

  function bindCanvas() {
    $('#tplName').addEventListener('input', (e) => {
      state.template.name = e.target.value;
    });
    $('#canvasPreset').addEventListener('change', (e) => {
      const custom = e.target.value === 'custom';
      $('#customSize').hidden = !custom;
      if (custom) {
        // A template without a canvas takes its size from its background image.
        $('#canvasWidth').value = (state.template.canvas || {}).width || '';
        $('#canvasHeight').value = (state.template.canvas || {}).height || '';
        return;
      }
      const [w, h] = e.target.value.split('x').map(Number);
      state.template.canvas = { width: w, height: h };
      schedulePreview();
    });
    ['#canvasWidth', '#canvasHeight'].forEach((sel) => {
      $(sel).addEventListener('input', () => {
        const w = parseInt($('#canvasWidth').value, 10);
        const h = parseInt($('#canvasHeight').value, 10);
        if (w > 0 && h > 0) {
          state.template.canvas = { width: w, height: h };
          schedulePreview();
        }
      });
    });
    $$('input[name="bgKind"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        const kind = $('input[name="bgKind"]:checked').value;
        $('#bgColorRow').hidden = kind !== 'color';
        $('#bgAssetRow').hidden = kind !== 'asset';
        state.template.background = kind === 'color'
          ? { color: $('#bgColor').value.toUpperCase() }
          : { asset: $('#bgAsset').value };
        if (kind === 'asset' && !$('#bgAsset').value) return;
        schedulePreview();
      });
    });
    $('#bgColor').addEventListener('input', (e) => {
      state.template.background = { color: e.target.value.toUpperCase() };
      schedulePreview();
    });
    $('#bgAsset').addEventListener('change', (e) => {
      state.template.background = { asset: e.target.value };
      schedulePreview();
    });
  }

  // ── Assets ─────────────────────────────────────────

  async function loadAssets() {
    const resp = await fetch('/api/template/assets');
    state.assets = (await resp.json()).assets;
    drawAssets();
  }

  function drawAssets() {
    const ul = $('#assetList');
    ul.replaceChildren();
    if (!state.assets.length) {
      const li = document.createElement('li');
      li.textContent = 'No assets yet.';
      ul.append(li);
    }
    state.assets.forEach((a) => {
      const li = document.createElement('li');
      const img = document.createElement('img');
      img.src = `/api/template/assets/${a.id}`;
      img.alt = '';
      const name = document.createElement('span');
      name.className = 'asset-name';
      name.textContent = `${a.id} (${a.width}×${a.height})`;
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'tpl-icon-btn';
      del.textContent = 'Delete';
      del.setAttribute('aria-label', `Delete asset ${a.id}`);
      del.addEventListener('click', async () => {
        await fetch(`/api/template/assets/${a.id}`, { method: 'DELETE' });
        await loadAssets();
        schedulePreview();
      });
      li.append(img, name, del);
      ul.append(li);
    });
    $$('.asset-select').forEach((select) => {
      const current = select.value;
      select.replaceChildren(new Option('Choose an asset…', ''));
      state.assets.forEach((a) => select.append(new Option(a.id, a.id)));
      select.value = current;
    });
    drawProperties();
    if (state.template.roles) drawVariants();
  }

  function bindAssets() {
    $('#assetFile').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const form = new FormData();
      form.append('file', file);
      const resp = await fetch('/api/template/assets', { method: 'POST', body: form });
      const body = await resp.json();
      e.target.value = '';
      if (!resp.ok) {
        setStatus(`Upload failed: ${body.error}`);
        return;
      }
      setStatus(`Uploaded asset ${body.id}.`);
      await loadAssets();
    });
  }

  // ── Layers ─────────────────────────────────────────

  function describe(layer) {
    if (layer.type === 'text') return `Text: ${layer.text || '(empty)'}`;
    if (layer.type === 'qr') return `QR: ${layer.data || '(empty)'}`;
    return `Image: ${layer.asset || '(choose an asset)'}`;
  }

  function drawLayers() {
    const ol = $('#layerList');
    ol.replaceChildren();
    state.template.layers.forEach((layer, i) => {
      const li = document.createElement('li');
      li.classList.toggle('selected', i === state.selected);
      const pick = document.createElement('button');
      pick.type = 'button';
      pick.className = 'layer-select';
      pick.textContent = `${i + 1}. ${describe(layer)}`;
      pick.setAttribute('aria-pressed', String(i === state.selected));
      pick.addEventListener('click', () => select(i));
      li.append(pick,
        iconButton('Up', `Move layer ${i + 1} up`, i === 0, () => move(i, -1)),
        iconButton('Down', `Move layer ${i + 1} down`, i === state.template.layers.length - 1, () => move(i, 1)),
        iconButton('Delete', `Delete layer ${i + 1}`, false, () => remove(i)));
      ol.append(li);
    });
    drawOverlay();
  }

  function iconButton(text, label, disabled, onClick) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'tpl-icon-btn';
    b.textContent = text;
    b.setAttribute('aria-label', label);
    b.disabled = disabled;
    b.addEventListener('click', onClick);
    return b;
  }

  function select(i) {
    state.selected = i;
    drawLayers();
    drawProperties();
  }

  function move(i, delta) {
    const layers = state.template.layers;
    const [layer] = layers.splice(i, 1);
    layers.splice(i + delta, 0, layer);
    state.selected = i + delta;
    drawLayers();
    drawProperties();
    schedulePreview();
  }

  function remove(i) {
    state.template.layers.splice(i, 1);
    state.selected = Math.min(state.selected, state.template.layers.length - 1);
    drawLayers();
    drawProperties();
    schedulePreview();
  }

  function bindLayerButtons() {
    $$('[data-add]').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.template.layers.push(NEW_LAYERS[btn.dataset.add]());
        select(state.template.layers.length - 1);
        schedulePreview();
      });
    });
  }

  // ── Properties of the selected layer ───────────────

  function current() {
    return state.template.layers[state.selected];
  }

  function drawProperties() {
    const layer = current();
    $('#propsSection').hidden = !layer;
    if (!layer) return;
    $('#propsTitle').textContent = `Layer ${state.selected + 1}: ${layer.type === 'qr' ? 'QR code' : layer.type}`;
    $$('#propsSection [data-kind]').forEach((el) => {
      el.hidden = el.dataset.kind !== layer.type;
    });
    $$('[data-box]').forEach((input) => {
      input.value = layer.box[input.dataset.box];
    });
    const panel = $(`#propsSection [data-kind="${layer.type}"]`);
    panel.querySelectorAll('[data-prop]').forEach((input) => {
      const value = layer[input.dataset.prop];
      if (input.type === 'checkbox') input.checked = Boolean(value);
      else if (input.type === 'color') input.value = (value || defaultColor(input)).slice(0, 7);
      else input.value = value === undefined ? (input.dataset.prop === 'overflow' ? 'shrink'
        : input.dataset.prop === 'align' ? 'center' : '') : value;
    });
  }

  function defaultColor(input) {
    if (input.dataset.prop === 'background') return '#ffffff';
    return current().type === 'qr' ? '#000000' : '#ffffff';
  }

  function bindProperties() {
    $$('[data-box]').forEach((input) => {
      input.addEventListener('input', () => {
        const n = parseFloat(input.value);
        if (Number.isFinite(n)) {
          current().box[input.dataset.box] = n;
          drawOverlay();
          schedulePreview();
        }
      });
    });
    $$('#propsSection [data-prop]').forEach((input) => {
      const event = input.tagName === 'SELECT' || input.type === 'checkbox' ? 'change' : 'input';
      input.addEventListener(event, () => {
        const layer = current();
        const key = input.dataset.prop;
        if (input.type === 'checkbox') {
          if (input.checked) layer[key] = true; else delete layer[key];
        } else if (input.dataset.type === 'number') {
          const n = parseFloat(input.value);
          if (Number.isFinite(n)) layer[key] = n;
          else if (input.dataset.optional !== undefined) delete layer[key];
          else return;
        } else if (input.type === 'color') {
          layer[key] = input.value.toUpperCase();
        } else {
          layer[key] = input.value;
        }
        drawLayers();
        schedulePreview();
      });
    });
    $$('[data-insert]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.insert);
        const variable = `{{${btn.previousElementSibling.value}}}`;
        const at = target.selectionStart ?? target.value.length;
        target.value = target.value.slice(0, at) + variable + target.value.slice(target.selectionEnd ?? at);
        target.dispatchEvent(new Event('input'));
        target.focus();
        target.setSelectionRange(at + variable.length, at + variable.length);
      });
    });
  }

  // ── Boxes over the preview (drag, resize, keys) ────

  const MIN_SIDE = 0.01;
  const SNAP = 0.01; // snap when the center is within 1% of the canvas
  const round = (n) => Math.round(n * 10000) / 10000;

  function clampBox(box) {
    const w = Math.min(1, Math.max(MIN_SIDE, box.w));
    const h = Math.min(1, Math.max(MIN_SIDE, box.h));
    return {
      x: round(Math.min(1 - w, Math.max(0, box.x))),
      y: round(Math.min(1 - h, Math.max(0, box.y))),
      w: round(w),
      h: round(h),
    };
  }

  function snapBox(box) {
    const snapped = { ...box };
    const v = Math.abs(box.x + box.w / 2 - 0.5) < SNAP;
    const h = Math.abs(box.y + box.h / 2 - 0.5) < SNAP;
    if (v) snapped.x = round(0.5 - box.w / 2);
    if (h) snapped.y = round(0.5 - box.h / 2);
    $('.tpl-guide-v').hidden = !v;
    $('.tpl-guide-h').hidden = !h;
    return snapped;
  }

  function hideGuides() {
    $('.tpl-guide-v').hidden = true;
    $('.tpl-guide-h').hidden = true;
  }

  function placeFrame(frame, layer, i) {
    const b = layer.box;
    Object.assign(frame.style, {
      left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%`,
    });
    frame.classList.toggle('selected', i === state.selected);
    frame.querySelector('.tpl-boxlabel').textContent = String(i + 1);
    frame.setAttribute('aria-label', `Layer ${i + 1} box (${layer.type}): x ${b.x}, y ${b.y}, `
      + `width ${b.w}, height ${b.h}${i === state.selected ? ', editing' : ''}`);
  }

  function drawOverlay() {
    const overlay = $('#overlay');
    const layers = state.template.layers;
    let frames = $$('#overlay .tpl-boxframe');
    // Rebuild only when the count changes, so a focused or dragged box keeps
    // its element (and focus or pointer capture) while it is updated.
    if (frames.length !== layers.length) {
      frames.forEach((f) => f.remove());
      frames = layers.map((_, i) => makeFrame(i));
      frames.forEach((f) => overlay.append(f));
    }
    frames.forEach((frame, i) => placeFrame(frame, layers[i], i));
  }

  function makeFrame(i) {
    const frame = document.createElement('div');
    frame.className = 'tpl-boxframe';
    frame.tabIndex = 0;
    frame.dataset.index = String(i);
    const label = document.createElement('span');
    label.className = 'tpl-boxlabel';
    const handle = document.createElement('div');
    handle.className = 'tpl-resize';
    handle.setAttribute('aria-hidden', 'true');
    frame.append(label, handle);
    frame.addEventListener('pointerdown', startDrag);
    frame.addEventListener('keydown', nudge);
    frame.addEventListener('focus', () => {
      const index = Number(frame.dataset.index);
      if (index !== state.selected) select(index);
    });
    return frame;
  }

  function commitBox(i, box) {
    state.template.layers[i].box = box;
    if (i === state.selected) {
      $$('[data-box]').forEach((input) => {
        input.value = box[input.dataset.box];
      });
    }
    drawOverlay();
    schedulePreview();
  }

  function startDrag(event) {
    if (event.button !== 0) return;
    const frame = event.currentTarget;
    const i = Number(frame.dataset.index);
    if (i !== state.selected) select(i);
    const stage = $('#stage').getBoundingClientRect();
    const start = { ...state.template.layers[i].box };
    const resizing = event.target.classList.contains('tpl-resize');
    const sx = event.clientX;
    const sy = event.clientY;
    frame.setPointerCapture(event.pointerId);
    event.preventDefault(); // no text selection while dragging
    frame.focus({ preventScroll: true });

    function move(e) {
      const dx = (e.clientX - sx) / stage.width;
      const dy = (e.clientY - sy) / stage.height;
      let box = resizing
        ? clampBox({ ...start, w: start.w + dx, h: start.h + dy })
        : clampBox({ ...start, x: start.x + dx, y: start.y + dy });
      if (!resizing) box = clampBox(snapBox(box));
      commitBox(i, box);
    }

    function end(e) {
      frame.releasePointerCapture(e.pointerId);
      frame.removeEventListener('pointermove', move);
      frame.removeEventListener('pointerup', end);
      frame.removeEventListener('pointercancel', end);
      hideGuides();
    }

    frame.addEventListener('pointermove', move);
    frame.addEventListener('pointerup', end);
    frame.addEventListener('pointercancel', end);
  }

  const KEYS = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

  function nudge(event) {
    const dir = KEYS[event.key];
    if (!dir) return;
    event.preventDefault();
    const i = Number(event.currentTarget.dataset.index);
    const step = event.shiftKey ? 0.05 : 0.005;
    const b = state.template.layers[i].box;
    const box = event.altKey
      ? clampBox({ ...b, w: b.w + dir[0] * step, h: b.h + dir[1] * step })
      : clampBox(snapBox(clampBox({ ...b, x: b.x + dir[0] * step, y: b.y + dir[1] * step })));
    commitBox(i, box);
    clearTimeout(nudge.guideTimer);
    nudge.guideTimer = setTimeout(hideGuides, 800);
  }

  // ── Devices: safe-area guides and the device grid ──

  function pickedDevices() {
    return $$('.device-pick:checked').map((c) => c.value);
  }

  function profile(id) {
    return DEVICES.find((p) => p.id === id);
  }

  function screenSize(p, orientation) {
    const [w, h] = p.screen;
    return orientation === 'landscape' ? [h, w] : [w, h];
  }

  // Mirrors wallrender.devices.visible_region: cover-scale, then center.
  function visibleRegion(cw, ch, sw, sh) {
    const scale = Math.max(sw / cw, sh / ch);
    const vw = Math.min(1, sw / scale / cw);
    const vh = Math.min(1, sh / scale / ch);
    return [(1 - vw) / 2, (1 - vh) / 2, (1 + vw) / 2, (1 + vh) / 2];
  }

  function hatch(cls, label, [x0, y0, x1, y1]) {
    const el = document.createElement('div');
    el.className = cls;
    Object.assign(el.style, {
      left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%`,
    });
    const span = document.createElement('span');
    span.textContent = label;
    el.append(span);
    return el;
  }

  function drawSafeAreas() {
    const layer = $('#safeAreas');
    layer.replaceChildren();
    const img = $('#previewImage');
    const p = profile(state.guide.device);
    $('#guideOrientation').disabled = !p || !p.rotates;
    if (!p || !img.naturalWidth) return;
    const orientation = p.rotates ? state.guide.orientation : 'portrait';
    const [sw, sh] = screenSize(p, orientation);
    const [vx0, vy0, vx1, vy1] = visibleRegion(img.naturalWidth, img.naturalHeight, sw, sh);
    const cut = 'Cropped off';
    if (vy0 > 0) layer.append(hatch('tpl-cropped', cut, [0, 0, 1, vy0]), hatch('tpl-cropped', cut, [0, vy1, 1, 1]));
    if (vx0 > 0) layer.append(hatch('tpl-cropped', cut, [0, vy0, vx0, vy1]), hatch('tpl-cropped', cut, [vx1, vy0, 1, vy1]));
    p.zones[orientation][state.guide.screen].forEach((z) => {
      const [x0, y0, x1, y1] = z.box;
      layer.append(hatch('tpl-zone', z.label, [
        vx0 + x0 * (vx1 - vx0), vy0 + y0 * (vy1 - vy0), vx0 + x1 * (vx1 - vx0), vy0 + y1 * (vy1 - vy0),
      ]));
    });
  }

  function drawDeviceGrid() {
    const grid = $('#deviceGrid');
    grid.replaceChildren();
    if (!state.lastImage) return;
    pickedDevices().forEach((id) => {
      const p = profile(id);
      (p.rotates ? ['portrait', 'landscape'] : ['portrait']).forEach((orientation) => {
        const [sw, sh] = screenSize(p, orientation);
        const fig = document.createElement('figure');
        const screen = document.createElement('div');
        screen.className = 'tpl-screen';
        const width = orientation === 'landscape' ? 200 : 120;
        screen.style.width = `${width}px`;
        screen.style.height = `${Math.round(width * sh / sw)}px`;
        screen.style.backgroundImage = `url(${state.lastImage})`;
        screen.setAttribute('role', 'img');
        screen.setAttribute('aria-label', `${p.name}, ${orientation}, ${state.guide.screen} screen`);
        p.zones[orientation][state.guide.screen].forEach((z) => screen.append(hatch('tpl-zone', z.label, z.box)));
        const cap = document.createElement('figcaption');
        cap.textContent = p.rotates ? `${p.name} (${orientation})` : p.name;
        fig.append(screen, cap);
        grid.append(fig);
      });
    });
  }

  function bindDevices() {
    $('#guideDevice').addEventListener('change', (e) => {
      state.guide.device = e.target.value;
      drawSafeAreas();
    });
    $('#guideOrientation').addEventListener('change', (e) => {
      state.guide.orientation = e.target.value;
      drawSafeAreas();
    });
    $('#guideScreen').addEventListener('change', (e) => {
      state.guide.screen = e.target.value;
      drawSafeAreas();
      schedulePreview(); // device warnings depend on the screen
    });
    $$('.device-pick').forEach((c) => c.addEventListener('change', schedulePreview));
    $('#guideOrientation').disabled = true;
  }

  // ── Role variants ──────────────────────────────────

  // Same rule as wallrender.roles.normalize_role and Brander's role images.
  const roleKey = (text) => String(text || '').replace(/\s+/g, '').toLowerCase();

  function previewValues() {
    if (!state.template.roles || state.previewRole === null) return state.values;
    return { ...state.values, role: state.previewRole };
  }

  function parseValues(text) {
    const out = {};
    text.split('\n').forEach((line) => {
      const at = line.indexOf('=');
      if (at > 0) out[line.slice(0, at).trim()] = line.slice(at + 1).trim();
    });
    return out;
  }

  const formatValues = (values) => Object.entries(values || {}).map(([k, v]) => `${k} = ${v}`).join('\n');

  function variantCard(title, variant, onChange, extras) {
    const li = document.createElement('li');
    const h = document.createElement('h4');
    h.textContent = title;
    li.append(h);
    if (extras) extras(li);

    const bgLabel = document.createElement('label');
    bgLabel.textContent = 'Background';
    const bg = document.createElement('select');
    [['', 'Template background'], ['color', 'Color'], ['asset', 'Image asset']].forEach(([v, t]) => bg.append(new Option(t, v)));
    const color = document.createElement('input');
    color.type = 'color';
    color.setAttribute('aria-label', `${title} background color`);
    const asset = document.createElement('select');
    asset.className = 'asset-select';
    asset.setAttribute('aria-label', `${title} background image`);
    asset.append(new Option('Choose an asset…', ''));
    state.assets.forEach((a) => asset.append(new Option(a.id, a.id)));
    const b = variant.background || {};
    bg.value = b.asset !== undefined ? 'asset' : b.color ? 'color' : '';
    color.value = (b.color || '#0b2545').slice(0, 7);
    asset.value = b.asset || '';
    const showBg = () => {
      color.hidden = bg.value !== 'color';
      asset.hidden = bg.value !== 'asset';
    };
    showBg();
    const applyBg = () => {
      showBg();
      if (bg.value === 'color') variant.background = { color: color.value.toUpperCase() };
      else if (bg.value === 'asset' && asset.value) variant.background = { asset: asset.value };
      else delete variant.background;
      onChange();
    };
    [bg, color, asset].forEach((el) => el.addEventListener('change', applyBg));
    color.addEventListener('input', applyBg);
    bgLabel.append(bg);
    li.append(bgLabel, color, asset);

    const valuesLabel = document.createElement('label');
    valuesLabel.textContent = 'Text values, one per line: name = text';
    const values = document.createElement('textarea');
    values.rows = 2;
    values.value = formatValues(variant.values);
    values.addEventListener('input', () => {
      variant.values = parseValues(values.value);
      if (!Object.keys(variant.values).length) delete variant.values;
      onChange();
    });
    valuesLabel.append(values);
    li.append(valuesLabel);
    return li;
  }

  function rolesChanged() {
    drawRoleOptions();
    schedulePreview();
  }

  function drawVariants() {
    const roles = state.template.roles;
    $('#rolesOn').checked = Boolean(roles);
    $('#rolesBody').hidden = !roles;
    const list = $('#variantList');
    list.replaceChildren();
    if (!roles) {
      drawRoleOptions();
      return;
    }
    $('#roleAttribute').value = roles.attribute || '';
    roles.variants = roles.variants || {};
    Object.keys(roles.variants).forEach((key) => {
      list.append(variantCard(`Role: ${state.roleLabels[key] || key}`, roles.variants[key], rolesChanged, (li) => {
        const label = document.createElement('label');
        label.textContent = 'Role, as written in Jamf';
        const input = document.createElement('input');
        input.type = 'text';
        input.value = state.roleLabels[key] || key;
        const shown = document.createElement('span');
        shown.className = 'tpl-variant-key';
        shown.textContent = `matches "${key}"`;
        input.addEventListener('change', () => {
          const next = roleKey(input.value);
          if (!next || (next !== key && roles.variants[next])) {
            input.value = state.roleLabels[key] || key;
            setStatus(next ? `There is already a variant for "${next}".` : 'A role needs a name.');
            return;
          }
          const variant = roles.variants[key];
          delete roles.variants[key];
          roles.variants[next] = variant;
          delete state.roleLabels[key];
          state.roleLabels[next] = input.value.trim();
          drawVariants();
          rolesChanged();
        });
        const remove = iconButton('Delete', `Delete the variant for ${key}`, false, () => {
          delete roles.variants[key];
          drawVariants();
          rolesChanged();
        });
        label.append(input);
        li.append(label, shown, remove);
      }));
    });
    roles.empty = roles.empty || {};
    roles.default = roles.default || {};
    list.append(variantCard('No role set', roles.empty, rolesChanged));
    list.append(variantCard('Any other role', roles.default, rolesChanged));
    drawRoleOptions();
  }

  function roleValueNames() {
    const roles = state.template.roles;
    if (!roles) return [];
    const names = new Set(['name']);
    [...Object.values(roles.variants || {}), roles.empty || {}, roles.default || {}].forEach((v) => {
      Object.keys(v.values || {}).forEach((k) => names.add(k));
    });
    return [...names].map((n) => `role.${n}`);
  }

  function drawRoleOptions() {
    // Preview-as picker.
    const pick = $('#previewRole');
    const keep = state.previewRole === null ? '__sample__' : state.previewRole;
    pick.replaceChildren(new Option("The sample device's values", '__sample__'), new Option('No role set', ''));
    const roles = state.template.roles;
    Object.keys((roles && roles.variants) || {}).forEach((key) => pick.append(new Option(state.roleLabels[key] || key, state.roleLabels[key] || key)));
    pick.append(new Option('Any other role', 'Another role'));
    pick.value = Array.from(pick.options).some((o) => o.value === keep) ? keep : '__sample__';
    state.previewRole = pick.value === '__sample__' ? null : pick.value;
    // Variable insert lists gain role.* names, and user.* when the
    // template opts in to personal fields (never for QR data).
    const userNames = state.template.person_fields ? ['user.real_name', 'user.username', 'user.email'] : [];
    $$('.variable-select').forEach((select) => {
      Array.from(select.options).filter((o) => o.value.startsWith('role.') || o.value.startsWith('user.'))
        .forEach((o) => o.remove());
      const extra = select.id === 'variableData' ? roleValueNames() : [...roleValueNames(), ...userNames];
      extra.forEach((n) => select.append(new Option(`{{${n}}}`, n)));
    });
  }

  // Which screen the template is for. "both" checks the lock screen's
  // safe areas, the stricter of the two.
  function applyTemplateScreen() {
    const screen = state.template.screen;
    if (screen) {
      state.guide.screen = screen === 'home' ? 'home' : 'lock';
      $('#guideScreen').value = state.guide.screen;
    }
  }

  function bindTemplateScreen() {
    $('#templateScreen').addEventListener('change', (e) => {
      if (e.target.value) state.template.screen = e.target.value;
      else delete state.template.screen;
      applyTemplateScreen();
      drawSafeAreas();
      schedulePreview();
    });
  }

  function bindPersonFields() {
    $('#personFields').addEventListener('change', (e) => {
      if (e.target.checked) state.template.person_fields = true;
      else delete state.template.person_fields;
      drawRoleOptions();
      schedulePreview();
    });
  }

  // Extension attribute names exported by JAWA (/brander/ea-names.json):
  // offered as suggestions for the role attribute. Names only, read here.
  function bindEaNames() {
    $('#eaNamesFile').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      e.target.value = '';
      if (!file) return;
      try {
        const data = JSON.parse(await file.text());
        if (data.kind !== 'jamf-ea-names' || !Array.isArray(data.names)) throw new Error('not a JAWA attribute names file');
        const names = data.names.filter((n) => typeof n === 'string' && n.length <= 100).slice(0, 500);
        $('#eaNames').replaceChildren(...names.map((n) => new Option(n, n)));
        $('#eaNamesStatus').textContent = `Loaded ${names.length} attribute names; pick one above.`;
      } catch (err) {
        $('#eaNamesStatus').textContent = `Not loaded: ${err.message}.`;
      }
    });
  }

  function bindRoles() {
    $('#rolesOn').addEventListener('change', (e) => {
      if (e.target.checked) state.template.roles = { variants: {}, empty: {}, default: {} };
      else delete state.template.roles;
      drawVariants();
      schedulePreview();
    });
    $('#roleAttribute').addEventListener('input', (e) => {
      if (e.target.value.trim()) state.template.roles.attribute = e.target.value.trim();
      else delete state.template.roles.attribute;
    });
    $('#addVariant').addEventListener('click', () => {
      const roles = state.template.roles;
      let n = 1;
      while (roles.variants[`role${n}`]) n += 1;
      roles.variants[`role${n}`] = { values: { title: `Role ${n}` } };
      state.roleLabels[`role${n}`] = `Role ${n}`;
      drawVariants();
      rolesChanged();
    });
    $('#previewRole').addEventListener('change', (e) => {
      state.previewRole = e.target.value === '__sample__' ? null : e.target.value;
      schedulePreview();
    });
  }

  // ── Sample values and export ───────────────────────

  function bindValues() {
    const area = $('#sampleValues');
    area.value = JSON.stringify(SAMPLE, null, 2);
    $('#samplePreset').addEventListener('change', (e) => {
      if (e.target.value === 'custom') {
        area.focus();
        return;
      }
      state.values = PRESETS[Number(e.target.value)].values;
      area.value = JSON.stringify(state.values, null, 2);
      $('#sampleError').hidden = true;
      schedulePreview();
    });
    $('#stressToggle').addEventListener('change', (e) => {
      state.stress = e.target.checked;
      schedulePreview();
    });
    area.addEventListener('input', () => {
      $('#samplePreset').value = 'custom';
      try {
        const parsed = JSON.parse(area.value);
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Values must be a JSON object.');
        state.values = parsed;
        $('#sampleError').hidden = true;
        schedulePreview();
      } catch (err) {
        $('#sampleError').textContent = err.message;
        $('#sampleError').hidden = false;
      }
    });
  }

  function slug(name) {
    return (name || 'template').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'template';
  }

  function saveBlob(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function ioStatus(text) {
    $('#ioStatus').textContent = text;
  }

  // Put a loaded template into the form: name, canvas, background, layers.
  function loadTemplate(t) {
    state.template = t;
    state.selected = t.layers.length ? 0 : -1;
    $('#tplName').value = t.name || '';
    const preset = $('#canvasPreset');
    const key = t.canvas ? `${t.canvas.width}x${t.canvas.height}` : '';
    const known = Array.from(preset.options).some((o) => o.value === key);
    preset.value = known ? key : 'custom';
    $('#customSize').hidden = known;
    $('#canvasWidth').value = t.canvas ? t.canvas.width : '';
    $('#canvasHeight').value = t.canvas ? t.canvas.height : '';
    const isAsset = Boolean(t.background && t.background.asset);
    $(`input[name="bgKind"][value="${isAsset ? 'asset' : 'color'}"]`).checked = true;
    $('#bgColorRow').hidden = isAsset;
    $('#bgAssetRow').hidden = !isAsset;
    if (isAsset) $('#bgAsset').value = t.background.asset;
    else $('#bgColor').value = (t.background.color || '#000000').slice(0, 7).toLowerCase();
    state.roleLabels = {};
    $('#personFields').checked = t.person_fields === true;
    $('#templateScreen').value = t.screen || '';
    applyTemplateScreen();
    drawVariants();
    drawLayers();
    drawProperties();
    schedulePreview();
  }

  function bindExport() {
    $('#openTemplate').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      e.target.value = '';
      if (!file) return;
      const form = new FormData();
      form.append('file', file);
      const resp = await fetch('/api/template/import', { method: 'POST', body: form });
      const body = await resp.json();
      if (!resp.ok) {
        ioStatus(`Not opened: ${body.error}${body.problems ? ' ' + body.problems.join('; ') : ''}`);
        return;
      }
      await loadAssets();
      loadTemplate(body.template);
      const added = body.assets.length ? ` Added assets: ${body.assets.join(', ')}.` : '';
      const replaced = body.replaced && body.replaced.length ? ` Replaced library assets: ${body.replaced.join(', ')}.` : '';
      const skipped = body.skipped && body.skipped.length ? ` Skipped: ${body.skipped.join('; ')}.` : '';
      ioStatus(`Opened ${file.name}.${added}${replaced}${skipped}`);
    });
    $('#downloadPackage').addEventListener('click', async () => {
      const t = exportable();
      const resp = await fetch('/api/template/package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: t }),
      });
      if (!resp.ok) {
        const body = await resp.json();
        ioStatus(`Not exported: ${(body.problems || [body.error]).join('; ')}`);
        return;
      }
      saveBlob(await resp.blob(), `${slug(t.name)}.brander.json`);
      ioStatus(`Downloaded ${slug(t.name)}.brander.json: upload it to JAWA's template store.`);
    });
    $('#downloadBundle').addEventListener('click', async () => {
      const t = exportable();
      const resp = await fetch('/api/template/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: t }),
      });
      if (!resp.ok) {
        const body = await resp.json();
        ioStatus(`Not exported: ${(body.problems || [body.error]).join('; ')}`);
        return;
      }
      saveBlob(await resp.blob(), `${slug(t.name)}.zip`);
      ioStatus(`Downloaded ${slug(t.name)}.zip: copy its files into Brander's assets folder.`);
    });
    $('#downloadJson').addEventListener('click', () => {
      const t = exportable();
      saveBlob(new Blob([JSON.stringify(t, null, 2) + '\n'], { type: 'application/json' }), `${slug(t.name)}.json`);
    });
  }

  // ── Start ──────────────────────────────────────────

  function init() {
    bindCanvas();
    bindAssets();
    bindLayerButtons();
    bindProperties();
    bindValues();
    bindExport();
    bindDevices();
    bindRoles();
    bindEaNames();
    bindPersonFields();
    bindTemplateScreen();
    drawVariants();
    drawLayers();
    drawProperties();
    loadAssets();
    renderPreview();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
