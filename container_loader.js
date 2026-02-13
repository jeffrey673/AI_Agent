/* SKIN1004 AI — loader.js
   1) Theme default (dark on first visit)
   2) Inject Craver "WHAT DO YOU CRAVE?" animation on login page
   3) Theme toggle button (bottom-right)
*/

// ===== 1. Theme: respect user choice (no forced override) =====
if (!localStorage.theme) {
  localStorage.theme = "dark";
}

// ===== 1b. Inject dark mode logo CSS =====
// splash.png is now the DARK version (black bg + white "C.").
// - Dark mode: Tailwind adds dark:invert → we cancel it with filter:none
// - Light mode: No Tailwind filter → we add invert(1) to flip to white bg + black "C."
(function() {
  var style = document.createElement('style');
  style.id = 'skin-logo-fix';
  style.textContent = [
    'html.dark img[alt="logo"] { filter: none !important; -webkit-filter: none !important; }',
    'html.light img[alt="logo"] { filter: invert(1) !important; -webkit-filter: invert(1) !important; }',
    'img[alt="logo"] { transition: filter 0.2s ease !important; }'
  ].join('\n');
  document.head.appendChild(style);
})();

// ===== 2. Craver animation injection =====
(function () {
  var MARQUEE_HTML = [
    '<div id="craver-bg">',

    // ---- Big CRAVE text (center) ----
    '  <div class="craver-crave">',
    '    <p class="craver-line craver-l1">WHAT</p>',
    '    <p class="craver-line craver-l2">DO YOU</p>',
    '    <p class="craver-line craver-l3">CRAVE?</p>',
    '  </div>',

    // ---- Marquee rows ----
    '  <div class="craver-marquees">',

    // Row 1 — scrolls left
    '    <div class="craver-row craver-row1">',
    '      <div class="craver-track craver-track-left">',
    '        <span class="craver-outline">WHAT YOU NEED. WE</span>',
    '        <span class="craver-solid"><em>WONDER</em><small>\uBB34\uC5C7\uC774 \uD544\uC694\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '        <span class="craver-outline">WHAT YOU NEED. WE</span>',
    '        <span class="craver-solid"><em>WONDER</em><small>\uBB34\uC5C7\uC774 \uD544\uC694\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '      </div>',
    '    </div>',

    // Row 2 — scrolls right (reverse)
    '    <div class="craver-row craver-row2">',
    '      <div class="craver-track craver-track-right">',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '      </div>',
    '    </div>',

    // Row 3 — scrolls left
    '    <div class="craver-row craver-row3">',
    '      <div class="craver-track craver-track-left">',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_work.png" alt="" />',
    '        <span class="craver-outline">FOR TODAY? WHAT</span>',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_work.png" alt="" />',
    '        <span class="craver-outline">FOR TODAY? WHAT</span>',
    '      </div>',
    '    </div>',

    '  </div>',
    '</div>'
  ].join("\n");

  // ---- Chat page marquee (no big CRAVE text, just scrolling rows) ----
  var CHAT_MARQUEE_HTML = [
    '<div id="craver-bg" class="craver-chat-mode">',
    '  <div class="craver-marquees">',

    // Row 1 — scrolls left (top)
    '    <div class="craver-row craver-row1">',
    '      <div class="craver-track craver-track-left">',
    '        <span class="craver-outline">WHAT YOU NEED. WE</span>',
    '        <span class="craver-solid"><em>WONDER</em><small>\uBB34\uC5C7\uC774 \uD544\uC694\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '        <span class="craver-outline">WHAT YOU NEED. WE</span>',
    '        <span class="craver-solid"><em>WONDER</em><small>\uBB34\uC5C7\uC774 \uD544\uC694\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '      </div>',
    '    </div>',

    // Row 2 — scrolls right (middle)
    '    <div class="craver-row craver-row2">',
    '      <div class="craver-track craver-track-right">',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '      </div>',
    '    </div>',

    // Row 3 — scrolls left (bottom)
    '    <div class="craver-row craver-row3">',
    '      <div class="craver-track craver-track-left">',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_work.png" alt="" />',
    '        <span class="craver-outline">FOR TODAY? WHAT</span>',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/static/craver_work.png" alt="" />',
    '        <span class="craver-outline">FOR TODAY? WHAT</span>',
    '      </div>',
    '    </div>',

    '  </div>',
    '</div>'
  ].join("\n");

  function isAuthPage() {
    var p = window.location.pathname;
    return p.startsWith("/auth");
  }

  function inject() {
    if (document.getElementById("craver-bg")) return;

    var wrapper = document.createElement("div");
    if (isAuthPage()) {
      // Auth page: full craver bg (big CRAVE text + marquees)
      wrapper.innerHTML = MARQUEE_HTML;
    } else {
      // Chat page: marquees only (no big CRAVE text)
      wrapper.innerHTML = CHAT_MARQUEE_HTML;
    }
    var el = wrapper.firstElementChild;
    document.body.appendChild(el);
  }

  function cleanup() {
    var el = document.getElementById("craver-bg");
    if (!el) return;
    // Remove if switching between auth <-> chat (different layouts)
    var onAuth = isAuthPage();
    var isChatMode = el.classList.contains("craver-chat-mode");
    if ((onAuth && isChatMode) || (!onAuth && !isChatMode)) {
      el.remove();
    }
  }

  // Inject after DOM ready
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    inject();
    setTimeout(inject, 300);
    setTimeout(inject, 800);
    setTimeout(inject, 2000);
    setTimeout(inject, 4000);
  });

  // Watch for SvelteKit client-side navigation
  var lastPath = window.location.pathname;
  setInterval(function () {
    var cur = window.location.pathname;
    if (cur !== lastPath) {
      lastPath = cur;
      cleanup();
      inject();
      setTimeout(inject, 300);
      setTimeout(inject, 800);
    }
    // Re-inject if removed by SvelteKit DOM replacement
    if (!document.getElementById("craver-bg")) {
      inject();
    }
  }, 500);

  // MutationObserver: re-inject if SvelteKit removes craver-bg
  if (typeof MutationObserver !== "undefined") {
    ready(function () {
      var mo = new MutationObserver(function () {
        if (!document.getElementById("craver-bg")) {
          inject();
        }
      });
      mo.observe(document.body, { childList: true, subtree: false });
    });
  }
})();


// ===== 3. Theme toggle button (bottom-right) =====
(function () {
  // SVG icons
  var SUN_SVG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
  var MOON_SVG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

  function getCurrentTheme() {
    return localStorage.theme || "dark";
  }

  function applyTheme(theme) {
    var html = document.documentElement;
    html.classList.remove("dark", "light", "oled-dark", "her");
    html.classList.add(theme);
    localStorage.theme = theme;

    // Update meta theme-color
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute("content", theme === "light" ? "#ffffff" : "#171717");
    }

    // Update favicon dynamically
    var favicons = document.querySelectorAll('link[rel*="icon"]');
    favicons.forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href || !href.startsWith("/static/favicon")) return;
      if (theme === "dark") {
        // Use dark (white) favicon
        if (href.indexOf("favicon.png") !== -1 && href.indexOf("96x96") === -1) {
          link.setAttribute("href", "/static/favicon-dark.png");
        }
      } else {
        // Use light (black) favicon
        if (href.indexOf("favicon-dark.png") !== -1) {
          link.setAttribute("href", "/static/favicon.png");
        }
      }
    });

    // Update toggle button icon
    updateToggleIcon();

    // Logo handling: splash.png is now the dark version.
    // CSS injection (Section 1b) handles dark/light via filter overrides.
    // No src swapping needed — just ensure filter reapplies on theme change.
    var imgs = document.querySelectorAll('img[alt="logo"]');
    imgs.forEach(function (img) {
      // Force browser to re-evaluate CSS by toggling a data attribute
      img.setAttribute("data-theme", theme);
    });
  }

  function updateToggleIcon() {
    var btn = document.getElementById("skin-theme-toggle");
    if (!btn) return;
    var theme = getCurrentTheme();
    // Show sun icon in dark mode (click to go light), moon icon in light mode (click to go dark)
    btn.innerHTML = (theme === "light") ? MOON_SVG : SUN_SVG;
    btn.title = (theme === "light") ? "Dark Mode" : "Light Mode";
  }

  function createToggle() {
    if (document.getElementById("skin-theme-toggle")) return;

    var btn = document.createElement("button");
    btn.id = "skin-theme-toggle";
    btn.setAttribute("aria-label", "Toggle theme");

    btn.addEventListener("click", function () {
      var cur = getCurrentTheme();
      var next = (cur === "light") ? "dark" : "light";
      applyTheme(next);
    });

    document.body.appendChild(btn);
    updateToggleIcon();
  }

  // Initialize
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    createToggle();
    setTimeout(createToggle, 500);
  });
})();


// ===== 4. (removed — Dashboard is self-hosted at :8100/dashboard) =====


// ===== 5. Dark mode logo — CSS-only approach =====
// splash.png IS the dark version (black bg + white "C.").
// Section 1b injects CSS: dark mode → filter:none, light mode → filter:invert(1).
// No JS src swapping needed. This section is kept as a safety net
// to ensure the CSS style element exists after SvelteKit navigation.
(function () {
  function ensureLogoCSS() {
    if (document.getElementById('skin-logo-fix')) return;
    var style = document.createElement('style');
    style.id = 'skin-logo-fix';
    style.textContent = [
      'html.dark img[alt="logo"] { filter: none !important; -webkit-filter: none !important; }',
      'html.light img[alt="logo"] { filter: invert(1) !important; -webkit-filter: invert(1) !important; }',
      'img[alt="logo"] { transition: filter 0.2s ease !important; }'
    ].join('\n');
    document.head.appendChild(style);
  }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    ensureLogoCSS();
    setTimeout(ensureLogoCSS, 300);
    setTimeout(ensureLogoCSS, 800);
    setTimeout(ensureLogoCSS, 2000);
  });

  // Watch for SvelteKit navigation that might remove <head> styles
  if (typeof MutationObserver !== "undefined") {
    var observer = new MutationObserver(function () {
      ensureLogoCSS();
    });
    ready(function () {
      observer.observe(document.head, { childList: true, subtree: true });
    });
  }
})();
