/**
 * QuickAid assistant — POSTs to Django keyword router, renders bubbles + cards.
 */
(function () {
  "use strict";

  var root = document.getElementById("qa-chat-root");
  if (!root) return;

  var replyUrl = root.getAttribute("data-reply-url") || "";
  var logEl = document.getElementById("qa-chat-log");
  var form = document.getElementById("qa-chat-form");
  var input = document.getElementById("qa-chat-input");
  var chipsWrap = document.getElementById("qa-chat-chips");

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var typingDelay = reduceMotion ? 60 : 560;

  function getCsrf() {
    var t = root.getAttribute("data-csrf");
    if (t) return t;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1].trim()) : "";
  }

  function escapeHtml(str) {
    if (str == null) return "";
    var d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  function scrollToBottom() {
    if (!logEl) return;
    logEl.scrollTop = logEl.scrollHeight;
  }

  function appendRow(side, innerHtml) {
    if (!logEl) return;
    var row = document.createElement("div");
    row.className = "qa-chat-row qa-chat-row--" + side + (reduceMotion ? "" : " qa-chat-row--in");
    row.innerHTML = innerHtml;
    logEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function bubbleUser(text) {
    appendRow(
      "user",
      '<div class="qa-chat-bubble qa-chat-bubble--user"><p class="mb-0">' + escapeHtml(text) + "</p></div>"
    );
  }

  function showTyping() {
    return appendRow(
      "bot",
      '<div class="qa-chat-typing-wrap" role="status" aria-live="polite">' +
        '<span class="qa-chat-typing"><span></span><span></span><span></span></span>' +
        '<span class="visually-hidden">Assistant is typing</span></div>'
    );
  }

  function formatWhen(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch (e) {
      return "";
    }
  }

  function renderCards(cards) {
    if (!cards || !cards.length) return "";
    var html = '<div class="qa-chat-cards mt-2">';
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i];
      if (c.kind === "report") {
        html +=
          '<article class="qa-chat-card qa-chat-card--report">' +
          '<div class="qa-chat-card-badges">' +
          '<span class="badge text-bg-primary rounded-pill">' +
          escapeHtml(c.category_label || c.category || "Report") +
          "</span>" +
          '<span class="badge text-bg-secondary rounded-pill">' +
          escapeHtml(c.status_label || "") +
          "</span></div>" +
          '<h3 class="qa-chat-card-title h6 mb-1 mt-2">' +
          escapeHtml(c.title || "") +
          "</h3>" +
          '<p class="qa-chat-card-sub small text-secondary mb-1">' +
          escapeHtml(c.subtitle || "") +
          "</p>" +
          (c.when_iso
            ? '<p class="small text-secondary opacity-75 mb-0">' + escapeHtml(formatWhen(c.when_iso)) + "</p>"
            : "") +
          "</article>";
      } else if (c.kind === "hospital") {
        html +=
          '<article class="qa-chat-card qa-chat-card--hospital">' +
          '<h3 class="qa-chat-card-title h6 mb-1">' +
          escapeHtml(c.title || "") +
          "</h3>" +
          '<p class="qa-chat-card-sub small text-secondary mb-2">' +
          escapeHtml(c.subtitle || "") +
          "</p>" +
          (c.phone
            ? '<p class="small mb-0"><a class="link-light" href="tel:' +
              escapeHtml(c.phone.replace(/\s/g, "")) +
              '">' +
              escapeHtml(c.phone) +
              "</a></p>"
            : "") +
          (c.has_coords
            ? '<p class="small text-secondary mb-0 mt-2">Has map coordinates — see the <a class="link-light" href="/map/">live map</a>.</p>'
            : "") +
          "</article>";
      } else if (c.kind === "contact") {
        html +=
          '<article class="qa-chat-card qa-chat-card--contact">' +
          '<h3 class="qa-chat-card-title h6 mb-1">' +
          escapeHtml(c.title || "") +
          "</h3>" +
          '<p class="small mb-0"><a class="link-light fw-semibold" href="tel:' +
          escapeHtml(String(c.subtitle || "").replace(/\s/g, "")) +
          '">' +
          escapeHtml(c.subtitle || "") +
          "</a></p>" +
          "</article>";
      }
    }
    html += "</div>";
    return html;
  }

  function renderLinks(links) {
    if (!links || !links.length) return "";
    var html = '<div class="qa-chat-links d-flex flex-wrap gap-2 mt-3">';
    for (var i = 0; i < links.length; i++) {
      var L = links[i];
      html +=
        '<a class="btn btn-sm btn-outline-light rounded-pill" href="' +
        escapeHtml(L.href || "#") +
        '">' +
        escapeHtml(L.label || "Open") +
        "</a>";
    }
    html += "</div>";
    return html;
  }

  function botMessage(payload) {
    var intro = escapeHtml(payload.intro || "");
    var body =
      '<div class="qa-chat-bubble qa-chat-bubble--bot">' +
      '<p class="mb-0">' +
      intro +
      "</p>" +
      renderCards(payload.cards) +
      renderLinks(payload.links) +
      "</div>";
    appendRow("bot", body);
  }

  function removeTypingRow(row) {
    if (row && row.parentNode) row.parentNode.removeChild(row);
  }

  function sendMessage(text) {
    var trimmed = (text || "").trim();
    if (!trimmed || !replyUrl) return;

    bubbleUser(trimmed);
    if (input) input.value = "";

    var typingRow = showTyping();
    scrollToBottom();

    window.setTimeout(function () {
      fetch(replyUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": getCsrf(),
        },
        body: JSON.stringify({ message: trimmed }),
      })
        .then(function (r) {
          if (!r.ok) throw new Error("bad_status");
          return r.json();
        })
        .then(function (data) {
          removeTypingRow(typingRow);
          if (data.error) {
            botMessage({
              intro: "Something went wrong. Refresh and try again.",
              cards: [],
              links: [{ label: "Reload", href: window.location.pathname }],
            });
            return;
          }
          botMessage(data);
          if (data.hints && chipsWrap) {
            chipsWrap.innerHTML = "";
            data.hints.slice(0, 6).forEach(function (hint) {
              var b = document.createElement("button");
              b.type = "button";
              b.className = "btn btn-sm btn-outline-secondary rounded-pill qa-chat-chip";
              b.textContent = hint;
              b.addEventListener("click", function () {
                sendMessage(hint);
              });
              chipsWrap.appendChild(b);
            });
          }
          scrollToBottom();
        })
        .catch(function () {
          removeTypingRow(typingRow);
          botMessage({
            intro: "Network error — check your connection and try again.",
            cards: [],
            links: [],
          });
        });
    }, typingDelay);
  }

  if (form && input) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      sendMessage(input.value);
    });
  }

  if (chipsWrap) {
    chipsWrap.addEventListener("click", function (ev) {
      var t = ev.target;
      if (t && t.classList && t.classList.contains("qa-chat-chip")) {
        sendMessage(t.textContent || "");
      }
    });
  }

  scrollToBottom();
})();
