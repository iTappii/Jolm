# Ш-66 (iOS) — дневной лимит ИИ

- `APIErrorBody.decode`: 429 с кодом `llm_budget_exceeded` остаётся `APIError.server(status: 429, code:, message:)`; обычный `rate_limited` по-прежнему `APIError.rateLimited`.
- `ChatFailure.budgetExceeded(message:)`: текст сервера, а если пусто — локальный RU/EN («Лимит сообщений ИИ на сегодня исчерпан…»). Без отсчёта, без «Повторить» и без «Новый чат» (`canRetry == false`, `offersNewChat == false`); поле ввода остаётся рабочим. Тот же путь у гостевого чата (`ChatModel.run`). 503 `llm_budget_service` показывается как обычный `.server(message)`.
- `RetryDelay.text`: «Повторить через …» форматируется как «45 с» / «2 мин» / «11 ч 7 мин», а не десятки тысяч секунд.
- Stub (`-JolStubAPI`): сообщение со словом «budget» отвечает 429 `llm_budget_exceeded` с `Retry-After: 40000`.
- Тесты: `JolTests/BudgetLimitTests` (декодирование 429 с кодом, маппинг budget vs rate limit, форматирование), UI `ChatUITests.testDailyAILimitShowsMessageWithoutRetryAndInputStaysUsable`.
