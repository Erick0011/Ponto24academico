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

---

## 11. Funcionalidades Extra

- [ ] **Provas Simuladas** — página under-construction carrega com animações
- [ ] **Como Funciona** — página carrega sem erros
- [ ] **Navbar ativa** — link da página atual fica destacado
- [ ] **Responsividade mobile** — navbar colapsa, layout adapta
- [ ] **CLI importar-lote** — `flask importar-lote <pasta> --dry-run` mostra preview sem gravar

---

**Total: 80 testes**
