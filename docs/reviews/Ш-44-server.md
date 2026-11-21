# Ревью Ш-44 (сервер) — отправка контента

Серверная часть: загрузка фото, отправки пяти типов (отзыв, меню, фото, данные о транспорте, цены
за вход), отзывы для вкладки карточки «Отзывы», реальные URL фото. iOS-часть (экран отправки,
сжатие, удаление EXIF/GPS) не входит. Закрывает `Ш-17.md` №1 (у фото был только `storage_key`).

## Что сделано

- Миграция `0018_submissions.sql`: `uploads` (слот загрузки) и `submissions`
  (`user_id`, `place_id`, `type`, `payload jsonb`, `status`, `filter_result`, `content_hash`,
  `place_photo_id`, `moderator_id`, `decided_at`). По TECH_PLAN §3 схема `submissions` та же,
  добавлены `uploads`, `content_hash`, `place_photo_id`, `locale`.
- Правило 8: у `submissions.place_id` нет `ON DELETE CASCADE`; `data/osm/merge.py` переносит строки
  (`test_merge_moves_submissions_to_the_survivor`). Уникального индекса «один отзыв на человека и
  место» в схеме нет нарочно: слияние двух мест, где человек оставил оба отзыва, нарушило бы его;
  правило держит API (409 `already_submitted`).
- Хранилище: `app/providers/storage/` — интерфейс `StorageProvider`, адаптер `S3Storage`
  (SigV4 presigned PUT руками на `hashlib`/`hmac`, без AWS SDK; подписаны `Content-Type` и
  `Content-Length`, поэтому бакет отвергнет тело другого размера или типа) и `LocalStorage`
  (диск, `PUT /v1/dev-uploads/...`, раздача `/media`; только `app_env` dev/test, в prod
  `make_storage` его не создаёт). Пустой `STORAGE_PROVIDER` = 503 `storage_unavailable`.
- Фото получают URL: `GET /v1/places/{id}` → `photos[].url`, `GET /v1/trips/{id}` →
  `place.photo.url`, офлайн-копия — `photo_url` (теперь через общий `media_url`). Пока
  `MEDIA_BASE_URL` пуст — `null`, `storage_key` остаётся.
- Удаление аккаунта: опубликованные отзывы и фото остаются обезличенными (`user_id` = NULL, как
  `place_photos.author_user_id` в 0008); неопубликованные отправки, слоты и их файлы удаляются
  (файлы задачей `storage.delete`, обработчик в `worker.py`). Тест
  `test_account_deletion_anonymizes_published_and_removes_the_rest`.

## API

`POST /v1/uploads` `{"content_type": "image/jpeg|png|webp", "size_bytes": n}` → 201
`{"upload_id", "url", "method": "PUT", "headers": {"Content-Type": ...}, "expires_at", "max_bytes"}`.
Клиент убирает EXIF/GPS, сжимает и делает PUT ровно `size_bytes` байт с этими заголовками.
Лимиты: JPEG/PNG/WebP, до 8 МБ, 40 слотов в сутки (429 `rate_limited` с `Retry-After`).

`POST /v1/submissions` `{"type": "review|menu|photo|transit|price", "place_id": uuid|null, "payload": {...}}`
→ 201 `{"id","type","place":{"id","name"}|null,"status","pending_review","reason_codes","payload",
"photo_url","created_at","decided_at"}`. `place_id` обязателен для всех типов, кроме `transit`.
Payload: review `{rating 1..5, text?}`; menu `{items:[{name, price_kzt?, description?}], upload_id?}`
(нужно одно из двух); photo `{upload_id, caption?}`; transit `{route_ref, stop?, direction?,
interval_min?, price_kzt?, note?}`; price `{price_kzt, audience: adult|child|student|senior|foreigner|resident, note?}`.
Лишние поля, чужой `status` и т. п. — 422. Не более 30 отправок в сутки.
Статусы: `published_pending_review` (опубликовано, «проверится позже», `pending_review: true`),
`rejected_auto` (201, `reason_codes`, см. Ш-45), `approved`, `rejected`.

`GET /v1/me/submissions?limit&cursor` → `{"items": [...как выше], "next_cursor"}`, новые первыми.

`GET /v1/places/{id}/reviews?limit&cursor` (публично) → `{"items":[{"id","rating","text",
"author_name","created_at","pending_review"}], "next_cursor", "summary":{"count","average"}}`.
Только `published_pending_review` и `approved`. `author_name` = `users.display_name` (сейчас его
никто не заполняет, поэтому всегда `null`; iOS показывает «Аноним»). Курсор непрозрачный.

Коды ошибок: 422 `invalid_image` (не изображение / размер или тип не те — слот помечается
отклонённым, файл ставится на удаление), 422 `upload_not_found` (нет слота, чужой, просрочен —
слот живёт час, — или файл не пришёл), 409 `upload_used`, 409 `already_submitted`, 404 `not_found`.

## Проверки

- 43 теста `test_submissions.py` + 6 `test_storage.py` + тест слияния. Среди прочего: каждый тип
  принимается; 19 некорректных payload; подделки изображений (HTML под видом JPEG, PNG под видом
  JPEG, GIF); файл не загружен; размер не совпал; чужой, повторно использованный и просроченный
  слот; пагинация и сводка отзывов; видимость по статусам; удаление аккаунта; задача
  `storage.delete`.
- SigV4 проверен на примере из документации AWS (подпись совпала побайтно:
  `aeeed9bb…404`), чтение/удаление — на `httpx.MockTransport`.
- `make ci`: 708 passed, 1 skipped (было 606 / 1). Тесты в целях проверки на гонки по порядку
  запускались по три раза подряд.

## Не проверено и ограничения

- **`S3Storage` ни разу не работал с настоящим бакетом.** Образ MinIO в `infra/docker-compose.yml`
  не добавлен: образы `minio/*` с Docker Hub не скачались, а точные теги на quay.io проверить
  не удалось (нет доступа к реестру). Подписывать и добавлять непроверенный тег хуже, чем честно
  не добавлять. Для dev есть `local`-адаптер (проверен тестами). Перед TestFlight нужно один раз
  прогнать загрузку на реальный бакет (MinIO / S3 / R2): особенно path-style адресацию и политику
  публичного чтения для `MEDIA_BASE_URL`.
- Проверка «это изображение» — по магическим байтам (JPEG, PNG, WebP) и размеру; картинка не
  декодируется, возможна «полиглот»-подделка. Pillow не подключал: это лишняя зависимость ради
  защиты, которую даёт и сам бакет (отдача как статики с `Content-Type` и без выполнения).
- EXIF/GPS сервер не убирает и не проверяет: чистит клиент (Ш-44 iOS). Если клиент пришлёт
  файл с геометками, он опубликуется как есть. Дешёвая проверка APP1/GPS для JPEG возможна позже.
- Чтение объекта целиком (до 8 МБ) на запрос отправки идёт из процесса API; при росте нагрузки
  это вынести в задачу воркера.
- Объекты удалённых или отклонённых отправок чистятся задачей `storage.delete`; без настроенного
  хранилища она пишет предупреждение и завершается (файлы остаются).
- Просроченные слоты (`pending` старше часа) и их файлы никто не убирает: нужна периодическая
  уборка (в Ш-45/46 или отдельно). Это не утечка данных, но мусор в бакете.
- Одно `LocalStorage` на процесс; несколько процессов API должны использовать общий каталог.

## Для iOS

Последовательность: `POST /v1/uploads` → PUT с заголовками из ответа и ровно `size_bytes` →
`POST /v1/submissions`. Вкладка «Фото» строится по `photos[].url`; «Отзывы» — по
`/places/{id}/reviews` (пометка «проверится позже» при `pending_review`). Для `rejected_auto`
ответ 201 приходит с `reason_codes`: показывать «не прошло проверку», а не «ошибка сети».
Меню, цены и данные о транспорте на карточке не появятся, пока модератор их не одобрит.

## Ревью координатора (2026-11-21)

Миграции `0017`, `0018` прочитаны: `submissions.place_id` без каскада и в `merge_place` (правило
8), опубликованное при удалении аккаунта обезличивается (`user_id` → NULL), неопубликованное и
файлы удаляются задачей. `LocalStorage` защищён от выхода за корень (`resolve` + проверка
родителя) и монтируется только в dev. `make ci` перезапущен — 708 прошли, 1 пропущен. Замечания:

1. **Средне (до продакшена).** `S3Storage` не запускался на реальном бакете, MinIO в
   `docker-compose` нет — проверить на настоящем S3-совместимом хранилище до TestFlight.
2. **Низко.** Просроченные слоты загрузки не чистятся; `session_retired_tokens` растёт за всё
   время жизни сессии — добавить очистку в задачу воркера.
3. Сервер не проверяет EXIF/GPS — снимать геоданные обязан клиент (iOS-часть Ш-44).

## Исправления (2026-11-21)

Замечание 2 (очистка) закрыто. Задача воркера `retention.cleanup` (расписание — раз в час, в
`SCHEDULES`; код в `app/worker.py`):

- удаляет слоты `uploads` со статусом `pending`/`rejected` и истёкшим `expires_at` (до 500 за
  запуск, остальное — в следующий час) и в той же транзакции ставит задачу `storage.delete` с
  их ключами, так что файл не теряется и сбой хранилища не блокирует очистку. Слоты `used`
  остаются: на файл ссылается публикация;
- удаляет из `session_retired_tokens` записи старше 60 дней (срок жизни refresh-токена) —
  отдельно от прореживания при каждом обновлении токена.

Тест `test_retention_cleanup_drops_stale_slots_and_old_retired_tokens` (в `test_submissions.py`):
просроченные pending/rejected исчезают и попадают в `storage.delete`, `used` и живой слот
остаются, старый retired-токен удалён, свежий нет, повторный запуск ничего не дублирует.
Не проверено: работа на реальном S3 и под нагрузкой (замечание 1 остаётся).
