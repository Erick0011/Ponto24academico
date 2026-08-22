/* Comunidade — votar sem recarregar a página.
 *
 * Os botões continuam a ser <form> normais: sem JavaScript o voto funciona
 * como sempre (POST + redirect). Aqui só intercetamos o submit para votar por
 * fetch e atualizar o número no sítio — o que interessa sobretudo no feed,
 * onde o recarregamento fazia perder a posição no scroll infinito.
 */
(function () {
  "use strict";

  function pintar(widget, score, meuVoto) {
    var el = widget.querySelector(".p24-voto-score");
    var cima = widget.querySelector(".p24-voto-cima");
    var baixo = widget.querySelector(".p24-voto-baixo");

    el.textContent = score;
    el.classList.toggle("positivo", score > 0);
    el.classList.toggle("negativo", score < 0);

    cima.classList.toggle("ativo", meuVoto === 1);
    baixo.classList.toggle("ativo", meuVoto === -1);
    cima.setAttribute("aria-pressed", meuVoto === 1 ? "true" : "false");
    baixo.setAttribute("aria-pressed", meuVoto === -1 ? "true" : "false");
    widget.dataset.votoActual = meuVoto || 0;
  }

  function avisar(widget, mensagem) {
    /* Aviso discreto junto ao widget (ex: "não podes votar no teu próprio
     * conteúdo"), em vez do flash que só apareceria após recarregar. */
    var anterior = widget.parentNode.querySelector(".p24-voto-aviso");
    if (anterior) anterior.remove();

    var aviso = document.createElement("div");
    aviso.className = "p24-voto-aviso text-muted small mt-1";
    aviso.setAttribute("role", "status");
    aviso.textContent = mensagem;
    widget.insertAdjacentElement("afterend", aviso);
    setTimeout(function () { aviso.remove(); }, 4000);
  }

  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form.classList || !form.classList.contains("p24-voto-form")) return;

    var widget = form.closest("[data-voto]");
    if (!widget) return;

    ev.preventDefault();
    if (widget.classList.contains("ocupado")) return;
    widget.classList.add("ocupado");

    fetch(widget.dataset.votoUrl, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch" }
    })
      .then(function (r) {
        /* Sessão expirada: o Flask-Login responde com um redirect para o
         * login, que o fetch segue e devolve HTML. Nesse caso vale mais
         * mandar a pessoa para o login do que falhar em silêncio. */
        if (r.redirected || r.status === 401) {
          window.location.href = r.url || "/auth/entrar";
          return null;
        }
        return r.json().catch(function () { return { ok: false }; });
      })
      .then(function (dados) {
        if (!dados) return;
        if (dados.ok) {
          pintar(widget, dados.score, dados.meu_voto);
        } else {
          avisar(widget, dados.erro || "Não foi possível registar o voto.");
        }
      })
      .catch(function () {
        avisar(widget, "Sem ligação. Tenta de novo.");
      })
      .then(function () {
        widget.classList.remove("ocupado");
      });
  });
})();
