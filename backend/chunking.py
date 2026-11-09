"""
chunking.py — Fragmentação segura de documentos longos.

Editais de concurso podem passar de 100 páginas. Este módulo divide o texto
em fragmentos ("chunks") que cabem com folga no limite de tokens da chamada,
respeitando as fronteiras naturais do documento nesta ordem de preferência:

    1. Cabeçalhos de seção/artigo (ex.: "1. DAS INSCRIÇÕES", "Art. 5º")
    2. Parágrafos (linha em branco)
    3. Quebra de linha simples
    4. Corte duro (último recurso, nunca no meio de uma palavra)

A continuidade de contexto entre fragmentos é garantida de duas formas:
    a) Cada chunk carrega os últimos N caracteres do chunk anterior
       (campo `context_tail`), enviados ao modelo apenas como referência.
    b) O prompt informa a posição do chunk ("parte 3 de 7") para o modelo
       manter numeração e terminologia consistentes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import CHUNK_CONTEXT_TAIL_CHARS, CHUNK_TARGET_CHARS

# Padrões típicos de início de seção em editais e documentos oficiais.
_SECTION_PATTERN = re.compile(
    r"(?m)^(?="
    r"\d{1,2}[\.\)]\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]"       # "1. DAS INSCRIÇÕES" / "2) DOS ..."
    r"|CAP[IÍ]TULO\s+[IVXLC\d]"                 # "CAPÍTULO IV"
    r"|SE[ÇC][ÃA]O\s+[IVXLC\d]"                 # "SEÇÃO II"
    r"|ANEXO\s+[IVXLC\d]"                       # "ANEXO I"
    r"|Art(?:igo)?\.?\s*\d"                     # "Art. 5º"
    r"|\[--- Página \d+ ---\]"                  # marcador inserido pelo extrator
    r")"
)


@dataclass
class Chunk:
    """Um fragmento de documento pronto para tradução."""
    index: int          # posição (1-based)
    total: int          # total de fragmentos
    text: str           # conteúdo a traduzir
    context_tail: str   # cauda do fragmento anterior (só contexto, não traduzir)


def _split_oversized(block: str, limit: int) -> list[str]:
    """Divide um bloco maior que o limite por parágrafos, linhas ou corte duro."""
    if len(block) <= limit:
        return [block]

    # 2º nível: parágrafos.
    paragraphs = re.split(r"\n\s*\n", block)
    if len(paragraphs) == 1:
        # 3º nível: linhas simples.
        paragraphs = block.split("\n")

    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                pieces.append(current)
            if len(para) <= limit:
                current = para
            else:
                # 4º nível: corte duro em espaço mais próximo do limite.
                start = 0
                while start < len(para):
                    end = min(start + limit, len(para))
                    if end < len(para):
                        space = para.rfind(" ", start, end)
                        if space > start:
                            end = space
                    pieces.append(para[start:end])
                    start = end
                current = ""
    if current:
        pieces.append(current)
    return pieces


def chunk_document(text: str, target_chars: int = CHUNK_TARGET_CHARS) -> list[Chunk]:
    """
    Divide o documento completo em uma lista de Chunks com contexto encadeado.
    Documentos curtos retornam um único chunk (sem overhead).
    """
    text = text.strip()
    if not text:
        return []

    # 1º nível: dividir por cabeçalhos de seção.
    sections = _SECTION_PATTERN.split(text)
    sections = [s for s in sections if s.strip()]

    # Agrupa seções pequenas até se aproximar do alvo; explode as gigantes.
    raw_chunks: list[str] = []
    current = ""
    for section in sections:
        for piece in _split_oversized(section, target_chars):
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= target_chars:
                current = candidate
            else:
                if current:
                    raw_chunks.append(current)
                current = piece
    if current:
        raw_chunks.append(current)

    total = len(raw_chunks)
    chunks: list[Chunk] = []
    for i, chunk_text in enumerate(raw_chunks, start=1):
        tail = raw_chunks[i - 2][-CHUNK_CONTEXT_TAIL_CHARS:] if i > 1 else ""
        chunks.append(Chunk(index=i, total=total, text=chunk_text, context_tail=tail))
    return chunks
