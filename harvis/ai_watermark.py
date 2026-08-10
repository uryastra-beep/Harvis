from __future__ import annotations

import re
import unicodedata


_AUTHORED_CONTENT_RE = re.compile(
    r"\b(?:"
    r"texto|mensaje|correo|email|e-mail|carta|parrafo|descripcion|publicacion|post|caption|"
    r"comentario|respuesta|resumen|guion|poema|historia|documento|nota|issue|reporte|informe|"
    r"ensayo|articulo|bio|biografia|copy|prompt|speech|discurso|"
    r"text|message|mail|letter|paragraph|description|comment|reply|summary|script|story|document|"
    r"note|report|essay|article"
    r")\b"
)

_STRONG_WRITING_RE = re.compile(
    r"\b(?:"
    r"escrib\w*|redact\w*|reescrib\w*|reformula\w*|parafrase\w*|compon\w*|"
    r"write|writes|writing|draft|drafts|compose|composes|rewrite|rewrites|rephrase|rephrases|"
    r"summarize|summarise|resume|resumeme|resumir|contesta\w*|respond\w*|reply"
    r")\b"
)

_GENERIC_CREATION_RE = re.compile(
    r"\b(?:"
    r"haz|hazme|hace|haceme|hacer|crea\w*|genera\w*|elabora\w*|prepara\w*|formula\w*|"
    r"inventa\w*|arma\w*|"
    r"create|creates|generate|generates|prepare|prepares|make|makes|formulate|formulates"
    r")\b"
)

_SEARCH_OR_NAVIGATION_RE = re.compile(
    r"\b(?:"
    r"busca\w*|buscar|googlea\w*|googlear|buscador|busqueda|"
    r"search|searches|searching|google|look\s+up|find|"
    r"barra\s+de\s+busqueda|campo\s+de\s+busqueda|barra\s+de\s+direcciones|"
    r"search\s+bar|search\s+box|address\s+bar|"
    r"abre|abrir|open|ve\s+a|ir\s+a|go\s+to|navigate|navega\w*"
    r")\b"
)

_URL_OR_LINK_RE = re.compile(
    r"(?:https?://|www\.|\b(?:url|enlace|link|sitio\s+web|pagina\s+web|web\s+address|website)\b|"
    r"\b[a-z0-9][a-z0-9.-]*\.(?:com|org|net|io|dev|app|ai|co|cr|edu|gov)(?:\b|/))"
)


def _normalize_request(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(character for character in value if not unicodedata.combining(character))


def should_watermark_ai_authored_text(user_request: str) -> bool:
    """Return True only when the request clearly asks Harvis to author written content."""

    value = " ".join(_normalize_request(user_request).split()).strip()
    if not value:
        return False

    has_authored_content = _AUTHORED_CONTENT_RE.search(value) is not None
    has_strong_writing = _STRONG_WRITING_RE.search(value) is not None
    has_generic_creation = _GENERIC_CREATION_RE.search(value) is not None

    # Explicit requests to create a recognizable piece of written content win even
    # when the user also asks Harvis to research something first.
    if has_authored_content and (has_strong_writing or has_generic_creation):
        return True

    # Searches, URLs, navigation, and browser-field entry are operational typing,
    # not AI-authored content, so they must never receive the authorship marker.
    if _URL_OR_LINK_RE.search(value) or _SEARCH_OR_NAVIGATION_RE.search(value):
        return False

    # Direct writing verbs such as "write", "redacta", or "escribe" are enough
    # when no search/navigation context is present.
    return has_strong_writing


__all__ = ["should_watermark_ai_authored_text"]
