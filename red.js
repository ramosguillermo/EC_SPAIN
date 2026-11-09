/* Vista «Promotores»: red de ensayos unidos a su promotor (grafo de fuerzas, monocromo) */
(function () {
  var EC = window.EC, d3 = window.d3;
  if (!EC || !d3) return;
  var cont = document.getElementById("red");
  var svg, gZoom, sim, nodos = [], enlaces = [], sel = {}, listo = false, ancho = 0, alto = 0;
  var TIPOS = { industria: "Industria", cooperativo: "Grupo cooperativo", academico: "Hospital / universidad" };
  var COL_P = { industria: "#4363d8", cooperativo: "#ffe119", academico: "#00a99d", otro: "#bbbbbb" };
  var COL_G = { bmad: "#e6194b", pc: "#911eb4", lma: "#f58231", nmp: "#3cb44b", smd: "#9a6324", lla: "#f032e6", cit: "#800000", tph: "#808000",
    hem: "#000075", tnk: "#46f0f0", hbp: "#bcf60c", comp: "#fabed4", hodgkin: "#e6beff", hist: "#aaffc3", inm: "#ffd8b1", masto: "#008080",
    otro: "#9a9a9a", varias: "#111111" };
  function grupoDe(e) { var g = EC.grupos(e); return g.length >= 3 ? "varias" : (g[0] || "otro"); }

  function construir() {
    var T = EC.T, P = {}, id = 0;
    T.forEach(function (e) {
      var c = e.promotor_c || "Sin promotor";
      if (!P[c]) P[c] = { id: "p:" + c, k: "p", nombre: c, tipo: e.promotor_t || "otro", n: 0, ens: [] };
      P[c].n++; P[c].ens.push(e);
    });
    Object.keys(P).forEach(function (c) { var p = P[c]; p.r = 9 + 4.2 * Math.sqrt(p.n); nodos.push(p); });
    T.forEach(function (e) {
      var n = { id: "e:" + e.identificador, k: "e", e: e, g: grupoDe(e), r: 4.2, prom: "p:" + (e.promotor_c || "Sin promotor") };
      nodos.push(n); enlaces.push({ source: n.prom, target: n.id });
    });
  }

  function medir() { ancho = cont.clientWidth || window.innerWidth; alto = cont.clientHeight || window.innerHeight; }

  function montar() {
    construir(); medir();
    svg = d3.select(cont).append("svg").attr("width", "100%").attr("height", "100%").attr("role", "img")
      .attr("aria-label", "Red que une cada ensayo con su promotor");
    gZoom = svg.append("g");
    var zoom = d3.zoom().scaleExtent([.3, 6]).on("zoom", function (ev) { gZoom.attr("transform", ev.transform); });
    svg.call(zoom).on("dblclick.zoom", null);
    svg.on("click", function (ev) { if (ev.target === svg.node()) { EC.cerrarPanel(); } });

    var ln = gZoom.append("g").attr("class", "r-enl").selectAll("line").data(enlaces).enter().append("line");
    var nd = gZoom.append("g").attr("class", "r-nod").selectAll("g").data(nodos).enter().append("g")
      .attr("class", function (d) { return "r-n " + d.k + (d.k === "p" ? " t-" + d.tipo : ""); })
      .attr("tabindex", function (d) { return d.k === "p" ? 0 : null; });
    nd.each(function (d) {
      var g = d3.select(this);
      if (d.k === "p" && d.tipo === "academico") g.append("rect").attr("x", -d.r).attr("y", -d.r).attr("width", 2 * d.r).attr("height", 2 * d.r).attr("rx", 3);
      else g.append("circle").attr("r", d.r);
      g.select("circle,rect").style("fill", d.k === "p" ? (COL_P[d.tipo] || COL_P.otro) : (COL_G[d.g] || COL_G.otro));
      if (d.k === "p") g.append("title").text(d.nombre + " · " + d.n + " ensayo(s)");
      else g.append("title").text((d.e.nombre ? d.e.nombre + " · " : "") + (d.e.titulo || d.e.identificador) + " · " + (d.g === "varias" ? "Varias enfermedades" : EC.nombreGrupo(d.g)));
    });
    var tx = gZoom.append("g").attr("class", "r-txt").selectAll("text").data(nodos.filter(function (d) { return d.k === "p"; })).enter().append("text")
      .attr("text-anchor", "middle").text(function (d) { return d.nombre.length > 22 ? d.nombre.slice(0, 21) + "…" : d.nombre; })
      .attr("class", function (d) { return d.n >= 3 ? "grande" : "peq"; });

    nd.on("click", function (ev, d) {
      ev.stopPropagation();
      if (d.k === "p") EC.abrirPromotor(d.nombre, null); else EC.abrirPromotor(d.e.promotor_c, d.e.identificador);
      resaltar();
    });
    nd.on("keydown", function (ev, d) { if (ev.key === "Enter") { EC.abrirPromotor(d.nombre, null); resaltar(); } });
    nd.on("mouseenter", function (ev, d) { hover(d); }).on("mouseleave", function () { hover(null); });
    nd.call(d3.drag().on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(.25).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
      .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

    sim = d3.forceSimulation(nodos)
      .force("link", d3.forceLink(enlaces).id(function (d) { return d.id; }).distance(function (l) { return 16 + l.source.r; }).strength(.9))
      .force("charge", d3.forceManyBody().strength(function (d) { return d.k === "p" ? -60 - 14 * d.n : -9; }))
      .force("col", d3.forceCollide().radius(function (d) { return d.r + (d.k === "p" ? 8 : 1.6); }).iterations(2))
      .force("x", d3.forceX(0).strength(.05)).force("y", d3.forceY(0).strength(.05))
      .on("tick", function () {
        ln.attr("x1", function (d) { return d.source.x; }).attr("y1", function (d) { return d.source.y; })
          .attr("x2", function (d) { return d.target.x; }).attr("y2", function (d) { return d.target.y; });
        nd.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")"; });
        tx.attr("x", function (d) { return d.x; }).attr("y", function (d) { return d.y + d.r + 12; });
      });
    sim.stop();
    for (var i = 0; i < 260; i++) sim.tick();         // se coloca de entrada; después queda viva para arrastrar
    sim.alpha(.05).restart();
    svg._ln = ln; svg._nd = nd; svg._tx = tx; svg._zoom = zoom;

    var cuentaG = {}; nodos.forEach(function (d) { if (d.k === "e") cuentaG[d.g] = (cuentaG[d.g] || 0) + 1; });
    var gs = Object.keys(cuentaG).sort(function (a, b) { return cuentaG[b] - cuentaG[a]; });
    var ley = document.createElement("details"); ley.className = "r-ley"; ley.open = window.innerWidth > 700;
    var h = '<summary>Leyenda</summary><div class="cuerpo"><h6>Promotor (tamaño = nº de ensayos)</h6>' +
      '<span><i class="c" style="background:' + COL_P.industria + '"></i>Industria</span>' +
      '<span><i class="c" style="background:' + COL_P.cooperativo + '"></i>Grupo cooperativo</span>' +
      '<span><i class="c q" style="background:' + COL_P.academico + '"></i>Hospital / universidad</span>' +
      '<h6>Enfermedad del ensayo (punto)</h6>';
    gs.forEach(function (g) {
      h += '<button type="button" data-g="' + g + '"><i class="c m" style="background:' + (COL_G[g] || COL_G.otro) + '"></i>' +
        (g === "varias" ? "Varias enfermedades" : EC.nombreGrupo(g).replace(/\s*\(.*$/, "")) + ' <b>' + cuentaG[g] + '</b></button>';
    });
    ley.innerHTML = h + '</div>';
    cont.appendChild(ley);
    Array.prototype.forEach.call(ley.querySelectorAll("button"), function (b) {
      var g = b.getAttribute("data-g");
      b.addEventListener("mouseenter", function () { resaltarGrupo(g); }); b.addEventListener("mouseleave", function () { resaltarGrupo(null); });
      b.addEventListener("focus", function () { resaltarGrupo(g); }); b.addEventListener("blur", function () { resaltarGrupo(null); });
      b.addEventListener("click", function () { resaltarGrupo(g); });
    });
    listo = true; encajar(); actualizar();
  }

  function encajar() {
    if (!listo) return;
    medir();
    var xs = nodos.map(function (d) { return d.x; }), ys = nodos.map(function (d) { return d.y; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var w = x1 - x0 + 120, h = y1 - y0 + 120, k = Math.min(ancho / w, (alto - 190) / h, 1.6);
    var tx = ancho / 2 - k * (x0 + x1) / 2, ty = (alto - 90) / 2 - k * (y0 + y1) / 2 + 20;
    svg.call(svg._zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  }

  function hover(d) {
    if (!listo) return;
    var vec = {};
    if (d) { vec[d.id] = 1; enlaces.forEach(function (l) { if (l.source.id === d.id) vec[l.target.id] = 1; if (l.target.id === d.id) vec[l.source.id] = 1; }); }
    svg._nd.classed("hv", function (n) { return !!d && !vec[n.id]; });
    svg._ln.classed("hv", function (l) { return !!d && !(vec[l.source.id] && vec[l.target.id] && (l.source.id === d.id || l.target.id === d.id)); });
    svg._tx.classed("ver", function (n) { return !!d && !!vec[n.id]; });
  }

  function resaltarGrupo(g) {
    if (!listo) return;
    svg._nd.classed("hv", function (n) { return !!g && (n.k === "e" ? n.g !== g : !n.ens.some(function (e) { return grupoDe(e) === g; })); });
    svg._ln.classed("hv", function (l) { return !!g && l.target.g !== g; });
  }

  function resaltar() {
    if (!listo) return;
    var abierto = EC.promotorAbierto();
    svg._nd.classed("abierto", function (n) { return n.k === "p" && n.nombre === abierto; });
  }

  function actualizar() {
    if (!listo || cont.hidden) return;
    var v = EC.vistos(), filtro = EC.hayFiltro();
    var okP = {};
    nodos.forEach(function (d) { if (d.k === "e" && v[d.e.identificador]) okP[d.prom] = (okP[d.prom] || 0) + 1; });
    svg._nd.classed("off", function (d) { return filtro && (d.k === "e" ? !v[d.e.identificador] : !okP[d.id]); });
    svg._ln.classed("off", function (l) { return filtro && !v[l.target.e.identificador]; });
    svg._tx.classed("off", function (d) { return filtro && !okP[d.id]; });
    svg._nd.select("text.n").remove();
    resaltar();
  }

  function mostrar() {
    if (!listo) setTimeout(montar, 30); else { actualizar(); encajar(); }
  }
  window.addEventListener("resize", function () { if (!cont.hidden) encajar(); });
  EC.red = { mostrar: mostrar, actualizar: actualizar };
})();
