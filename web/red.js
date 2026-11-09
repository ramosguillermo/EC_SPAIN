/* Vista «Red»: promotores · ensayos · investigadores principales (grafo de fuerzas). Cada capa se puede ocultar. */
(function () {
  var EC = window.EC, d3 = window.d3;
  if (!EC || !d3) return;
  var cont = document.getElementById("red");
  var svg, gZoom, sim, nodos = [], enlaces = [], listo = false, ancho = 0, alto = 0, capas = { p: true, i: true, e: true };
  var BASE = null, pos = {}, sels = {};
  var COL_P = { industria: "#4363d8", cooperativo: "#ffe119", academico: "#00a99d", otro: "#bbbbbb" };
  var COL_G = { bmad: "#e6194b", pc: "#911eb4", lma: "#f58231", nmp: "#3cb44b", smd: "#9a6324", lla: "#f032e6", cit: "#800000", tph: "#808000",
    hem: "#000075", tnk: "#46f0f0", hbp: "#bcf60c", comp: "#fabed4", hodgkin: "#e6beff", hist: "#aaffc3", inm: "#ffd8b1", masto: "#008080",
    otro: "#9a9a9a", varias: "#111111" };
  var COL_I = "#ff2d95";
  function grupoDe(e) { var g = EC.grupos(e); return g.length >= 3 ? "varias" : (g[0] || "otro"); }

  // ---- datos base (una sola vez) ----
  function base() {
    var P = {}, I = {}, E = [];
    EC.T.forEach(function (e) {
      var c = e.promotor_c || "Sin promotor";
      if (!P[c]) P[c] = { id: "p:" + c, k: "p", nombre: c, tipo: e.promotor_t || "otro", ens: [], ips: {} };
      P[c].ens.push(e);
      var ips = {};
      e.centros.forEach(function (x) { if (x.ip) ips[x.ip] = 1; });
      Object.keys(ips).forEach(function (n) {
        if (!I[n]) I[n] = { id: "i:" + n, k: "i", nombre: n, ens: [], sedes: {} };
        I[n].ens.push(e);
        e.centros.forEach(function (x) { if (x.ip === n) I[n].sedes[x.centro] = 1; });
      });
      E.push({ id: "e:" + e.identificador, k: "e", e: e, g: grupoDe(e), prom: "p:" + c, ips: Object.keys(ips).map(function (n) { return "i:" + n; }) });
    });
    return { P: P, I: I, E: E };
  }

  function r(d) { return d.k === "p" ? 9 + 4.2 * Math.sqrt(d.ens.length) : d.k === "i" ? 5.5 + 2.8 * Math.sqrt(d.ens.length) : 4.2; }

  // ---- grafo según capas activas ----
  function grafo() {
    var ns = [], ls = [], B = BASE;
    if (capas.p) Object.keys(B.P).forEach(function (k) { ns.push(B.P[k]); });
    if (capas.i) Object.keys(B.I).forEach(function (k) { ns.push(B.I[k]); });
    if (capas.e) B.E.forEach(function (n) { ns.push(n); });
    if (capas.e) {
      B.E.forEach(function (n) {
        if (capas.p) ls.push({ source: n.prom, target: n.id, w: 1 });
        if (capas.i) n.ips.forEach(function (i) { ls.push({ source: i, target: n.id, w: 1 }); });
      });
    } else if (capas.p && capas.i) {                 // sin ensayos: promotor ↔ investigador, con peso = nº de ensayos compartidos
      var W = {};
      B.E.forEach(function (n) { n.ips.forEach(function (i) { var k = n.prom + "|" + i; W[k] = (W[k] || 0) + 1; }); });
      Object.keys(W).forEach(function (k) { var s = k.split("|"); ls.push({ source: s[0], target: s[1], w: W[k] }); });
    }
    return { ns: ns, ls: ls };
  }

  function medir() { ancho = cont.clientWidth || window.innerWidth; alto = cont.clientHeight || window.innerHeight; }

  function pintarForma(g, d) {
    var c = d.k === "p" ? COL_P[d.tipo] || COL_P.otro : d.k === "i" ? COL_I : COL_G[d.g] || COL_G.otro, rr = d.r, f;
    if (d.k === "p" && d.tipo === "academico") f = g.append("rect").attr("x", -rr).attr("y", -rr).attr("width", 2 * rr).attr("height", 2 * rr).attr("rx", 3);
    else if (d.k === "i") f = g.append("path").attr("d", "M0," + -rr * 1.25 + "L" + rr * 1.1 + ",0L0," + rr * 1.25 + "L" + -rr * 1.1 + ",0Z");
    else f = g.append("circle").attr("r", rr);
    f.style("fill", c);
  }

  function montarGrafo(primera) {
    medir();
    var G = grafo(); nodos = G.ns; enlaces = G.ls;
    nodos.forEach(function (d) { d.r = r(d); var q = pos[d.id]; if (q) { d.x = q[0]; d.y = q[1]; } });
    if (sim) sim.stop();
    gZoom.selectAll("*").remove();
    var ln = gZoom.append("g").attr("class", "r-enl").selectAll("line").data(enlaces).enter().append("line")
      .style("stroke-width", function (l) { return capas.e ? 1 : Math.min(5, .8 + l.w * .8); });
    var nd = gZoom.append("g").attr("class", "r-nod").selectAll("g").data(nodos, function (d) { return d.id; }).enter().append("g")
      .attr("class", function (d) { return "r-n " + d.k; }).attr("tabindex", function (d) { return d.k === "e" ? null : 0; });
    nd.each(function (d) {
      var g = d3.select(this); pintarForma(g, d);
      var t = d.k === "p" ? d.nombre + " · " + d.ens.length + " ensayo(s)" : d.k === "i" ? d.nombre + " (IP) · " + d.ens.length + " ensayo(s)"
        : (d.e.nombre ? d.e.nombre + " · " : "") + (d.e.titulo || d.e.identificador) + " · " + (d.g === "varias" ? "Varias enfermedades" : EC.nombreGrupo(d.g));
      g.append("title").text(t);
    });
    var tx = gZoom.append("g").attr("class", "r-txt").selectAll("text").data(nodos.filter(function (d) { return d.k !== "e"; })).enter().append("text")
      .attr("text-anchor", "middle").text(function (d) { return d.nombre.length > 24 ? d.nombre.slice(0, 23) + "…" : d.nombre; })
      .attr("class", function (d) { return (d.ens.length >= 3 ? "grande" : "peq") + (d.k === "i" ? " ip" : ""); });

    nd.on("click", function (ev, d) {
      ev.stopPropagation();
      if (d.k === "p") EC.abrirPromotor(d.nombre, null);
      else if (d.k === "i") EC.abrirInvestigador(d.nombre, null);
      else EC.abrirPromotor(d.e.promotor_c, d.e.identificador);
      resaltar();
    });
    nd.on("keydown", function (ev, d) { if (ev.key === "Enter") { if (d.k === "p") EC.abrirPromotor(d.nombre, null); else EC.abrirInvestigador(d.nombre, null); resaltar(); } });
    nd.on("mouseenter", function (ev, d) { hover(d); }).on("mouseleave", function () { hover(null); });
    nd.call(d3.drag().on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(.25).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
      .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

    sim = d3.forceSimulation(nodos)
      .force("link", d3.forceLink(enlaces).id(function (d) { return d.id; }).distance(function (l) { return 34 + l.source.r * 1.6 + (capas.e ? 0 : 60); }).strength(.55))
      .force("charge", d3.forceManyBody().strength(function (d) { return d.k === "p" ? -260 - 40 * d.ens.length : d.k === "i" ? -110 - 20 * d.ens.length : -38; }))
      .force("col", d3.forceCollide().radius(function (d) { return d.r + (d.k === "e" ? 5 : 14); }).iterations(2))
      .force("x", d3.forceX(0).strength(.02)).force("y", d3.forceY(0).strength(.02))
      .on("tick", function () {
        ln.attr("x1", function (d) { return d.source.x; }).attr("y1", function (d) { return d.source.y; })
          .attr("x2", function (d) { return d.target.x; }).attr("y2", function (d) { return d.target.y; });
        nd.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
        tx.attr("x", function (d) { return d.x; }).attr("y", function (d) { return d.y + d.r + 12; });
        nodos.forEach(function (d) { pos[d.id] = [d.x, d.y]; });
      });
    sim.stop();
    for (var i = 0; i < (primera ? 280 : 120); i++) sim.tick();
    sim.alpha(.05).restart();
    sels.ln = ln; sels.nd = nd; sels.tx = tx;
    actualizar();
    if (primera) encajar();
  }

  function montar() {
    BASE = base(); medir();
    svg = d3.select(cont).append("svg").attr("width", "100%").attr("height", "100%").attr("role", "img").attr("aria-label", "Red de promotores, ensayos e investigadores");
    gZoom = svg.append("g");
    var zoom = d3.zoom().scaleExtent([.25, 6]).on("zoom", function (ev) { gZoom.attr("transform", ev.transform); });
    svg.call(zoom).on("dblclick.zoom", null); svg._zoom = zoom;
    svg.on("click", function (ev) { if (ev.target === svg.node()) EC.cerrarPanel(); });
    interfaz();
    listo = true;
    montarGrafo(true);
  }

  // ---- controles: capas y leyenda ----
  function interfaz() {
    var cp = document.createElement("div"); cp.className = "r-capas"; cp.setAttribute("role", "group"); cp.setAttribute("aria-label", "Capas de la red");
    [["p", "Promotores"], ["e", "Ensayos"], ["i", "Investigadores"]].forEach(function (x) {
      var b = document.createElement("button"); b.type = "button"; b.textContent = x[1]; b.className = "on"; b.setAttribute("aria-pressed", "true");
      b.addEventListener("click", function () {
        var n = Object.keys(capas).filter(function (k) { return capas[k]; }).length;
        if (capas[x[0]] && n <= 2) return;                       // hacen falta al menos dos capas para que haya red
        capas[x[0]] = !capas[x[0]]; b.classList.toggle("on", capas[x[0]]); b.setAttribute("aria-pressed", capas[x[0]]);
        if (EC.promotorAbierto() || EC.investigadorAbierto()) { if (!capas[EC.investigadorAbierto() ? "i" : "p"]) EC.cerrarPanel(); }
        montarGrafo(false);
        setTimeout(encajar, 0);
      });
      cp.appendChild(b);
    });
    cont.appendChild(cp);

    var cuentaG = {}; BASE.E.forEach(function (d) { cuentaG[d.g] = (cuentaG[d.g] || 0) + 1; });
    var gs = Object.keys(cuentaG).sort(function (a, b) { return cuentaG[b] - cuentaG[a]; });
    var ley = document.createElement("details"); ley.className = "r-ley"; ley.open = window.innerWidth > 700;
    var h = '<summary>Leyenda</summary><div class="cuerpo"><h6>Promotor (tamaño = nº de ensayos)</h6>' +
      '<span><i class="c" style="background:' + COL_P.industria + '"></i>Industria</span>' +
      '<span><i class="c" style="background:' + COL_P.cooperativo + '"></i>Grupo cooperativo</span>' +
      '<span><i class="c q" style="background:' + COL_P.academico + '"></i>Hospital / universidad</span>' +
      '<h6>Investigador principal</h6><span><i class="c d" style="background:' + COL_I + '"></i>Investigador (tamaño = nº de ensayos)</span>' +
      '<h6>Enfermedad del ensayo (punto)</h6>';
    gs.forEach(function (g) {
      h += '<button type="button" data-g="' + g + '"><i class="c m" style="background:' + (COL_G[g] || COL_G.otro) + '"></i>' +
        (g === "varias" ? "Varias enfermedades" : EC.nombreGrupo(g).replace(/\s*\(.*$/, "")) + ' <b>' + cuentaG[g] + '</b></button>';
    });
    ley.innerHTML = h + '</div>';
    cont.appendChild(ley);
    Array.prototype.forEach.call(ley.querySelectorAll("button"), function (b) {
      var g = b.getAttribute("data-g");
      ["mouseenter", "focus"].forEach(function (ev) { b.addEventListener(ev, function () { resaltarGrupo(g); }); });
      ["mouseleave", "blur"].forEach(function (ev) { b.addEventListener(ev, function () { resaltarGrupo(null); }); });
      b.addEventListener("click", function () { resaltarGrupo(g); });
    });
  }

  function encajar() {
    if (!listo || !nodos.length) return;
    medir();
    var xs = nodos.map(function (d) { return d.x; }), ys = nodos.map(function (d) { return d.y; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var w = x1 - x0 + 120, h = y1 - y0 + 120, k = Math.min(ancho / w, (alto - 190) / h, 1.6);
    var tx = ancho / 2 - k * (x0 + x1) / 2, ty = (alto - 90) / 2 - k * (y0 + y1) / 2 + 30;
    svg.call(svg._zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  }

  function vecinos(d) {
    var v = {}; v[d.id] = 1;
    enlaces.forEach(function (l) { if (l.source.id === d.id) v[l.target.id] = 1; if (l.target.id === d.id) v[l.source.id] = 1; });
    return v;
  }
  function hover(d) {
    if (!listo) return;
    var v = d ? vecinos(d) : {};
    sels.nd.classed("hv", function (n) { return !!d && !v[n.id]; });
    sels.ln.classed("hv", function (l) { return !!d && !(l.source.id === d.id || l.target.id === d.id); });
    sels.tx.classed("ver", function (n) { return !!d && !!v[n.id]; });
  }
  function resaltarGrupo(g) {
    if (!listo) return;
    function tiene(n) { return n.ens.some(function (e) { return grupoDe(e) === g; }); }
    sels.nd.classed("hv", function (n) { return !!g && (n.k === "e" ? n.g !== g : !tiene(n)); });
    sels.ln.classed("hv", function (l) { return !!g && (l.target.k === "e" ? l.target.g !== g : !(tiene(l.source) && tiene(l.target))); });
  }
  function resaltar() {
    if (!listo) return;
    var p = EC.promotorAbierto(), i = EC.investigadorAbierto();
    sels.nd.classed("abierto", function (n) { return (n.k === "p" && n.nombre === p) || (n.k === "i" && n.nombre === i); });
  }

  function actualizar() {
    if (!listo || cont.hidden) return;
    var v = EC.vistos(), filtro = EC.hayFiltro(), okN = {};
    nodos.forEach(function (d) {
      if (d.k === "e") { if (v[d.e.identificador]) okN[d.id] = 1; }
      else if (d.ens.some(function (e) { return v[e.identificador]; })) okN[d.id] = 1;
    });
    sels.nd.classed("off", function (d) { return !okN[d.id] && (filtro || !!(d.k === "e" && !v[d.e.identificador])); });
    sels.ln.classed("off", function (l) { return !okN[l.source.id] || !okN[l.target.id]; });
    sels.tx.classed("off", function (d) { return !okN[d.id]; });
    resaltar();
  }

  function mostrar() { if (!listo) setTimeout(montar, 30); else { actualizar(); encajar(); } }
  window.addEventListener("resize", function () { if (!cont.hidden) encajar(); });
  EC.red = { mostrar: mostrar, actualizar: actualizar };
})();
