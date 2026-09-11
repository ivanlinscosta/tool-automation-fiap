# Deploy no Railway: FIAP Student Desk Lab

## Objetivo
Publicar a FIAP Student Desk Lab API em um ambiente público para integração com ferramentas de workflow.

## Passo a Passo

1. **Conectar GitHub:** No Railway, selecione o repositório do projeto.
2. **Configurar Root:** Certifique-se de que o Railway aponte para a pasta `api/` onde está o `Dockerfile`.
3. **Variáveis de Ambiente:**
   - `PORT`: 8000 (ou a porta detectada pelo Railway).
   - `ENVIRONMENT`: production.
4. **Domínio:** Gere um domínio público nas configurações do serviço (ex: `fiap-student-desk.up.railway.app`).

## Verificação
Após o deploy, teste os seguintes links:
- `https://seu-app.railway.app/health`
- `https://seu-app.railway.app/docs`

## Dicas
- O Railway detectará automaticamente o `Dockerfile` e fará o build da imagem.
- Se o build falhar, verifique os logs para identificar dependências ausentes no `requirements.txt`.
