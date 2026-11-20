"""Server message localization (RU/EN) by Accept-Language."""

from typing import Optional

SUPPORTED = ("ru", "en")
DEFAULT_LOCALE = "en"

MESSAGES = {
    "internal_error": {"en": "Internal server error", "ru": "Внутренняя ошибка сервера"},
    "not_found": {"en": "Not found", "ru": "Не найдено"},
    "validation_error": {"en": "Invalid request", "ru": "Некорректный запрос"},
    "method_not_allowed": {"en": "Method not allowed", "ru": "Метод не поддерживается"},
    "unauthorized": {"en": "Authentication required", "ru": "Требуется авторизация"},
    "forbidden": {"en": "Access denied", "ru": "Доступ запрещён"},
    "db_unavailable": {"en": "Database unavailable", "ru": "База данных недоступна"},
    "http_error": {"en": "Request failed", "ru": "Не удалось выполнить запрос"},
}


def pick_locale(accept_language: Optional[str]) -> str:
    """Pick the best supported locale from an Accept-Language header (q-values honoured)."""
    if not accept_language:
        return DEFAULT_LOCALE
    candidates = []
    for index, part in enumerate(accept_language.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        q = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                q = float(params[2:])
            except ValueError:
                q = 0.0
        lang = tag.strip().lower().split("-")[0]
        if lang in SUPPORTED and q > 0:
            candidates.append((-q, index, lang))
    if not candidates:
        return DEFAULT_LOCALE
    return sorted(candidates)[0][2]


def translate(code: str, locale: str) -> str:
    entry = MESSAGES.get(code) or MESSAGES["http_error"]
    return entry.get(locale) or entry[DEFAULT_LOCALE]
