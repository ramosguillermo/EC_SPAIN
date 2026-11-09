/* Pestaña «Candidato»: perfil de un paciente -> ensayos posibles, a revisar y descartados (con el motivo y la frase del criterio) */
(function () {
  var EC = window.EC; if (!EC) return;
  var cont = document.getElementById("cand"), el = EC.el, listo = false, F = {};

  // Comorbilidades: se buscan en los criterios de EXCLUSIÓN; nunca descartan por sí solas, solo avisan.
  var COMORB = [
    ["cardio", "Cardiopatía / FEVI baja / arritmia", /cardiac|cardio|heart failure|myocardial|infarct|LVEF|ejection fraction|FEVI|QTc?\b|arrhythm|angina|NYHA|insuficiencia cardiaca|cardiopat/i],
    ["renal", "Insuficiencia renal", /renal|kidney|creatinine|CrCl|eGFR|glomerular|dialysis|diálisis|aclaramiento/i],
    ["hepatica", "Hepatopatía / cirrosis", /hepatic|liver|cirrho|bilirubin|\bALT\b|\bAST\b|transaminas|hepatopat/i],
    ["vih", "VIH", /\bHIV\b|\bVIH\b|immunodeficiency virus/i],
    ["hepat", "Hepatitis B o C", /hepatitis [BC]|\bHBV\b|\bHCV\b|HBsAg/i],
    ["infeccion", "Infección activa", /active infection|uncontrolled infection|systemic infection|serious infection|infección activa|infección no controlada/i],
    ["tumor", "Otra neoplasia previa o concomitante", /second malignan|other malignan|prior malignan|previous malignan|concurrent malignan|history of (another )?(cancer|malignan)|otra neoplasia|segunda neoplasia/i],
    ["snc", "Afectación del sistema nervioso central", /\bCNS\b|central nervous|brain metast|leptomening|SNC\b/i],
    ["pulmon", "Enfermedad pulmonar (EPOC, EPID, oxígeno)", /pulmonary|lung disease|interstitial|\bCOPD\b|\bILD\b|oxygen|pneumonitis|pulmonar|EPOC/i],
    ["sangrado", "Anticoagulación / sangrado activo", /anticoagul|bleeding|hemorrhag|sangrado|hemorrag/i],
    ["neuropatia", "Neuropatía periférica", /neuropath|neuropat/i],
    ["autoinmune", "Enfermedad autoinmune / inmunosupresión", /autoimmune|autoinmun|immunosuppress|inmunosupres|systemic steroids|corticosteroid/i],
    ["trasplante", "Trasplante previo (alo o auto)", /prior (allogeneic|autologous|stem cell|bone marrow)|previous (allogeneic|transplant)|allo-?HSCT|allogeneic (stem cell )?transplant|trasplante previo/i],
    ["embarazo", "Embarazo o lactancia", /pregnan|breast.?feeding|lactating|embarazo|lactancia/i]
  ];

  function lineas(arr) { return (arr || []).filter(function (l) { return l.indexOf("§ ") !== 0; }); }
  function anios(s) {          // "18 años" -> 18 ; "6 meses" -> 0.5
    var m = /^\s*(\d+)\s*(\S+)/.exec(s || ""); if (!m) return null;
    var n = +m[1], u = m[2];
    return /mes/.test(u) ? n / 12 : /seman/.test(u) ? n / 52 : /d[ií]a/.test(u) ? n / 365 : n;
  }
  function frase(l) { l = String(l).replace(/\s+/g, " ").trim(); return l.length > 230 ? l.slice(0, 229) + "…" : l; }

  function ecogMax(inc) {      // -> {max, explicito, linea} o null
    for (var i = 0; i < inc.length; i++) {
      var l = inc[i]; if (!/ECOG|performance status|WHO PS|\bPS\b/i.test(l)) continue;
      if (/(?:ECOG|performance status|\bPS\b)[^0-9]{0,45}?(?:≥|>=|>|at least|greater than|mayor)/i.test(l)) continue;   // mínimo, no límite superior
      var m = /(?:ECOG|performance status|\bPS\b)[^0-9]{0,45}?(\d)\s*(?:-|–|to|or|a|o)\s*(\d)/i.exec(l);
      if (m) return { max: +m[2], explicito: true, linea: l };
      m = /(?:ECOG|performance status|\bPS\b)[^0-9]{0,45}?(?:≤|<=|no (?:greater|higher|mayor) than|at most|less than or equal to|menor o igual (?:a|que)|of|score of|de)\s*(\d)/i.exec(l);
      if (m) return { max: +m[1], explicito: true, linea: l };
      m = /(?:ECOG|performance status|\bPS\b)[^0-9]{0,30}(\d)\b/i.exec(l);
      if (m) return { max: +m[1], explicito: false, linea: l };
    }
    return null;
  }

  function evalua(e, p) {
    var out = { e: e, dur: [], rev: [], ok: [] };
    var cr = e.criterios || {}, inc = lineas(cr.inc), exc = lineas(cr.exc), el0 = e.elegibilidad || {};
    // enfermedad
    if (p.enf) {
      if (!EC.cumpleEnf(e, p.enf)) return null;
      if (EC.soloPorGenerico(e, p.enf)) out.rev.push("El registro indica la enfermedad de forma general: comprueba en los criterios que incluye la tuya.");
    }
    if (e.seguimiento && !p.seg) return null;
    // edad
    if (p.edad != null) {
      var mn = anios(el0.edad_min), mx = anios(el0.edad_max);
      if (mn != null && p.edad < mn) out.dur.push("Edad mínima: " + el0.edad_min + ".");
      else if (mx != null && p.edad > mx) out.dur.push("Edad máxima: " + el0.edad_max + ".");
      else if (mn == null && mx == null) {
        var gr = [["ninos", 0, 11.99], ["adolescentes", 12, 17.99], ["adultos", 18, 64.99], ["ancianos", 65, 200]], hay = false, cabe = false;
        gr.forEach(function (g) { if (String(e[g[0]]) === "1") { hay = true; if (p.edad >= g[1] && p.edad <= g[2]) cabe = true; } });
        if (hay && !cabe) out.dur.push("El REec no incluye el grupo de edad del paciente.");
        else if (!hay) out.rev.push("El registro no indica edades: comprueba los criterios.");
      }
    }
    // sexo
    if (p.sexo && el0.sexo) {
      if ((p.sexo === "F" && el0.sexo === "Solo hombres") || (p.sexo === "M" && el0.sexo === "Solo mujeres")) out.dur.push(el0.sexo + ".");
    }
    // ECOG
    if (p.ecog != null) {
      var ec = ecogMax(inc);
      if (ec && p.ecog > ec.max) {
        if (ec.explicito) out.dur.push("ECOG máximo permitido: " + ec.max + ".  «" + frase(ec.linea) + "»");
        else out.rev.push("Posible límite de ECOG ≤ " + ec.max + " (el registro no deja claro el signo).  «" + frase(ec.linea) + "»");
      }
    }
    // comorbilidades
    COMORB.forEach(function (c) {
      if (!p.com[c[0]]) return;
      var hit = exc.filter(function (l) { return c[2].test(l); });
      if (hit.length) out.rev.push("Criterio de exclusión relacionado con «" + c[1].toLowerCase() + "» (" + hit.length + "): «" + frase(hit[0]) + "»");
    });
    if (!inc.length && !exc.length) out.rev.push("No hay criterios publicados: no se puede comprobar.");
    out.estado = out.dur.length ? "no" : out.rev.length ? "rev" : "si";
    return out;
  }

  function tarjeta(o) {
    var e = o.e, art = el("article", "ens");
    var t = el("h4"), b = el("button"); b.type = "button";
    if (e.nombre) b.appendChild(el("span", e.nombre_tipo === "protocolo" ? "nom cod" : "nom", e.nombre));
    b.appendChild(document.createTextNode(EC.corto(EC.tituloEnsayo(e), 140)));
    t.appendChild(b); art.appendChild(t); art.appendChild(EC.chips(e));
    var motivos = o.estado === "no" ? o.dur : o.rev;
    if (motivos.length) {
      var ul = el("ul", "rz");
      motivos.forEach(function (m) { ul.appendChild(el("li", null, m)); });
      if (o.estado === "no" && o.rev.length) o.rev.forEach(function (m) { ul.appendChild(el("li", "ev", m)); });
      art.appendChild(ul);
    }
    art.appendChild(el("div", "meta", e.centros.length + " centro(s) abierto(s) · " + (e.promotor || "")));
    var abierta = false, det = null;
    b.addEventListener("click", function () {
      abierta = !abierta;
      if (abierta) { det = EC.ficha(e, null); art.appendChild(det); art.classList.add("sel"); } else { det.remove(); art.classList.remove("sel"); }
    });
    return art;
  }

  function pintar() {
    var res = cont.querySelector(".res"); res.textContent = "";
    var p = { enf: F.enf.value, edad: F.edad.value === "" ? null : +F.edad.value, sexo: F.sexo.value, ecog: F.ecog.value === "" ? null : +F.ecog.value, seg: false, com: {} };
    Array.prototype.forEach.call(cont.querySelectorAll(".chks input"), function (c) { p.com[c.value] = c.checked; });
    if (!p.enf && p.edad == null && !p.sexo && p.ecog == null && !Object.keys(p.com).some(function (k) { return p.com[k]; })) {
      res.appendChild(el("p", "mut", "Elige al menos la enfermedad para ver los ensayos."));
      return;
    }
    var L = EC.T.map(function (e) { return evalua(e, p); }).filter(Boolean);
    var si = L.filter(function (o) { return o.estado === "si"; }), rev = L.filter(function (o) { return o.estado === "rev"; }), no = L.filter(function (o) { return o.estado === "no"; });
    function bloque(tit, arr, abierto, nota) {
      if (!arr.length) return;
      var d = el("details"); d.open = abierto; d.appendChild(el("summary", null, tit + " (" + arr.length + ")"));
      if (nota) d.appendChild(el("p", "mut", nota));
      var l = el("div", "res"); arr.forEach(function (o) { l.appendChild(tarjeta(o)); }); d.appendChild(l); res.appendChild(d);
    }
    res.appendChild(el("h3", null, L.length + " ensayo(s) abiertos para esa enfermedad"));
    bloque("Sin impedimentos detectados", si, true, "No se ha encontrado ningún criterio que lo impida con los datos introducidos. Aun así, hay que leer los criterios completos.");
    bloque("A revisar", rev, true, "Hay algo que comprobar: un criterio de exclusión relacionado, información que falta o una enfermedad indicada de forma general.");
    bloque("Descartados con los datos introducidos", no, false);
    if (!L.length) res.appendChild(el("p", "mut", "No hay ensayos abiertos para esa enfermedad."));
  }

  function montar() {
    var in_ = el("div", "in");
    in_.appendChild(el("h2", null, "¿A qué ensayos podría optar un paciente?"));
    in_.appendChild(el("p", "aviso", "Herramienta orientativa. Compara el perfil con los criterios publicados en el registro, que pueden estar incompletos o resumidos, y solo detecta algunos motivos de exclusión. La decisión de incluir a un paciente la toma siempre el equipo investigador del ensayo."));
    var form = el("div", "form");
    function campo(txt, ctl, ancho) { var l = el("label", ancho ? "ancho" : null, txt); l.appendChild(ctl); form.appendChild(l); return ctl; }
    var s = document.createElement("select"); s.innerHTML = '<option value="">Cualquier enfermedad</option>' + EC.opcionesEnf().replace(/<option value="">[^<]*<\/option>/, ""); F.enf = campo("Enfermedad (clasificación OMS)", s, true);
    var n = document.createElement("input"); n.type = "number"; n.min = 0; n.max = 110; n.placeholder = "años"; F.edad = campo("Edad", n);
    var sx = document.createElement("select"); sx.innerHTML = '<option value="">No indicado</option><option value="F">Mujer</option><option value="M">Hombre</option>'; F.sexo = campo("Sexo", sx);
    var ec = document.createElement("select"); ec.innerHTML = '<option value="">No indicado</option><option value="0">0 · asintomático</option><option value="1">1 · síntomas leves, ambulatorio</option><option value="2">2 · encamado menos del 50 % del día</option><option value="3">3 · encamado más del 50 %</option><option value="4">4 · encamado todo el día</option>'; F.ecog = campo("Estado funcional (ECOG)", ec, true);
    var fs = el("fieldset"); fs.appendChild(el("legend", null, "Comorbilidades del paciente"));
    var g = el("div", "chks");
    COMORB.forEach(function (c) { var l = el("label"), i = document.createElement("input"); i.type = "checkbox"; i.value = c[0]; l.appendChild(i); l.appendChild(document.createTextNode(c[1])); g.appendChild(l); });
    fs.appendChild(g); var w = el("label", "ancho"); w.style.color = "inherit"; w.appendChild(fs); form.appendChild(w);
    in_.appendChild(form);
    in_.appendChild(el("div", "res"));
    cont.appendChild(in_);
    cont.addEventListener("input", pintar); cont.addEventListener("change", pintar);
    listo = true; pintar();
  }
  EC.cand = { mostrar: function () { if (!listo) montar(); } };
})();
