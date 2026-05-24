import os
import re
import uuid
from sqlalchemy import func
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, send_from_directory, abort, jsonify
)
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria, Avaliacao, Favorito
from app.models.lista_espera import RelatorioMaterial
from app.services.upload_service import guardar_ficheiro, apagar_ficheiro, nome_download
from app.services.creditos_service import dar_creditos_upload, cobrar_creditos_download
from app.services.notificacoes_service import criar_notificacao
from app.models.notificacao import Notificacao

materiais_bp = Blueprint("materiais", __name__, url_prefix="/materiais")


@materiais_bp.route("/")
def listar():
    """Página principal de pesquisa e listagem de materiais."""
    page = request.args.get("page", 1, type=int)

    query = Material.query.filter_by(status=Material.STATUS_APROVADO)

    # Filtros opcionais
    busca = request.args.get("q", "").strip()
    instituicao = request.args.get("instituicao", "").strip()
    disciplina = request.args.get("disciplina", "").strip()
    categoria_id = request.args.get("categoria", type=int)
    ano_letivo = request.args.get("ano_letivo", "").strip()
    ordenar = request.args.get("ordenar", "recente")

    if busca:
        like = f"%{busca}%"
        query = query.filter(
            db.or_(
                Material.titulo.ilike(like),
                Material.disciplina.ilike(like),
                Material.descricao.ilike(like),
            )
        )
    if instituicao:
        query = query.filter(Material.instituicao.ilike(f"%{instituicao}%"))
    if disciplina:
        query = query.filter(Material.disciplina.ilike(f"%{disciplina}%"))
    if categoria_id:
        query = query.filter(Material.categoria_id == categoria_id)
    if ano_letivo:
        query = query.filter(Material.ano_letivo.ilike(f"%{ano_letivo}%"))

    # Deduplicar grupos: só mostrar o primeiro material de cada grupo
    lider_ids = (
        db.session.query(func.min(Material.id))
        .filter(Material.grupo_upload.isnot(None), Material.status == Material.STATUS_APROVADO)
        .group_by(Material.grupo_upload)
    )
    query = query.filter(
        db.or_(Material.grupo_upload.is_(None), Material.id.in_(lider_ids))
    )

    # Ordenação
    if ordenar == "popular":
        query = query.order_by(Material.downloads.desc())
    elif ordenar == "avaliado":
        query = query.order_by(Material.nota_media.desc())
    else:
        query = query.order_by(Material.criado_em.desc())

    materiais = query.paginate(page=page, per_page=12, error_out=False)

    # Registar pesquisa (só na primeira página, só quando há termo)
    if busca and page == 1:
        from app.models.kpi import PesquisaLog
        db.session.add(PesquisaLog(
            termo=busca[:300],
            n_resultados=materiais.total,
            utilizador_id=current_user.id if current_user.is_authenticated else None,
        ))
        db.session.commit()

    categorias = Categoria.query.all()

    # Listas dinâmicas para os dropdowns de filtro
    _aprovado = Material.STATUS_APROVADO
    instituicoes = [r[0] for r in db.session.query(Material.instituicao)
        .filter(Material.status == _aprovado, Material.instituicao.isnot(None), Material.instituicao != "")
        .distinct().order_by(Material.instituicao).all()]
    anos = [r[0] for r in db.session.query(Material.ano_letivo)
        .filter(Material.status == _aprovado, Material.ano_letivo.isnot(None), Material.ano_letivo != "")
        .distinct().order_by(Material.ano_letivo.desc()).all()]

    # Parâmetros de URL para preservar filtros na paginação e ordenação
    url_params = {k: v for k, v in request.args.items() if k != "page"}

    # Pré-carregar contagens e thumbnails de grupos visíveis na página
    grupos_ids = [m.grupo_upload for m in materiais.items if m.grupo_upload]
    grupo_counts = {}
    grupo_thumbs = {}
    if grupos_ids:
        contagens = (
            db.session.query(Material.grupo_upload, func.count(Material.id))
            .filter(Material.grupo_upload.in_(grupos_ids), Material.status == Material.STATUS_APROVADO)
            .group_by(Material.grupo_upload)
            .all()
        )
        grupo_counts = {g: c for g, c in contagens}

        membros = (
            db.session.query(Material)
            .filter(Material.grupo_upload.in_(grupos_ids), Material.status == Material.STATUS_APROVADO)
            .order_by(Material.id)
            .all()
        )
        for m in membros:
            grupo_thumbs.setdefault(m.grupo_upload, []).append(m)

    return render_template(
        "materials/listar.html",
        materiais=materiais,
        categorias=categorias,
        busca=busca,
        filtros={
            "instituicao": instituicao,
            "disciplina": disciplina,
            "categoria_id": categoria_id,
            "ano_letivo": ano_letivo,
        },
        ordenar=ordenar,
        grupo_counts=grupo_counts,
        grupo_thumbs=grupo_thumbs,
        instituicoes=instituicoes,
        anos=anos,
        url_params=url_params,
    )


@materiais_bp.route("/<int:id>")
def detalhe(id):
    """Página de detalhe de um material."""
    material = Material.query.get_or_404(id)

    if not material.esta_aprovado and (
        not current_user.is_authenticated
        or (current_user.id != material.autor_id and not current_user.is_admin)
    ):
        abort(404)

    material.incrementar_visualizacoes()
    db.session.commit()

    avaliacao_user = None
    favorito_ativo = False
    if current_user.is_authenticated:
        avaliacao_user = Avaliacao.query.filter_by(
            utilizador_id=current_user.id,
            material_id=id
        ).first()
        favorito_ativo = Favorito.query.filter_by(
            utilizador_id=current_user.id,
            material_id=id
        ).first() is not None

    grupo_materiais = []
    if material.grupo_upload:
        grupo_materiais = (
            Material.query
            .filter_by(grupo_upload=material.grupo_upload, status=Material.STATUS_APROVADO)
            .order_by(Material.id)
            .all()
        )

    return render_template(
        "materials/detalhe.html",
        material=material,
        avaliacao_user=avaliacao_user,
        grupo_materiais=grupo_materiais,
        favorito_ativo=favorito_ativo,
    )


@materiais_bp.route("/sugestoes")
def sugestoes():
    """Retorna sugestões de autocompletar para os campos do formulário de upload."""
    campo = request.args.get("campo", "")
    q = request.args.get("q", "").strip()
    instituicao = request.args.get("instituicao", "").strip()

    campos_permitidos = {"instituicao", "disciplina", "curso"}
    if campo not in campos_permitidos:
        return jsonify([])

    col = getattr(Material, campo)
    query = db.session.query(col).filter(col.isnot(None), col != "")

    if q:
        query = query.filter(col.ilike(f"%{q}%"))

    # Se pedir disciplinas/cursos filtrados por instituição
    if campo in ("disciplina", "curso") and instituicao:
        query = query.filter(Material.instituicao.ilike(f"%{instituicao}%"))

    resultados = [r[0] for r in query.distinct().order_by(col).limit(10).all()]
    return jsonify(resultados)


@materiais_bp.route("/submeter", methods=["GET", "POST"])
@login_required
def submeter():
    """Formulário de submissão de novo material."""
    categorias = Categoria.query.all()

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        instituicao = request.form.get("instituicao", "").strip()
        curso = request.form.get("curso", "").strip()
        disciplina = request.form.get("disciplina", "").strip()
        ano_letivo = request.form.get("ano_letivo", "").strip()
        ano_escolar = request.form.get("ano_escolar", "").strip()
        semestre = request.form.get("semestre", "").strip()
        categoria_id = request.form.get("categoria_id", type=int)
        ficheiros = [f for f in request.files.getlist("ficheiro") if f.filename != ""]

        # Validações
        if not all([titulo, instituicao, disciplina]) or not ficheiros:
            flash("Preenche os campos obrigatórios e seleciona pelo menos um ficheiro.", "erro")
            return render_template("materials/submeter.html", categorias=categorias)

        total = len(ficheiros)
        grupo_id = str(uuid.uuid4()) if total > 1 else None

        from datetime import datetime
        import unicodedata as _ud
        _ano = datetime.now().strftime("%Y")
        _mes = datetime.now().strftime("%m")
        if categoria_id:
            _cat = Categoria.query.get(categoria_id)
            _slug = _cat.nome.lower() if _cat else "geral"
            _slug = "".join(c for c in _ud.normalize("NFD", _slug) if _ud.category(c) != "Mn")
            _slug = re.sub(r"[^\w]", "_", _slug).strip("_") or "geral"
        else:
            _slug = "geral"
        _subfolder = f"materiais/{_slug}/{_ano}/{_mes}"

        guardados = []
        try:
            for f in ficheiros:
                guardados.append(guardar_ficheiro(f, subfolder=_subfolder))
        except ValueError as e:
            for info in guardados:
                apagar_ficheiro(info["path_relativo"])
            flash(str(e), "erro")
            return render_template("materials/submeter.html", categorias=categorias)

        # Verificar duplicados exactos por hash SHA-256
        duplicados_encontrados = []
        for info in guardados:
            existente = Material.query.filter_by(ficheiro_hash=info["hash"]).first()
            if existente:
                duplicados_encontrados.append((info, existente))

        if duplicados_encontrados:
            for info, _ in duplicados_encontrados:
                apagar_ficheiro(info["path_relativo"])
            # Se só 1 ficheiro, limpa tudo; se múltiplos, só os duplicados
            nao_duplicados = [i for i in guardados if i not in [d[0] for d in duplicados_encontrados]]
            for info in nao_duplicados:
                apagar_ficheiro(info["path_relativo"])
            dup = duplicados_encontrados[0][1]
            flash(
                f"Este ficheiro já existe na plataforma: \"{dup.titulo_base}\" "
                f"(submetido em {dup.criado_em.strftime('%d/%m/%Y')}). "
                "Se tens uma versão diferente, envia como novo material.",
                "aviso",
            )
            return render_template("materials/submeter.html", categorias=categorias)

        primeiro_id = None
        for i, info in enumerate(guardados):
            titulo_final = titulo if total == 1 else f"{titulo} — Pág. {i + 1} de {total}"
            material = Material(
                titulo=titulo_final,
                descricao=descricao,
                instituicao=instituicao,
                curso=curso,
                disciplina=disciplina,
                ano_letivo=ano_letivo,
                ano_escolar=ano_escolar,
                semestre=semestre,
                categoria_id=categoria_id,
                ficheiro_nome=info["nome_original"],
                ficheiro_path=info["path_relativo"],
                ficheiro_tipo=info["tipo"],
                ficheiro_tamanho=info["tamanho"],
                ficheiro_hash=info["hash"],
                autor_id=current_user.id,
                status=Material.STATUS_PENDENTE,
                grupo_upload=grupo_id,
            )
            db.session.add(material)
            db.session.flush()
            if primeiro_id is None:
                primeiro_id = material.id

        db.session.commit()

        if total == 1:
            flash("Material submetido com sucesso! Está a aguardar aprovação.", "sucesso")
        else:
            flash(f"{total} fotografias submetidas com sucesso! Estão a aguardar aprovação.", "sucesso")
        return redirect(url_for("materiais.detalhe", id=primeiro_id))

    return render_template("materials/submeter.html", categorias=categorias)


@materiais_bp.route("/<int:id>/preview")
@login_required
def preview(id):
    """Serve o ficheiro inline para previsualização (sem cobrar créditos)."""
    material = Material.query.get_or_404(id)
    e_autor = current_user.is_authenticated and current_user.id == material.autor_id
    pode_moderar = current_user.is_admin or getattr(current_user, "is_moderador", False)
    if not material.esta_aprovado and not e_autor and not pode_moderar:
        abort(403)

    if os.environ.get("R2_ENDPOINT"):
        from app.services.r2_service import presigned_url
        return redirect(presigned_url(material.ficheiro_path, expires=3600))

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(
        directory=upload_folder,
        path=material.ficheiro_path.replace("\\", "/"),
        as_attachment=False,
    )


@materiais_bp.route("/<int:id>/download")
@login_required
def download(id):
    """Faz download de um material (gasta créditos)."""
    material = Material.query.get_or_404(id)

    e_autor = current_user.id == material.autor_id
    pode_moderar = current_user.is_admin or getattr(current_user, "is_moderador", False)
    if not material.esta_aprovado and not e_autor and not pode_moderar:
        abort(403)

    # Não cobra créditos ao próprio autor
    if not e_autor:
        sucesso = cobrar_creditos_download(current_user)
        if not sucesso:
            flash("Créditos insuficientes. Submete materiais para ganhar mais.", "erro")
            return redirect(url_for("materiais.detalhe", id=id))

    material.incrementar_downloads()
    db.session.commit()

    if os.environ.get("R2_ENDPOINT"):
        from app.services.r2_service import presigned_url
        dn = nome_download(material.titulo_base, material.ficheiro_tipo)
        return redirect(presigned_url(material.ficheiro_path, expires=300, download_name=dn))

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(
        directory=upload_folder,
        path=material.ficheiro_path.replace("\\", "/"),
        as_attachment=True,
        download_name=nome_download(material.titulo_base, material.ficheiro_tipo),
    )


@materiais_bp.route("/<int:id>/guardar", methods=["POST"])
@login_required
def guardar(id):
    """Adiciona ou remove um material dos favoritos do utilizador."""
    material = Material.query.get_or_404(id)
    fav = Favorito.query.filter_by(utilizador_id=current_user.id, material_id=id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        return jsonify({"guardado": False})
    else:
        db.session.add(Favorito(utilizador_id=current_user.id, material_id=material.id))
        db.session.commit()
        return jsonify({"guardado": True})


@materiais_bp.route("/<int:id>/avaliar", methods=["POST"])
@login_required
def avaliar(id):
    """Avalia um material (1-5 estrelas)."""
    material = Material.query.get_or_404(id)

    if not material.esta_aprovado:
        abort(403)

    if current_user.id == material.autor_id:
        flash("Não podes avaliar o teu próprio material.", "aviso")
        return redirect(url_for("materiais.detalhe", id=id))

    nota = request.form.get("nota", type=int)
    comentario = request.form.get("comentario", "").strip()

    if nota not in range(1, 6):
        flash("Avaliação inválida.", "erro")
        return redirect(url_for("materiais.detalhe", id=id))

    avaliacao = Avaliacao.query.filter_by(
        utilizador_id=current_user.id, material_id=id
    ).first()

    if avaliacao:
        avaliacao.nota = nota
        avaliacao.comentario = comentario
    else:
        avaliacao = Avaliacao(
            nota=nota,
            comentario=comentario,
            utilizador_id=current_user.id,
            material_id=id,
        )
        db.session.add(avaliacao)

    material.recalcular_nota()

    # Notifica o autor (só se não for ele próprio a avaliar)
    if material.autor_id != current_user.id:
        criar_notificacao(
            utilizador_id=material.autor_id,
            tipo=Notificacao.TIPO_SISTEMA,
            titulo="Nova avaliação no teu material",
            mensagem=f"{current_user.nome.split()[0]} avaliou \"{material.titulo_base}\" — {nota} de 5.",
            url=url_for("materiais.detalhe", id=material.id),
        )

    db.session.commit()

    flash("Avaliação guardada!", "sucesso")
    return redirect(url_for("materiais.detalhe", id=id))


@materiais_bp.route("/<int:id>/reportar", methods=["POST"])
@login_required
def reportar(id):
    """Reporta um material como inadequado."""
    material = Material.query.get_or_404(id)

    motivo    = request.form.get("motivo", "").strip()
    descricao = request.form.get("descricao", "").strip()

    if not motivo:
        flash("Seleciona o motivo do reporte.", "erro")
        return redirect(url_for("materiais.detalhe", id=id))

    # Impede reportes duplicados do mesmo utilizador
    ja_reportou = RelatorioMaterial.query.filter_by(
        material_id=id, autor_id=current_user.id, status=RelatorioMaterial.STATUS_PENDENTE
    ).first()
    if ja_reportou:
        flash("Já reportaste este material. Estamos a analisá-lo.", "aviso")
        return redirect(url_for("materiais.detalhe", id=id))

    db.session.add(RelatorioMaterial(
        material_id=id,
        autor_id=current_user.id,
        motivo=motivo,
        descricao=descricao,
    ))
    db.session.commit()

    flash("Reporte enviado. A equipa de moderação irá analisar em breve.", "sucesso")
    return redirect(url_for("materiais.detalhe", id=id))
