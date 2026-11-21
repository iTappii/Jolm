"""Server message localization (RU/EN) by Accept-Language."""

from typing import Optional

SUPPORTED = ("ru", "en")
DEFAULT_LOCALE = "en"

MESSAGES = {
    "internal_error": {"en": "Internal server error", "ru": "Внутренняя ошибка сервера"},
    "not_found": {"en": "Not found", "ru": "Не найдено"},
    "validation_error": {"en": "Invalid request", "ru": "Некорректный запрос"},
    "method_not_allowed": {"en": "Method not allowed", "ru": "Метод не поддерживается"},
    "otp_invalid": {"en": "Invalid or expired code", "ru": "Неверный или просроченный код"},
    "otp_rate_limited": {"en": "Try again later", "ru": "Попробуйте позже"},
    "otp_delivery_unavailable": {
        "en": "Code delivery unavailable",
        "ru": "Не удалось отправить код",
    },
    "otp_invalid_destination": {"en": "Invalid destination", "ru": "Некорректный адрес или номер"},
    "auth_unavailable": {"en": "Sign-in unavailable", "ru": "Вход временно недоступен"},
    "unauthorized": {"en": "Authentication required", "ru": "Требуется авторизация"},
    "forbidden": {"en": "Access denied", "ru": "Доступ запрещён"},
    "db_unavailable": {"en": "Database unavailable", "ru": "База данных недоступна"},
    "routing_unavailable": {"en": "Directions unavailable", "ru": "Маршруты недоступны"},
    "rate_limited": {
        "en": "Too many requests, try again later",
        "ru": "Слишком много запросов, попробуйте позже",
    },
    "llm_unavailable": {"en": "Assistant unavailable", "ru": "Ассистент временно недоступен"},
    "llm_timeout": {
        "en": "The assistant took too long to answer",
        "ru": "Ассистент слишком долго отвечает",
    },
    "llm_error": {"en": "The assistant failed to answer", "ru": "Ассистент не смог ответить"},
    "chat_full": {
        "en": "This chat is full, start a new one",
        "ru": "Чат заполнен, начните новый",
    },
    "chat_busy": {
        "en": "The assistant is still answering in this chat, wait for it to finish",
        "ru": "Ассистент ещё отвечает в этом чате, дождитесь окончания",
    },
    "budget_choice_unavailable": {
        "en": "Nothing to choose: the trip fits the budget or the choice was already made",
        "ru": "Выбирать нечего: поездка укладывается в бюджет или выбор уже сделан",
    },
    "must_have": {
        "en": "This stop is one of your must-haves; confirm to change it anyway",
        "ru": "Это обязательное место из ваших пожеланий; подтвердите, чтобы изменить его",
    },
    "no_replacement": {
        "en": "No suitable replacement fits that day",
        "ru": "Подходящей замены на этот день не нашлось",
    },
    "proposal_decided": {
        "en": "This proposal has already been answered",
        "ru": "На это предложение уже ответили",
    },
    "proposal_stale": {
        "en": "The plan changed since this proposal was made",
        "ru": "План изменился после этого предложения",
    },
    "proposal_not_applicable": {
        "en": "The change no longer fits the plan",
        "ru": "Это изменение больше не вписывается в план",
    },
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
