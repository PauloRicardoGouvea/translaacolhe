"""
jobs.py — Gerenciador de trabalhos de tradução em background.

Cada upload vira um "job" processado em thread própria, permitindo que o
frontend React acompanhe o progresso por polling (GET /api/jobs/{id})
enquanto documentos longos são traduzidos chunk a chunk.

Armazenamento em memória (dict + lock): suficiente para uma instância
única. Para produção multi-instância, trocar por Redis/fila — a interface
pública (create_job / get_job) foi desenhada para isolar essa troca.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from chunking import chunk_document
from extractors import ExtractionError, extract_text
from translator import TranslationResult, run_pipeline

# Jobs concluídos expiram após este tempo (limpeza preguiçosa).
_JOB_TTL = timedelta(hours=2)


@dataclass
class Job:
    id: str
    filename: str
    language: str
    model: str
    status: str = "queued"          # queued | extracting | translating | done | error
    progress: float = 0.0           # 0.0 → 1.0
    message: str = "Na fila"
    error: Optional[str] = None
    result: Optional[TranslationResult] = None
    full_markdown: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_public_dict(self) -> dict:
        """Representação JSON enviada ao frontend."""
        payload = {
            "id": self.id,
            "filename": self.filename,
            "language": self.language,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "error": self.error,
        }
        if self.status == "done" and self.result:
            payload["result"] = {
                "summary": self.result.executive_summary,
                "document": self.result.translated_document,
                "alerts": self.result.alerts_md,
                "glossary": self.result.glossary_md,
            }
        return payload


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def _cleanup_expired() -> None:
    """Remove jobs antigos (chamado a cada criação de job)."""
    now = datetime.now(timezone.utc)
    with _lock:
        expired = [jid for jid, j in _jobs.items() if now - j.created_at > _JOB_TTL]
        for jid in expired:
            del _jobs[jid]


def _worker(job: Job, api_key: str, file_bytes: bytes) -> None:
    """Executa extração → chunking → tradução, atualizando o job."""
    try:
        job.status = "extracting"
        job.message = "Lendo o documento"
        raw_text = extract_text(job.filename, file_bytes)

        chunks = chunk_document(raw_text)
        if not chunks:
            raise ExtractionError("O documento está vazio.")

        job.status = "translating"

        def on_progress(fraction: float, message: str) -> None:
            job.progress = fraction
            job.message = message

        result = run_pipeline(
            api_key=api_key,
            chunks=chunks,
            target_language_label=job.language,
            model=job.model,
            progress_callback=on_progress,
        )
        job.result = result
        job.full_markdown = result.to_full_markdown()
        job.status = "done"
        job.progress = 1.0
        job.message = "Tradução concluída"
    except ExtractionError as exc:
        job.status = "error"
        job.error = str(exc)
        job.message = "Falha na leitura do documento"
    except Exception as exc:  # erros de API (chave inválida, modelo, rede...)
        job.status = "error"
        job.error = f"Erro ao chamar a API da Anthropic: {exc}"
        job.message = "Falha na tradução"


def create_job(*, filename: str, language: str, model: str, api_key: str, file_bytes: bytes) -> Job:
    """Registra o job e dispara a thread de processamento."""
    _cleanup_expired()
    job = Job(id=uuid.uuid4().hex, filename=filename, language=language, model=model)
    with _lock:
        _jobs[job.id] = job
    thread = threading.Thread(target=_worker, args=(job, api_key, file_bytes), daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)
