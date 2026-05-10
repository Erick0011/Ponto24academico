# Ponto 24 Académico 🎓

Plataforma digital de organização, partilha e descoberta de materiais académicos.

## Requisitos

- Python 3.10+
- pip

---

## Instalação e arranque rápido

```bash
# 1. Clona o projeto
git clone <repo-url>
cd ponto24

# 2. Cria e ativa o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 3. Instala dependências
pip install -r requirements.txt

# 4. Configura variáveis de ambiente
cp .env.example .env
# Edita o ficheiro .env com os teus valores

# 5. Cria as tabelas na base de dados
flask --app manage.py db init
flask --app manage.py db migrate -m "tabelas iniciais"
flask --app manage.py db upgrade

# 6. Popula com dados iniciais (categorias)
flask --app manage.py seed-db

# 7. Cria um administrador
flask --app manage.py criar-admin admin@ponto24.ao senha123

# 8. Arranca o servidor
python run.py
```

Acede em: **http://localhost:5000**

---

## Estrutura do projeto

```
ponto24/
├── app/
│   ├── __init__.py          # Application factory
│   ├── models/
│   │   ├── user.py          # Modelo de utilizador
│   │   └── material.py      # Modelos de material, categoria, avaliação
│   ├── routes/
│   │   ├── auth.py          # Login, registo, logout
│   │   ├── main.py          # Home, dashboard, perfil
│   │   ├── materiais.py     # Upload, pesquisa, download, avaliação
│   │   └── admin.py         # Painel de moderação
│   ├── services/
│   │   ├── upload_service.py    # Gestão de ficheiros
│   │   └── creditos_service.py  # Sistema de créditos
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── uploads/         # Ficheiros enviados pelos utilizadores
│   └── templates/
│       ├── auth/            # Login, registo
│       ├── dashboard/       # Dashboard, perfil
│       ├── materials/       # Listar, detalhe, submeter
│       └── admin/           # Painel admin
├── config/
│   └── settings.py          # Configurações por ambiente
├── migrations/              # Migrações da base de dados
├── tests/                   # Testes (a desenvolver)
├── manage.py                # Comandos CLI
├── run.py                   # Ponto de entrada
├── requirements.txt         # Dependências
└── .env.example             # Template de variáveis de ambiente
```

---

## Sistema de créditos

| Ação                          | Créditos |
|-------------------------------|----------|
| Registo                       | +10      |
| Upload aprovado               | +5       |
| Download de material          | -1       |

---

## Funcionalidades implementadas

- [x] Registo e autenticação de utilizadores
- [x] Upload de ficheiros (PDF, imagens, DOCX)
- [x] Categorização por instituição, curso, disciplina, ano
- [x] Pesquisa e filtros
- [x] Sistema de créditos (upload → ganhar, download → gastar)
- [x] Avaliação de materiais (1-5 estrelas)
- [x] Painel de moderação para admins
- [x] Geração de thumbnails para imagens

## A desenvolver (próximas fases)

- [ ] Templates HTML com design Ponto 24
- [ ] API REST (para app mobile futura)
- [ ] Notificações por email
- [ ] Sistema de tags/etiquetas livres
- [ ] Histórico de downloads do utilizador
- [ ] Estatísticas avançadas no painel admin
