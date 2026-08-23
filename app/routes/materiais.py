import os
import re
import uuid
from sqlalchemy import func
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, send_from_directory, abort, jsonify
)
from flask_login import login_required, current_user
from app import db, limiter
from app.models.material import Material, Categoria, Avaliacao, Favorito
from app.models.lista_espera import RelatorioMaterial
from app.models.pasta import Pasta
from app.services.upload_service import guardar_ficheiro, apagar_ficheiro, nome_download
from app.services.creditos_service import cobrar_creditos_download
from app.services.notificacoes_service import criar_notificacao
from app.models.notificacao import Notificacao
from app.models.atividade import AtividadeLog
from app.services.atividade_service import registar_atividade
from app.services.pesquisa_service import condicoes_e_pontuacao
from app.services.recomendacao_service import materiais_relacionados

materiais_bp = Blueprint("materiais", __name__, url_prefix="/materiais")


def _truncar(texto, limite=157):
    """Corta texto no limite de caracteres sem partir palavras (para meta description)."""
    texto = " ".join((texto or "").split())
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",.;") + "…"


def _meta_descricao_material(material):
    """Gera uma meta description única (120-160 caracteres) a partir dos dados do material."""
    partes = [material.categoria.nome if material.categoria else "Material académico", material.disciplina]
    if material.instituicao:
        partes.append(material.instituicao)
    base = " — ".join(p for p in partes if p)
    resumo = (material.descricao or "").strip()
    texto = f"{base}. {resumo}" if resumo else f"{base}. Descarrega grátis no Ponto 24 Académico."
    return _truncar(texto)


def _grupo_metadados(materiais_items):
    """Pré-carrega contagens e thumbnails de grupos (grupo_upload) para uma lista
    de materiais — reutilizado por listar() e pela navegação por pastas."""
    grupos_ids = [m.grupo_upload for m in materiais_items if m.grupo_upload]
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
    return grupo_counts, grupo_thumbs


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
    pasta_id = request.args.get("pasta", type=int)
    ordenar = request.args.get("ordenar", "recente")

    relevancia = None
    if busca:
        condicao, relevancia = condicoes_e_pontuacao(busca, [
            (Material.titulo, 5), (Material.disciplina, 3),
            (Material.instituicao, 2), (Material.curso, 2), (Material.descricao, 1),
        ])
        if condicao is not None:
            query = query.filter(condicao)
    if instituicao:
        query = query.filter(Material.instituicao.ilike(f"%{instituicao}%"))
    if disciplina:
        query = query.filter(Material.disciplina.ilike(f"%{disciplina}%"))
    if categoria_id:
        query = query.filter(Material.categoria_id == categoria_id)
    if ano_letivo:
        query = query.filter(Material.ano_letivo.ilike(f"%{ano_letivo}%"))
    pasta_sel = Pasta.query.get(pasta_id) if pasta_id else None
    if pasta_sel:
        query = query.filter(Material.pasta_id.in_(pasta_sel.ids_subquery()))

    # Deduplicar grupos: só mostrar o primeiro material de cada grupo
    lider_ids = (
        db.session.query(func.min(Material.id))
        .filter(Material.grupo_upload.isnot(None), Material.status == Material.STATUS_APROVADO)
        .group_by(Material.grupo_upload)
    )
    query = query.filter(
        db.or_(Material.grupo_upload.is_(None), Material.id.in_(lider_ids))
    )

    # Ordenação — havendo pesquisa, a relevância manda primeiro e o critério
    # escolhido (recente/popular/avaliado/visitado) serve de desempate.
    colunas_ordenar = {
        "popular":  [Material.downloads.desc()],
        "avaliado": [Material.nota_media.desc(), Material.downloads.desc()],
        "visitado": [Material.visualizacoes.desc()],
    }.get(ordenar, [Material.criado_em.desc()])
    if relevancia is not None:
        query = query.order_by(relevancia.desc(), *colunas_ordenar)
    else:
        query = query.order_by(*colunas_ordenar)

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
    grupo_counts, grupo_thumbs = _grupo_metadados(materiais.items)

    from app.models.user import User
    total_materiais_real = Material.query.filter_by(status=Material.STATUS_APROVADO).count()
    total_instituicoes = db.session.query(Material.instituicao).filter(
        Material.status == Material.STATUS_APROVADO,
        Material.instituicao.isnot(None), Material.instituicao != ""
    ).distinct().count()
    total_disciplinas_real = db.session.query(Material.disciplina).filter(
        Material.status == Material.STATUS_APROVADO,
        Material.disciplina.isnot(None), Material.disciplina != ""
    ).distinct().count()
    total_estudantes = User.query.filter_by(is_active=True).count() + 500

    # Meta description dinâmica: reflete os filtros ativos para não repetir a
    # mesma description em cada combinação de pesquisa indexada.
    if busca:
        meta_descricao = _truncar(f'Resultados para "{busca}" — {materiais.total} materiais encontrados no Ponto 24 Académico.')
    elif disciplina or instituicao:
        alvo = " — ".join(p for p in (disciplina, instituicao) if p)
        meta_descricao = _truncar(f"Materiais de {alvo} disponíveis para download no Ponto 24 Académico.")
    else:
        meta_descricao = _truncar(
            f"Explora {total_materiais_real} materiais académicos aprovados: provas, resumos, exercícios e "
            f"apontamentos de {total_instituicoes} instituições angolanas."
        )

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
            "pasta_id": pasta_id,
        },
        meta_descricao=meta_descricao,
        ordenar=ordenar,
        grupo_counts=grupo_counts,
        grupo_thumbs=grupo_thumbs,
        instituicoes=instituicoes,
        anos=anos,
        url_params=url_params,
        total_materiais_real=total_materiais_real,
        total_instituicoes=total_instituicoes,
        total_disciplinas_real=total_disciplinas_real,
        total_estudantes=total_estudantes,
        pastas_raiz_lista=Pasta.query.filter_by(parent_id=None).order_by(Pasta.nome).all(),
        pasta_selecionada=pasta_sel,
    )


@materiais_bp.route("/pastas")
def pastas_raiz():
    return _render_pasta(None)


@materiais_bp.route("/pastas/<int:id>")
def pastas_ver(id):
    return _render_pasta(Pasta.query.get_or_404(id))


@materiais_bp.route("/pastas/sem-pasta")
def pastas_sem_pasta():
    """Materiais aprovados sem pasta atribuída — sobretudo os que já existiam
    antes das pastas serem criadas (pasta_id é opcional, nunca foi obrigatório,
    por isso nada parte para eles: continuam a aparecer em /materiais/ e nas
    pesquisas normalmente, só não apareciam na navegação por pastas até agora)."""
    return _render_pasta(None, sem_pasta=True)


def _contagem_pasta(pasta):
    """Nº de materiais aprovados na pasta e em toda a sua subárvore."""
    return Material.query.filter(
        Material.status == Material.STATUS_APROVADO,
        Material.pasta_id.in_(pasta.ids_subquery()),
    ).count()


def _proxima_pasta_com_conteudo(pasta):
    """Quando a pasta atual está vazia, sugere a próxima pasta-irmã (na mesma
    ordem alfabética usada na navegação) que já tenha algum material aprovado
    — para quem cai numa pasta vazia não ficar sem saber para onde ir."""
    irmas = Pasta.query.filter_by(parent_id=pasta.parent_id).order_by(Pasta.nome).all()
    idx = next((i for i, p in enumerate(irmas) if p.id == pasta.id), None)
    if idx is None:
        return None
    ordem = irmas[idx + 1:] + irmas[:idx]  # depois da atual, depois as anteriores
    for candidata in ordem:
        if _contagem_pasta(candidata) > 0:
            return candidata
    return None


def _render_pasta(pasta, sem_pasta=False):
    """Navegação pública (leitura) da árvore de pastas — reaproveita o mesmo
    dedup de grupo_upload e metadados de grupo usados em listar()."""
    page = request.args.get("page", 1, type=int)

    breadcrumb = []
    sem_pasta_count = 0
    sugestao_pasta = None
    filhos_contagem = {}
    if sem_pasta:
        filhos = []
        query = (
            Material.query
            .filter(Material.status == Material.STATUS_APROVADO, Material.pasta_id.is_(None))
            .order_by(Material.criado_em.desc())
        )
        materiais = query.paginate(page=page, per_page=12, error_out=False)
        grupo_counts, grupo_thumbs = _grupo_metadados(materiais.items)
    elif pasta is None:
        filhos = Pasta.query.filter_by(parent_id=None).order_by(Pasta.nome).all()
        materiais = None
        grupo_counts, grupo_thumbs = {}, {}
        # Para não "perder" materiais antigos/sem pasta na navegação — continuam
        # 100% acessíveis em /materiais/, isto é só para não ficarem esquecidos
        # de quem navega exclusivamente por pastas.
        sem_pasta_count = Material.query.filter(
            Material.status == Material.STATUS_APROVADO, Material.pasta_id.is_(None)
        ).count()
    else:
        no = pasta
        while no is not None:
            breadcrumb.append(no)
            no = no.parent
        breadcrumb.reverse()
        filhos = pasta.filhos.order_by(Pasta.nome).all()
        ids_subquery = pasta.ids_subquery()

        lider_ids = (
            db.session.query(func.min(Material.id))
            .filter(Material.grupo_upload.isnot(None), Material.status == Material.STATUS_APROVADO,
                    Material.pasta_id.in_(ids_subquery))
            .group_by(Material.grupo_upload)
        )
        query = (
            Material.query
            .filter(Material.status == Material.STATUS_APROVADO)
            .filter(Material.pasta_id.in_(ids_subquery))
            .filter(db.or_(Material.grupo_upload.is_(None), Material.id.in_(lider_ids)))
            .order_by(Material.criado_em.desc())
        )
        materiais = query.paginate(page=page, per_page=12, error_out=False)
        grupo_counts, grupo_thumbs = _grupo_metadados(materiais.items)

        if not filhos and not materiais.items:
            sugestao_pasta = _proxima_pasta_com_conteudo(pasta)

    for f in filhos:
        filhos_contagem[f.id] = _contagem_pasta(f)

    if sem_pasta:
        meta_descricao = _truncar("Materiais aprovados que ainda não foram organizados em nenhuma pasta.")
    elif pasta is not None:
        meta_descricao = _truncar(f"Materiais em {pasta.caminho_display} — explora e descarrega no Ponto 24 Académico.")
    else:
        meta_descricao = _truncar("Navega os materiais académicos do Ponto 24 Académico organizados por pastas: universidade, curso, disciplina e ano.")

    pode_moderar = current_user.is_authenticated and (
        current_user.is_admin or getattr(current_user, "is_moderador", False)
    )

    return render_template(
        "materials/pastas.html",
        pasta_atual=pasta, filhos=filhos, filhos_contagem=filhos_contagem,
        materiais=materiais, breadcrumb=breadcrumb,
        grupo_counts=grupo_counts, grupo_thumbs=grupo_thumbs, meta_descricao=meta_descricao,
        sem_pasta=sem_pasta, sem_pasta_count=sem_pasta_count,
        sugestao_pasta=sugestao_pasta, pode_moderar=pode_moderar,
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
        meta_descricao=_meta_descricao_material(material),
        relacionados=materiais_relacionados(material),
        # _card.html (reaproveitado nos "Materiais relacionados") espera estas
        # duas variáveis para agrupar uploads múltiplos — aqui não há grupos.
        grupo_counts={}, grupo_thumbs={},
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
@limiter.limit("20 per hour", methods=["POST"])
def submeter():
    """Formulário de submissão de novo material."""
    categorias = Categoria.query.all()

    # Upload direto para uma pasta — só admin/moderador (link "Enviar material
    # para esta pasta" em materials/pastas.html). Reaplicado em cada re-render
    # do formulário (erro de validação, duplicado, etc.) para não se perder.
    pode_moderar = current_user.is_admin or getattr(current_user, "is_moderador", False)
    pasta_id_bruto = (
        request.form.get("pasta_id", type=int) if request.method == "POST"
        else request.args.get("pasta_id", type=int)
    )
    pasta_destino = Pasta.query.get(pasta_id_bruto) if pode_moderar and pasta_id_bruto else None

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
            return render_template("materials/submeter.html", categorias=categorias, pasta_destino=pasta_destino)

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
            return render_template("materials/submeter.html", categorias=categorias, pasta_destino=pasta_destino)

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
            return render_template("materials/submeter.html", categorias=categorias, pasta_destino=pasta_destino)

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
                pasta_id=pasta_destino.id if pasta_destino else None,
            )
            db.session.add(material)
            db.session.flush()
            registar_atividade(
                AtividadeLog.EVENTO_MATERIAL_SUBMETIDO,
                utilizador_id=current_user.id, alvo_tipo="material", alvo_id=material.id,
                detalhes={"titulo": titulo_final, "disciplina": disciplina},
            )
            if primeiro_id is None:
                primeiro_id = material.id

        db.session.commit()

        # Notifica moderadores do novo material pendente
        from app.services.notificacoes_service import notificar_moderadores_novo_material
        primeiro_material = Material.query.get(primeiro_id)
        if primeiro_material:
            try:
                notificar_moderadores_novo_material(primeiro_material)
                db.session.commit()
            except Exception:
                current_app.logger.exception(
                    "Falha ao notificar moderadores do material #%s", primeiro_material.id
                )

        sufixo_pasta = f" Vai para a pasta \"{pasta_destino.nome}\" assim que for aprovado." if pasta_destino else ""
        if total == 1:
            flash(f"Material submetido com sucesso! Está a aguardar aprovação.{sufixo_pasta}", "sucesso")
        else:
            flash(f"{total} fotografias submetidas com sucesso! Estão a aguardar aprovação.{sufixo_pasta}", "sucesso")
        return redirect(url_for("materiais.detalhe", id=primeiro_id))

    return render_template("materials/submeter.html", categorias=categorias, pasta_destino=pasta_destino)


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
    registar_atividade(
        AtividadeLog.EVENTO_DOWNLOAD,
        utilizador_id=current_user.id, alvo_tipo="material", alvo_id=material.id,
        detalhes={"creditos_cobrados": not e_autor},
    )
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
