/**
 * DocPilot — Webdrift-Inspired Interactive Engine (landing.js)
 * Features:
 * - Continuous infinite paper-plane flight loop along calligraphic swirl
 * - Interactive ambient constellation canvas with mouse filament attraction
 * - Live AJAX document upload with immediate classification inspection card
 * - Full image and PDF handling (never renames unexpectedly)
 * - Synchronized theme management with live color adaptation
 * - Zero external libraries, high performance, 60fps GPU-accelerated
 */

(function () {
  'use strict';

  // ── 1. UTILITY FUNCTIONS ───────────────────────────────────────────────
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // ── 2. DOM INITIALIZATION ─────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initAmbientCanvas();
    initContinuousLoop();
    initSearch();
    initUpload();
    initAccordion();
    initScrollEffects();
    initKeyboardShortcuts();
  });

  // ── 3. SYNCHRONIZED THEME MANAGEMENT ──────────────────────────────────
  function initTheme() {
    const toggleBtn = document.getElementById('theme-toggle');
    if (!toggleBtn) return;

    const savedTheme = localStorage.getItem('dp-theme');
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
      updateThemeIcon(toggleBtn, savedTheme === 'dark');
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      updateThemeIcon(toggleBtn, prefersDark);
    }

    toggleBtn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme');
      const isCurrentlyDark = currentTheme === 'dark' || 
        (!currentTheme && window.matchMedia('(prefers-color-scheme: dark)').matches);
      const nextTheme = isCurrentlyDark ? 'light' : 'dark';

      document.documentElement.setAttribute('data-theme', nextTheme);
      localStorage.setItem('dp-theme', nextTheme);
      updateThemeIcon(toggleBtn, nextTheme === 'dark');
      window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: nextTheme } }));
    });
  }

  function updateThemeIcon(btn, isDark) {
    btn.setAttribute('aria-label', isDark ? 'Switch to light theme' : 'Switch to dark theme');
    if (isDark) {
      btn.innerHTML = `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
    } else {
      btn.innerHTML = `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
  }

  // ── 4. INTERACTIVE AMBIENT CONSTELLATION CANVAS ───────────────────────
  function initAmbientCanvas() {
    const canvas = document.getElementById('ambient-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0, height = 0;
    let particles = [];
    let mouse = { x: -1000, y: -1000, isHovering: false };
    let isVisible = true;
    let animId = null;

    function resize() {
      const hero = canvas.parentElement;
      width = canvas.width = hero.clientWidth || window.innerWidth;
      height = canvas.height = hero.clientHeight || window.innerHeight;
      createParticles();
    }

    function createParticles() {
      particles = [];
      const count = Math.min(Math.floor((width * height) / 18000), 55);
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.45,
          vy: (Math.random() - 0.5) * 0.45,
          radius: Math.random() * 1.8 + 1,
          phase: Math.random() * Math.PI * 2
        });
      }
    }

    function getColors() {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
        (!document.documentElement.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
      return {
        node: isDark ? 'rgba(202, 255, 166, 0.65)' : 'rgba(32, 70, 84, 0.45)',
        filament: isDark ? 'rgba(169, 224, 241, ' : 'rgba(32, 70, 84, ',
        mouseGlow: isDark ? 'rgba(202, 255, 166, 0.15)' : 'rgba(32, 70, 84, 0.08)'
      };
    }

    let colors = getColors();
    window.addEventListener('themechange', () => { colors = getColors(); });

    // Mouse movement interaction
    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.isHovering = (mouse.x >= 0 && mouse.x <= width && mouse.y >= 0 && mouse.y <= height);
    }, { passive: true });

    window.addEventListener('mouseleave', () => {
      mouse.isHovering = false;
      mouse.x = -1000;
      mouse.y = -1000;
    });

    // Visibility optimization (pause when scrolled out of view)
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        isVisible = entries[0].isIntersecting;
        if (isVisible && !animId) loop();
      }, { threshold: 0.05 });
      observer.observe(canvas.parentElement);
    }

    function loop() {
      if (!isVisible) {
        animId = null;
        return;
      }

      ctx.clearRect(0, 0, width, height);

      // Mouse soft gravitational glow
      if (mouse.isHovering) {
        const grad = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, 140);
        grad.addColorStop(0, colors.mouseGlow);
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 140, 0, Math.PI * 2);
        ctx.fill();
      }

      // Update & render particles
      const maxDist = 110;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        // Wrap edges smoothly
        if (p.x < -10) p.x = width + 10;
        if (p.x > width + 10) p.x = -10;
        if (p.y < -10) p.y = height + 10;
        if (p.y > height + 10) p.y = -10;

        // Slight magnetic reaction to mouse
        if (mouse.isHovering) {
          const mdx = mouse.x - p.x;
          const mdy = mouse.y - p.y;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
          if (mdist < 140 && mdist > 2) {
            p.x += (mdx / mdist) * 0.4;
            p.y += (mdy / mdist) * 0.4;
          }
        }

        // Draw node
        ctx.fillStyle = colors.node;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        // Connect filaments to nearby nodes
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < maxDist) {
            const alpha = (1 - dist / maxDist) * 0.28;
            ctx.strokeStyle = colors.filament + alpha + ')';
            ctx.lineWidth = 0.85;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }

        // Connect filament to mouse cursor if near
        if (mouse.isHovering) {
          const mdx = p.x - mouse.x;
          const mdy = p.y - mouse.y;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
          if (mdist < 130) {
            const mAlpha = (1 - mdist / 130) * 0.35;
            ctx.strokeStyle = colors.filament + mAlpha + ')';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(mouse.x, mouse.y);
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(loop);
    }

    window.addEventListener('resize', resize);
    resize();
    loop();
  }

  // ── 5. CRAZY CONTINUOUS FLIGHT LOOP & TELEMETRY ────────────────────────
  let loopState = {
    rafId: null,
    totalLen: 0,
    startTime: null,
    cycleDuration: 5200, // 5.2s per complete flight loop
    uiRevealed: false
  };

  function initContinuousLoop() {
    const ribbon = document.getElementById('swirl-ribbon');
    const plane = document.getElementById('dp-plane');
    const searchCard = document.getElementById('search-card');
    const siteHeader = document.getElementById('site-header');
    const skipBtn = document.getElementById('skip-intro');
    const telemetryTag = document.getElementById('telemetry-tag');

    if (!ribbon || !plane || !searchCard) return;

    try {
      loopState.totalLen = ribbon.getTotalLength();
    } catch (e) {
      loopState.totalLen = 2200;
    }

    const totalLen = loopState.totalLen;
    ribbon.style.strokeDasharray = `${totalLen * 0.6} ${totalLen * 0.4}`;
    plane.style.visibility = 'visible';
    plane.style.opacity = '1';

    // Reveal UI quickly so user can immediately use search/upload without waiting
    setTimeout(() => {
      revealCard(searchCard, siteHeader, skipBtn);
    }, 700);

    if (skipBtn) {
      skipBtn.addEventListener('click', () => {
        revealCard(searchCard, siteHeader, skipBtn);
        if (skipBtn) skipBtn.hidden = true;
      });
    }

    function tick(timestamp) {
      if (!loopState.startTime) loopState.startTime = timestamp;
      const elapsed = timestamp - loopState.startTime;

      // Loop progress from 0 to 1 continuously
      const progress = (elapsed % loopState.cycleDuration) / loopState.cycleDuration;

      // Current coordinates along calligraphic ribbon
      const curDist = progress * totalLen;
      const curPt = ribbon.getPointAtLength(curDist);

      // Ahead coordinate to determine flight tangent
      const aheadDist = (curDist + 6) % totalLen;
      const aheadPt = ribbon.getPointAtLength(aheadDist);

      const dx = aheadPt.x - curPt.x;
      const dy = aheadPt.y - curPt.y;
      const angle = Math.atan2(dy, dx) * (180 / Math.PI);
      const wobble = Math.sin(progress * Math.PI * 16) * 1.8;

      // Dynamic electric ribbon beam offset
      const ribbonOffset = (totalLen * (1 - progress * 2)) % totalLen;
      ribbon.style.strokeDashoffset = ribbonOffset.toFixed(1);

      // Paper plane positioning
      plane.setAttribute(
        'transform',
        `translate(${curPt.x.toFixed(1)}, ${curPt.y.toFixed(1)}) rotate(${(angle + wobble).toFixed(1)})`
      );

      // Live telemetry readout updates
      if (telemetryTag) {
        telemetryTag.textContent = `x ${(curPt.x / 1000).toFixed(2)} · y ${(curPt.y / 480).toFixed(2)} · ${(angle).toFixed(0)}°`;
      }

      loopState.rafId = requestAnimationFrame(tick);
    }

    loopState.rafId = requestAnimationFrame(tick);
  }

  function revealCard(searchCard, siteHeader, skipBtn) {
    if (!loopState.uiRevealed && searchCard) {
      searchCard.classList.add('revealed');
      searchCard.removeAttribute('inert');
      searchCard.removeAttribute('aria-hidden');
      loopState.uiRevealed = true;
    }
    if (siteHeader) siteHeader.removeAttribute('aria-hidden');
    if (skipBtn) skipBtn.hidden = true;
  }

  // ── 6. INSTANT LIVE SEARCH ─────────────────────────────────────────────
  function initSearch() {
    const form = document.getElementById('search-form');
    const input = document.getElementById('search-input');
    const clearBtn = document.getElementById('input-clear');
    const submitBtn = document.getElementById('btn-search');
    const resultsLive = document.getElementById('results-live');

    if (!form || !input || !resultsLive) return;

    input.addEventListener('input', () => {
      const hasValue = input.value.trim().length > 0;
      if (clearBtn) clearBtn.hidden = !hasValue;
      if (!hasValue) resultsLive.innerHTML = '';
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        input.value = '';
        clearBtn.hidden = true;
        resultsLive.innerHTML = '';
        input.focus();
      });
    }

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const query = input.value.trim();
      if (!query) return;

      performSearch(query, submitBtn, resultsLive);
    });
  }

  async function performSearch(query, submitBtn, resultsLive) {
    if (submitBtn) submitBtn.classList.add('loading');
    resultsLive.innerHTML = `
      <div class="results-state">
        <div class="spinner" style="margin: 0 auto 10px;"></div>
        <p>Scanning local indexed documents...</p>
      </div>
    `;

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Query error');
      const data = await res.json();
      const results = data.results || [];

      if (results.length === 0) {
        resultsLive.innerHTML = `
          <div class="results-state">
            <p>No filed documents matching "<strong>${escapeHtml(query)}</strong>".</p>
            <p style="font-size:12px;margin-top:6px;opacity:0.8">Try searching by category, party name, or invoice number.</p>
          </div>
        `;
      } else {
        const items = results.map(r => `
          <div class="result-card">
            <div class="result-filename" title="${escapeHtml(r.filename)}">${escapeHtml(r.filename)}</div>
            <span class="result-type">${escapeHtml(r.doc_type || 'Document')}</span>
            <span class="result-conf">${r.confidence}% match</span>
            <a href="/dashboard" class="btn-primary" style="height:28px;padding:0 12px;font-size:12px;margin-left:auto;text-decoration:none">View</a>
          </div>
        `).join('');

        resultsLive.innerHTML = `<div class="results-grid">${items}</div>`;
      }
    } catch (err) {
      resultsLive.innerHTML = `
        <div class="results-state">
          <p>Search query could not be executed. Access all records in the <a href="/dashboard" style="text-decoration:underline">Workspace</a>.</p>
        </div>
      `;
    } finally {
      if (submitBtn) submitBtn.classList.remove('loading');
    }
  }

  // ── 7. ROBUST UPLOAD & LIVE CLASSIFICATION INSPECTOR ───────────────────
  function initUpload() {
    const zone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const errorMsg = document.getElementById('zone-error');
    const preview = document.getElementById('file-preview');
    const previewName = document.getElementById('preview-filename');
    const previewSize = document.getElementById('preview-filesize');
    const removeBtn = document.getElementById('remove-file');
    const submitBtn = document.getElementById('btn-upload-submit');
    const progressWrap = document.getElementById('upload-progress');
    const progressFill = document.getElementById('upload-progress-fill');
    const resultsLive = document.getElementById('results-live');

    if (!zone || !fileInput) return;

    let selectedFile = null;

    zone.addEventListener('click', (e) => {
      if (e.target.closest('#remove-file') || e.target.closest('#btn-upload-submit')) return;
      fileInput.click();
    });

    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        validateAndSetFile(fileInput.files[0]);
      }
    });

    ['dragenter', 'dragover'].forEach(name => {
      zone.addEventListener(name, (e) => {
        e.preventDefault(); e.stopPropagation();
        zone.classList.add('dragging');
      });
    });

    ['dragleave', 'dragend', 'drop'].forEach(name => {
      zone.addEventListener(name, (e) => {
        e.preventDefault(); e.stopPropagation();
        zone.classList.remove('dragging');
      });
    });

    zone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        validateAndSetFile(e.dataTransfer.files[0]);
      }
    });

    window.addEventListener('paste', (e) => {
      if (e.clipboardData && e.clipboardData.files.length > 0) {
        validateAndSetFile(e.clipboardData.files[0]);
      }
    });

    function validateAndSetFile(file) {
      if (!file) return;

      const validExts = ['.pdf', '.png', '.jpg', '.jpeg', '.webp'];
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      const maxSize = 10 * 1024 * 1024; // 10MB

      if (!validExts.includes(ext)) {
        showError('Supported formats: PDF, PNG, JPG, JPEG, and WebP.');
        return;
      }

      if (file.size > maxSize) {
        showError('File exceeds 10 MB limit. Please select a smaller document.');
        return;
      }

      clearError();
      selectedFile = file;

      if (previewName) previewName.textContent = file.name;
      if (previewSize) previewSize.textContent = formatBytes(file.size);
      if (preview) preview.hidden = false;
      if (submitBtn) {
        submitBtn.hidden = false;
        submitBtn.disabled = false;
        submitBtn.textContent = 'Process & Classify Document';
      }
    }

    function showError(msg) {
      if (errorMsg) errorMsg.textContent = msg;
      zone.classList.add('has-error');
      if (preview) preview.hidden = true;
      if (submitBtn) submitBtn.hidden = true;
      selectedFile = null;
    }

    function clearError() {
      if (errorMsg) errorMsg.textContent = '';
      zone.classList.remove('has-error');
    }

    if (removeBtn) {
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFile = null;
        fileInput.value = '';
        if (preview) preview.hidden = true;
        if (submitBtn) submitBtn.hidden = true;
        clearError();
      });
    }

    // Interactive AJAX upload handling
    if (submitBtn) {
      submitBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!selectedFile) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Analyzing content...';
        if (progressWrap) progressWrap.hidden = false;
        if (progressFill) progressFill.style.width = '35%';

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
          if (progressFill) progressFill.style.width = '70%';

          const response = await fetch('/upload?json=1', {
            method: 'POST',
            body: formData,
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'Accept': 'application/json'
            }
          });

          if (progressFill) progressFill.style.width = '100%';

          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || 'Upload error');
          }

          const data = await response.json();

          // Render live Webdrift inspector card directly on the landing page!
          renderUploadResult(data);

          // Reset dropzone for next file
          selectedFile = null;
          fileInput.value = '';
          if (preview) preview.hidden = true;
          submitBtn.hidden = true;
          setTimeout(() => {
            if (progressWrap) progressWrap.hidden = true;
            if (progressFill) progressFill.style.width = '0%';
          }, 400);

        } catch (err) {
          showError(err.message || 'Processing failed. Please retry.');
          submitBtn.disabled = false;
          submitBtn.textContent = 'Process & Classify Document';
          if (progressWrap) progressWrap.hidden = true;
        }
      });
    }

    function renderUploadResult(data) {
      if (!resultsLive) return;

      const isDup = data.is_duplicate;
      const statusLabel = data.status === 'filed' ? 'Auto-Filed' :
        (data.status === 'pending_approval' ? 'Awaiting Approval' : 'Review Queue');

      const cardHtml = `
        <div class="upload-live-result" role="region" aria-label="Filing result for ${escapeHtml(data.filename)}">
          <div class="ulr-header">
            <span class="ulr-badge">
              <span class="status-dot"></span>
              ${isDup ? 'Previously Processed' : 'Filing Verified'}
            </span>
            <span style="font-family:var(--mono);font-size:12px;font-weight:700;color:var(--spring)">
              ${data.confidence}% Confidence
            </span>
          </div>

          <div class="ulr-title">
            Document: <strong>${escapeHtml(data.filename)}</strong>
          </div>

          <div class="ulr-meta">
            Detected Type: <strong>${escapeHtml(data.doc_type)}</strong> · Destination: <strong>${escapeHtml(data.destination)}/</strong><br>
            Status: <span style="color:var(--text-1);font-weight:600">${statusLabel}</span> · ${escapeHtml(data.reasoning || data.message || '')}
          </div>

          <div class="ulr-actions">
            <a href="/dashboard" class="btn-primary" style="height:34px;padding:0 16px;font-size:13px">
              Open in Dashboard
            </a>
            ${data.result_url ? `
              <a href="${data.result_url}" class="btn-secondary" style="height:34px;padding:0 14px;font-size:13px">
                View Audit Details
              </a>
            ` : ''}
            <button type="button" class="btn-secondary" id="ulr-dismiss-btn" style="height:34px;padding:0 14px;font-size:13px;margin-left:auto">
              Dismiss
            </button>
          </div>
        </div>
      `;

      resultsLive.innerHTML = cardHtml;

      const dismissBtn = document.getElementById('ulr-dismiss-btn');
      if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
          resultsLive.innerHTML = '';
        });
      }
    }
  }

  // ── 8. ACCORDION NAVIGATION ────────────────────────────────────────────
  function initAccordion() {
    const triggers = Array.from(document.querySelectorAll('.accordion-trigger'));
    if (!triggers.length) return;

    triggers.forEach((trigger, idx) => {
      trigger.addEventListener('click', () => {
        const isExpanded = trigger.getAttribute('aria-expanded') === 'true';
        triggers.forEach(t => {
          if (t !== trigger) t.setAttribute('aria-expanded', 'false');
        });
        trigger.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
      });

      trigger.addEventListener('keydown', (e) => {
        let targetIdx = null;
        if (e.key === 'ArrowDown') targetIdx = (idx + 1) % triggers.length;
        else if (e.key === 'ArrowUp') targetIdx = (idx - 1 + triggers.length) % triggers.length;
        else if (e.key === 'Home') targetIdx = 0;
        else if (e.key === 'End') targetIdx = triggers.length - 1;

        if (targetIdx !== null) {
          e.preventDefault();
          triggers[targetIdx].focus();
        }
      });
    });
  }

  // ── 9. SCROLL EFFECTS & REVEAL ─────────────────────────────────────────
  function initScrollEffects() {
    const scrollProgress = document.getElementById('scroll-progress');
    const revealItems = document.querySelectorAll('.reveal-item');

    if (scrollProgress) {
      window.addEventListener('scroll', () => {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const percent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
        scrollProgress.style.width = percent.toFixed(1) + '%';
      }, { passive: true });
    }

    if ('IntersectionObserver' in window && revealItems.length > 0) {
      const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            obs.unobserve(entry.target);
          }
        });
      }, { threshold: 0.1 });

      revealItems.forEach(item => observer.observe(item));
    } else {
      revealItems.forEach(item => item.classList.add('visible'));
    }
  }

  // ── 10. KEYBOARD SHORTCUTS ─────────────────────────────────────────────
  function initKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      if (activeTag === 'input' || activeTag === 'textarea') {
        if (e.key === 'Escape') {
          const searchInput = document.getElementById('search-input');
          const clearBtn = document.getElementById('input-clear');
          const resultsLive = document.getElementById('results-live');
          if (searchInput && document.activeElement === searchInput) {
            searchInput.value = '';
            if (clearBtn) clearBtn.hidden = true;
            if (resultsLive) resultsLive.innerHTML = '';
            searchInput.blur();
          }
        }
        return;
      }

      if (e.key === '/') {
        e.preventDefault();
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });
  }

})();
