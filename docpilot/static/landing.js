/**
 * DocPilot — Landing Page Interactive Engine (landing.js)
 * Features:
 * - 2.4s pure rAF paper-plane flight path intro along the brand logo swirl
 * - Instant skip via button, sessionStorage, or prefers-reduced-motion
 * - Live document search via /api/search
 * - Drag-drop, paste, and browse file upload with progress bar
 * - Accessible FAQ accordion with keyboard navigation
 * - Theme toggle (persisted to localStorage)
 * - Zero external dependencies, lightweight, 60fps smooth
 */

(function () {
  'use strict';

  // ── 1. HELPERS ──────────────────────────────────────────────────────────
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
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // ── 2. INITIALIZATION ON DOM READY ─────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initIntroAnimation();
    initSearch();
    initUpload();
    initAccordion();
    initScrollEffects();
    initKeyboardShortcuts();
  });

  // ── 3. THEME TOGGLE ────────────────────────────────────────────────────
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
    });
  }

  function updateThemeIcon(btn, isDark) {
    btn.setAttribute('aria-label', isDark ? 'Switch to light theme' : 'Switch to dark theme');
    // SVG icons (sun vs moon)
    if (isDark) {
      btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
    } else {
      btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
  }

  // ── 4. PAPER PLANE & SWIRL INTRO ANIMATION ────────────────────────────
  let animState = {
    rafId: null,
    startTime: null,
    revealed: false,
    duration: 2400, // 2.4s total flight duration
    revealAt: 0.65  // reveal UI at 65% of flight
  };

  function initIntroAnimation() {
    const ribbon = document.getElementById('swirl-ribbon');
    const plane = document.getElementById('dp-plane');
    const searchCard = document.getElementById('search-card');
    const siteHeader = document.getElementById('site-header');
    const skipBtn = document.getElementById('skip-intro');

    if (!ribbon || !plane || !searchCard) return;

    let totalLen = 0;
    try {
      totalLen = ribbon.getTotalLength();
    } catch (e) {
      totalLen = 2200;
    }

    const alreadySeen = sessionStorage.getItem('dp-intro') === '1';
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (alreadySeen || prefersReducedMotion) {
      skipIntroInstant(ribbon, plane, searchCard, siteHeader, skipBtn);
      return;
    }

    // Prepare ribbon & plane for flight
    ribbon.style.strokeDasharray = totalLen;
    ribbon.style.strokeDashoffset = totalLen;
    plane.style.visibility = 'visible';
    plane.style.opacity = '1';

    if (skipBtn) {
      skipBtn.addEventListener('click', () => {
        skipIntroInstant(ribbon, plane, searchCard, siteHeader, skipBtn);
      });
    }

    function tick(timestamp) {
      if (!animState.startTime) animState.startTime = timestamp;
      const elapsed = timestamp - animState.startTime;
      const progress = Math.min(elapsed / animState.duration, 1);

      // Current position & direction tangent
      const curDist = progress * totalLen;
      const curPt = ribbon.getPointAtLength(curDist);
      const aheadDist = Math.min(curDist + 4, totalLen);
      const aheadPt = ribbon.getPointAtLength(aheadDist);

      const dx = aheadPt.x - curPt.x;
      const dy = aheadPt.y - curPt.y;
      const angleDeg = Math.atan2(dy, dx) * (180 / Math.PI);
      const wobble = Math.sin(progress * Math.PI * 12) * 1.8;

      plane.setAttribute('transform', `translate(${curPt.x.toFixed(1)}, ${curPt.y.toFixed(1)}) rotate(${(angleDeg + wobble).toFixed(1)})`);
      ribbon.style.strokeDashoffset = (totalLen * (1 - progress)).toFixed(1);

      // Reveal Search UI at 65% progress
      if (progress >= animState.revealAt && !animState.revealed) {
        revealCard(searchCard);
        animState.revealed = true;
      }

      if (progress < 1) {
        animState.rafId = requestAnimationFrame(tick);
      } else {
        finishAnimation(plane, siteHeader, skipBtn);
      }
    }

    animState.rafId = requestAnimationFrame(tick);
  }

  function revealCard(searchCard) {
    if (!searchCard) return;
    searchCard.classList.add('revealed');
    searchCard.removeAttribute('inert');
    searchCard.removeAttribute('aria-hidden');
  }

  function finishAnimation(plane, siteHeader, skipBtn) {
    if (plane) {
      plane.style.transition = 'opacity 300ms ease';
      plane.style.opacity = '0';
      setTimeout(() => {
        plane.style.visibility = 'hidden';
      }, 300);
    }
    if (siteHeader) {
      siteHeader.removeAttribute('aria-hidden');
    }
    if (skipBtn) {
      skipBtn.hidden = true;
    }
    sessionStorage.setItem('dp-intro', '1');
  }

  function skipIntroInstant(ribbon, plane, searchCard, siteHeader, skipBtn) {
    if (animState.rafId) {
      cancelAnimationFrame(animState.rafId);
      animState.rafId = null;
    }
    if (ribbon) {
      ribbon.style.strokeDashoffset = '0';
    }
    if (plane) {
      plane.style.visibility = 'hidden';
      plane.style.opacity = '0';
    }
    revealCard(searchCard);
    if (siteHeader) {
      siteHeader.removeAttribute('aria-hidden');
    }
    if (skipBtn) {
      skipBtn.hidden = true;
    }
    sessionStorage.setItem('dp-intro', '1');
  }

  // ── 5. SEARCH LOGIC ────────────────────────────────────────────────────
  function initSearch() {
    const form = document.getElementById('search-form');
    const input = document.getElementById('search-input');
    const clearBtn = document.getElementById('input-clear');
    const submitBtn = document.getElementById('btn-search');
    const resultsLive = document.getElementById('results-live');

    if (!form || !input || !resultsLive) return;

    // Toggle clear button
    input.addEventListener('input', () => {
      const hasValue = input.value.trim().length > 0;
      if (clearBtn) clearBtn.hidden = !hasValue;
      if (!hasValue) {
        resultsLive.innerHTML = '';
      }
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
        <p>Searching filed documents...</p>
      </div>
    `;

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Network error');
      const data = await res.json();
      const results = data.results || [];

      if (results.length === 0) {
        resultsLive.innerHTML = `
          <div class="results-state">
            <p>No filed documents matching "<strong>${escapeHtml(query)}</strong>".</p>
            <p style="font-size:12px;margin-top:6px;opacity:0.8">Try searching by type (e.g. Invoice, Contract, Receipt) or folder name.</p>
          </div>
        `;
      } else {
        const itemsHtml = results.map(r => `
          <div class="result-card">
            <div class="result-filename" title="${escapeHtml(r.filename)}">${escapeHtml(r.filename)}</div>
            <span class="result-type">${escapeHtml(r.doc_type || 'Document')}</span>
            <span class="result-conf">${r.confidence}%</span>
            <a href="/dashboard" class="btn-primary" style="height:28px;padding:0 12px;font-size:12px;margin-left:auto;text-decoration:none">View</a>
          </div>
        `).join('');

        resultsLive.innerHTML = `
          <div class="results-grid">
            ${itemsHtml}
          </div>
        `;
      }
    } catch (err) {
      resultsLive.innerHTML = `
        <div class="results-state">
          <p>Could not retrieve search results. You can access all files in the <a href="/dashboard" style="text-decoration:underline">Dashboard</a>.</p>
        </div>
      `;
    } finally {
      if (submitBtn) submitBtn.classList.remove('loading');
    }
  }

  // ── 6. UPLOAD HANDLING ─────────────────────────────────────────────────
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

    if (!zone || !fileInput) return;

    let selectedFile = null;

    // Click on dropzone opens picker
    zone.addEventListener('click', (e) => {
      if (e.target.closest('#remove-file') || e.target.closest('#btn-upload-submit')) return;
      fileInput.click();
    });

    // Keyboard support on dropzone
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });

    // File input change
    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        validateAndSetFile(fileInput.files[0]);
      }
    });

    // Drag and Drop
    ['dragenter', 'dragover'].forEach(name => {
      zone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add('dragging');
      });
    });

    ['dragleave', 'dragend', 'drop'].forEach(name => {
      zone.addEventListener(name, (e) => {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove('dragging');
      });
    });

    zone.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        validateAndSetFile(e.dataTransfer.files[0]);
      }
    });

    // Paste file / image support
    window.addEventListener('paste', (e) => {
      if (e.clipboardData && e.clipboardData.files.length > 0) {
        validateAndSetFile(e.clipboardData.files[0]);
      }
    });

    function validateAndSetFile(file) {
      if (!file) return;

      const validExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp'];
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      const maxSize = 10 * 1024 * 1024; // 10MB

      if (!validExtensions.includes(ext)) {
        showError('Only PDF, PNG, JPG, and WebP files are accepted.');
        return;
      }

      if (file.size > maxSize) {
        showError('File exceeds 10 MB limit. Please select a smaller document.');
        return;
      }

      // Valid file
      clearError();
      selectedFile = file;

      if (previewName) previewName.textContent = file.name;
      if (previewSize) previewSize.textContent = formatBytes(file.size);
      if (preview) preview.hidden = false;
      if (submitBtn) submitBtn.hidden = false;
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

    // Remove file
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

    // Submit upload via fetch to /upload
    if (submitBtn) {
      submitBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!selectedFile) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Processing...';
        if (progressWrap) progressWrap.hidden = false;
        if (progressFill) progressFill.style.width = '45%';

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
          if (progressFill) progressFill.style.width = '75%';
          const response = await fetch('/upload', {
            method: 'POST',
            body: formData
          });

          if (progressFill) progressFill.style.width = '100%';

          // If redirected, navigate to dashboard or target URL
          if (response.redirected) {
            window.location.href = response.url;
          } else {
            window.location.href = '/dashboard';
          }
        } catch (err) {
          showError('Upload failed. Please check your connection and retry.');
          submitBtn.disabled = false;
          submitBtn.textContent = 'File Document Now';
          if (progressWrap) progressWrap.hidden = true;
        }
      });
    }
  }

  // ── 7. FAQ ACCORDION ───────────────────────────────────────────────────
  function initAccordion() {
    const triggers = Array.from(document.querySelectorAll('.accordion-trigger'));
    if (!triggers.length) return;

    triggers.forEach((trigger, idx) => {
      trigger.addEventListener('click', () => {
        const isExpanded = trigger.getAttribute('aria-expanded') === 'true';

        // Optional: close other items for clean single-expanded view
        triggers.forEach(t => {
          if (t !== trigger) {
            t.setAttribute('aria-expanded', 'false');
          }
        });

        trigger.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
      });

      // Keyboard navigation: Arrow Up, Arrow Down, Home, End
      trigger.addEventListener('keydown', (e) => {
        let targetIdx = null;
        if (e.key === 'ArrowDown') {
          targetIdx = (idx + 1) % triggers.length;
        } else if (e.key === 'ArrowUp') {
          targetIdx = (idx - 1 + triggers.length) % triggers.length;
        } else if (e.key === 'Home') {
          targetIdx = 0;
        } else if (e.key === 'End') {
          targetIdx = triggers.length - 1;
        }

        if (targetIdx !== null) {
          e.preventDefault();
          triggers[targetIdx].focus();
        }
      });
    });
  }

  // ── 8. SCROLL EFFECTS ──────────────────────────────────────────────────
  function initScrollEffects() {
    const scrollProgress = document.getElementById('scroll-progress');
    const revealItems = document.querySelectorAll('.reveal-item');

    // Scroll progress bar
    if (scrollProgress) {
      window.addEventListener('scroll', () => {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const percent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
        scrollProgress.style.width = percent.toFixed(1) + '%';
      }, { passive: true });
    }

    // Scroll reveal observer
    if ('IntersectionObserver' in window && revealItems.length > 0) {
      const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            obs.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 });

      revealItems.forEach(item => observer.observe(item));
    } else {
      // Fallback: reveal immediately
      revealItems.forEach(item => item.classList.add('visible'));
    }
  }

  // ── 9. KEYBOARD SHORTCUTS ──────────────────────────────────────────────
  function initKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      // If typing in an input, textarea, or editable element, skip '/'
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
