/* ── EWOK Application ──────────────────────── */

(function () {
  'use strict';

  // ── State ───────────────────────────────────
  let currentFilename = null;
  let processedFilename = null;
  let textOverlayCount = 0;

  // ── DOM refs ────────────────────────────────
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const uploadArea = $('#uploadArea');
  const fileInput = $('#fileInput');
  const statusMessage = $('#statusMessage');
  const controlsGrid = $('#controlsGrid');
  const previewContainer = $('#previewContainer');
  const downloadSection = $('#downloadSection');
  const processBtn = $('#processBtn');
  const downloadBtn = $('#downloadBtn');
  const resetBtn = $('#resetBtn');
  const textOverlaysContainer = $('#textOverlays');
  const addTextBtn = $('[data-action="add-text"]');

  // Range display bindings
  const rangeBindings = [
    { input: 'opacity', display: 'opacityValue', suffix: '%' },
    { input: 'saturation', display: 'saturationValue', suffix: '%' },
    { input: 'resize', display: 'resizeValue', suffix: '%' },
    { input: 'watermarkOpacity', display: 'watermarkOpacityValue', suffix: '%' },
  ];

  // ── Initialization ──────────────────────────

  function init() {
    bindUpload();
    bindButtons();
    bindRangeInputs();
    bindBackgroundType();
    bindEffectStrengthDelegation();
  }

  // ── Upload ──────────────────────────────────

  function bindUpload() {
    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
      uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadArea.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
      }
    });
  }

  async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);
    showStatus('Uploading image...', 'info');

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const result = await response.json();

      if (result.success) {
        currentFilename = result.filename;
        showStatus(
          `Image uploaded — ${result.dimensions.width}\u00d7${result.dimensions.height}`,
          'success'
        );
        showControls();
        showPreview();
        processBtn.disabled = false;
      } else {
        showStatus('Upload failed: ' + result.error, 'error');
      }
    } catch (err) {
      showStatus('Upload failed: ' + err.message, 'error');
      showToast('Upload failed — check your connection', 'error');
    }
  }

  // ── Buttons ─────────────────────────────────

  function bindButtons() {
    processBtn.addEventListener('click', processImage);
    downloadBtn.addEventListener('click', downloadImage);
    resetBtn.addEventListener('click', resetAll);
    addTextBtn.addEventListener('click', addTextOverlay);

    // Toggle buttons
    $('[data-action="toggle-wallpaper"]').addEventListener('click', toggleWallpaperMode);
    $('[data-action="toggle-background"]').addEventListener('click', toggleBackground);

    // Section collapse — delegate from all section headers
    $$('[data-section]').forEach((header) => {
      header.addEventListener('click', () => {
        toggleSection(header.getAttribute('data-section'));
      });
    });
  }

  // ── Range inputs ────────────────────────────

  function bindRangeInputs() {
    rangeBindings.forEach(({ input, display, suffix }) => {
      const el = document.getElementById(input);
      const disp = document.getElementById(display);
      if (el && disp) {
        el.addEventListener('input', () => {
          disp.textContent = el.value + suffix;
        });
      }
    });
  }

  // ── Background type switcher ────────────────

  function bindBackgroundType() {
    const bgType = $('#backgroundType');
    if (!bgType) return;

    bgType.addEventListener('change', () => {
      $$('.bg-options').forEach((p) => (p.style.display = 'none'));
      const map = {
        color: 'colorOptions',
        gradient: 'gradientOptions',
        pattern: 'patternOptions',
      };
      const target = document.getElementById(map[bgType.value]);
      if (target) target.style.display = 'block';
    });
  }

  // ── Delegated effect strength display ───────

  function bindEffectStrengthDelegation() {
    document.addEventListener('input', (e) => {
      if (e.target.classList.contains('effect-strength')) {
        const span = e.target.nextElementSibling;
        if (span && span.classList.contains('effect-strength-value')) {
          span.textContent = e.target.value;
        }
      }
    });
  }

  // ── Process Image ───────────────────────────

  async function processImage() {
    if (!currentFilename) return;

    setLoading(processBtn, true);
    showStatus('Processing image...', 'info');

    const data = {
      filename: currentFilename,
      opacity: parseInt($('#opacity').value, 10),
      saturation: parseInt($('#saturation').value, 10),
      resize: parseInt($('#resize').value, 10),
      text_overlays: getTextOverlays(),
      background: getBackgroundConfig(),
      watermark: getWatermarkConfig(),
      output_format: $('#outputFormat').value,
    };

    if ($('#wallpaperMode').checked) {
      data.wallpaper_mode = true;
      data.wallpaper_preset = $('#wallpaperPreset').value;
      data.fit_mode = $('#fitMode').value;
    }

    try {
      const response = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();

      if (result.success) {
        processedFilename = result.processed_filename;
        showStatus(
          `Processed — ${result.dimensions.width}\u00d7${result.dimensions.height}`,
          'success'
        );
        showPreview();
        downloadSection.style.display = 'block';
      } else {
        showStatus('Processing failed: ' + result.error, 'error');
        showToast(result.error, 'error');
      }
    } catch (err) {
      showStatus('Processing failed: ' + err.message, 'error');
      showToast('Processing failed — check console for details', 'error');
    }

    setLoading(processBtn, false);
  }

  // ── Download ────────────────────────────────

  function downloadImage() {
    if (processedFilename) {
      window.open('/api/download/' + processedFilename, '_blank');
    }
  }

  // ── Reset ───────────────────────────────────

  function resetAll() {
    currentFilename = null;
    processedFilename = null;
    controlsGrid.style.display = 'none';
    statusMessage.textContent = '';
    statusMessage.className = '';
    textOverlaysContainer.innerHTML = '';
    downloadSection.style.display = 'none';
    processBtn.disabled = true;
    textOverlayCount = 0;

    // Reset sliders
    $('#opacity').value = 100;
    $('#opacityValue').textContent = '100%';
    $('#saturation').value = 100;
    $('#saturationValue').textContent = '100%';
    $('#resize').value = 100;
    $('#resizeValue').textContent = '100%';

    // Reset format selector
    $('#outputFormat').value = 'png';

    // Reset toggles
    $('#wallpaperMode').checked = false;
    $('#wallpaperOptions').style.display = 'none';
    $('#enableBackground').checked = false;
    $('#backgroundOptions').style.display = 'none';
    $$('.toggle-button').forEach((btn) => btn.classList.remove('active'));

    // Reset preview
    previewContainer.innerHTML = '<p>Upload an image to see preview</p>';
  }

  // ── Sections ────────────────────────────────

  function toggleSection(sectionId) {
    const content = document.getElementById(sectionId + '-content');
    const icon = document.getElementById(sectionId + '-icon');
    if (!content || !icon) return;

    const isCollapsed = content.classList.toggle('collapsed');
    icon.classList.toggle('collapsed', isCollapsed);

    // ARIA
    const header = icon.closest('[data-section]');
    if (header) {
      header.setAttribute('aria-expanded', String(!isCollapsed));
    }
  }

  // ── Toggle Modes ────────────────────────────

  function toggleWallpaperMode() {
    const cb = $('#wallpaperMode');
    const button = cb.parentElement;
    cb.checked = !cb.checked;
    button.classList.toggle('active', cb.checked);
    $('#wallpaperOptions').style.display = cb.checked ? 'block' : 'none';
  }

  function toggleBackground() {
    const cb = $('#enableBackground');
    const button = cb.parentElement;
    cb.checked = !cb.checked;
    button.classList.toggle('active', cb.checked);
    $('#backgroundOptions').style.display = cb.checked ? 'block' : 'none';
    adjustFontSizesForBackground(cb.checked);
  }

  function adjustFontSizesForBackground(enabled) {
    const watermarkSize = $('#watermarkSize');
    if (enabled && watermarkSize.value === '24') {
      watermarkSize.value = '48';
    } else if (!enabled && watermarkSize.value === '48') {
      watermarkSize.value = '24';
    }

    $$('.overlay-size').forEach((input) => {
      if (enabled && input.value === '24') input.value = '48';
      else if (!enabled && input.value === '48') input.value = '24';
    });
  }

  // ── Text Overlays ──────────────────────────

  function getDefaultFontSize() {
    const bgEnabled = $('#enableBackground').checked;
    return bgEnabled ? 48 : 24;
  }

  function addTextOverlay() {
    textOverlayCount++;
    const defaultSize = getDefaultFontSize();
    const div = document.createElement('div');
    div.className = 'text-overlay-item';
    div.innerHTML = `
      <div class="text-overlay-header">
        <input type="text" class="overlay-text" placeholder="Enter your text" style="flex:1;font-weight:500;">
        <button class="btn btn-danger" data-action="remove-overlay" title="Remove">
          <i class="fas fa-trash"></i>
        </button>
      </div>
      <div class="overlay-settings">
        <div class="setting-row">
          <div class="setting-group">
            <label>Position</label>
            <div class="position-inputs">
              <input type="text" class="overlay-x" value="50%" placeholder="X" title="Horizontal position (px or %)">
              <input type="text" class="overlay-y" value="50%" placeholder="Y" title="Vertical position (px or %)">
            </div>
          </div>
          <div class="setting-group">
            <label>Align</label>
            <div class="alignment-group">
              <button type="button" class="align-btn" data-align="left" title="Left align">
                <i class="fas fa-align-left"></i>
              </button>
              <button type="button" class="align-btn active" data-align="center" title="Center align">
                <i class="fas fa-align-center"></i>
              </button>
              <button type="button" class="align-btn" data-align="right" title="Right align">
                <i class="fas fa-align-right"></i>
              </button>
            </div>
          </div>
          <div class="setting-group">
            <label>Size</label>
            <div class="size-input-group">
              <input type="number" class="overlay-size" value="${defaultSize}" min="8" max="200">
              <button type="button" class="size-mode-btn" data-mode="px" title="Toggle px/% sizing">px</button>
            </div>
          </div>
          <div class="setting-group">
            <label>Color</label>
            <input type="color" class="overlay-color" value="#FFFFFF">
          </div>
        </div>
        <div class="setting-row">
          <div class="setting-group">
            <label>Effect</label>
            <select class="text-effect">
              <option value="none">None</option>
              <option value="shadow">Shadow</option>
              <option value="outline">Outline</option>
              <option value="glow">Glow</option>
            </select>
          </div>
          <div class="setting-group effect-color-group">
            <label>Effect Color</label>
            <input type="color" class="effect-color" value="#000000">
          </div>
          <div class="setting-group">
            <label>Strength</label>
            <div class="strength-control">
              <input type="range" class="effect-strength" min="1" max="10" value="3">
              <span class="effect-strength-value">3</span>
            </div>
          </div>
        </div>
      </div>`;
    textOverlaysContainer.appendChild(div);

    // Remove button
    div.querySelector('[data-action="remove-overlay"]').addEventListener('click', () => {
      div.remove();
    });

    // Alignment buttons — toggle active state
    div.querySelectorAll('.align-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        div.querySelectorAll('.align-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    // Size mode toggle — switch between px and %
    const sizeModeBtn = div.querySelector('.size-mode-btn');
    const sizeInput = div.querySelector('.overlay-size');
    sizeModeBtn.addEventListener('click', () => {
      if (sizeModeBtn.dataset.mode === 'px') {
        sizeModeBtn.dataset.mode = '%';
        sizeModeBtn.textContent = '%';
        sizeInput.min = 1;
        sizeInput.max = 50;
        sizeInput.value = 5;
      } else {
        sizeModeBtn.dataset.mode = 'px';
        sizeModeBtn.textContent = 'px';
        sizeInput.min = 8;
        sizeInput.max = 200;
        sizeInput.value = getDefaultFontSize();
      }
    });

    // Effect type visibility
    const effectSelect = div.querySelector('.text-effect');
    const effectColorGroup = div.querySelector('.effect-color-group');
    effectSelect.addEventListener('change', () => {
      effectColorGroup.style.display =
        effectSelect.value === 'none' || effectSelect.value === 'glow' ? 'none' : 'flex';
    });
    // Initial state
    effectColorGroup.style.display = 'none';
  }

  function getTextOverlays() {
    const overlays = [];
    $$('.text-overlay-item').forEach((item) => {
      const text = item.querySelector('.overlay-text').value;
      if (text.trim()) {
        const sizeMode = item.querySelector('.size-mode-btn').dataset.mode;
        const sizeValue = parseInt(item.querySelector('.overlay-size').value, 10);

        const overlay = {
          text,
          x: item.querySelector('.overlay-x').value,
          y: item.querySelector('.overlay-y').value,
          color: item.querySelector('.overlay-color').value,
          alignment: item.querySelector('.align-btn.active').dataset.align,
          text_effect: item.querySelector('.text-effect').value,
          effect_color: item.querySelector('.effect-color').value,
          effect_strength: parseInt(item.querySelector('.effect-strength').value, 10),
        };

        if (sizeMode === '%') {
          overlay.size_percent = sizeValue;
        } else {
          overlay.size = sizeValue;
        }

        overlays.push(overlay);
      }
    });
    return overlays;
  }

  // ── Background Config ───────────────────────

  function getBackgroundConfig() {
    if (!$('#enableBackground').checked) return null;

    const bgType = $('#backgroundType').value;
    if (bgType === 'color') {
      return { type: 'color', color: $('#backgroundColor').value };
    }
    if (bgType === 'gradient') {
      return {
        type: 'gradient',
        start_color: $('#gradientStart').value,
        end_color: $('#gradientEnd').value,
        direction: $('#gradientDirection').value,
      };
    }
    if (bgType === 'pattern') {
      return {
        type: 'pattern',
        pattern: $('#patternType').value,
        color1: $('#patternColor1').value,
        color2: $('#patternColor2').value,
      };
    }
    return null;
  }

  // ── Watermark Config ────────────────────────

  function getWatermarkConfig() {
    const text = $('#watermarkText').value.trim();
    if (!text) return null;
    return {
      type: 'text',
      text,
      position: $('#watermarkPosition').value,
      size: parseInt($('#watermarkSize').value, 10),
      color: $('#watermarkColor').value,
      opacity: parseInt($('#watermarkOpacity').value, 10),
    };
  }

  // ── Preview ─────────────────────────────────

  function showPreview() {
    let src;
    if (processedFilename) {
      src = '/api/preview/' + processedFilename;
    } else if (currentFilename) {
      src = '/api/original/' + currentFilename;
    } else {
      previewContainer.innerHTML = '<p>Upload an image to see preview</p>';
      return;
    }

    previewContainer.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.className = 'preview-container click-to-place';

    const img = document.createElement('img');
    img.id = 'preview-image';
    img.alt = 'Preview';
    img.src = src;
    img.addEventListener('error', () => {
      previewContainer.innerHTML = '<p>Failed to load preview</p>';
      showToast('Preview image failed to load', 'error');
    });

    // Click-to-place handler
    img.addEventListener('click', handlePreviewClick);

    wrapper.appendChild(img);
    previewContainer.appendChild(wrapper);
  }

  function handlePreviewClick(e) {
    const img = e.target;
    const rect = img.getBoundingClientRect();
    const xPct = ((e.clientX - rect.left) / rect.width * 100).toFixed(1);
    const yPct = ((e.clientY - rect.top) / rect.height * 100).toFixed(1);

    // If no text overlays exist, create one
    let overlayItems = $$('.text-overlay-item');
    if (overlayItems.length === 0) {
      addTextOverlay();
      overlayItems = $$('.text-overlay-item');
    }

    // Set position on the last text overlay
    const lastOverlay = overlayItems[overlayItems.length - 1];
    lastOverlay.querySelector('.overlay-x').value = xPct + '%';
    lastOverlay.querySelector('.overlay-y').value = yPct + '%';

    // Visual indicator
    const wrapper = img.parentElement;
    const existing = wrapper.querySelector('.click-indicator');
    if (existing) existing.remove();

    const dot = document.createElement('div');
    dot.className = 'click-indicator';
    dot.style.left = xPct + '%';
    dot.style.top = yPct + '%';
    wrapper.appendChild(dot);
  }

  function showControls() {
    controlsGrid.style.display = 'grid';
  }

  // ── Status & Toast ──────────────────────────

  function showStatus(message, type) {
    statusMessage.className = 'status-message status-' + type;
    statusMessage.textContent = message;
    statusMessage.setAttribute('aria-live', 'polite');
  }

  function showToast(message, type) {
    // Remove existing toast
    const old = $('.toast');
    if (old) old.remove();

    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    toast.setAttribute('role', 'alert');
    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ── Loading State ───────────────────────────

  function setLoading(btn, loading) {
    if (loading) {
      btn.classList.add('loading');
      btn.disabled = true;
    } else {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  }

  // ── Boot ────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
