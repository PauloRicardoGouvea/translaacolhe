"""Validate the full upload and export flow, optionally with the real API."""

import argparse
import io
import os
import time
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from main import app


def message(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Use the configured Anthropic API key")
    args = parser.parse_args()
    if args.live and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Set ANTHROPIC_API_KEY before running the live test.")

    replies = [
        message("<traducao>Submit your appeal within two business days.</traducao>"),
        message("<resumo>Appeal deadline.</resumo><alertas>Two business days.</alertas>"
                "<glossario>Appeal: request a review.</glossario>"),
    ]
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: replies.pop(0)))
    key = nullcontext() if args.live else patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only"})
    model = nullcontext() if args.live else patch("translator.anthropic.Anthropic", return_value=fake_client)

    with key, model, TestClient(app) as client:
        assert client.get("/").status_code == 200, "Build the frontend before running this test."
        assert "Inglês" in {language["label"] for language in client.get("/api/languages").json()}
        response = client.post(
            "/api/translate",
            data={"language": "Inglês"},
            files={"file": ("edital-ficticio.txt", b"Apresente recurso em dois dias uteis.", "text/plain")},
        )
        assert response.status_code == 200, response.text
        job_url = "/api/jobs/" + response.json()["job_id"]
        deadline = time.monotonic() + (120 if args.live else 10)
        while time.monotonic() < deadline:
            job = client.get(job_url).json()
            if job["status"] in {"done", "error"}:
                break
            time.sleep(0.25)
        assert job["status"] == "done", job.get("error") or "Translation did not complete."
        assert all(job["result"][key] for key in ("summary", "document", "alerts", "glossary"))
        txt = client.get(job_url + "/download?format=txt")
        docx = client.get(job_url + "/download?format=docx")
        assert txt.status_code == docx.status_code == 200
        assert job["result"]["document"] in txt.content.decode("utf-8-sig")
        assert len(Document(io.BytesIO(docx.content)).paragraphs) > 1

    print("PASS: upload, translation pipeline, job polling, TXT and DOCX"
          + (" with the live API" if args.live else " with simulated API responses"))


if __name__ == "__main__":
    main()
