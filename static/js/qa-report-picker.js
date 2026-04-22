/**
 * Report form: mini-map + geolocation + server geocode to set latitude/longitude.
 */
(function () {
  "use strict";

  var mapEl = document.getElementById("report-location-map");
  var latEl = document.getElementById("id_latitude");
  var lngEl = document.getElementById("id_longitude");
  if (!mapEl || !latEl || !lngEl || typeof L === "undefined") {
    return;
  }

  var geocodeUrl = mapEl.getAttribute("data-geocode-url") || "";
  var qInput = document.getElementById("qa-geocode-q");
  var searchBtn = document.getElementById("qa-geocode-search");
  var resultsEl = document.getElementById("qa-geocode-results");
  var myLocBtn = document.getElementById("qa-btn-my-location");
  var clearBtn = document.getElementById("qa-btn-clear-location");
  var msgEl = document.getElementById("qa-location-msg");

  var ghanaCenter = [7.9465, -1.0232];
  var map = L.map(mapEl, {
    zoomControl: true,
    scrollWheelZoom: true,
  }).setView(ghanaCenter, 6.5);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
      '&copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 20,
  }).addTo(map);

  var marker = null;

  function setMsg(text, isError) {
    if (!msgEl) return;
    msgEl.textContent = text || "";
    msgEl.classList.toggle("text-warning", !!isError);
    msgEl.classList.toggle("text-secondary", !isError && !!text);
  }

  function formatCoord(n) {
    if (typeof n !== "number" || isNaN(n)) return "";
    return String(Math.round(n * 1e6) / 1e6);
  }

  function readLatLng() {
    var la = parseFloat(latEl.value);
    var lo = parseFloat(lngEl.value);
    if (isNaN(la) || isNaN(lo)) return null;
    return [la, lo];
  }

  function setInputs(lat, lng) {
    latEl.value = formatCoord(lat);
    lngEl.value = formatCoord(lng);
  }

  function clearInputs() {
    latEl.value = "";
    lngEl.value = "";
  }

  function ensureMarker(latlng) {
    if (marker) {
      marker.setLatLng(latlng);
      return marker;
    }
    marker = L.marker(latlng, { draggable: true }).addTo(map);
    marker.on("dragend", function () {
      var ll = marker.getLatLng();
      setInputs(ll.lat, ll.lng);
      setMsg("Pin moved — coordinates updated.", false);
    });
    return marker;
  }

  function setPosition(lat, lng, zoomMin) {
    ensureMarker([lat, lng]);
    setInputs(lat, lng);
    var z = map.getZoom();
    var want = zoomMin != null ? zoomMin : 14;
    map.setView([lat, lng], Math.max(z, want));
    setTimeout(function () {
      map.invalidateSize(true);
    }, 50);
  }

  function clearPin() {
    if (marker) {
      map.removeLayer(marker);
      marker = null;
    }
    clearInputs();
    if (resultsEl) {
      resultsEl.innerHTML = "";
      resultsEl.hidden = true;
    }
    setMsg("", false);
  }

  map.on("click", function (ev) {
    var ll = ev.latlng;
    setPosition(ll.lat, ll.lng, 14);
    setMsg("Location set from map click.", false);
  });

  if (myLocBtn) {
    myLocBtn.addEventListener("click", function () {
      if (!navigator.geolocation) {
        setMsg("Your browser does not support location.", true);
        return;
      }
      setMsg("Getting your location…", false);
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          var lat = pos.coords.latitude;
          var lng = pos.coords.longitude;
          setPosition(lat, lng, 15);
          setMsg("Using your current location.", false);
        },
        function () {
          setMsg("Could not read location — check permissions or try search.", true);
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
      );
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      clearPin();
    });
  }

  function showResults(items) {
    if (!resultsEl) return;
    resultsEl.innerHTML = "";
    if (!items.length) {
      resultsEl.hidden = true;
      setMsg("No matches — try another place name.", true);
      return;
    }
    resultsEl.hidden = false;
    setMsg("Pick a result to drop the pin.", false);
    items.forEach(function (item) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-sm btn-outline-secondary text-start py-2 qa-geocode-result-btn";
      btn.textContent = item.label;
      btn.addEventListener("click", function () {
        setPosition(item.lat, item.lng, 14);
        resultsEl.innerHTML = "";
        resultsEl.hidden = true;
        setMsg("Location set from search.", false);
      });
      resultsEl.appendChild(btn);
    });
  }

  function runSearch() {
    if (!geocodeUrl) {
      setMsg("Search is not configured.", true);
      return;
    }
    var q = (qInput && qInput.value ? qInput.value : "").trim();
    if (q.length < 2) {
      setMsg("Type at least 2 characters to search.", true);
      return;
    }
    setMsg("Searching…", false);
    var url = geocodeUrl + (geocodeUrl.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(q);
    fetch(url, { method: "GET", headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        var list = (data && data.results) || [];
        showResults(list);
      })
      .catch(function () {
        if (resultsEl) {
          resultsEl.innerHTML = "";
          resultsEl.hidden = true;
        }
        setMsg("Search failed — try again later.", true);
      });
  }

  if (searchBtn && qInput) {
    searchBtn.addEventListener("click", runSearch);
    qInput.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        runSearch();
      }
    });
  }

  var existing = readLatLng();
  if (existing) {
    setPosition(existing[0], existing[1], 12);
  }

  function invalidate() {
    map.invalidateSize(true);
  }
  invalidate();
  setTimeout(invalidate, 120);
  setTimeout(invalidate, 500);
  window.addEventListener("resize", invalidate);
})();
