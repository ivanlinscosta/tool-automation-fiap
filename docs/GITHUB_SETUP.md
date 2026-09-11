# Publicação no GitHub: FIAP Student Desk Lab

## Objetivo
Versionar e publicar a FIAP Student Desk Lab API em um repositório GitHub.

## Fluxo Básico

1. **Inicializar Git:**
   ```bash
   git init
   ```

2. **Adicionar Arquivos:**
   ```bash
   git add .
   ```

3. **Commit:**
   ```bash
   git commit -m "feat: inicializando FIAP Student Desk Lab API"
   ```

4. **Configurar Remoto:**
   ```bash
   git remote add origin https://github.com/SEU-USUARIO/fiap-student-desk-lab.git
   ```

5. **Push:**
   ```bash
   git push -u origin main
   ```

## Boas Práticas
- **Não suba o banco de dados:** O arquivo `*.db` deve estar no `.gitignore`.
- **Não suba o ambiente virtual:** A pasta `.venv/` deve estar no `.gitignore`.
- **Segredos:** Nunca versione arquivos `.env` com chaves reais da OpenAI ou outras APIs.

## Checklist
- [ ] `git status` limpo.
- [ ] `.gitignore` configurado corretamente.
- [ ] README.md atualizado com o nome do projeto.
