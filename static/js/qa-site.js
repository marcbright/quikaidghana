/**
 * QuickAid site-wide UX: nav collapse, counters, anchors, flash toasts, typing, auto-refresh, form validation.
 */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function ready(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  var THEME_KEY = "qa-theme";

  function getStoredTheme() {
    try {
      var saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") return saved;
    } catch (e) {}
    return null;
  }

  function systemTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function updateThemeToggleUI(theme) {
    var btn = document.getElementById("qa-theme-toggle");
    if (!btn) return;
    var icon = btn.querySelector("[data-theme-icon]");
    var label = btn.querySelector("[data-theme-label]");
    var next = theme === "dark" ? "light" : "dark";
    btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    btn.setAttribute("aria-label", "Switch to " + next + " mode");
    btn.setAttribute("title", "Switch to " + next + " mode");
    if (icon) icon.textContent = theme === "dark" ? "🌙" : "☀️";
    if (label) label.textContent = theme === "dark" ? "Dark" : "Light";
  }

  function applyTheme(theme, opts) {
    if (theme !== "light" && theme !== "dark") return;
    var root = document.documentElement;
    var options = opts || {};
    if (options.animate) document.body.classList.add("qa-theme-transition");
    root.setAttribute("data-bs-theme", theme);
    root.style.colorScheme = theme;
    var nav = document.getElementById("qaNavbar");
    if (nav) {
      nav.classList.toggle("navbar-dark", theme === "dark");
      nav.classList.toggle("navbar-light", theme === "light");
    }
    updateThemeToggleUI(theme);
    window.dispatchEvent(new CustomEvent("qa:themechange", { detail: { theme: theme } }));
    if (options.persist) {
      try {
        localStorage.setItem(THEME_KEY, theme);
      } catch (e) {}
    }
    if (options.animate) {
      window.setTimeout(function () {
        document.body.classList.remove("qa-theme-transition");
      }, 380);
    }
  }

  function initThemeSystem() {
    var saved = getStoredTheme();
    applyTheme(saved || systemTheme(), { persist: false, animate: false });

    var btn = document.getElementById("qa-theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var current = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
        var next = current === "dark" ? "light" : "dark";
        applyTheme(next, { persist: true, animate: !reduceMotion });
      });
    }

    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      var onSystem = function () {
        if (getStoredTheme()) return;
        applyTheme(systemTheme(), { persist: false, animate: !reduceMotion });
      };
      if (typeof mq.addEventListener === "function") mq.addEventListener("change", onSystem);
      else if (typeof mq.addListener === "function") mq.addListener(onSystem);
    }
  }

  /* --- Navbar: close mobile menu after navigating a link --- */
  function initNavCollapse() {
    var mainNav = document.getElementById("mainNav");
    if (!mainNav || typeof bootstrap === "undefined" || !bootstrap.Collapse) return;
    mainNav.querySelectorAll(".qa-nav-link, .nav-link").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.innerWidth >= 992) return;
        if (!mainNav.classList.contains("show")) return;
        var inst = bootstrap.Collapse.getInstance(mainNav);
        if (inst) inst.hide();
      });
    });
    var toggler = document.querySelector('[data-bs-target="#mainNav"]');
    if (toggler && mainNav) {
      mainNav.addEventListener("shown.bs.collapse", function () {
        toggler.setAttribute("aria-expanded", "true");
      });
      mainNav.addEventListener("hidden.bs.collapse", function () {
        toggler.setAttribute("aria-expanded", "false");
      });
    }
  }

  /* --- Navbar: elevation on scroll --- */
  function initNavbarScrollState() {
    var nav = document.getElementById("qaNavbar");
    if (!nav) return;
    var onScroll = function () {
      if (window.scrollY > 8) nav.classList.add("is-scrolled");
      else nav.classList.remove("is-scrolled");
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* --- Animated counters (home stats) --- */
  function easeOutExpo(t) {
    return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }

  function animateCounter(el, target, durationMs) {
    var start = performance.now();
    var from = 0;
    var dur = reduceMotion ? 0 : durationMs;
    function frame(now) {
      var t = dur <= 0 ? 1 : Math.min(1, (now - start) / dur);
      var v = Math.round(from + (target - from) * easeOutExpo(t));
      el.textContent = String(v);
      if (t < 1) requestAnimationFrame(frame);
      else el.textContent = String(target);
    }
    requestAnimationFrame(frame);
  }

  function initCounters() {
    var nodes = document.querySelectorAll(".qa-counter[data-target]");
    if (!nodes.length) return;
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var el = entry.target;
          if (el.getAttribute("data-counter-done")) return;
          el.setAttribute("data-counter-done", "1");
          var raw = el.getAttribute("data-target");
          var target = parseInt(raw, 10);
          if (isNaN(target)) target = 0;
          animateCounter(el, target, 1400);
          io.unobserve(el);
        });
      },
      { root: null, rootMargin: "0px 0px -8% 0px", threshold: 0.15 }
    );
    nodes.forEach(function (n) {
      if (reduceMotion) {
        var t = parseInt(n.getAttribute("data-target"), 10) || 0;
        n.textContent = String(t);
        return;
      }
      io.observe(n);
    });
  }

  /* --- Same-page #anchors with fixed navbar offset --- */
  function initSmoothAnchors() {
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
      var id = a.getAttribute("href");
      if (!id || id === "#" || id.length < 2) return;
      a.addEventListener("click", function (ev) {
        var target = document.querySelector(id);
        if (!target) return;
        ev.preventDefault();
        var nav = document.getElementById("qaNavbar");
        var offset = nav ? nav.offsetHeight + 12 : 72;
        var top = target.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({
          top: Math.max(0, top),
          behavior: reduceMotion ? "auto" : "smooth",
        });
        history.replaceState(null, "", id);
      });
    });
  }

  /* --- Django messages → Bootstrap toasts --- */
  function tagToToastBg(tags) {
    var t = (tags || "").trim().split(/\s+/)[0] || "info";
    if (t === "error") t = "danger";
    var map = {
      success: "text-bg-success",
      danger: "text-bg-danger",
      error: "text-bg-danger",
      warning: "text-bg-warning",
      info: "text-bg-info",
      debug: "text-bg-secondary",
    };
    return map[t] || "text-bg-primary";
  }

  function initFlashToasts() {
    if (typeof bootstrap === "undefined" || !bootstrap.Toast) return;
    var stack = document.getElementById("qa-toast-stack");
    if (!stack) return;
    var wrap = document.getElementById("qa-message-alerts");
    if (!wrap) return;
    var alerts = wrap.querySelectorAll(".alert");
    if (!alerts.length) return;
    alerts.forEach(function (alert, i) {
      var level = alert.className.match(/alert-(\w+)/);
      var tag = level ? level[1] : "info";
      var body = alert.textContent.trim();
      if (!body) return;
      var toast = document.createElement("div");
      toast.className = "toast align-items-center border-0 shadow-lg mb-2 " + tagToToastBg(tag);
      toast.setAttribute("role", "alert");
      toast.setAttribute("aria-live", "assertive");
      var closeClass = tag === "warning" ? "btn-close" : "btn-close btn-close-white";
      toast.innerHTML =
        '<div class="d-flex">' +
        '<div class="toast-body pe-3">' +
        escapeHtml(body) +
        "</div>" +
        '<button type="button" class="' +
        closeClass +
        ' me-2 m-auto" data-bs-dismiss="toast" aria-label="Dismiss"></button></div>';
      stack.appendChild(toast);
      var delay = tag === "danger" || tag === "error" ? 9000 : 6000;
      var t = new bootstrap.Toast(toast, { autohide: true, delay: delay });
      window.setTimeout(function () {
        t.show();
      }, 120 + i * 160);
    });
    wrap.style.display = "none";
    wrap.setAttribute("aria-hidden", "true");
  }

  /* --- Hero typing (data-typing-text on #qa-hero-typed) --- */
  function initTyping() {
    var el = document.getElementById("qa-hero-typed");
    if (!el) return;
    var full = el.getAttribute("data-typing-text") || "";
    if (!full) return;
    if (reduceMotion) {
      el.textContent = full;
      var c = el.parentElement && el.parentElement.querySelector(".qa-typing-caret");
      if (c) c.style.visibility = "hidden";
      return;
    }
    var speed = parseInt(el.getAttribute("data-typing-speed") || "38", 10);
    el.textContent = "";
    var i = 0;
    var caret = el.parentElement ? el.parentElement.querySelector(".qa-typing-caret") : null;
    function tick() {
      if (i <= full.length) {
        el.textContent = full.slice(0, i);
        i += 1;
        window.setTimeout(tick, speed);
      } else if (caret) {
        caret.style.visibility = "hidden";
      }
    }
    window.setTimeout(tick, 280);
  }

  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el || !el.textContent) return [];
    try {
      var data = JSON.parse(el.textContent);
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  function haversineKm(lat1, lon1, lat2, lon2) {
    var toRad = Math.PI / 180;
    var dLat = (lat2 - lat1) * toRad;
    var dLon = (lon2 - lon1) * toRad;
    var a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return 6371 * c;
  }

  function initHomeLocalPanels() {
    var feed = readJsonScript("qa-home-incident-feed");
    if (!feed.length) return;

    var chips = document.querySelectorAll(".qa-home-city-chip[data-city-query]");
    var outageList = document.getElementById("qa-home-outage-list");
    var communityList = document.getElementById("qa-home-community-list");
    var outageEmpty = document.getElementById("qa-home-outage-empty");
    var communityEmpty = document.getElementById("qa-home-community-empty");

    var favInput = document.getElementById("qa-home-fav-input");
    var favAddBtn = document.getElementById("qa-home-fav-add");
    var favList = document.getElementById("qa-home-fav-list");
    var favStatus = document.getElementById("qa-home-fav-status");
    var actionTitle = document.getElementById("qa-home-action-title");
    var actionMeta = document.getElementById("qa-home-action-meta");
    var actionReports = document.getElementById("qa-home-action-reports");
    var actionMap = document.getElementById("qa-home-action-map");

    function renderItems(items, isOutage, targetList, emptyEl, emptyText) {
      if (!targetList) return;
      targetList.innerHTML = "";
      var filtered = items.filter(function (x) {
        return isOutage ? !!x.is_outage : true;
      }).slice(0, 3);

      if (!filtered.length) {
        if (emptyEl) {
          emptyEl.hidden = false;
          emptyEl.textContent = emptyText;
        }
        return;
      }
      if (emptyEl) emptyEl.hidden = true;

      filtered.forEach(function (r) {
        var li = document.createElement("li");
        li.className = "qa-home-live-item";
        var title = isOutage ? escapeHtml(r.location || "") : escapeHtml((r.category || "Report") + " · " + (r.location || ""));
        li.innerHTML =
          '<p class="small text-white fw-semibold mb-1">' +
          title +
          "</p>" +
          '<p class="small text-secondary mb-0">' +
          escapeHtml(r.created_label || "") +
          " · " +
          escapeHtml(r.status || "") +
          "</p>";
        targetList.appendChild(li);
      });
    }

    function applyCity(query, label) {
      var q = (query || "").toLowerCase().trim();
      var items = q
        ? feed.filter(function (r) {
            var loc = (r.location || "").toLowerCase();
            return loc.indexOf(q) >= 0;
          })
        : feed.slice();

      renderItems(
        items,
        true,
        outageList,
        outageEmpty,
        "No outage reports for " + label + " yet."
      );
      renderItems(
        items,
        false,
        communityList,
        communityEmpty,
        "No community reports for " + label + " yet."
      );
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        chips.forEach(function (c) {
          c.classList.remove("is-active");
        });
        chip.classList.add("is-active");
        applyCity(chip.getAttribute("data-city-query") || "", chip.getAttribute("data-city-label") || "selected area");
      });
    });

    var nearBtn = document.getElementById("qa-btn-near-me");
    var nearList = document.getElementById("qa-near-me-list");
    var nearStatus = document.getElementById("qa-near-me-status");

    function setNearStatus(text, isError) {
      if (!nearStatus) return;
      nearStatus.textContent = text;
      nearStatus.classList.toggle("text-warning", !!isError);
      nearStatus.classList.toggle("text-secondary", !isError);
    }

    if (nearBtn && nearList && nearStatus) {
      nearBtn.addEventListener("click", function () {
        if (!navigator.geolocation) {
          setNearStatus("Geolocation is not supported in this browser.", true);
          return;
        }
        setNearStatus("Checking your location…", false);
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude;
            var lng = pos.coords.longitude;
            var withGeo = feed.filter(function (r) {
              return typeof r.lat === "number" && typeof r.lng === "number";
            });
            withGeo.sort(function (a, b) {
              return haversineKm(lat, lng, a.lat, a.lng) - haversineKm(lat, lng, b.lat, b.lng);
            });
            var nearest = withGeo.slice(0, 3);
            nearList.innerHTML = "";
            if (!nearest.length) {
              setNearStatus("No geo-tagged reports yet. Ask users to pin locations when reporting.", true);
              return;
            }
            setNearStatus("Nearest live reports to your current location:", false);
            nearest.forEach(function (r) {
              var km = haversineKm(lat, lng, r.lat, r.lng);
              var li = document.createElement("li");
              li.className = "qa-home-live-item";
              li.innerHTML =
                '<p class="small text-white fw-semibold mb-1">' +
                escapeHtml((r.category || "Report") + " · " + (r.location || "")) +
                "</p>" +
                '<p class="small text-secondary mb-0">' +
                escapeHtml(km.toFixed(1) + " km away") +
                " · " +
                escapeHtml(r.status || "") +
                "</p>";
              nearList.appendChild(li);
            });
          },
          function () {
            setNearStatus("Could not get your location. Enable permission and try again.", true);
          },
          { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
        );
      });
    }

    var STORAGE_KEY = "qa-home-favorites";
    var selectedFav = "";

    function loadFavs() {
      try {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        var arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return [];
        return arr.filter(function (x) { return typeof x === "string" && x.trim(); }).slice(0, 5);
      } catch (e) {
        return [];
      }
    }

    function saveFavs(list) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(0, 5)));
      } catch (e) {
        // ignore storage failures
      }
    }

    function countForLocation(name) {
      var q = (name || "").toLowerCase();
      if (!q) return { total: 0, pending: 0, outages: 0 };
      var total = 0;
      var pending = 0;
      var outages = 0;
      feed.forEach(function (r) {
        var loc = (r.location || "").toLowerCase();
        if (loc.indexOf(q) === -1) return;
        total += 1;
        if ((r.status || "").toLowerCase().indexOf("pending") >= 0) pending += 1;
        if (r.is_outage) outages += 1;
      });
      return { total: total, pending: pending, outages: outages };
    }

    function setActionForFavorite(name) {
      var label = (name || "").trim();
      if (!label) {
        if (actionTitle) actionTitle.textContent = "No favorite selected";
        if (actionMeta) actionMeta.textContent = "Save a location to personalize quick actions.";
        if (actionReports) actionReports.href = "/reports/";
        if (actionMap) actionMap.href = "/map/";
        if (favStatus) favStatus.textContent = "Save places you care about and get quick routes to live incidents.";
        return;
      }
      selectedFav = label;
      var counts = countForLocation(label);
      if (actionTitle) actionTitle.textContent = label;
      if (actionMeta) {
        actionMeta.textContent =
          counts.total + " report" + (counts.total === 1 ? "" : "s") +
          " · " + counts.pending + " pending" +
          " · " + counts.outages + " outage" + (counts.outages === 1 ? "" : "s");
      }
      if (actionReports) actionReports.href = "/reports/?q=" + encodeURIComponent(label);
      if (actionMap) actionMap.href = "/map/";
      if (favStatus) favStatus.textContent = "Personalized for " + label + ".";
    }

    function renderFavs() {
      if (!favList) return;
      var favs = loadFavs();
      favList.innerHTML = "";
      if (!favs.length) {
        setActionForFavorite("");
        return;
      }
      favs.forEach(function (name, idx) {
        var wrap = document.createElement("div");
        wrap.className = "qa-home-fav-pill" + ((selectedFav || favs[0]) === name ? " is-active" : "");

        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-sm qa-home-fav-select";
        btn.textContent = name;
        btn.addEventListener("click", function () {
          setActionForFavorite(name);
          renderFavs();
        });

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "btn btn-sm qa-home-fav-remove";
        remove.setAttribute("aria-label", "Remove favorite " + name);
        remove.textContent = "×";
        remove.addEventListener("click", function () {
          var list = loadFavs().filter(function (x) { return x !== name; });
          saveFavs(list);
          if (selectedFav === name) selectedFav = list[0] || "";
          renderFavs();
        });

        wrap.appendChild(btn);
        wrap.appendChild(remove);
        favList.appendChild(wrap);
        if (idx === 0 && !selectedFav) setActionForFavorite(name);
      });
    }

    if (favAddBtn && favInput) {
      favAddBtn.addEventListener("click", function () {
        var value = (favInput.value || "").trim();
        if (!value) return;
        var list = loadFavs();
        var exists = list.some(function (x) { return x.toLowerCase() === value.toLowerCase(); });
        if (!exists) list.unshift(value);
        saveFavs(list);
        selectedFav = value;
        favInput.value = "";
        renderFavs();
      });
      favInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          favAddBtn.click();
        }
      });
    }

    renderFavs();
  }

  /* --- Reports list: soft reload while tab visible --- */
  function initReportsAutoRefresh() {
    var root = document.querySelector("[data-qa-auto-refresh]");
    if (!root) return;
    var sec = parseInt(root.getAttribute("data-qa-auto-refresh"), 10);
    if (isNaN(sec) || sec < 45) return;
    window.setInterval(function () {
      if (document.visibilityState !== "visible") return;
      var form = root.querySelector(".qa-reports-filters");
      if (form && form.contains(document.activeElement)) return;
      window.location.reload();
    }, sec * 1000);
  }

  /* --- Client-side validation + scroll to first error --- */
  function initFormValidation() {
    document.querySelectorAll("form.qa-report-form, form.qa-contact-form").forEach(function (form) {
      form.addEventListener(
        "submit",
        function (ev) {
          if (!form.checkValidity()) {
            ev.preventDefault();
            ev.stopPropagation();
            var first = form.querySelector(":invalid");
            if (first) {
              first.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
              window.setTimeout(function () {
                first.focus({ preventScroll: true });
              }, 300);
            }
          }
          form.classList.add("was-validated");
        },
        false
      );
    });
  }

  ready(function () {
    initThemeSystem();
    initNavbarScrollState();
    initNavCollapse();
    initCounters();
    initSmoothAnchors();
    initFlashToasts();
    initTyping();
    initHomeLocalPanels();
    initReportsAutoRefresh();
    initFormValidation();
  });
})();
