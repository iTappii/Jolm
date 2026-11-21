# Ревью Ш-52 (часть «legal / about») — О приложении, манифест приватности, черновики политики

- Дата: 2026-11-21
- Исполнитель: сабагент (Sonnet), ветка `sh-43-52-ios` (worktree)
- Итог: часть Ш-52 выполнена как **черновик**. Юридические тексты требуют проверки владельцем /
  юристом; Ш-52 в целом (скриншоты, VoiceOver, Dynamic Type, ревью Apple) **не закрыт**.

## Что сделано

- **«О приложении»** (`ios/Jol/Features/Profile/AboutScreen.swift`, вынесен из `ProfileSubscreens.swift`):
  версия и сборка; «© OpenStreetMap contributors» (ссылка на openstreetmap.org/copyright); «Map rendering by
  MapLibre Native.» (ссылка); «Weather data by Open-Meteo.com» (ссылка open-meteo.com) и «CC BY 4.0»
  (ссылка на лицензию); «Политика конфиденциальности» — ссылка из `JOL_PRIVACY_URL`
  (`Config.xcconfig` → `Info.plist` → `AppConfig.privacyPolicyURL`, только https; пусто → пункт скрыт).
  **Адрес `https://jol.kz/privacy` — заглушка**, домена может не быть.
- **`ios/Jol/PrivacyInfo.xcprivacy`**: `NSPrivacyTracking=false`; обязательная причина
  `UserDefaults` → `CA92.1`; собираемые типы: e-mail, телефон, точная геопозиция, прочий
  пользовательский контент, фото, ID пользователя, ID устройства, взаимодействие с продуктом — все
  «связано с личностью = да, для отслеживания = нет». Основания по каждому — в `docs/legal/app-privacy.md`.
- **Разрешения**: проверены все `NS…UsageDescription`: геопозиция есть в `Info.plist` и RU+EN в
  `InfoPlist.xcstrings`. Добавлен `NSPhotoLibraryUsageDescription` (RU+EN) для Ш-44. Уведомления:
  ключа в Info.plist не существует, системный запрос — в Ш-40 (другая ветка).
- **`docs/legal/privacy-policy.md`** (RU + EN, черновик, `[ЗАПОЛНИТЬ]` на неизвестном) и
  **`docs/legal/app-privacy.md`** (ответы для App Store Connect «App Privacy», таблица «тип данных →
  собираем / связано / цель → доказательства: файлы и эндпоинты», API с обоснованием, список решений владельца).
- Тесты: `SidebarAndLegalTests` — наличие каждой строки разрешения для `ru` и `en` в собранном
  бандле, содержимое манифеста, правила `JOL_PRIVACY_URL`; `HomeScreenUITests` — три ссылки на экране
  «О приложении».

## Проверки

РЕЗУЛЬТАТЫ — см. раздел «Итог прогона» в конце файла.

- Поиск required-reason API в `ios/Jol`: `FileManager`, `attributesOfItem`, `resourceValues`,
  `systemUptime`, `systemFreeSize`, `mach_`, `@AppStorage` → 0 совпадений; `UserDefaults` — 3 файла
  (`InstallID.swift`, `AppLanguage.swift`, `AppContainer.swift`).

## Замечания

| # | Важность | Замечание | Что нужно |
|---|---|---|---|
| 1 | высокая | **Локализация ПДн в РК**: где хранить данные граждан, влияет на политику и «Передачу данных» (Ш-51) | Решение владельца → SSOT |
| 2 | высокая | Нужен реальный публичный URL политики; сейчас заглушка `jol.kz/privacy` | Владелец: домен/страница; текст — из `privacy-policy.md` после проверки юристом |
| 3 | средняя | iOS-части Ш-40 (push, возможные файлы), Ш-42 (скачанный маршрут), Ш-44 (фото, EXIF), Ш-50 (аналитика) в другой ветке; манифест написан по серверу и плану | После слияния заново искать required-reason API (`FileTimestamp`, `DiskSpace`) и сверить таблицу |
| 4 | средняя | Манифест MapLibre Native 6.31.0 не проверялся (`PrivacyInfo.xcprivacy` в его пакете) | Проверить в собранном `.app` перед отправкой в ревью |
| 5 | средняя | Провайдеры LLM/SMS/e-mail не выбраны — «кому передаём» неполно | Дополнить после выбора |
| 6 | низкая | Аналитика: iOS-клиент отсутствует в ветке, ответ «Взаимодействие с продуктом» дан по серверу (`/v1/analytics/events`) | Убрать из манифеста, если клиент не будет слать события |
| 7 | низкая | Срок хранения и возрастная граница в политике не заполнены | Решение владельца |

## Итог прогона

- Те же прогоны, что в [Ш-43-ios](Ш-43-ios.md): юнит 151/151 (`SidebarAndLegalTests` 5/5: строки разрешений
  RU+EN, манифест, URL политики, форма ответов сервера); UI — `HomeScreenUITests.testProfileMenuItemsOpenForGuest`
  (ссылки `about-osm`, `about-open-meteo`, `about-privacy`, `about-version`) прошёл; `swiftlint` → 0.
- Не проверено: открытие ссылок в Safari; тёмная тема/Dynamic Type/VoiceOver на экране «О приложении»;
  сборка Release (манифест MapLibre, предупреждения Xcode о privacy manifest); юридическая корректность текстов.
