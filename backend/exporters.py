"""
exporters.py — Geração dos arquivos de download (.txt e .docx).

O .docx é montado com python-docx a partir do Markdown consolidado,
convertendo cabeçalhos (#, ##), listas (-) e tabelas Markdown (| a | b |)
em elementos nativos do Word — importante para quem vai imprimir o
documento ou levá-lo a um atendimento no CRAS/DPU.
"""

from __future__ import annotations

import io
import re

from docx import Document
from docx.shared import Pt

_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")


def to_txt_bytes(markdown_text: str) -> bytes:
    """Exportação simples: o Markdown legível vira .txt em UTF-8 (com BOM,
    para abrir corretamente no Bloco de Notas do Windows)."""
    return markdown_text.encode("utf-8-sig")


def to_docx_bytes(markdown_text: str) -> bytes:
    """Converte o Markdown consolidado em um .docx estruturado."""
    doc = Document()

    # Fonte padrão legível para impressão.
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    lines = markdown_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # --- Tabelas Markdown -> tabela nativa do Word ---
        if _TABLE_ROW_RE.match(line):
            rows: list[list[str]] = []
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                if not _TABLE_SEPARATOR_RE.match(lines[i]):  # pula linha |---|---|
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    rows.append(cells)
                i += 1
            if rows:
                n_cols = max(len(r) for r in rows)
                table = doc.add_table(rows=len(rows), cols=n_cols)
                table.style = "Light Grid Accent 1"
                for r_idx, row in enumerate(rows):
                    for c_idx in range(n_cols):
                        text = row[c_idx] if c_idx < len(row) else ""
                        table.rows[r_idx].cells[c_idx].text = _strip_md(text)
            continue

        # --- Cabeçalhos ---
        if line.startswith("### "):
            doc.add_heading(_strip_md(line[4:]), level=3)
        elif line.startswith("## "):
            doc.add_heading(_strip_md(line[3:]), level=2)
        elif line.startswith("# "):
            doc.add_heading(_strip_md(line[2:]), level=1)
        # --- Itens de lista ---
        elif line.lstrip().startswith(("- ", "* ")):
            doc.add_paragraph(_strip_md(line.lstrip()[2:]), style="List Bullet")
        # --- Parágrafo comum ---
        elif line.strip():
            doc.add_paragraph(_strip_md(line))

        i += 1

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _strip_md(text: str) -> str:
    """Remove marcação inline básica (**negrito**, _itálico_) para o Word."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return text.strip()
