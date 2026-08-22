/* Visualizador de PDF baseado em pdf.js.
 *
 * Substitui o antigo <iframe src="ficheiro.pdf">, que nunca funcionou em
 * mobile: o Chrome no Android e o Safari no iOS não têm visualizador de PDF
 * embutido para iframes e limitam-se a mostrar um painel branco.
 *
 * A biblioteca (≈370 KB) só é descarregada quando o visualizador entra no
 * ecrã — quem abre a página e não desce até à pré-visualização não paga esses
 * dados.
 */
(function () {
  "use strict";

  var libPromise = null;

  function carregarLib(url, workerUrl) {
    if (libPromise) return libPromise;
    libPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = url;
      s.onload = function () {
        var lib = window.pdfjsLib;
        if (!lib) return reject(new Error("pdfjsLib indisponível"));
        lib.GlobalWorkerOptions.workerSrc = workerUrl;
        resolve(lib);
      };
      s.onerror = function () { reject(new Error("falha ao carregar pdf.js")); };
      document.head.appendChild(s);
    });
    return libPromise;
  }

  function iniciar(raiz) {
    if (raiz.dataset.pdfIniciado) return;
    raiz.dataset.pdfIniciado = "1";

    var palco     = raiz.querySelector(".p24-pdf-palco");
    var canvas    = raiz.querySelector(".p24-pdf-canvas");
    var estado    = raiz.querySelector(".p24-pdf-estado");
    var fallback  = raiz.querySelector(".p24-pdf-fallback");
    var btnAnt    = raiz.querySelector(".p24-pdf-anterior");
    var btnSeg    = raiz.querySelector(".p24-pdf-seguinte");
    var btnMenos  = raiz.querySelector(".p24-pdf-menos");
    var btnMais   = raiz.querySelector(".p24-pdf-mais");
    var elPagina  = raiz.querySelector(".p24-pdf-pagina");
    var elTotal   = raiz.querySelector(".p24-pdf-total");

    var doc = null, pagina = 1, total = 0, zoom = 1, aRenderizar = false, pendente = null;

    function falhar() {
      raiz.classList.add("p24-pdf-falhou");
      if (palco) palco.classList.add("d-none");
      if (fallback) fallback.classList.remove("d-none");
    }

    function actualizarBotoes() {
      btnAnt.disabled = pagina <= 1;
      btnSeg.disabled = pagina >= total;
      btnMenos.disabled = zoom <= 0.5;
      btnMais.disabled = zoom >= 3;
    }

    /* Escala "fit width": a página ocupa a largura disponível, multiplicada
     * pelo zoom escolhido. É o que faz o PDF ser legível num telemóvel sem
     * obrigar a fazer scroll horizontal. */
    function escalaBase(page) {
      var largura = palco.clientWidth || raiz.clientWidth || 320;
      var natural = page.getViewport({ scale: 1 });
      return (largura / natural.width) * zoom;
    }

    function renderizar() {
      if (!doc) return;
      if (aRenderizar) { pendente = pagina; return; }
      aRenderizar = true;

      doc.getPage(pagina).then(function (page) {
        var escala = escalaBase(page);
        var viewport = page.getViewport({ scale: escala });
        /* devicePixelRatio: sem isto o canvas fica desfocado em ecrãs retina. */
        var dpr = Math.min(window.devicePixelRatio || 1, 2);

        canvas.width  = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        canvas.style.width  = Math.floor(viewport.width) + "px";
        canvas.style.height = Math.floor(viewport.height) + "px";

        var ctx = canvas.getContext("2d");
        return page.render({
          canvasContext: ctx,
          viewport: viewport,
          transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null
        }).promise;
      }).then(function () {
        aRenderizar = false;
        elPagina.textContent = pagina;
        actualizarBotoes();
        if (pendente !== null && pendente !== pagina) { pagina = pendente; pendente = null; renderizar(); }
        else { pendente = null; }
      }).catch(function () {
        aRenderizar = false;
        falhar();
      });
    }

    function irPara(n) {
      if (!doc || n < 1 || n > total || n === pagina) return;
      pagina = n;
      renderizar();
      /* Ao mudar de página, volta ao topo da página nova. */
      palco.scrollTop = 0;
    }

    btnAnt.addEventListener("click", function () { irPara(pagina - 1); });
    btnSeg.addEventListener("click", function () { irPara(pagina + 1); });
    btnMenos.addEventListener("click", function () {
      zoom = Math.max(0.5, Math.round((zoom - 0.25) * 100) / 100); renderizar();
    });
    btnMais.addEventListener("click", function () {
      zoom = Math.min(3, Math.round((zoom + 0.25) * 100) / 100); renderizar();
    });

    var redimensionar;
    window.addEventListener("resize", function () {
      clearTimeout(redimensionar);
      redimensionar = setTimeout(renderizar, 200);
    });

    carregarLib(raiz.dataset.pdfLib, raiz.dataset.pdfWorker)
      .then(function (lib) {
        return lib.getDocument({ url: raiz.dataset.pdfSrc }).promise;
      })
      .then(function (d) {
        doc = d;
        total = d.numPages;
        elTotal.textContent = total;
        if (estado) estado.remove();
        raiz.classList.add("p24-pdf-pronto");
        renderizar();
      })
      .catch(falhar);
  }

  function arrancar() {
    var viewers = document.querySelectorAll(".p24-pdf");
    if (!viewers.length) return;

    if (!("IntersectionObserver" in window)) {
      Array.prototype.forEach.call(viewers, iniciar);
      return;
    }
    var obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (e.isIntersecting) { obs.unobserve(e.target); iniciar(e.target); }
      });
    }, { rootMargin: "200px" });
    Array.prototype.forEach.call(viewers, function (v) { obs.observe(v); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arrancar);
  } else {
    arrancar();
  }
})();
