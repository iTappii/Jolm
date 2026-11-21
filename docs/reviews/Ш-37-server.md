# Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта

Экран полной карты (iOS) здесь не делался. Сервер отдаёт всё, что ему нужно: список поездок,
полную поездку и выбор вида транспорта для перехода. Закрыто замечание координатора Ш-36 №1.

## Что сделано

- **Один фильтр `variant = 'main'`.** Константа `MAIN` и функции `main_items`, `main_legs`
  (`server/app/trips/store.py`) — единственное место, где план читается. Альтернативы бюджета
  читает только `variant_items`, и только для раздела `budget` (чтобы клиент показал выбор).
- `server/app/trips/read.py` — чистые функции JSON; `server/app/trips/api.py` — маршруты;
  `server/app/trips/edit.py::set_leg_mode` — выбор транспорта. Миграций нет.
- Авторизация: Bearer, как у чатов. Чужая или несуществующая поездка (и чужой/несуществующий
  переход) — одинаковый 404 `not_found`.
- Время в ответах — в Asia/Almaty со смещением (сейчас `+05:00`, не `+06:00`), даты — локальные.
  Имена мест — по `Accept-Language` (ru: ru, en, kk; en: en, ru, kk), как в API мест.

## `GET /v1/trips?limit=50&before=<updated_at>`

```json
{"items": [{
  "id": "<uuid>", "chat_id": "<uuid>|null",
  "start_date": "2026-12-05", "end_date": "2026-12-07", "days": 3,
  "version": 2, "status": "active",
  "budget": {"status": "ok"|"over"|null, "budget_kzt": 900000, "total_kzt": 120000},
  "updated_at": "2026-11-21T09:09:54+05:00"}]}
```

Свежие сверху; `before` — `updated_at` последнего элемента (как в чатах).

## `GET /v1/trips/{id}`

```json
{
 "id": "<uuid>", "chat_id": "<uuid>|null", "version": 1, "status": "active",
 "start_date": "2026-12-05", "end_date": "2026-12-07",
 "budget_kzt": 900000, "total_cost_kzt": 120000, "budget_choice": null,
 "weather_checked_at": null, "created_at": "...+05:00", "updated_at": "...+05:00",
 "days": [{
   "date": "2026-12-05",
   "items": [{
     "id": "<uuid>", "ord": 1, "kind": "activity"|"meal", "meal": null|"lunch"|"dinner",
     "place": {"id": "<uuid>", "name": "Кок-Тобе", "name_lang": "ru"|"en"|"kk",
               "category": "viewpoint", "category_name": "Смотровая площадка",
               "lat": 43.233, "lon": 76.974,
               "photo": null | {"id": "<uuid>", "storage_key": "kok.jpg"}},
     "starts_at": "2026-12-05T09:30:00+05:00", "ends_at": "...", "visit_min": 60,
     "must_have": false, "est_cost_kzt": 3000,
     "cost_assumed": false, "hours_assumed": false, "rain_exposed": false}],
   "legs": [{
     "id": "<uuid>", "from_item_id": "<uuid>|null", "to_item_id": "<uuid>",
     "depart_at": "...+05:00", "travel_s": 540, "estimated": false,
     "chosen_mode": "walk"|null, "cost_kzt": 0,
     "options": [{"mode": "walk", "duration_s": 540.0, "duration_s_min"?, "duration_s_max"?,
                  "distance_m": 700.0, "cost_kzt_min": 0, "cost_kzt_max": 0,
                  "geometry": "<polyline6>", "approximate": false, "recommended": true}]}]}],
 "budget": { ...блок бюджета Ш-35/36..., "lodging": {"needed", "nights", "cost_kzt",
     "price_assumed", "options": [{"id", "name", "name_lang", "category", "lat", "lon",
         "rank", "price_per_night_kzt", "price_assumed", "nights", "total_kzt",
         "recommended"}]},
   "variants": null | {
     "drop_places": {"feasible", "total_kzt", "saves_kzt", "shortfall_kzt", "breakdown",
         "removed_count", "removed": [{"id", "name", "name_lang", "category", "lat", "lon"}]},
     "cheaper": {"feasible", "total_kzt", "saves_kzt", "shortfall_kzt", "breakdown",
         "swaps_count", "lodging_changed", "lodging_total_kzt",
         "swaps": [{"from": <place>, "to": <place>|null}],
         "lodging": null | {"id", "name", ..., "total_kzt"}}}},
 "warnings": [{"code", "date", "detail"}],
 "must_have_unmet": [{"wish", "place_name", "reason"}]
}
```

- `days` содержит **каждую дату поездки**, пустые дни — `items: []`. Переход `legs[i]` приходит
  в `items[i+1]` (`to_item_id`); первая остановка дня перехода не имеет (начало дня — центр).
- `options[].geometry` — polyline6 (как в `POST /v1/directions`), у переходов без роутера
  `options = []`, `chosen_mode = null`, `estimated = true`.
- `variants.*.removed` / `swaps` собираются **из строк вариантов** (в `trips.budget` id мест не
  хранятся). Для `cheaper` пары «убрано → пришло» выводятся эвристикой: тот же вид остановки и
  слот обеда/ужина, ближайший день (`to: null`, если пары нет). `lodging` — самое дешёвое жильё
  из вариантов, как при применении выбора.
- `budget.lodging.options` — без `distance_km` (его нет в БД; есть в событии `route_ready`).
- `must_have_unmet[].place_name` сохранён на языке чата, в котором строился план.

## `POST /v1/trips/{id}/legs/{leg_id}/mode`  `{"mode": "walk"|"scooter"|"bus"|"metro"|"taxi"|"car"}`

```json
{"trip_id": "<uuid>", "version": 2,
 "leg": { ...тот же объект, что в days[].legs, уже с новым chosen_mode/cost_kzt/travel_s... },
 "arrives_at": "...+05:00", "late_by_s": 0, "changed_days": ["2026-12-05"],
 "budget": {"status", "total_kzt", "remaining_kzt", "shortfall_kzt", "breakdown": {...}}}
```

- Режима нет среди `options` перехода (или значение вне списка) — 422 `validation_error`.
- Обновляются `chosen_mode`, `cost_kzt` (верхняя оценка варианта, как в планировщике),
  `travel_s` (`duration_s_max` либо `duration_s`); пересчитываются транспорт и итог в
  `trips.budget` / `total_cost_kzt`.
- **`version` растёт** (скачанный маршрут и стоимость изменились — Ш-42 сможет это заметить).
- **Расписание дня не пересобирается** (решение, ADR 0003): медленный вариант может прибыть
  позже начала следующей остановки — `late_by_s > 0`, клиент показывает предупреждение. Следующая
  правка дня (Ш-38) учитывает сделанный выбор.
- Устаревшие варианты бюджета при этом удаляются (как при любой правке, см. Ш-38).

## Проверки

`tests/test_trips_read.py`, 7 тестов: 401 без токена и 404 для чужого на всех маршрутах; список
(поля, `before`); полная поездка (состав полей, имена RU/EN, фото, порядок и непрерывность
переходов, пустые дни); варианты не попадают в дни, `removed`/`swaps` совпадают с событием
`route_ready`; жильё вместе с бюджетом; выбор транспорта (стоимость, итог, версия, БД);
отказы (режим вне списка, неизвестный переход). `make ci`: 544 прошли, 1 пропущен.

## Не сделано / не проверено

- iOS-экран (карта по дням, мини-карточка, выбор варианта транспорта) — отдельно.
- Парность «убрано → пришло» в `cheaper.swaps` — эвристика, не точное воспроизведение замены
  планировщика (достаточно для показа выбора; при необходимости хранить пары явно).
- Ответ `GET /v1/trips/{id}` включает геометрию всех вариантов всех переходов: порядка сотен КБ на
  длинную поездку (замечание Ш-36 о размере `options` остаётся).
- `weather_checked_at` всегда `null` до Ш-40.

## Ревью координатора (2026-11-21)

`make ci` перезапущен — 544 прошли, 1 пропущен. Фильтр `variant = 'main'` собран в одном месте
(`store.MAIN`, `main_items`, `main_legs`) — замечание Ш-36 №1 закрыто. Чужая поездка → 404.
Шаг остаётся `[~]`: iOS-экран полной карты не сделан. Замечание: смена вида транспорта не
пересчитывает время дня, а отдаёт `late_by_s` — клиент обязан это показать (низко).
