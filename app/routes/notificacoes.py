from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.notificacao import Notificacao

notificacoes_bp = Blueprint("notificacoes", __name__, url_prefix="/notificacoes")


@notificacoes_bp.route("/")
@login_required
def index():
    """Página de notificações do utilizador."""
    page = request.args.get("page", 1, type=int)
    notificacoes = (
        current_user.notificacoes
        .order_by(Notificacao.criado_em.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    # Marca todas as mostradas como lidas
    nao_lidas = (
        current_user.notificacoes
        .filter_by(lida=False)
        .all()
    )
    for n in nao_lidas:
        n.lida = True
    if nao_lidas:
        db.session.commit()

    return render_template("notificacoes/index.html", notificacoes=notificacoes)


@notificacoes_bp.route("/<int:id>/ler", methods=["POST"])
@login_required
def marcar_lida(id):
    """Marca uma notificação como lida e redireciona para o URL associado."""
    n = Notificacao.query.filter_by(id=id, utilizador_id=current_user.id).first_or_404()
    n.lida = True
    db.session.commit()
    return redirect(n.url or url_for("notificacoes.index"))


@notificacoes_bp.route("/ler-todas", methods=["POST"])
@login_required
def marcar_todas_lidas():
    current_user.notificacoes.filter_by(lida=False).update({"lida": True})
    db.session.commit()
    return redirect(url_for("notificacoes.index"))


@notificacoes_bp.route("/contagem")
@login_required
def contagem():
    """Retorna o número de notificações não lidas (JSON, para polling futuro)."""
    total = current_user.notificacoes.filter_by(lida=False).count()
    return jsonify({"nao_lidas": total})
