"""
config.py — Configurações centrais do TranslaAcolhe.

Centraliza constantes de modelo, idiomas, chunking e caminhos,
para que ajustes operacionais não exijam mudanças no restante do código.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# MODELO DA API ANTHROPIC
# ---------------------------------------------------------------------------
# NOTA DE ARQUITETURA: o identificador 'claude-3-5-sonnet' pertence a uma
# geração aposentada (retired) da API e não deve ser usado em produção.
# O modelo atual da linha Sonnet é 'claude-sonnet-4-6' (ID sem data,
# snapshot fixo). Referência: https://platform.claude.com/docs/en/about-claude/models/overview
DEFAULT_MODEL = "claude-sonnet-4-6"

# Máximo de tokens de SAÍDA por chamada (tradução de um chunk).
MAX_OUTPUT_TOKENS = 8000

# Temperatura baixa: tradução de documentos oficiais exige consistência,
# não criatividade.
TEMPERATURE = 0.2

# ---------------------------------------------------------------------------
# CHUNKING (fragmentação de documentos longos)
# ---------------------------------------------------------------------------
# Tamanho-alvo de cada fragmento, em CARACTERES.
# Regra prática para português: ~3,5 caracteres por token.
# 12.000 caracteres ≈ 3.400 tokens de entrada por chunk — margem confortável
# considerando que o system prompt + base de conhecimento ocupam ~4k tokens
# e que a tradução de saída tende a ter tamanho similar ao da entrada.
CHUNK_TARGET_CHARS = 12_000

# Sobreposição de contexto: os últimos N caracteres do chunk anterior são
# enviados como "memória" para o chunk seguinte, evitando perda de contexto
# em frases/tabelas cortadas na fronteira entre fragmentos.
CHUNK_CONTEXT_TAIL_CHARS = 800

# ---------------------------------------------------------------------------
# IDIOMAS DE DESTINO
# ---------------------------------------------------------------------------
# Mapeia o rótulo exibido na interface -> instrução linguística detalhada
# que será injetada no prompt (guiando registro, variante e alfabeto).
TARGET_LANGUAGES: dict[str, str] = {
    "Espanhol Latino-Americano": (
        "Espanhol latino-americano neutro (público: venezuelanos, cubanos e "
        "outros hispanofalantes). Use vocabulário simples e evite regionalismos "
        "peninsulares (Espanha)."
    ),
    "Árabe": (
        "Árabe Moderno Padrão (fuṣḥā), com frases curtas e claras (público: "
        "refugiados sírios e do Oriente Médio). Texto em alfabeto árabe, "
        "direção direita-para-esquerda. Mantenha nomes de órgãos brasileiros "
        "em alfabeto latino entre parênteses."
    ),
    "Francês": (
        "Francês claro e acessível (público: haitianos, senegaleses, "
        "congoleses e África Ocidental francófona). Evite jargão jurídico "
        "francês; prefira paráfrases simples."
    ),
    "Crioulo Haitiano": (
        "Crioulo haitiano (Kreyòl ayisyen) na ortografia oficial. Público em "
        "processo de alfabetização: frases muito curtas e diretas. Mantenha "
        "siglas brasileiras (CPF, RNM, CRAS) na forma original, explicadas."
    ),
    "Inglês": (
        "Inglês simples e internacional — 'plain English' (público: "
        "nigerianos, cameroneses e África Oriental). Evite phrasal verbs "
        "obscuros e legalês anglo-saxão."
    ),
    "Português Angolano/Moçambicano": (
        "Manter em português, MAS adaptar a burocracia brasileira para o "
        "entendimento de falantes de Angola e Moçambique: explicar siglas e "
        "institutos exclusivamente brasileiros (CadÚnico, CRAS, RNM, "
        "Celpe-Bras), aproximando de equivalentes lusófonos quando existirem "
        "(ex: 'Bilhete de Identidade' ~ 'RG'). Simplificar o juridiquês."
    ),
}

# ---------------------------------------------------------------------------
# FORMATOS DE ARQUIVO ACEITOS
# ---------------------------------------------------------------------------
ACCEPTED_EXTENSIONS = ["pdf", "docx", "txt", "xml"]

# ---------------------------------------------------------------------------
# CAMINHOS
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
