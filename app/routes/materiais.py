from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, send_from_directory, abort
)
from flask_login import login_required, current_user
from app import db
from app.models.material import Material, Categoria, Avaliacao
from app.services.upload_service import guardar_ficheiro
from app.services.creditos_service import dar_creditos_upload, cobrar_creditos_download

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

    # Ordenação
    if ordenar == "popular":
        query = query.order_by(Material.downloads.desc())
    elif ordenar == "avaliado":
        query = query.order_by(Material.nota_media.desc())
    else:
        query = query.order_by(Material.criado_em.desc())

    materiais = query.paginate(page=page, per_page=12, error_out=False)
    categorias = Categoria.query.all()

    return render_template(
        "materials/listar.html",
        materiais=materiais,
        categorias=categorias,
        busca=busca,
        filtros={"instituicao": instituicao, "disciplina": disciplina, "categoria_id": categoria_id},
        ordenar=ordenar,
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
    if current_user.is_authenticated:
        avaliacao_user = Avaliacao.query.filter_by(
            utilizador_id=current_user.id,
            material_id=id
        ).first()

    return render_template(
        "materials/detalhe.html",
        material=material,
        avaliacao_user=avaliacao_user,
    )


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
        ficheiro = request.files.get("ficheiro")

        # Validações
        if not all([titulo, instituicao, disciplina, ficheiro]):
            flash("Preenche os campos obrigatórios e seleciona um ficheiro.", "erro")
            return render_template("materials/submeter.html", categorias=categorias)

        if ficheiro.filename == "":
            flash("Nenhum ficheiro selecionado.", "erro")
            return render_template("materials/submeter.html", categorias=categorias)

        try:
            info = guardar_ficheiro(ficheiro, subfolder="materiais")
        except ValueError as e:
            flash(str(e), "erro")
            return render_template("materials/submeter.html", categorias=categorias)

        material = Material(
            titulo=titulo,
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
            autor_id=current_user.id,
            status=Material.STATUS_PENDENTE,
        )
        db.session.add(material)
        db.session.commit()

        flash("Material submetido com sucesso! Está a aguardar aprovação.", "sucesso")
        return redirect(url_for("materiais.detalhe", id=material.id))

    return render_template("materials/submeter.html", categorias=categorias)


@materiais_bp.route("/<int:id>/download")
@login_required
def download(id):
    """Faz download de um material (gasta créditos)."""
    material = Material.query.get_or_404(id)

    if not material.esta_aprovado:
        abort(403)

    # Não cobra créditos ao próprio autor
    if current_user.id != material.autor_id:
        sucesso = cobrar_creditos_download(current_user)
        if not sucesso:
            flash("Créditos insuficientes. Submete materiais para ganhar mais.", "erro")
            return redirect(url_for("materiais.detalhe", id=id))

    material.incrementar_downloads()
    db.session.commit()

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    pasta = "materiais"
    nome_ficheiro = material.ficheiro_path.replace(f"{pasta}/", "")

    return send_from_directory(
        directory=os.path.join(upload_folder, pasta),
        path=nome_ficheiro,
        as_attachment=True,
        download_name=material.ficheiro_nome,
    )


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
    db.session.commit()

    flash("Avaliação guardada!", "sucesso")
    return redirect(url_for("materiais.detalhe", id=id))
