"""
main.py — API HTTP do TranslaAcolhe (FastAPI).

Endpoints:
    GET  /api/health                       → status do serviço
    GET  /api/languages                    → idiomas de destino disponíveis
    POST /api/translate                    → cria job (multipart: file + language [+ model])
    GET  /api/jobs/{job_id}                → status/progresso/resultado (polling)
    GET  /api/jobs/{job_id}/download       → ?format=txt|docx

Execução (dentro de backend/):
    uvicorn main:app --reload --port 8000

A chave da API vem da variável de ambiente ANTHROPIC_API_KEY (nunca do
frontend — o navegador jamais vê a chave).
"""

from __future__ import annotations

import io
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import jobs
from config import ACCEPTED_EXTENSIONS, DEFAULT_MODEL, TARGET_LANGUAGES
from exporters import to_docx_bytes, to_txt_bytes

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

app = FastAPI(title="TranslaAcolhe API", version="2.0.0")

# CORS: em desenvolvimento o Vite roda em :5173 e faz proxy de /api,
# mas liberamos as origens locais para permitir também acesso direto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",  # vite preview
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": DEFAULT_MODEL,
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.get("/api/languages")
def languages() -> list[dict]:
    """Idiomas para o seletor de 'carimbos' do frontend."""
    return [
        {"label": label, "description": description}
        for label, description in TARGET_LANGUAGES.items()
    ]


@app.post("/api/translate")
async def translate(
    file: UploadFile = File(...),
    language: str = Form(...),
    model: str = Form(DEFAULT_MODEL),
) -> dict:
    # --- Validações de entrada ---
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Servidor sem chave da API. Defina a variável de ambiente ANTHROPIC_API_KEY.",
        )
    if language not in TARGET_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"Idioma inválido: {language}")

    filename = file.filename or "documento"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Formato '.{ext}' não suportado. Envie: {', '.join(ACCEPTED_EXTENSIONS)}.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo maior que 25 MB.")
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Arquivo vazio.")

    # --- Cria o job em background ---
    job = jobs.create_job(
        filename=filename,
        language=language,
        model=(model or DEFAULT_MODEL).strip(),
        api_key=api_key,
        file_bytes=file_bytes,
    )
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")
    return job.to_public_dict()


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, format: str = "txt") -> StreamingResponse:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado ou expirado.")
    if job.status != "done":
        raise HTTPException(status_code=409, detail="A tradução ainda não terminou.")

    if format == "docx":
        data = to_docx_bytes(job.full_markdown)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        name = "translaacolhe_traducao.docx"
    elif format == "txt":
        data = to_txt_bytes(job.full_markdown)
        media = "text/plain; charset=utf-8"
        name = "translaacolhe_traducao.txt"
    else:
        raise HTTPException(status_code=422, detail="Formato deve ser 'txt' ou 'docx'.")

    return StreamingResponse(
        io.BytesIO(data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
