# App Store Connect — «App Privacy»: ответы и доказательства

> **ЧЕРНОВИК. Проверить владельцу/юристу.** Ответы построены по коду на 2026-11-21 (ветка
> `sh-22-24-auth` + эта ветка). Нужно пересверить перед отправкой в ревью: серверные доказательства
> могли измениться; iOS-части Ш-40 (push), Ш-44 (отправка контента), Ш-50 (аналитика на клиенте)
> лежат в других ветках и в этом дереве отсутствуют — отмечены «(в другой ветке)».
> Манифест приватности приложения: `ios/Jol/PrivacyInfo.xcprivacy` — он должен совпадать с таблицей.

## 1. Общие ответы

| Вопрос | Ответ | Основание |
|---|---|---|
| Собираете ли вы данные из приложения? | **Да** | таблица ниже |
| Используются ли данные для **отслеживания** (tracking, ATT)? | **Нет** | нет рекламных SDK, нет передачи данных брокерам; в iOS-коде нет `ATTrackingManager`; `NSPrivacyTracking = false`. Идентификатор установки (UUID) не передаётся третьим лицам и не пересекается между приложениями |
| Сторонние SDK | MapLibre Native (карта) | `ios/project.yml` → пакет `maplibre-gl-native-distribution` 6.31.0. **Не проверено:** есть ли в его поставке собственный `PrivacyInfo.xcprivacy` — проверить в собранном `.app` перед отправкой |

## 2. Типы данных (что отметить в App Store Connect)

«Связано с личностью» = привязано к аккаунту/установке; «Для отслеживания» = нет для всех.

| Категория App Store | Тип | Собираем | Связано с личностью | Цели | Доказательства |
|---|---|---|---|---|---|
| Контактная информация | Адрес e-mail | да | да | функциональность приложения | `server/app/auth/otp_api.py`, `email.py`; таблица `auth_identities` (`db/migrations/0006_accounts.sql`) |
| Контактная информация | Номер телефона | да | да | функциональность приложения | `server/app/auth/sms.py`, `otp_api.py`; `auth_identities`, `otp_codes` (хранится хэш адресата `destination_hash`) |
| Геопозиция | Точная геопозиция | да (только по действию пользователя) | да (отметки «я здесь» и отчёты) | функциональность приложения | iOS: `ios/Jol/Features/Directions/LocationProvider.swift`, `DirectionsModel.swift` → `POST /v1/directions {from, to_place_id}` (`server/app/routing/api.py`). Отметка/отчёт: `POST /v1/places/{id}/checkin`, `/crowd` с `lat, lon` → `place_crowd_reports` (`0021_crowd.sql`, `server/app/crowd/api.py`) |
| Пользовательский контент | Другой пользовательский контент | да | да | функциональность приложения | чат: `POST /v1/chats/{id}/messages`, таблицы чатов `0009_chats.sql`; память `0016_user_memory_notes.sql`; отзывы/меню/цены/транспорт `POST /v1/submissions` (`server/app/submissions/api.py`, `0018_submissions.sql`). Гостевой чат на сервере **не пишется**: `server/app/chat` (гостевой путь), комментарий в `0025_rate_limits.sql` |
| Пользовательский контент | Фото или видео | да (при отправке фото места) | да | функциональность приложения | `POST /v1/uploads` → S3 по presigned URL (`server/app/submissions/api.py`); клиент снимает EXIF/GPS (Ш-44, iOS — в другой ветке); `NSPhotoLibraryUsageDescription` |
| Идентификаторы | ID пользователя | да | да | функциональность приложения, аналитика | `users.id`; `analytics_events.user_id` (`0024_analytics.sql`); при удалении аккаунта обнуляется (`analytics.anonymize_user`) |
| Идентификаторы | ID устройства (идентификатор установки + токен APNs) | да | да | функциональность приложения, аналитика | `ios/Jol/Core/InstallID.swift` → заголовок `X-Install-ID`; `POST /v1/devices` (`server/app/devices/api.py`, таблица `devices`); `analytics_events.install_id`. Это **не** IDFA/IDFV |
| Данные об использовании | Взаимодействие с продуктом | да | да | аналитика | `POST /v1/analytics/events` (`server/app/analytics/api.py`), события `app_install`, `app_launch`, `directions_start` + серверные `sign_in`, `route_created`, `place_shown`, `trip_downloaded` (`events.py`); свойства — только версия, язык, режим транспорта. Клиент аналитики (Ш-50) — в другой ветке |
| Покупки / Финансовая информация | — | нет | — | — | оплаты в приложении нет (SSOT §9, §16.7); брони — только данные заказа (`bookings.payload`) → это «Другой пользовательский контент» |
| Диагностика | Сбои, производительность | **нет** в коде | — | — | нет SDK краш-репортов в iOS; если добавится Sentry и т. п. — обновить. Серверные логи и мониторинг (`server/app/observability.py`) относятся к серверу |
| Здоровье, финансы, контакты, история поиска/просмотров, чувствительные данные | — | нет | — | — | в коде отсутствуют |
| Имя | — | нет | — | — | профиль без имени |

Примечание про IP: сервер читает IP (`server/app/clientip.py`) только для лимитов запросов и хранит
**sha256-хэш** (`rate_limit_hits.key_hash`, `otp_codes.ip_hash`). В App Store Connect это отдельно
не декларируется, но указано в политике конфиденциальности.

## 3. API с «обоснованием причины» (Privacy Manifest)

| API | Где в коде | Причина |
|---|---|---|
| `UserDefaults` | `ios/Jol/Core/InstallID.swift`, `Localization/AppLanguage.swift`, `App/AppContainer.swift` | `CA92.1` (доступ к собственным настройкам приложения) |
| Метки времени файлов, свободное место на диске, системное время работы, активные клавиатуры | не используются (поиск по `ios/Jol`: `FileManager`, `attributesOfItem`, `resourceValues`, `systemUptime`, `systemFreeSize`, `mach_`, `@AppStorage` — 0 совпадений) | — |

При добавлении Ш-42 (скачанный маршрут на устройстве, файлы) и Ш-40/50 — перепроверить на
`FileManager`/метки времени (категория `FileTimestamp`, причины `C617.1`/`0A2A.1`) и `DiskSpace`.

## 4. Разрешения (Info.plist) — RU + EN

| Ключ | Где текст | RU | EN |
|---|---|---|---|
| `NSLocationWhenInUseUsageDescription` | `ios/Jol/Info.plist`, `Resources/InfoPlist.xcstrings` | да | да |
| `NSPhotoLibraryUsageDescription` (Ш-44; добавлен заранее — `PhotosPicker` строго его не требует) | то же | да | да |
| Уведомления | ключа в Info.plist нет: системный запрос `UNUserNotificationCenter.requestAuthorization` с текстом-подготовкой в приложении (Ш-40, в другой ветке) | — | — |

Автотест `SidebarAndLegalTests.testEveryPermissionStringExistsInRussianAndEnglish` проверяет, что
каждый `NS…UsageDescription` есть и для `ru`, и для `en`.

## 5. Что решить владельцу до отправки

1. Где хранятся данные (закон РК о ПДн; Ш-51) — влияет на политику и на ответы о передаче данных.
2. Провайдеры LLM / SMS / e-mail — это обработчики данных; указать в политике.
3. Реальный URL политики конфиденциальности: сейчас заглушка `https://jol.kz/privacy`
   (`ios/Config.xcconfig` → `JOL_PRIVACY_URL`); сайта может не быть.
4. Исходная точка `POST /v1/directions` на сервере не сохраняется (`server/app/routing/api.py`: нет записи в БД, только лог ошибки без координат) — по правилам Apple это обработка в реальном времени, но точная геопозиция всё равно декларируется из-за отметок. Если появятся логи запросов с телом — пересмотреть.
5. Sign in with Apple (Ш-26) — когда включится, добавить «Идентификаторы → ID пользователя» (уже учтён) и
   ссылку на отзыв токена при удалении аккаунта (уже реализовано на сервере, `accounts.py`).
