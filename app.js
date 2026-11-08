(function () {
  "use strict";
  var D = window.DATOS || { meta: {}, ensayos: [] };
  var T = D.ensayos;
  var TX = (D.meta && D.meta.taxonomia) || { grupos: [], entidades: [] };
  var $ = function (s) { return document.querySelector(s); };

  // --- utilidades -----------------------------------------------------------
  function norm(s) { return String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  var MINUS = { de: 1, del: 1, la: 1, las: 1, los: 1, el: 1, y: 1, i: 1, d: 1 };
  function titulo(s) {
    return String(s || "").toLowerCase().replace(/[^\s\-/]+/g, function (w, i) {
      return (i > 0 && MINUS[w]) ? w : w.charAt(0).toUpperCase() + w.slice(1);
    });
  }
  function nombreCcaa(raw) {
    var p = String(raw || "").split(",").map(function (x) { return x.trim(); });
    return p.length === 2 ? titulo(p[1] + " " + p[0]) : titulo(raw);
  }
  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  }
  function tituloEnsayo(e) { return e.titulo || e.titulo_cientifico || e.identificador; }
  function corto(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s; }

  // --- taxonomía, hospitales y puntos del mapa -----------------------------------
  var ENT = {}, GR = {};
  TX.entidades.forEach(function (e) { ENT[e.id] = e; });
  TX.grupos.forEach(function (g) { GR[g.id] = g; });

  var H = {}, S = {};          // hospitales por id; "sitios" = puntos del mapa (≈100 m)
  T.forEach(function (e) {
    e.centros.forEach(function (c) {
      var id = c.hospital_id || (c.centro + "|" + c.lat);
      var h = H[id] = H[id] || { id: id, c: c, ensayos: [], ok: [] };
      if (h.ensayos.indexOf(e) < 0) h.ensayos.push(e);
    });
  });
  Object.keys(H).forEach(function (id) {
    var h = H[id], k = Number(h.c.lat).toFixed(3) + "," + Number(h.c.lon).toFixed(3);
    var s = S[k] = S[k] || { key: k, lat: Number(h.c.lat), lon: Number(h.c.lon), hs: [], n: 0 };
    s.hs.push(h); h.sitio = k;
  });
  var cache = {};
  T.forEach(function (e) {
    var ents = (e.entidades || []).map(function (i) { return ENT[i] ? ENT[i].n + " " + (GR[ENT[i].g] ? GR[ENT[i].g].n : "") : ""; });
    cache[e.identificador] = norm([e.identificador, e.nombre, e.protocolo, tituloEnsayo(e), e.titulo_cientifico, e.indicacion, e.medicamentos, e.promotor,
      ents.join(" "), e.centros.map(function (c) { return c.centro + " " + c.localidad; }).join(" ")].join(" "));
  });

  // --- estado y filtros -----------------------------------------------------
  var estado = { q: "", enf: "", ccaa: "", prov: "", fase: "", seg: false, ens: null, sitio: null, exp: null };

  function cumpleEnf(e, v) {      // v = "g:grupo" o "e:entidad"; los genéricos del REec cubren a sus concretas
    if (!v) return true;
    var tipo = v.charAt(0), id = v.slice(2);
    return (e.entidades || []).some(function (i) {
      var en = ENT[i]; if (!en) return false;
      if (tipo === "g") return en.g === id || (en.c || []).some(function (c) { return ENT[c] && ENT[c].g === id; });
      return i === id || (en.c || []).indexOf(id) >= 0;
    });
  }
  function soloPorGenerico(e) {   // coincide con la enfermedad elegida solo porque el REec la indica de forma general
    if (!estado.enf) return false;
    var tipo = estado.enf.charAt(0), id = estado.enf.slice(2);
    return !(e.entidades || []).some(function (i) {
      return tipo === "g" ? (ENT[i] && ENT[i].g === id) : i === id;
    });
  }
  function coincide(e) {
    if (estado.ens) return e.identificador === estado.ens;
    if (!estado.seg && e.seguimiento) return false;
    if (estado.fase && (e.fase || "").split("/").indexOf(estado.fase) < 0) return false;
    if (!cumpleEnf(e, estado.enf)) return false;
    var q = norm(estado.q).trim().split(/\s+/).filter(Boolean);
    return q.every(function (w) { return cache[e.identificador].indexOf(w) >= 0; });
  }
  function hayFiltro() { return !!(estado.q.trim() || estado.enf || estado.fase || estado.ccaa || estado.prov || estado.ens); }

  var res = { ensayos: 0, hospitales: 0, vistos: {} };
  var vista = "mapa", prom = null;
  function calcular() {
    var okE = {}, vistos = {}, nh = 0;
    T.forEach(function (e) { okE[e.identificador] = coincide(e); });
    Object.keys(H).forEach(function (id) {
      var h = H[id];
      var geo = (!estado.ccaa || h.c.ccaa === estado.ccaa) && (!estado.prov || h.c.provincia === estado.prov);
      h.ok = geo ? h.ensayos.filter(function (e) { return okE[e.identificador]; }) : [];
      if (h.ok.length) { nh++; h.ok.forEach(function (e) { vistos[e.identificador] = 1; }); }
    });
    Object.keys(S).forEach(function (k) {
      S[k].n = S[k].hs.reduce(function (a, h) { return a + h.ok.length; }, 0);
    });
    res = { ensayos: Object.keys(vistos).length, hospitales: nh, vistos: vistos };
  }

  // --- mapa -----------------------------------------------------------------
  var map = L.map("mapa", { zoomControl: false }).setView([40.2, -3.7], 6);
  L.control.zoom({ position: "topright" }).addTo(map);
  L.tileLayer("https://www.ign.es/wmts/ign-base?service=WMTS&request=GetTile&version=1.0.0" +
    "&Format=image/jpeg&layer=IGNBaseTodo&style=default&tilematrixset=GoogleMapsCompatible" +
    "&TileMatrix={z}&TileRow={y}&TileCol={x}", {
    maxZoom: 18,
    attribution: 'Mapa base: <a href="https://www.ign.es" target="_blank" rel="noopener">IGN</a> · CC BY 4.0 scne.es'
  }).addTo(map);
  var grupo = L.markerClusterGroup({
    showCoverageOnHover: false, maxClusterRadius: 40,
    iconCreateFunction: function (c) {
      return L.divIcon({ className: "cl", html: "<span>" + c.getChildCount() + "</span>", iconSize: [40, 40] });
    }
  });
  var inactivos = L.layerGroup();
  map.addLayer(inactivos); map.addLayer(grupo);

  function pinIcon(n, sel) {
    return L.divIcon({ className: "pin" + (sel ? " sel" : ""), html: "<span>" + (n > 1 ? n : "") + "</span>", iconSize: [26, 26], iconAnchor: [13, 13] });
  }
  function padOpts(max) {
    var abierto = !$("#panel").hidden, w = window.innerWidth;
    if (w > 800) return { paddingTopLeft: [abierto ? 460 : 60, 80], paddingBottomRight: [60, 130], maxZoom: max };
    return { paddingTopLeft: [30, 70], paddingBottomRight: [30, abierto ? Math.round(window.innerHeight * 0.48) + 110 : 130], maxZoom: max };
  }
  function pintarMapa(ajustar) {
    grupo.clearLayers(); inactivos.clearLayers();
    var filtro = hayFiltro(), activos = [];
    Object.keys(S).forEach(function (k) {
      var s = S[k], ll = [s.lat, s.lon], m;
      if (!s.n) {
        if (!filtro) return;
        m = L.circleMarker(ll, { radius: 5, color: "#fff", weight: 1.5, fillColor: "#b0b0b0", fillOpacity: 1 });
        inactivos.addLayer(m);
      } else {
        var aprox = s.hs.every(function (h) { return h.c.precision !== "direccion" && h.c.precision !== "nombre"; });
        var sel = k === estado.sitio;
        m = aprox
          ? L.circleMarker(ll, { radius: 11, color: "#0a0a0a", weight: sel ? 4 : 2, dashArray: "3", fillColor: "#fff", fillOpacity: .8 })
          : L.marker(ll, { icon: pinIcon(s.n, sel), title: s.hs[0].c.centro });
        grupo.addLayer(m); activos.push(ll);
      }
      m.on("click", function () { abrirSitio(k); });
    });
    if (ajustar && activos.length) map.fitBounds(L.latLngBounds(activos), padOpts(filtro ? 12 : 11));
  }

  // --- panel del hospital ----------------------------------------------------
  function chipsEnsayo(e) {
    var chips = el("div", "chips");
    (e.entidades || []).forEach(function (i) {
      var en = ENT[i]; if (!en || i === "sin") return;
      chips.appendChild(el("span", "chip" + (en.c ? " gen" : ""), en.n));
    });
    if (e.fase) chips.appendChild(el("span", "chip", "Fase " + e.fase));
    if (e.seguimiento) chips.appendChild(el("span", "chip rara", "Seguimiento / extensión"));
    if (String(e.enfermedad_rara) === "1") chips.appendChild(el("span", "chip rara", "Enfermedad rara"));
    return chips;
  }
  function ficha(e, h) {
    var d = el("div", "det");
    function sec(t, node) { d.appendChild(el("h5", null, t)); d.appendChild(node); }
    if (e.seguimiento) d.appendChild(el("p", "aviso", "Estudio de seguimiento o extensión: normalmente solo admite a personas que ya participaron en un estudio previo."));
    if (soloPorGenerico(e)) d.appendChild(el("p", "aviso", "El registro indica la enfermedad de forma general. Comprueba en los criterios de inclusión si incluye la que buscas."));
    if (e.indicacion) sec("Enfermedad o condición según el REec", el("p", null, e.indicacion));
    if (e.titulo_cientifico && e.titulo_cientifico !== e.titulo) sec("Título científico", el("p", null, e.titulo_cientifico));
    if (e.medicamentos) sec("Medicamentos en estudio", el("p", null, e.medicamentos));
    var edades = [["ninos", "niños"], ["adolescentes", "adolescentes"], ["adultos", "adultos"], ["ancianos", "mayores"]]
      .filter(function (a) { return String(e[a[0]]) === "1"; }).map(function (a) { return a[1]; });
    if (edades.length) sec("Edades incluidas", el("p", null, edades.join(", ")));
    if (e.promotor) {
      sec("Promotor", el("p", null, e.promotor));
      if (vista !== "red") {
        var vp = el("button", "btn claro", "Ver sus ensayos en la red de promotores"); vp.type = "button";
        vp.addEventListener("click", function () { prom = e.promotor_c; estado.exp = e.identificador; cambiarVista("red"); });
        d.appendChild(vp);
      }
    }
    if (e.protocolo) sec("Código de protocolo", el("p", null, e.protocolo));
    var ul = el("ul");
    e.centros.forEach(function (c) {
      var li = el("li"), id = c.hospital_id || (c.centro + "|" + c.lat);
      if (h && id === h.id) { li.textContent = c.centro + " — " + c.localidad + " (este centro)"; }
      else {
        var b = el("button", null, c.centro + " — " + c.localidad); b.type = "button";
        b.addEventListener("click", function () { if (H[id]) abrirSitio(H[id].sitio); });
        li.appendChild(b);
      }
      ul.appendChild(li);
    });
    sec("Centros abiertos (" + e.centros.length + ")", ul);
    if (e.diseno) {
      var ds = e.diseno, el2 = e.elegibilidad || {}, f = [];
      [["Tipo", ds.tipo], ["Fase", ds.fases], ["Asignación", ds.asignacion], ["Modelo", ds.modelo], ["Enmascaramiento", ds.enmascaramiento],
       ["Finalidad", ds.proposito], ["Pacientes previstos", ds.n], ["Sexo", el2.sexo], ["Edad mínima", el2.edad_min], ["Edad máxima", el2.edad_max]]
        .forEach(function (x) { if (x[1]) f.push(x); });
      var dd = el("details"); dd.open = true; dd.appendChild(el("summary", null, "Diseño del ensayo"));
      if (e.resumen) dd.appendChild(el("p", "resumen", e.resumen));
      var dl = el("dl", "diseno");
      f.forEach(function (x) { dl.appendChild(el("dt", null, x[0])); dl.appendChild(el("dd", null, String(x[1]))); });
      dd.appendChild(dl);
      if ((e.brazos || []).length) {
        dd.appendChild(el("h5", null, "Brazos de tratamiento"));
        var ub = el("ul", "brazos");
        e.brazos.forEach(function (z) {
          var li = el("li"); li.appendChild(el("strong", null, z.n + (z.t ? " (" + z.t + ")" : "")));
          if (z.i && z.i.length) li.appendChild(el("div", "mut", z.i.join("; ")));
          if (z.d) li.appendChild(el("div", null, z.d));
          ub.appendChild(li);
        });
        dd.appendChild(ub);
      }
      if ((e.objetivos || []).length) {
        dd.appendChild(el("h5", null, "Objetivo principal"));
        var uo = el("ul", "brazos");
        e.objetivos.forEach(function (o) { uo.appendChild(el("li", null, o.m + (o.p ? " — " + o.p : ""))); });
        dd.appendChild(uo);
        if (e.n_secundarios) dd.appendChild(el("p", "mut", "Más " + e.n_secundarios + " objetivos secundarios."));
      }
      d.appendChild(dd);
    }
    var cr = e.criterios || { inc: [], exc: [] };
    if (cr.fuente && cr.fuente !== "REec" && (cr.inc.length || cr.exc.length)) d.appendChild(el("p", "aviso", "El REec no publica los criterios de este ensayo; se muestran los de " + (cr.fuente === "CTIS" ? "el registro europeo (CTIS), que son los criterios principales." : "ClinicalTrials.gov (registro estadounidense del mismo estudio, " + (e.nct || "") + ").")));
    [["Criterios de inclusión", cr.inc], ["Criterios de exclusión", cr.exc]].forEach(function (x) {
      if (!x[1].length) return;
      var n = x[1].filter(function (l) { return l.indexOf("§ ") !== 0; }).length;
      var dt = el("details"); dt.appendChild(el("summary", null, x[0] + " (" + n + ")"));
      var ul2 = el("ul", "crit");
      x[1].forEach(function (l) {
        var enc = l.indexOf("§ ") === 0;
        ul2.appendChild(el("li", enc ? "enc" : null, enc ? l.slice(2) : l));
      });
      dt.appendChild(ul2); d.appendChild(dt);
    });
    if (!cr.inc.length && !cr.exc.length) {
      d.appendChild(el("p", "aviso", "El REec no publica los criterios de inclusión y exclusión de este ensayo."));
      if (e.ctis) {
        var c = el("a", "btn claro", "Buscar sus criterios en el registro europeo (CTIS)");
        c.href = e.ctis; c.target = "_blank"; c.rel = "noopener"; d.appendChild(c);
      }
    }
    var v = el("button", "btn claro", "Ver todos sus centros en el mapa"); v.type = "button";
    v.addEventListener("click", function () { enfocar(e.identificador); });
    d.appendChild(v);
    var a = el("a", "btn", "Ver ficha oficial y datos de contacto");
    a.href = e.url_reec; a.target = "_blank"; a.rel = "noopener";
    d.appendChild(a);
    return d;
  }
  function tarjeta(e, h) {
    var abierta = estado.exp === e.identificador;
    var art = el("article", "ens" + (abierta ? " sel" : ""));
    var t = el("h4"), b = el("button");
    if (e.nombre) b.appendChild(el("span", e.nombre_tipo === "protocolo" ? "nom cod" : "nom", e.nombre));
    b.appendChild(document.createTextNode(corto(tituloEnsayo(e), e.nombre ? 130 : 150)));
    b.type = "button"; b.setAttribute("aria-expanded", abierta ? "true" : "false");
    b.addEventListener("click", function () {
      estado.exp = abierta ? null : e.identificador;
      var sc = $("#pcuerpo").scrollTop; renderPanel(); $("#pcuerpo").scrollTop = sc;
    });
    t.appendChild(b); art.appendChild(t);
    art.appendChild(chipsEnsayo(e));
    if (!abierta && e.indicacion) art.appendChild(el("p", "ind", corto(e.indicacion, 150)));
    art.appendChild(el("div", "meta", (e.centros.length) + " centro(s) abierto(s) · " + (e.promotor || "")));
    if (abierta) art.appendChild(ficha(e, h));
    return art;
  }
  function renderPanelProm() {
    var p = $("#panel"), cuerpo = $("#pcuerpo"); cuerpo.textContent = "";
    var lista = T.filter(function (e) { return e.promotor_c === prom; });
    if (!lista.length) { p.hidden = true; return; }
    p.hidden = false;
    var ok = lista.filter(function (e) { return res.vistos[e.identificador]; });
    var otros = lista.filter(function (e) { return !res.vistos[e.identificador]; });
    var tipo = { industria: "Industria farmacéutica", cooperativo: "Grupo cooperativo", academico: "Hospital, universidad o institución académica" }[lista[0].promotor_t] || "";
    var nombres = {}; lista.forEach(function (e) { if (e.promotor) nombres[e.promotor] = 1; });
    $("#ptit").textContent = prom;
    $("#psub").textContent = tipo + " · " + lista.length + " ensayo(s)";
    var nn = Object.keys(nombres);
    if (nn.length > 1 || (nn[0] && nn[0] !== prom)) cuerpo.appendChild(el("p", "dir", "Figura en el REec como: " + nn.join("; ")));
    var filtro = hayFiltro();
    cuerpo.appendChild(el("p", "cuenta", filtro ? ok.length + " de " + lista.length + " ensayos coinciden con tu búsqueda" : lista.length + " ensayo(s) abierto(s) en España"));
    if (ok.length) { var l = el("div", "lista"); ok.forEach(function (e) { l.appendChild(tarjeta(e, null)); }); cuerpo.appendChild(l); }
    if (otros.length) {
      var dt = el("details", "otros"); dt.open = !ok.length;
      dt.appendChild(el("summary", null, (ok.length ? "Otros " : "") + otros.length + " ensayo(s) de este promotor que no coinciden"));
      var l2 = el("div", "lista"); otros.forEach(function (e) { l2.appendChild(tarjeta(e, null)); }); dt.appendChild(l2);
      cuerpo.appendChild(dt);
    }
  }
  function renderPanel() {
    if (vista === "red") { if (!prom) $("#panel").hidden = true; else renderPanelProm(); return; }
    var p = $("#panel"), s = S[estado.sitio];
    if (!s) { p.hidden = true; return; }
    p.hidden = false;
    var cuerpo = $("#pcuerpo"); cuerpo.textContent = "";
    var multi = s.hs.length > 1, h0 = s.hs[0];
    $("#ptit").textContent = multi ? s.hs.length + " centros en este punto" : h0.c.centro;
    $("#psub").textContent = multi ? [h0.c.localidad, nombreProv(h0)].filter(Boolean).join(", ")
      : [h0.c.domicilio, h0.c.localidad].filter(Boolean).join(", ") + (h0.c.precision !== "direccion" && h0.c.precision !== "nombre" ? " · ubicación aproximada" : "");
    s.hs.forEach(function (h) {
      if (multi) { cuerpo.appendChild(el("h3", null, h.c.centro)); cuerpo.appendChild(el("p", "dir", [h.c.domicilio, h.c.localidad].filter(Boolean).join(", "))); }
      var okIds = {}; h.ok.forEach(function (e) { okIds[e.identificador] = 1; });
      var otros = h.ensayos.filter(function (e) { return !okIds[e.identificador]; });
      var filtro = hayFiltro();
      cuerpo.appendChild(el("p", "cuenta", filtro
        ? (h.ok.length ? h.ok.length + " de " + h.ensayos.length + " ensayos coinciden con tu búsqueda" : "Ningún ensayo de este centro coincide con tu búsqueda")
        : h.ensayos.length + " ensayo(s) abierto(s) en este centro"));
      if (h.ok.length) { var l = el("div", "lista"); h.ok.forEach(function (e) { l.appendChild(tarjeta(e, h)); }); cuerpo.appendChild(l); }
      if (otros.length && (filtro || !estado.seg)) {
        var dt = el("details", "otros"); dt.open = !h.ok.length;
        dt.appendChild(el("summary", null, (h.ok.length ? "Otros " : "") + otros.length + " ensayo(s) abiertos en este centro que no coinciden"));
        var l2 = el("div", "lista"); otros.forEach(function (e) { l2.appendChild(tarjeta(e, h)); }); dt.appendChild(l2);
        cuerpo.appendChild(dt);
      }
    });
  }
  function nombreProv(h) { return titulo(h.c.provincia); }
  function abrirSitio(k) {
    estado.sitio = k; estado.exp = null;
    renderPanel(); $("#pcuerpo").scrollTop = 0;
    cerrarHojas();
    pintarMapa(false);
    var s = S[k]; map.fitBounds(L.latLngBounds([[s.lat, s.lon]]), padOpts(Math.max(map.getZoom(), 10)));
  }
  function cerrarPanel() {
    estado.sitio = null; estado.exp = null; $("#panel").hidden = true;
    if (vista === "red") { prom = null; if (window.EC && EC.red) EC.red.actualizar(); } else pintarMapa(false);
  }

  // --- enfocar un ensayo (resalta sus centros en el mapa) ---------------------
  function enfocar(id) {
    if (vista === "red") cambiarVista("mapa", true);
    estado.ens = id; estado.q = ""; $("#q").value = ""; estado.sitio = null; estado.exp = null;
    $("#panel").hidden = true; cerrarHojas(); render(true);
  }
  function quitarFoco() { estado.ens = null; render(true); }

  // --- sugerencias de la búsqueda ----------------------------------------------
  function sugerir() {
    var cont = $("#sug"), q = norm($("#q").value).trim().split(/\s+/).filter(Boolean);
    cont.textContent = "";
    if (!q.length) { cont.hidden = true; return; }
    var m = T.filter(function (e) {
      return (estado.seg || !e.seguimiento) && q.every(function (w) { return cache[e.identificador].indexOf(w) >= 0; });
    });
    if (!m.length) { cont.appendChild(el("p", null, "Ningún ensayo coincide.")); cont.hidden = false; return; }
    cont.appendChild(el("p", null, m.length + " ensayo(s) resaltados en el mapa. Pulsa uno para ver solo sus centros:"));
    m.slice(0, 6).forEach(function (e) {
      var b = el("button", null, (e.nombre ? e.nombre + " · " : "") + corto(tituloEnsayo(e), 110)); b.type = "button"; b.setAttribute("role", "option");
      b.appendChild(el("small", null, e.identificador + " · " + e.centros.length + " centro(s)"));
      b.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
      b.addEventListener("click", function () { enfocar(e.identificador); });
      cont.appendChild(b);
    });
    cont.hidden = false;
  }

  // --- render general -------------------------------------------------------------
  function nFiltros() { return (estado.enf ? 1 : 0) + (estado.ccaa ? 1 : 0) + (estado.prov ? 1 : 0) + (estado.fase ? 1 : 0) + (estado.seg ? 1 : 0); }
  function render(ajustar) {
    calcular();
    var foco = estado.ens ? T.filter(function (e) { return e.identificador === estado.ens; })[0] : null;
    $("#foco").hidden = !foco;
    if (foco) $("#foco-t").textContent = (foco.nombre ? foco.nombre + " · " : "") + corto(tituloEnsayo(foco), 90);
    if (vista === "red") {
      var pm = {}; T.forEach(function (e) { if (res.vistos[e.identificador]) pm[e.promotor_c] = 1; });
      $("#estado").textContent = res.ensayos + " ensayo(s) · " + Object.keys(pm).length + " promotor(es)" + (hayFiltro() ? " resaltados en la red" : " con ensayos abiertos en España");
    } else
    $("#estado").textContent = res.ensayos + " ensayo(s) · " + res.hospitales + " centro(s)" + (hayFiltro() ? " resaltados en el mapa" : " abiertos en España");
    var nf = nFiltros(), b = $("#nfil"); b.hidden = !nf; b.textContent = nf;
    if (estado.sitio && !(S[estado.sitio])) estado.sitio = null;
    renderPanel();
    if (vista === "red") { if (window.EC && EC.red) EC.red.actualizar(); }
    else pintarMapa(!!ajustar);
  }

  // --- filtros ------------------------------------------------------------------
  function rellenar(sel, valores, etiqueta) {
    var actual = sel.value; sel.length = 1;
    valores.forEach(function (v) { var o = el("option", null, etiqueta ? etiqueta(v) : v); o.value = v; sel.appendChild(o); });
    sel.value = valores.indexOf(actual) >= 0 ? actual : "";
  }
  function unicos(campo, filtro) {
    var s = {};
    Object.keys(H).forEach(function (id) { var c = H[id].c; if (!filtro || filtro(c)) s[c[campo]] = 1; });
    return Object.keys(s).filter(Boolean).sort(function (a, b) { return a.localeCompare(b, "es"); });
  }
  function opcionesProv() {
    rellenar($("#f-prov"), unicos("provincia", function (c) { return !estado.ccaa || c.ccaa === estado.ccaa; }), titulo);
    estado.prov = $("#f-prov").value;
  }
  function opcionesEnfermedad() {
    var sel = $("#f-enf");
    function cuenta(v) { return T.filter(function (e) { return cumpleEnf(e, v); }).length; }
    TX.grupos.forEach(function (g) {
      var ents = TX.entidades.filter(function (e) { return e.g === g.id && cuenta("e:" + e.id) > 0; });
      var ng = cuenta("g:" + g.id);
      if (!ng) return;
      var og = document.createElement("optgroup"); og.label = g.n;
      var o = el("option", null, "Todo el grupo (" + ng + ")"); o.value = "g:" + g.id; og.appendChild(o);
      if (ents.length > 1 || (ents.length === 1 && ents[0].n !== g.n)) {
        ents.forEach(function (e) { var oe = el("option", null, "   " + e.n + " (" + cuenta("e:" + e.id) + ")"); oe.value = "e:" + e.id; og.appendChild(oe); });
      }
      sel.appendChild(og);
    });
  }
  function cerrarHojas() {
    $("#filtros").hidden = true; $("#btn-filtros").setAttribute("aria-expanded", "false"); $("#sug").hidden = true;
  }

  rellenar($("#f-ccaa"), unicos("ccaa"), nombreCcaa);
  opcionesProv();
  opcionesEnfermedad();
  var fases = {}; T.forEach(function (e) { (e.fase || "").split("/").forEach(function (f) { if (f) fases[f] = 1; }); });
  rellenar($("#f-fase"), Object.keys(fases).sort(), function (f) { return "Fase " + f; });

  function cambio(fn) { return function (ev) { fn(ev); estado.sitio = estado.sitio; render(true); }; }
  var tmr;
  $("#q").addEventListener("input", function (ev) {
    clearTimeout(tmr);
    tmr = setTimeout(function () {
      estado.q = ev.target.value; estado.ens = null; $("#filtros").hidden = true; sugerir(); render(true);
    }, 200);
  });
  $("#q").addEventListener("focus", sugerir);
  $("#q").addEventListener("blur", function () { setTimeout(function () { $("#sug").hidden = true; }, 150); });
  $("#f-enf").addEventListener("change", cambio(function (ev) { estado.enf = ev.target.value; estado.ens = null; }));
  $("#f-ccaa").addEventListener("change", cambio(function (ev) { estado.ccaa = ev.target.value; opcionesProv(); }));
  $("#f-prov").addEventListener("change", cambio(function (ev) { estado.prov = ev.target.value; }));
  $("#f-fase").addEventListener("change", cambio(function (ev) { estado.fase = ev.target.value; estado.ens = null; }));
  $("#f-seg").addEventListener("change", cambio(function (ev) { estado.seg = ev.target.checked; }));
  $("#limpiar").addEventListener("click", function () {
    estado = { q: "", enf: "", ccaa: "", prov: "", fase: "", seg: false, ens: null, sitio: null, exp: null };
    $("#q").value = ""; $("#f-enf").value = ""; $("#f-ccaa").value = ""; opcionesProv(); $("#f-fase").value = ""; $("#f-seg").checked = false;
    render(true);
  });
  $("#foco-x").addEventListener("click", quitarFoco);
  $("#pcerrar").addEventListener("click", cerrarPanel);
  $("#btn-filtros").addEventListener("click", function () {
    var f = $("#filtros"); f.hidden = !f.hidden; this.setAttribute("aria-expanded", f.hidden ? "false" : "true"); $("#sug").hidden = true;
  });
  $("#btn-info").addEventListener("click", function () { $("#info").hidden = false; $("#info-x").focus(); });
  $("#info-x").addEventListener("click", function () { $("#info").hidden = true; });
  $("#info").addEventListener("click", function (ev) { if (ev.target === this) this.hidden = true; });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    if (!$("#info").hidden) $("#info").hidden = true;
    else if (!$("#filtros").hidden || !$("#sug").hidden) cerrarHojas();
    else if (!$("#panel").hidden) cerrarPanel();
  });
  map.on("click", function () { cerrarHojas(); });

  function cambiarVista(v, sinRender) {
    if (v === vista) return;
    vista = v;
    $("#v-mapa").classList.toggle("on", v === "mapa"); $("#v-red").classList.toggle("on", v === "red");
    $("#red").hidden = v !== "red"; $("#mapa").style.visibility = v === "red" ? "hidden" : "";
    $("#panel").hidden = true; cerrarHojas();
    if (v === "red") { if (window.EC && EC.red) EC.red.mostrar(); }
    else { prom = null; setTimeout(function () { map.invalidateSize(); }, 0); }
    if (!sinRender) render(v !== "red");
  }
  $("#v-mapa").addEventListener("click", function () { cambiarVista("mapa"); });
  $("#v-red").addEventListener("click", function () { cambiarVista("red"); });
  window.EC = {
    T: T, estado: function () { return estado; }, vistos: function () { return res.vistos; }, hayFiltro: hayFiltro,
    abrirPromotor: function (c, ensayo) { prom = c; estado.exp = ensayo || null; renderPanelProm(); $("#pcuerpo").scrollTop = 0; cerrarHojas(); },
    promotorAbierto: function () { return prom; }, cerrarPanel: cerrarPanel
  };

  $("#fecha").textContent = D.meta.generado ? D.meta.generado.split("-").reverse().join("/") : "—";
  render(true);
})();
