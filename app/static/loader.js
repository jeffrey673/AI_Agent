/* SKIN1004 AI — loader.js
   1) Theme default (dark on first visit)
   1b) Logo swap (splash.png / splash-dark-new.png per theme)
   2) Inject Craver "WHAT DO YOU CRAVE?" animation on login page
   3) Theme toggle button (bottom-right)
   4) Dashboard drawer panel (intercept workspace/대시보드 clicks)
   Workspace rename: Korean locale file directly modified.
*/

// ===== 0. Debug =====
console.log("[SKIN1004 loader.js v20260224a] loaded at", new Date().toISOString());

// ===== 1. Theme: respect user choice (no forced override) =====
if (!localStorage.theme) {
  localStorage.theme = "dark";
}

// ===== 1a. Force Korean locale =====
if (localStorage.locale !== "ko-KR") {
  localStorage.locale = "ko-KR";
}

// ===== 1b. Logo swap — sidebar favicon + center model profile image =====
(function () {
  var DARK_LOGO = "/skin/static/splash-dark-new.png";  // white C
  var LIGHT_LOGO = "/skin/static/splash.png";           // black C
  var MARKER = "data-skin-logo";

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function swapLogos() {
    var src = isDark() ? DARK_LOGO : LIGHT_LOGO;

    // 1) Already-swapped images (marked with data attribute)
    document.querySelectorAll("img[" + MARKER + "]").forEach(function (img) {
      img.src = src;
    });

    // 2) Sidebar favicon (top-left icon, matches fresh renders)
    document.querySelectorAll('img[src*="favicon"]').forEach(function (img) {
      img.setAttribute(MARKER, "1");
      img.src = src;
    });

    // 3) Center model profile image
    document.querySelectorAll('img[src*="models/model/profile/image"]').forEach(function (img) {
      img.setAttribute(MARKER, "1");
      img.src = src;
    });
  }

  // Run on DOM ready + periodically (SvelteKit re-renders)
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    swapLogos();
    setTimeout(swapLogos, 500);
    setTimeout(swapLogos, 1500);
    setTimeout(swapLogos, 3000);
  });

  // Watch for theme changes (html class mutation)
  if (typeof MutationObserver !== "undefined") {
    ready(function () {
      var mo = new MutationObserver(function () { swapLogos(); });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    });
  }

  // Periodic check for new/re-rendered images
  setInterval(swapLogos, 2000);
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
    '        <img src="/skin/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '        <span class="craver-outline">WHAT YOU NEED. WE</span>',
    '        <span class="craver-solid"><em>WONDER</em><small>\uBB34\uC5C7\uC774 \uD544\uC694\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/skin/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '      </div>',
    '    </div>',

    // Row 2 — scrolls right (reverse)
    '    <div class="craver-row craver-row2">',
    '      <div class="craver-track craver-track-right">',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/skin/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/skin/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '      </div>',
    '    </div>',

    // Row 3 — scrolls left
    '    <div class="craver-row craver-row3">',
    '      <div class="craver-track craver-track-left">',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/skin/static/craver_work.png" alt="" />',
    '        <span class="craver-outline">FOR TODAY? WHAT</span>',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/skin/static/craver_work.png" alt="" />',
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
    '        <img src="/skin/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '        <span class="craver-outline">WHAT YOU NEED. WE</span>',
    '        <span class="craver-solid"><em>WONDER</em><small>\uBB34\uC5C7\uC774 \uD544\uC694\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/skin/static/craver_wonder.png" alt="" />',
    '        <span class="craver-outline">WHAT YOU NEED.</span>',
    '      </div>',
    '    </div>',

    // Row 2 — scrolls right (middle)
    '    <div class="craver-row craver-row2">',
    '      <div class="craver-track craver-track-right">',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/skin/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '        <span class="craver-outline">WE UNDERSTAND THE</span>',
    '        <img src="/skin/static/craver_needs.png" alt="" />',
    '        <span class="craver-solid"><em>NEEDS.</em><small>\uB2E4\uC591\uD55C \uC695\uAD6C\uB97C \uC774\uD574\uD569\uB2C8\uB2E4</small></span>',
    '      </div>',
    '    </div>',

    // Row 3 — scrolls left (bottom)
    '    <div class="craver-row craver-row3">',
    '      <div class="craver-track craver-track-left">',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/skin/static/craver_work.png" alt="" />',
    '        <span class="craver-outline">FOR TODAY? WHAT</span>',
    '        <span class="craver-outline">WHAT DO WE</span>',
    '        <span class="craver-solid"><em>WORK</em><small>\uBB34\uC5C7\uC744 \uC704\uD574 \uC77C\uD569\uB2C8\uAE4C?</small></span>',
    '        <img src="/skin/static/craver_work.png" alt="" />',
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
    // Auth pages: full marquee with CRAVE text. Chat pages: subtle rows only.
    wrapper.innerHTML = isAuthPage() ? MARQUEE_HTML : CHAT_MARQUEE_HTML;
    var el = wrapper.firstElementChild;
    document.body.appendChild(el);
  }

  function cleanup() {
    // Always remove so it re-injects the correct version for the current page
    var el = document.getElementById("craver-bg");
    if (el) el.remove();
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

    // Logo swap handled by Section 1b (MutationObserver on html class change).
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


// ===== 4. Dashboard Drawer Panel (intercepts /workspace clicks) =====
// Note: "Workspace" → "대시보드" rename is done in Korean locale file (Vy97ft12.js)
(function () {
  var DASHBOARD_URL = "http://localhost:8100/dashboard";
  var DRAWER_DEFAULT_WIDTH = 70; // vw

  // --- 4a. Create Dashboard Drawer DOM ---
  function createDashboardDrawer() {
    if (document.getElementById("skin-dashboard-overlay")) return;

    // Overlay
    var overlay = document.createElement("div");
    overlay.id = "skin-dashboard-overlay";
    overlay.className = "skin-drawer-closed";
    overlay.addEventListener("click", closeDrawer);

    // Drawer panel
    var drawer = document.createElement("div");
    drawer.id = "skin-dashboard-drawer";
    drawer.className = "skin-drawer-closed";
    drawer.style.width = DRAWER_DEFAULT_WIDTH + "vw";

    // Drag handle (left edge)
    var handle = document.createElement("div");
    handle.id = "skin-dashboard-handle";
    handle.title = "\uB4DC\uB798\uADF8\uD558\uC5EC \uD06C\uAE30 \uC870\uC808";

    // Header bar with close button (replaces floating close)
    var header = document.createElement("div");
    header.id = "skin-dashboard-header";

    var closeBtn = document.createElement("button");
    closeBtn.id = "skin-dashboard-close";
    closeBtn.innerHTML = '&times;';
    closeBtn.title = "\uB2EB\uAE30";
    closeBtn.addEventListener("click", closeDrawer);
    header.appendChild(closeBtn);

    // Iframe (below header)
    var iframe = document.createElement("iframe");
    iframe.id = "skin-dashboard-iframe";
    iframe.setAttribute("sandbox", "allow-same-origin allow-scripts allow-popups allow-forms allow-top-navigation");

    drawer.appendChild(handle);
    drawer.appendChild(header);
    drawer.appendChild(iframe);

    document.body.appendChild(overlay);
    document.body.appendChild(drawer);

    // --- Drag resize logic ---
    setupDragResize(handle, drawer);
  }

  // --- 4b. Drag resize ---
  function setupDragResize(handle, drawer) {
    var isDragging = false;
    var startX = 0;
    var startWidth = 0;

    handle.addEventListener("pointerdown", function (e) {
      isDragging = true;
      startX = e.clientX;
      startWidth = drawer.getBoundingClientRect().width;
      drawer.style.transition = "none";
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    });

    document.addEventListener("pointermove", function (e) {
      if (!isDragging) return;
      var delta = startX - e.clientX;
      var newWidth = startWidth + delta;
      var minW = 320;
      var maxW = window.innerWidth * 0.95;
      if (newWidth < minW) newWidth = minW;
      if (newWidth > maxW) newWidth = maxW;
      drawer.style.width = newWidth + "px";
    });

    document.addEventListener("pointerup", function () {
      if (!isDragging) return;
      isDragging = false;
      drawer.style.transition = "";
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    });
  }

  // --- 4c. Open / Close ---
  function openDrawer() {
    var overlay = document.getElementById("skin-dashboard-overlay");
    var drawer = document.getElementById("skin-dashboard-drawer");
    var iframe = document.getElementById("skin-dashboard-iframe");
    if (!overlay || !drawer) return;

    // Load iframe on first open
    if (!iframe.src || iframe.src === "about:blank" || !iframe.src.includes("/dashboard")) {
      iframe.src = DASHBOARD_URL;
    }

    overlay.className = "skin-drawer-open";
    drawer.className = "skin-drawer-open";
    document.body.classList.add("skin-drawer-active");
  }

  function closeDrawer() {
    var overlay = document.getElementById("skin-dashboard-overlay");
    var drawer = document.getElementById("skin-dashboard-drawer");
    if (!overlay || !drawer) return;

    overlay.className = "skin-drawer-closed";
    drawer.className = "skin-drawer-closed";
    document.body.classList.remove("skin-drawer-active");
  }

  // --- 4d. Intercept "대시보드" clicks ---
  function interceptDashboardClicks() {
    document.addEventListener("click", function (e) {
      var target = e.target;
      // Walk up to 6 parents to find <a href="/workspace"> or sidebar workspace button
      for (var i = 0; i < 6; i++) {
        if (!target) break;
        // Match <a> with href containing "/workspace"
        if (target.tagName === "A" && target.href && target.href.indexOf("/workspace") !== -1) {
          e.preventDefault();
          e.stopPropagation();
          openDrawer();
          return;
        }
        // Match sidebar workspace button by id
        if (target.id === "sidebar-workspace-button") {
          e.preventDefault();
          e.stopPropagation();
          openDrawer();
          return;
        }
        target = target.parentElement;
      }
    }, true); // capture phase
  }

  // --- Init ---
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    createDashboardDrawer();
    interceptDashboardClicks();
  });

  // Escape key closes drawer
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDrawer();
  });
})();


// ===== 5. (removed — logo handled by Tailwind dark:invert on splash.png) =====


// ===== 6a. Maintenance Banner (top bar) =====
(function () {
  var POLL_INTERVAL = 30000; // 30s
  var API_BASE = window.location.protocol + "//" + window.location.hostname + ":8100";

  function createBanner() {
    if (document.getElementById("skin-maintenance-banner")) return;
    var banner = document.createElement("div");
    banner.id = "skin-maintenance-banner";
    banner.className = "skin-banner-hidden";
    banner.innerHTML =
      '<span class="skin-banner-icon">\u26A0</span>' +
      '<span class="skin-banner-text">' +
        '\uB370\uC774\uD130 \uC810\uAC80 \uC911 | <span id="skin-banner-reason"></span> | ' +
        '\uB9E4\uCD9C \uC870\uD68C \uC77C\uC2DC \uC911\uB2E8, \uB2E4\uB978 \uAE30\uB2A5 \uC815\uC0C1' +
      '</span>';
    document.body.appendChild(banner);
  }

  function showBanner(reason) {
    var banner = document.getElementById("skin-maintenance-banner");
    if (!banner) { createBanner(); banner = document.getElementById("skin-maintenance-banner"); }
    var reasonEl = document.getElementById("skin-banner-reason");
    if (reasonEl) reasonEl.textContent = reason || "\uC810\uAC80 \uC911";
    banner.className = "skin-banner-visible";
  }

  function hideBanner() {
    var banner = document.getElementById("skin-maintenance-banner");
    if (banner) banner.className = "skin-banner-hidden";
  }

  function pollMaintenance() {
    fetch(API_BASE + "/admin/maintenance/status", { method: "GET" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.active) {
          showBanner(data.reason);
        } else {
          hideBanner();
        }
      })
      .catch(function () { /* silently ignore fetch errors */ });
  }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    createBanner();
    pollMaintenance();
    setInterval(pollMaintenance, POLL_INTERVAL);
  });
})();


// ===== 6b. Sidebar DB Status Panel =====
(function () {
  var POLL_INTERVAL = 30000; // 30s
  var API_BASE = window.location.protocol + "//" + window.location.hostname + ":8100";
  var PANEL_ID = "skin-db-status";

  var STATUS_LABELS = {
    ok: "\uC815\uC0C1",
    updating: "\uC5C5\uB370\uC774\uD2B8 \uC911",
    error: "\uC624\uB958"
  };

  function createPanel() {
    if (document.getElementById(PANEL_ID)) return;
    var panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.innerHTML =
      '<div class="skin-db-header">\uC2DC\uC2A4\uD15C \uC0C1\uD0DC</div>' +
      '<div class="skin-db-list"></div>';
    return panel;
  }

  function renderServices(services) {
    var panel = document.getElementById(PANEL_ID);
    if (!panel) return;
    var list = panel.querySelector(".skin-db-list");
    if (!list) return;

    var html = "";
    for (var name in services) {
      if (!services.hasOwnProperty(name)) continue;
      var svc = services[name];
      var st = svc.status || "ok";
      var dotClass = "skin-db-dot" + (st !== "ok" ? " " + st : "");
      var label = STATUS_LABELS[st] || st;
      html +=
        '<div class="skin-db-item">' +
        '  <span class="' + dotClass + '"></span>' +
        '  <span class="skin-db-name">' + name + '</span>' +
        '  <span class="skin-db-label skin-db-label-' + st + '">' + label + '</span>' +
        '</div>';
    }
    list.innerHTML = html;
  }

  function injectIntoSidebar() {
    if (document.getElementById(PANEL_ID)) return true;

    // Find Open WebUI sidebar
    var sidebar = document.getElementById("sidebar");
    if (!sidebar) return false;

    var panel = createPanel();
    if (!panel) return false;
    sidebar.appendChild(panel);
    return true;
  }

  function pollSafetyStatus() {
    fetch(API_BASE + "/safety/status", { method: "GET" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.services) {
          // Ensure panel exists in sidebar
          injectIntoSidebar();
          renderServices(data.services);
        }
      })
      .catch(function () { /* silently ignore */ });
  }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    // MutationObserver: inject panel when sidebar appears
    if (typeof MutationObserver !== "undefined") {
      var mo = new MutationObserver(function () {
        injectIntoSidebar();
      });
      mo.observe(document.body, { childList: true, subtree: true });
    }

    // Initial poll + periodic refresh
    setTimeout(pollSafetyStatus, 2000);
    setInterval(pollSafetyStatus, POLL_INTERVAL);
  });
})();
