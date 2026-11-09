# 🤝 TranslaAcolhe v2 — Full-stack (FastAPI + React/TypeScript)

## Abrir a aplicação no Windows

O pacote inclui a interface compilada. Abra o PowerShell na pasta extraída,
instale as dependências do servidor e inicie a aplicação:

```powershell
cd backend
python -m pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = Read-Host "Chave da API da Anthropic" -MaskInput
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000 no navegador. O FastAPI entrega a interface e a API
na mesma origem. A chave é necessária para traduzir seus documentos e fica
na sessão do PowerShell. Use o PowerShell 7 para o comando com `-MaskInput`.

## Abrir no GitHub Codespaces

No repositório, use **Code → Codespaces → Create codespace on main**.
Configure `ANTHROPIC_API_KEY` como um segredo do Codespaces com acesso a
este repositório. Ao iniciar, o Codespace instala as dependências, compila a
interface e abre o serviço na porta 8000. Reinicie o Codespace após adicionar
o segredo, se ele já estiver em execução.

Para testar, envie um documento de exemplo sem dados pessoais, selecione
um idioma e confira o resultado e os downloads em TXT e DOCX. O conteúdo
extraído do documento é enviado à API da Anthropic para gerar a tradução.

A demonstração de portfólio usa um edital fictício e uma resposta preparada
para mostrar as abas e os downloads.

Tradução, localização e simplificação de documentos oficiais e editais
brasileiros para imigrantes e refugiados.

## Arquitetura

```
translaacolhe-fullstack/
├── backend/                  # Python (FastAPI)
│   ├── main.py               # API HTTP: /api/translate, /api/jobs, /api/.../download
│   ├── jobs.py               # Jobs em background (thread) + polling de progresso
│   ├── translator.py         # Pipeline Anthropic + system_instructions oficial
│   ├── extractors.py         # PDF (pdfplumber), DOCX, TXT, XML
│   ├── chunking.py           # Fragmentação de editais longos com contexto
│   ├── knowledge_base.py     # Injeta os guias/glossários no prompt
│   ├── exporters.py          # Downloads .txt e .docx
│   ├── config.py             # Modelo, idiomas, limites
│   ├── knowledge/            # Base de conhecimento (.txt)
│   └── requirements.txt
└── frontend/                 # React 18 + TypeScript + Vite (Node)
    ├── src/App.tsx           # Fluxo: upload → carimbos de idioma → progresso → abas
    ├── src/components.tsx    # UploadZone, LanguageStamps, ProgressCard, ResultView
    ├── src/api.ts            # Cliente tipado + polling de jobs
    ├── src/styles.css        # Design system "papel & carimbo"
    └── vite.config.ts        # Proxy /api → localhost:8000
```

Fluxo: o React envia o arquivo (multipart) → o FastAPI cria um **job** em
background → o front faz **polling** (`GET /api/jobs/{id}`) exibindo o
progresso chunk a chunk → ao final, exibe Resumo / Documento / Alertas /
Glossário e oferece download em TXT/DOCX. A chave da API fica **somente no
servidor** (variável de ambiente) — o navegador nunca a vê.

## Como rodar

### 1. Backend (Python 3.10+)
```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows: set ANTHROPIC_API_KEY=...
uvicorn main:app --reload --port 8000
```

### 2. Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev        # abre em http://localhost:5173 (proxy /api → :8000)
```

### Build de produção
```bash
cd frontend && npm run build   # gera frontend/dist/
```
Sirva `dist/` por um servidor estático (Nginx, Vercel...) apontando `/api`
para o backend, ou monte a pasta no próprio FastAPI com StaticFiles.

## API

| Método | Rota                              | Descrição                              |
|--------|-----------------------------------|----------------------------------------|
| GET    | /api/health                       | Status + se a chave está configurada   |
| GET    | /api/languages                    | Idiomas de destino                     |
| POST   | /api/translate                    | multipart `file` + `language` → job_id |
| GET    | /api/jobs/{id}                    | status, progresso (0–1), resultado     |
| GET    | /api/jobs/{id}/download?format=   | `txt` ou `docx`                        |

## Modelo

Padrão: `claude-sonnet-4-6` (o ID `claude-3-5-sonnet` pertence a uma geração
aposentada da API). Configurável em `backend/config.py`.

## Aviso

Ferramenta de apoio — não substitui orientação jurídica (DPU e CRAS oferecem
ajuda gratuita).
