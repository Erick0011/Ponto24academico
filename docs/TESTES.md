# Checklist de Testes — Ponto 24 Académico

> Última atualização: 2026-08-21

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

## 14. Email Automático de Candidaturas e Marketing em Massa

### Email automático de candidaturas

- [ ] **Aprovar candidatura envia email** — `POST /admin/candidaturas/<id>/aprovar` chama `email_candidatura_aprovada`; sem SMTP configurado, falha silenciosamente (não quebra a aprovação)
- [ ] **Rejeitar candidatura envia email** — idem para `email_candidatura_rejeitada`
- [ ] **Templates sem emojis** — `email/candidatura_aprovada.html` e `email/candidatura_rejeitada.html` não usam nenhum caráter emoji (regra do projeto)
- [ ] **Flash confirma envio** — mensagem "Email enviado" aparece após aprovar/rejeitar

### Modelo e opt-out de marketing

- [ ] **`aceita_marketing` default True** — utilizadores existentes e novos ficam `True` após a migração/registo
- [ ] **`flask db upgrade` limpo** — migração aplica sem erro numa BD existente com utilizadores (server_default evita falha em coluna NOT NULL)

### Criar e enviar campanha

- [ ] **Criar campanha** — `/admin/marketing/criar` guarda como `rascunho`, regista `AtividadeLog.EVENTO_CAMPANHA_CRIADA`
- [ ] **Pré-visualização** — `/admin/marketing/<id>` mostra o HTML da campanha dentro do template de marca, num iframe
- [ ] **Só admin acede** — utilizador moderador (não admin) recebe 403 em todas as rotas `/admin/marketing*`
- [ ] **Enviar campanha** — dispara thread em segundo plano; `CampanhaEmailDestinatario` é populado uma vez (público elegível: ativo + `aceita_marketing=True`, mais filtro extra se público = confirmados/ativos)
- [ ] **Progresso em tempo real** — `/admin/marketing/<id>/estado` reflete contagem de enviados/falhados enquanto a thread corre
- [ ] **Throttle entre envios** — respeita `MARKETING_INTERVALO_SEGUNDOS` entre cada email
- [ ] **Limite diário pausa corretamente** — atinge `MARKETING_LIMITE_DIARIO` com destinatários ainda pendentes → estado `pausada_limite_diario`
- [ ] **Conclusão no limite exato** — quando o último destinatário pendente é enviado exatamente no envio que atinge o limite diário, o estado final é `concluida`, não `pausada_limite_diario`
- [ ] **Retomar no dia seguinte** — campanha pausada, ao reiniciar noutro dia (ou reclicar "Continuar envio"), retoma dos pendentes sem duplicar envios já feitos
- [ ] **Cancelar campanha** — campanha `enviando`/`pausada` pode ser cancelada; emails já enviados não são afetados; a thread para no próximo ciclo
- [ ] **Não reenvia campanha concluída/cancelada** — `POST /admin/marketing/<id>/enviar` numa campanha já concluída ou cancelada não recomeça o envio

### Proteções anti-bloqueio no email de marketing

- [ ] **Cabeçalho `List-Unsubscribe` presente** — inclui `mailto:` e URL de cancelamento
- [ ] **Cabeçalho `List-Unsubscribe-Post: List-Unsubscribe=One-Click` presente** (RFC 8058)
- [ ] **Cabeçalhos `Precedence: bulk` e `X-Auto-Response-Suppress: All` presentes**
- [ ] **Multipart com texto simples + HTML** — mensagem inclui `text/plain` (gerado a partir do HTML) antes do `text/html`
- [ ] **Link de cancelamento usa o domínio real** — construído a partir do `request.url_root` do pedido que disparou o envio, não `localhost`

### Cancelamento de subscrição (unsubscribe)

- [ ] **Link de cancelamento funciona sem login** — `GET /marketing/cancelar/<token>` marca `aceita_marketing=False` e mostra confirmação
- [ ] **Token inválido/adulterado** — mostra mensagem de erro e não altera nenhum utilizador
- [ ] **Utilizador que cancelou não recebe mais campanhas** — fica de fora de `publico_query()` em campanhas futuras
- [ ] **Rota acessível em modo pré-lançamento** — `main.cancelar_marketing` está na whitelist de endpoints públicos

---

---

## 15. Comunidade — Fase 4

### Publicações e respostas

- [ ] **Criar publicação** — `/comunidade/novo` cria com sucesso, tipo (dúvida/discussão/aviso) gravado corretamente
- [ ] **Criar publicação com fotos** — até 6 imagens anexadas, `ComunidadePostImagem` criada para cada uma, ficheiro gravado em `comunidade/{YYYY}/{MM}/`
- [ ] **Ficheiro inválido não bloqueia o post** — anexar um ficheiro de extensão não permitida é ignorado silenciosamente, o post é criado na mesma
- [ ] **Créditos ao publicar** — autor recebe `CREDITOS_POR_POST_COMUNIDADE`
- [ ] **Responder a um post** — `respostas_count` incrementa, resposta aparece na lista, ordenação por data/votos funciona
- [ ] **Créditos ao responder** — autor da resposta recebe `CREDITOS_POR_RESPOSTA_COMUNIDADE`
- [ ] **Notificação ao autor do post** — ao receber uma resposta (exceto se o autor responder a si próprio)
- [ ] **Honeypot bloqueia bots** — campo `website` preenchido em criar post/resposta é rejeitado
- [ ] **Rate limit** — `/comunidade/novo` e `/comunidade/<id>/responder` respeitam os limites definidos

### Votação

- [ ] **Upvote soma +1** ao `votos_score` do post/resposta
- [ ] **Downvote soma -1**
- [ ] **Clicar no mesmo voto remove-o (toggle off)** — volta a 0
- [ ] **Clicar no voto oposto troca-o** — delta de 2 aplicado corretamente
- [ ] **Bloqueio de auto-voto** — autor não consegue votar no próprio post/resposta
- [ ] **Votar a partir do feed mantém o utilizador no feed** (usa `request.referrer`)
- [ ] **Ordenar por votados** — feed e respostas respeitam `votos_score` na ordenação

### Denúncias e moderação

- [ ] **Denunciar post/resposta** — cria `ComunidadeRelatorio` com o `alvo_tipo` correto
- [ ] **Bloqueia denúncia duplicada** — mesmo utilizador não denuncia o mesmo alvo duas vezes enquanto pendente
- [ ] **Fila de denúncias admin** — `/admin/comunidade/relatorios`, tabs de contagem, só admin/moderador acede (403 para utilizador normal)
- [ ] **Resolver sem eliminar** — marca `resolvido`, conteúdo permanece
- [ ] **Ignorar denúncia** — marca `ignorado`
- [ ] **Eliminar conteúdo a partir da denúncia** — apaga o post/resposta denunciado, decrementa `respostas_count` do post pai quando aplicável, marca a denúncia como resolvida
- [ ] **Denúncia de conteúdo já eliminado** — fila mostra "Conteúdo já eliminado" em vez de rebentar

### Fixar, eliminar e permissões

- [ ] **Fixar post com prazo** (admin/moderador) — escolher duração (1/3/7/30 dias ou permanente), post aparece no topo do feed enquanto `esta_fixado_ativo`
- [ ] **Fixado expira sozinho** — após o `fixado_ate` passar, o post deixa de aparecer fixado no feed (sem precisar de ação manual)
- [ ] **Autor elimina o próprio post/resposta**
- [ ] **Moderador elimina post/resposta de outro utilizador**
- [ ] **Utilizador normal não consegue eliminar conteúdo alheio** (403)
- [ ] **Eliminar post remove as imagens do disco/R2**

### Banner patrocinado (migração dos Anúncios)

- [ ] **Banner deixa de aparecer sitewide** — `/`, `/materiais`, etc. não mostram mais o banner
- [ ] **Banner aparece dentro da Comunidade** — `/comunidade/` inclui `partials/banner.html` sem alterações ao `Anuncio`/`_banner()`/rotas `/admin/anuncios*`

### Navegação e regressão

- [ ] **Nav mostra "Comunidade"** em todas as páginas, `active` no endpoint correto
- [ ] **Feed público sem login**
- [ ] **`flask db upgrade` limpo** numa BD nova e numa existente
- [ ] **Logs de auditoria** — `comunidade_post_criado`, `comunidade_resposta_criada`, `comunidade_post_eliminado`, `comunidade_resposta_eliminada`, `comunidade_relatorio_resolvido`

---

## 16. Comunidade — Avisos, Tags e Suspensão (Fase 4b)

### Avisos oficiais

- [ ] **Utilizador normal não vê "Aviso" no select** de `/comunidade/novo`
- [ ] **Utilizador normal a forçar `tipo=aviso` no POST** — servidor rebaixa para "Discussão" e mostra aviso, não deixa passar como Aviso
- [ ] **Admin/moderador consegue publicar Aviso** normalmente
- [ ] **Badge "Aviso oficial"** aparece nos posts tipo aviso (feed e detalhe), com destaque visual distinto dos outros tipos

### Tags

- [ ] **Criar post com tags** — `"cálculo, provas, exame"` gera 3 `ComunidadeTag` (slugs sem acentos), associadas ao post
- [ ] **Reaproveita tag existente** — publicar outro post com uma tag já usada não duplica `ComunidadeTag` (mesmo slug)
- [ ] **Limite de 5 tags** — tags a mais são ignoradas
- [ ] **Tags aparecem como pills** no card do feed e na página do post, com link para `/comunidade/?tag=slug`
- [ ] **Filtrar por tag** — feed mostra só posts com aquela tag, chip "a filtrar por #tag" com opção de remover
- [ ] **Filtro de tag combina com filtro de tipo** e é preservado ao paginar/ordenar

### Suspensão de utilizadores na Comunidade

- [ ] **Admin/moderador suspende utilizador** em `/admin/comunidade/utilizadores` — duração (1/3/7/30 dias) ou permanente, com motivo opcional
- [ ] **Não é possível suspender admin/moderador** (bloqueado no servidor)
- [ ] **Utilizador suspenso não consegue criar post** — redirecionado ao feed com mensagem de erro
- [ ] **Utilizador suspenso não consegue responder** — redirecionado ao post com mensagem de erro
- [ ] **Suspensão temporária expira sozinha** — após `comunidade_suspenso_ate` passar, o utilizador volta a poder publicar sem ação manual
- [ ] **Reativar utilizador** — admin remove a suspensão manualmente antes do prazo
- [ ] **Lista de suspensos atuais** mostra motivo e prazo (ou "Permanente")
- [ ] **Link rápido a partir da fila de denúncias** — botão "gerir autor" preenche a pesquisa com o email do autor denunciado

---

---

## 17. Badges do Perfil (Fase 4c)

- [ ] **Badge "Contribuidor"** sobe de tier ao atingir 1/5/15/40 materiais **aprovados** enviados (materiais pendentes/rejeitados não contam)
- [ ] **Badge "Estudioso"** sobe de tier a cada 5/25/75/200 downloads feitos pelo próprio utilizador
- [ ] **Badge "Voz da Comunidade"** sobe de tier a cada 1/5/20/50 posts criados na Comunidade
- [ ] **Badge "Comentador"** sobe de tier a cada 1/10/40/100 respostas dadas na Comunidade
- [ ] **Badge "Conteúdo Popular"** reflete a soma de downloads recebidos em todos os materiais do utilizador
- [ ] **Badge "Reputação"** reflete a soma de `votos_score` de todos os posts + respostas do utilizador (pode ficar sempre bloqueado se o saldo for negativo)
- [ ] **Badges aparecem no perfil próprio** (`/perfil`) e no **perfil público** (`/utilizador/<id>`) de qualquer utilizador
- [ ] **Badge não conquistado** aparece a cinzento/opaco com "Por conquistar" e a contagem "faltam X para o próximo nível" no tooltip
- [ ] **Badge no tier máximo (Diamante)** não mostra "faltam X" (não há próximo nível)
- [ ] **Contagem "X / 6" no topo** do bloco de badges corresponde ao nº de categorias já com pelo menos o tier Bronze

---

---

## 18. Pesquisa Avançada e Recomendação (Fase 4d)

### Pesquisa de materiais

- [ ] **Pesquisa multi-palavra** — `"prova cálculo"` encontra materiais com as duas palavras nalgum campo (título/disciplina/instituição/curso/descrição), mesmo que não estejam juntas ou no mesmo campo
- [ ] **Palavra em falta não aparece** — `"prova xyzabc123"` não devolve nada (uma das palavras não corresponde a nada)
- [ ] **Título pesa mais que descrição** — resultado com a palavra no título aparece antes de um resultado com a palavra só na descrição
- [ ] **Relevância manda mesmo com "ordenar" definido** — pesquisar e escolher "Mais popular" usa a popularidade só como desempate, não sobrepõe a relevância
- [ ] **Sem pesquisa, comportamento antigo intacto** — filtros (instituição/disciplina/categoria/ano/pasta) e ordenação funcionam exatamente como antes

### Pesquisa na Comunidade (nova)

- [ ] **Caixa de pesquisa no feed** — `/comunidade/?q=termo` filtra por título+corpo, multi-palavra (mesma lógica AND-entre-palavras/OR-entre-campos)
- [ ] **Pesquisa combina com tipo e tag** — `?q=termo&tipo=duvida&tag=calculo` aplica os três filtros ao mesmo tempo
- [ ] **Chip de pesquisa ativa** — mostra `Resultados para "termo"` com opção de limpar, preservando tipo/tag
- [ ] **Estado vazio distingue pesquisa sem resultados** de "ainda não há publicações"

### Materiais relacionados

- [ ] **Aparecem na página de detalhe do material**, mesma disciplina/categoria/instituição/ano, ordenados por relevância e depois popularidade
- [ ] **Material sem nenhum critério partilhado** não aparece nos relacionados de outro (score teria de ser > 0)
- [ ] **Sem materiais relacionados, a secção não aparece** (não mostra bloco vazio)

### Publicações relacionadas

- [ ] **Aparecem na página de detalhe do post**, mesmo tipo ou tags partilhadas
- [ ] **Post sem tags** só relaciona por tipo
- [ ] **Sem publicações relacionadas, a secção não aparece**

### "Recomendado para ti" (dashboard)

- [ ] **Materiais recomendados** — utilizador com instituição/curso no perfil vê materiais dessa instituição/curso primeiro, completando com populares se faltarem
- [ ] **Utilizador sem instituição/curso** — cai direto para os materiais mais populares, sem erro
- [ ] **Nunca recomenda os próprios materiais** do utilizador
- [ ] **Publicações recomendadas** — utilizador que já postou/comentou vê publicações com tags semelhantes às dos posts em que participou
- [ ] **Utilizador sem atividade na Comunidade** — cai para os posts mais votados/recentes, sem erro
- [ ] **Nunca recomenda os próprios posts** do utilizador nem os posts em que já comentou

---

**Total: 268 testes**
