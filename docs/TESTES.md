# Checklist de Testes — Ponto 24 Académico

> Última atualização: 2026-05-13

---

## 1. Autenticação

- [x] **Registo** — criar conta nova com todos os campos
- [x] **Registo duplicado** — tentar registar com email já existente (deve mostrar erro)
- [x] **Registo campos em falta** — submeter formulário incompleto
- [ ] **Senha curta** — senha com menos de 6 caracteres
- [ ] **Senhas não coincidem** — confirmação diferente
- [ ] **Email de boas-vindas** — verificar que chega à caixa de entrada
- [ ] **Email de confirmação** — verificar que chega e que o link funciona
- [ ] **Login correto** — entrar com credenciais válidas
- [ ] **Login errado** — email/senha incorretos (mensagem genérica, não revela qual errou)
- [ ] **Login conta suspensa** — utilizador com `is_active=False`
- [ ] **Lembrar-me** — sessão persiste após fechar browser
- [ ] **Logout** — termina sessão e redireciona para login

---

## 2. Confirmação de Email

- [ ] **Banner visível** — banner amarelo aparece para conta não confirmada
- [ ] **Contagem regressiva** — dias restantes corretos no banner
- [ ] **Reenviar email (banner)** — botão do banner reenvia email com sucesso
- [ ] **Reenviar email (página bloqueio)** — botão na página `/email-nao-confirmado`
- [ ] **Link de confirmação válido** — confirmar email via link → acesso desbloqueado
- [ ] **Link expirado** — link com mais de 24h → mensagem de erro
- [ ] **Link inválido** — token adulterado → mensagem de erro
- [ ] **Bloqueio após 7 dias** — conta sem confirmar há +7 dias é redirecionada para a página de bloqueio
- [ ] **Endpoints permitidos sem confirmar** — `sair`, `reenviar`, `confirmar` funcionam mesmo bloqueado
- [ ] **Após confirmar, banner desaparece** — sem banner em conta confirmada

---

## 3. Recuperação de Senha

- [ ] **Formulário recuperar** — submeter com email registado → flash genérico (não revela se existe)
- [ ] **Formulário recuperar** — submeter com email inexistente → mesmo flash genérico
- [ ] **Email de recuperação** — chega com link funcional
- [ ] **Link de redefinição válido** — redireciona para formulário de nova senha
- [ ] **Link expirado (+1h)** — erro e redireciona para recuperar
- [ ] **Nova senha curta** — validação de menos de 6 caracteres
- [ ] **Senhas não coincidem** — validação
- [ ] **Senha redefinida** — login com nova senha funciona

---

## 4. Materiais — Explorar

- [ ] **Listagem** — página `/materiais` carrega com paginação
- [ ] **Pesquisa** — buscar por termo, resultados corretos
- [ ] **Filtros** — filtrar por categoria, instituição, curso, ano letivo
- [ ] **Sem resultados** — pesquisa sem hits mostra mensagem adequada
- [ ] **Detalhe do material** — clicar num material abre página de detalhe
- [ ] **Preview PDF** — botão preview abre visualizador inline
- [ ] **Download** — descarregar ficheiro (deduz créditos se necessário)
- [ ] **Download sem créditos** — utilizador sem créditos suficientes vê mensagem de erro
- [ ] **Avaliação (estrelas)** — votar numa estrela, reavaliar
- [ ] **Guardar material (AJAX)** — botão guardar/remover funciona sem reload
- [ ] **Sugestões** — endpoint `/materiais/sugestoes` responde

---

## 5. Materiais — Submissão

- [ ] **Formulário submeter** — acesso requer login
- [ ] **Upload válido** — submeter PDF/DOC com todos os campos
- [ ] **Ficheiro duplicado** — submeter o mesmo ficheiro → aviso de duplicado com link para o original
- [ ] **Ficheiro inválido** — extensão não permitida → erro
- [ ] **Pasta organizada** — ficheiro guardado em `uploads/materiais/{cat}/{ano}/{mes}/`
- [ ] **Material fica pendente** — não aparece na listagem pública antes de aprovação
- [ ] **Créditos atribuídos após aprovação** — verificar saldo

---

## 6. Perfil

- [ ] **Ver perfil** — `/perfil` mostra dados do utilizador e materiais submetidos
- [ ] **Editar perfil** — alterar nome/instituição/curso e guardar
- [ ] **Ver perfil de outro utilizador** — `/utilizador/<id>` público
- [ ] **Materiais guardados** — aparecem no perfil

---

## 7. Notificações

- [ ] **Ícone de sino** — mostra badge com nº de não lidas
- [ ] **Listar notificações** — `/notificacoes` mostra histórico
- [ ] **Marcar como lida** — clicar numa notificação marca como lida
- [ ] **Marcar todas como lidas** — botão "ler todas"
- [ ] **Contagem AJAX** — `/notificacoes/contagem` retorna JSON

---

## 8. Painel Admin

- [ ] **Acesso negado a utilizador normal** — `/admin` retorna 403
- [ ] **Acesso moderador** — só vê a aba de Moderação
- [ ] **Acesso admin** — vê tudo (Moderação, KPI, Utilizadores, Categorias, Materiais)

### Moderação

- [ ] **Listar materiais pendentes** — `/admin/moderacao`
- [ ] **Rever material** — ver detalhes antes de decidir
- [ ] **Aprovar material** — aparece na listagem pública + créditos ao autor
- [ ] **Rejeitar material** — remove da fila, notifica autor
- [ ] **Detecção de similaridade** — painel sugere materiais semelhantes ao moderar

### Utilizadores (admin only)

- [ ] **Listar utilizadores** — `/admin/utilizadores`
- [ ] **Suspender/ativar conta** — toggle `is_active`
- [ ] **Promover a admin** — toggle `is_admin`
- [ ] **Promover a moderador** — toggle `is_moderador` (desativado se já admin)
- [ ] **Ajustar créditos** — adicionar/remover créditos manualmente

### Categorias (admin only)

- [ ] **Criar categoria** — nome + slug + ícone
- [ ] **Categoria duplicada** — slug repetido mostra erro

### KPI (admin only)

- [ ] **Página KPI** — `/admin/kpi` carrega com dados
- [ ] **Top pesquisas** — termos mais procurados com barras de progresso
- [ ] **Pesquisas sem resultado** — lista do que falta na plataforma
- [ ] **Top downloads** — materiais mais descarregados
- [ ] **Por categoria** — distribuição de uploads
- [ ] **Novos utilizadores/materiais (7d)** — contadores corretos

---

## 9. Páginas de Erro

- [ ] **404** — URL inexistente mostra página de erro personalizada
- [ ] **403** — acesso proibido mostra página personalizada
- [ ] **500** — erro interno mostra página personalizada

---

## 10. Segurança

- [ ] **CSRF formulários** — remover token de um formulário e submeter → erro 400
- [ ] **CSRF AJAX** — remover header `X-CSRFToken` do fetch → erro 400
- [ ] **Open redirect** — `?next=https://evil.com` não redireciona para externo
- [ ] **Rota protegida sem login** — `/dashboard`, `/submeter`, etc. redirecionam para login
- [ ] **SQL injection** — campo de pesquisa com `' OR 1=1 --` não quebra nada

### 10a. Segurança — Fase 1 (rate limiting, honeypot, headers)

- [ ] **Rate limit login** — 11+ tentativas de login em 1 minuto → 429 na 11ª (com `gunicorn -w 4` o limite real pode chegar a ~4x devido aos workers independentes)
- [ ] **Rate limit registo** — 6+ registos em 1 hora do mesmo IP → 429
- [ ] **Rate limit recuperação de senha** — 6+ pedidos em 1 hora → 429
- [ ] **Rate limit suporte** — 6+ submissões em 1 hora → 429
- [ ] **Rate limit candidatura** — 6+ submissões em 1 hora → 429
- [ ] **Rate limit lista de espera** — 11+ submissões em 1 hora → 429
- [ ] **Rate limit upload** — 21+ submissões em 1 hora → 429
- [ ] **Página de erro 429** — mensagem amigável, sem stack trace
- [ ] **Honeypot registo** — preencher campo `website` via devtools e submeter → não cria conta, sem erro visível ao "bot"
- [ ] **Honeypot suporte/candidatura/lista de espera** — mesmo teste nos outros 3 formulários
- [ ] **Cabeçalhos de segurança** — inspecionar resposta HTTP (`curl -I` ou devtools) e confirmar `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`
- [ ] **Cookie de sessão** — em produção (`FLASK_ENV=production`), confirmar flags `Secure`, `HttpOnly`, `SameSite=Lax` no cookie de sessão
- [ ] **SECRET_KEY insegura bloqueia arranque em produção** — `FLASK_ENV=production` sem `SECRET_KEY` customizada no `.env` → app falha ao arrancar com `AssertionError`
- [ ] **Política de senha unificada** — senha de 6-7 caracteres falha; 8+ sem maiúscula/número falha; 8+ com maiúscula, minúscula e número passa (testar em registo, redefinir senha e alterar senha)
- [ ] **Email inválido em candidatura** — submeter `/juntar-se` com email mal formado → erro de validação
- [ ] **Footer "Candidatar-se"** — link/botão visível no rodapé em qualquer página, navega para `/juntar-se`
- [ ] **Números dinâmicos do index** — aprovar um novo material e confirmar que os contadores da home (topo e "Explorar por categoria") sobem de acordo

---

## 11. Funcionalidades Extra

- [ ] **Provas Simuladas** — página under-construction carrega com animações
- [ ] **Como Funciona** — página carrega sem erros
- [ ] **Navbar ativa** — link da página atual fica destacado
- [ ] **Responsividade mobile** — navbar colapsa, layout adapta
- [ ] **CLI importar-lote** — `flask importar-lote <pasta> --dry-run` mostra preview sem gravar

---

## 12. Painel Admin — Fase 2

### Candidaturas (só admin)

- [ ] **Listar candidaturas** — `/admin/candidaturas` carrega com contagens corretas nas tabs
- [ ] **Filtrar por estado** — tabs Pendentes/Aprovadas/Rejeitadas filtram corretamente
- [ ] **Pesquisar** — pesquisa por nome/email/universidade devolve resultados esperados
- [ ] **Ver detalhes** — modal mostra motivação, impacto, experiência e liderança sem quebrar layout
- [ ] **Aprovar candidatura** — estado muda para "Aprovada", `updated_at` atualizado
- [ ] **Rejeitar candidatura** — estado muda para "Rejeitada", `updated_at` atualizado
- [ ] **Acesso restrito a admin** — utilizador moderador (não admin) recebe 403 em `/admin/candidaturas`
- [ ] **Tabela responsiva** — em ecrã estreito (375px), tabela faz scroll horizontal em vez de overflow da página

### Badge de moderador

- [ ] **Badge visível** — utilizador com `is_moderador=True` mostra badge "Moderador" (azul/info) em `/admin/utilizadores`
- [ ] **Admin não mostra duplo badge** — utilizador admin mostra só "Admin", nunca os dois

### Navegação admin

- [ ] **Nav presente em todas as páginas admin** — sub-nav visível em Painel, Moderação, Candidaturas, Utilizadores, Categorias, Materiais, Relatórios, Lista de Espera, Anúncios, KPI, Configurações, Logs
- [ ] **Item ativo destacado** — a página atual aparece destacada na nav
- [ ] **Nav em mobile** — nav faz scroll horizontal em ecrã estreito sem quebrar o layout
- [ ] **Itens admin-only ocultos para moderador** — utilizador moderador (não admin) não vê Candidaturas/Utilizadores/Categorias/Materiais/etc. na nav

### KPI — Fase 2

- [ ] **KPI carrega em base de dados vazia** — sem erros mesmo sem nenhum `AtividadeLog`/`Candidatura` registados
- [ ] **Stat "Candidaturas pendentes"** — contagem correta
- [ ] **"Ações por tipo (30 dias)"** — lista agrupada corresponde aos eventos reais gerados
- [ ] **"Atividade recente"** — feed mostra os últimos eventos com utilizador e data corretos

### Log de auditoria — spot-checks

- [ ] **Aprovar material gera log** — aprovar um material cria uma linha `AtividadeLog` com `evento=material_aprovado`, `utilizador_id` do moderador, `alvo_id` do material
- [ ] **Rejeitar material gera log** — idem, `evento=material_rejeitado`, `detalhes` inclui o motivo
- [ ] **Download gera log** — descarregar um material cria linha `evento=download` com `utilizador_id` correto
- [ ] **Login gera log** — login com sucesso cria linha `evento=login`; tentativa falhada cria `evento=login_falhado`
- [ ] **Submeter candidatura gera log** — `/juntar-se` bem-sucedido cria linha `evento=candidatura_recebida`
- [ ] **Toggle de permissões gera log** — promover/remover admin ou moderador cria a linha correspondente

---

## 13. Sistema de Pastas — Fase 3

### Gestão de pastas (admin/moderador)

- [ ] **Criar pasta de topo** — `/admin/pastas`, criar pasta sem parent → aparece com nivel=0
- [ ] **Criar subpasta** — criar pasta com parent_id de uma existente → aparece indentada, nivel = parent.nivel+1
- [ ] **Criar hierarquia profunda** — criar 4+ níveis (ex: Universidade > Curso > Semestre > Disciplina) e confirmar indentação/caminho corretos em cada nível
- [ ] **Eliminar pasta vazia** — pasta sem subpastas nem materiais elimina com sucesso
- [ ] **Bloquear eliminação com subpastas** — pasta com filhos mostra botão desabilitado/erro e não elimina
- [ ] **Bloquear eliminação com materiais** — pasta com `Material.pasta_id` apontando para ela mostra botão desabilitado/erro e não elimina
- [ ] **Acesso restrito** — utilizador normal (não admin/moderador) recebe 403 em `/admin/pastas`
- [ ] **Moderador tem acesso** — utilizador `is_moderador=True` (não admin) consegue criar/ver pastas

### Mover materiais para pastas

- [ ] **Mover material único (disco local)** — mover um material para uma pasta; confirmar `ficheiro_path` na BD aponta para o novo caminho e o ficheiro físico existe lá; confirmar o caminho antigo já não existe
- [ ] **Mover material único (R2)** — se houver credenciais R2 no ambiente de teste, repetir o teste acima com `R2_ENDPOINT` configurado; sem credenciais, o ramo `copy_object` fica coberto só por revisão de código
- [ ] **Mover thumbnail junto** — para um material de imagem, confirmar que `thumbs/{nome}` também foi movido e a thumbnail continua a carregar em `listar.html`
- [ ] **Mover grupo_upload completo** — mover um material de um `grupo_upload` de 3+ páginas; confirmar que TODAS as páginas ficam com o mesmo `pasta_id`, nenhuma fica para trás
- [ ] **Remover material de uma pasta** — usar a opção "Sem pasta" no modal; `pasta_id` volta a `NULL`, ficheiro físico permanece onde estava

### Navegação pública de pastas

- [ ] **Árvore raiz carrega** — `/materiais/pastas` mostra as pastas de topo sem erro, sem necessidade de login
- [ ] **Navegar para subpasta** — clicar numa pasta filha mostra os seus filhos e breadcrumb atualizado
- [ ] **Materiais de descendentes aparecem** — colocar um material numa subpasta de nível 3; confirmar que aparece na grelha ao visitar a pasta de nível 1 (ancestral), não só na pasta direta
- [ ] **Só materiais aprovados aparecem** — material pendente/rejeitado numa pasta não aparece na navegação pública
- [ ] **Breadcrumb correto** — caminho mostrado corresponde à hierarquia real

### Pastas como filtro na pesquisa existente

- [ ] **Filtro por pasta isolado** — `/materiais?pasta=<id>` devolve só materiais dessa pasta e descendentes
- [ ] **Filtro pasta + categoria combinados** — `/materiais?pasta=<id>&categoria=<id>` aplica ambos os filtros em conjunto
- [ ] **Badge de filtro ativo** — selecionar uma pasta mostra badge removível na barra de filtros ativos
- [ ] **Paginação preserva o filtro de pasta** — navegar para página 2 com `pasta` na URL mantém o filtro

### Migração e regressão

- [ ] **`flask db upgrade` limpo** — aplica sem erros numa BD nova e numa BD existente com materiais
- [ ] **Materiais antigos continuam visíveis** — materiais com `pasta_id=NULL` continuam a aparecer normalmente em `/materiais` sem filtro
- [ ] **Log de auditoria — criar pasta** — cria `AtividadeLog` com `evento=pasta_criada`
- [ ] **Log de auditoria — mover material** — cria `AtividadeLog` com `evento=material_movido_pasta`

---

**Total: 158 testes**
