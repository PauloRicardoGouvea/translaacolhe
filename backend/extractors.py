"""
extractors.py — Extração de texto limpo de arquivos PDF, DOCX, TXT e XML.

Cada função recebe os BYTES do arquivo (como entregues pelo st.file_uploader)
e retorna uma string única com o texto, preservando ao máximo a estrutura
visual (quebras de linha entre parágrafos, células de tabela separadas).
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pdfplumber
from docx import Document


class ExtractionError(Exception):
    """Erro amigável de extração, exibido diretamente ao usuário na UI."""


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def extract_pdf(file_bytes: bytes) -> str:
    """
    Extrai texto de um PDF com pdfplumber (melhor fidelidade de layout que
    pypdf para editais, que costumam ter colunas e tabelas de cronograma).

    Insere um marcador de página para ajudar o modelo a citar a origem
    de prazos ("página X do edital").
    """
    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                # Tabelas (ex.: cronogramas) às vezes não saem no extract_text;
                # extraímos separadamente e serializamos como linhas "a | b | c".
                tables = page.extract_tables() or []
                table_lines: list[str] = []
                for table in tables:
                    for row in table:
                        cells = [(c or "").strip() for c in row]
                        if any(cells):
                            table_lines.append(" | ".join(cells))
                page_block = text.strip()
                if table_lines:
                    page_block += "\n[TABELA DETECTADA]\n" + "\n".join(table_lines)
                if page_block:
                    parts.append(f"[--- Página {i} ---]\n{page_block}")
    except Exception as exc:  # PDF corrompido, protegido por senha etc.
        raise ExtractionError(f"Não foi possível ler o PDF: {exc}") from exc

    full_text = "\n\n".join(parts).strip()
    if not full_text:
        raise ExtractionError(
            "O PDF não contém texto extraível. Provavelmente é um documento "
            "escaneado (imagem). Será necessário aplicar OCR antes de traduzir."
        )
    return full_text


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
def extract_docx(file_bytes: bytes) -> str:
    """
    Extrai texto de um .docx com python-docx, incluindo parágrafos E tabelas
    (na ordem do corpo do documento), pois editais em Word frequentemente
    colocam o cronograma em tabela.
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ExtractionError(f"Não foi possível ler o DOCX: {exc}") from exc

    parts: list[str] = []

    # Percorre o corpo na ordem original (parágrafos e tabelas intercalados).
    for element in doc.element.body:
        tag = element.tag.split("}")[-1]  # remove namespace
        if tag == "p":
            # Reconstrói o texto do parágrafo a partir dos runs.
            text = "".join(node.text or "" for node in element.iter() if node.tag.endswith("}t"))
            if text.strip():
                parts.append(text.strip())
        elif tag == "tbl":
            parts.append("[TABELA DETECTADA]")
            for row in element.iter():
                if row.tag.endswith("}tr"):
                    cells = []
                    for cell in row.iter():
                        if cell.tag.endswith("}tc"):
                            cell_text = "".join(
                                n.text or "" for n in cell.iter() if n.tag.endswith("}t")
                            ).strip()
                            cells.append(cell_text)
                    if any(cells):
                        parts.append(" | ".join(cells))

    full_text = "\n".join(parts).strip()
    if not full_text:
        raise ExtractionError("O DOCX está vazio ou não contém texto legível.")
    return full_text


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------
def extract_txt(file_bytes: bytes) -> str:
    """Decodifica TXT tentando encodings comuns em documentos brasileiros."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(encoding).strip()
            if text:
                return text
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Não foi possível decodificar o arquivo de texto.")


# ---------------------------------------------------------------------------
# XML
# ---------------------------------------------------------------------------
def extract_xml(file_bytes: bytes) -> str:
    """
    Extrai texto de XML estruturado SEM quebrar a lógica das tags:
    percorre a árvore em profundidade e serializa cada nó como
    "caminho/da/tag: texto", preservando a hierarquia como contexto legível.

    Exemplo: <edital><prazo>10/08/2026</prazo></edital>
    vira ->  "edital/prazo: 10/08/2026"
    """
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ExtractionError(f"XML malformado: {exc}") from exc

    lines: list[str] = []

    def _strip_ns(tag: str) -> str:
        return tag.split("}")[-1]  # remove namespaces {http://...}tag

    def walk(node: ET.Element, path: str) -> None:
        current = f"{path}/{_strip_ns(node.tag)}" if path else _strip_ns(node.tag)
        # Atributos podem carregar informação relevante (ex.: numero="01/2026").
        for key, value in node.attrib.items():
            if value.strip():
                lines.append(f"{current}@{key}: {value.strip()}")
        if node.text and node.text.strip():
            lines.append(f"{current}: {node.text.strip()}")
        for child in node:
            walk(child, current)
            if child.tail and child.tail.strip():
                lines.append(f"{current}: {child.tail.strip()}")

    walk(root, "")
    full_text = "\n".join(lines).strip()
    if not full_text:
        raise ExtractionError("O XML não contém texto extraível.")
    return full_text


# ---------------------------------------------------------------------------
# ROTEADOR
# ---------------------------------------------------------------------------
_EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
    "xml": extract_xml,
}


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Roteia a extração pela extensão do arquivo enviado."""
    ext = filename.rsplit(".", 1)[-1].lower()
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise ExtractionError(
            f"Formato '.{ext}' não suportado. Envie PDF, DOCX, TXT ou XML."
        )
    return extractor(file_bytes)
