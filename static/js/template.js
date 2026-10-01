/* EWOK template designer: edits a wallrender template (schema v1) and
   previews it through /api/template/preview. No framework; the template
   object is the single source of truth and the form is redrawn from it. */
(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const SAMPLE = {
    device_name: 'Ward 3 iPad',
    serial_number: 'DMPX1234ABCD',
    asset_tag: 'HR-0042',
    jss_id: 42,
    location: { building: 'North Campus' },
  };

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
        body: JSON.stringify({ template: exportable(), values: state.values }),
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
      setStatus(`Rendered ${state.template.canvas ? state.template.canvas.width + '×' + state.template.canvas.height : ''} with the sample device.`);
    } catch (err) {
      if (err.name !== 'AbortError') setStatus('Not rendered: could not reach EWOK.');
    }
  }

  function setStatus(text) {
    $('#previewStatus').textContent = text;
  }

  function showWarnings(list) {
    const ul = $('#warningList');
    ul.replaceChildren();
    if (!list.length) {
      const li = document.createElement('li');
      li.className = 'ok';
      li.textContent = 'No warnings.';
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
        $('#canvasWidth').value = state.template.canvas.width;
        $('#canvasHeight').value = state.template.canvas.height;
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
  const SNAP = 0.01; // snap when the centre is within 1% of the canvas
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

  // ── Sample values and export ───────────────────────

  function bindValues() {
    const area = $('#sampleValues');
    area.value = JSON.stringify(SAMPLE, null, 2);
    area.addEventListener('input', () => {
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

  function bindExport() {
    $('#downloadJson').addEventListener('click', () => {
      const t = exportable();
      const blob = new Blob([JSON.stringify(t, null, 2) + '\n'], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${(t.name || 'template').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'template'}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
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
    drawLayers();
    drawProperties();
    loadAssets();
    renderPreview();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
