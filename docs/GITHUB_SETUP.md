# Publicação no GitHub

## Objetivo

Versionar e publicar a FlowDesk Lab API em um repositório GitHub sem expor segredos, tokens ou credenciais.

## Fluxo básico

### 1. Verificar o estado local

```bash
git status
```

### 2. Adicionar os arquivos

```bash
git add .
```

> Antes de executar `git add .`, revise a árvore do projeto e confirme que arquivos como `.env`, bancos SQLite locais, exports de workflow e artefatos temporários não serão versionados.

### 3. Criar o commit

```bash
git commit -m "feat: FlowDesk Lab API"
```

### 4. Garantir a branch principal

```bash
git branch -M main
```

### 5. Configurar o remoto

```bash
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
```

### 6. Fazer o push

```bash
git push -u origin main
```

## Quando o remoto `origin` já existe

Primeiro, confira:

```bash
git remote -v
```

### Cenário A — o remoto já está correto

Basta enviar:

```bash
git push -u origin main
```

### Cenário B — o remoto existe, mas aponta para a URL errada

Atualize a URL:

```bash
git remote set-url origin https://github.com/SEU-USUARIO/SEU-REPO.git
git push -u origin main
```

### Cenário C — você quer remover e recriar

```bash
git remote remove origin
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
git push -u origin main
```

## Quando o projeto ainda não foi inicializado com Git

Se `git status` falhar porque ainda não existe repositório local:

```bash
git init
git status
git add .
git commit -m "feat: FlowDesk Lab API"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
git push -u origin main
```

## Boas práticas

- revise o conteúdo antes do `git add .`
- evite subir banco local, caches e arquivos temporários
- confirme se `.venv/` não será publicado
- confirme se `flowdesk.db`, exports de n8n/Make/Dify e arquivos `.env` estão fora do commit
- mantenha exemplos com dados fictícios

## Segurança

**Não inclua:**

- API keys
- tokens do GitHub
- credenciais do Railway
- arquivos `.env` com segredos reais
- cookies, sessões ou dumps com dados sensíveis

## Checklist rápido

- `git status` limpo após commit
- remoto `origin` configurado corretamente
- branch `main` criada
- push concluído com sucesso
- nenhum segredo versionado
