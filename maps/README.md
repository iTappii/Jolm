# maps/ — карта Jol (Ш-11, Ш-12)

Векторные тайлы OpenStreetMap (схема OpenMapTiles) → один файл `kazakhstan.pmtiles` (вся страна, ~380 МБ, z0–14; Ш-59) или `almaty.pmtiles` (только Алматы, 21 МБ) + стиль Jol для MapLibre.

## 1. Сборка тайлов (Ш-11)

```bash
./maps/build_tiles.sh        # или: make tiles — вся страна, bbox 46.4,40.5,87.4,55.5 (~1 мин)
AREA=almaty ./maps/build_tiles.sh   # или: make tiles-almaty — только Алматы
```

Что делает: скачивает выгрузку Казахстана Geofabrik (~230 МБ) в `maps/build/` (в git не попадает),
запускает Planetiler (схема OpenMapTiles, подписи `ru,en`, bbox Алматы + горы:
`76.6,42.95,77.35,43.45` — Медеу, Шымбулак, БАО, Кок-Жайляу), пишет `maps/build/almaty.pmtiles` (~22 МБ, z0–14).

- Раннер: Docker (`ghcr.io/onthegomap/planetiler`), если демон запущен, иначе `planetiler.jar` (нужна Java 21+;
  jar скачивается в `maps/build/`). Принудительно: `RUNNER=docker|jar`.
- Переменные: `BOUNDS`, `LANGS`, `REFRESH=1` (перекачать pbf), `JAVA_XMX` (по умолчанию 4g).
- Planetiler сам докачивает вспомогательные данные (Natural Earth, water polygons) в `maps/build/sources/`.
- Данные © OpenStreetMap contributors (ODbL) — атрибуция обязательна и уже есть в стиле.

## 2. Локальный просмотр (демо)

PMTiles читается HTTP Range-запросами, поэтому нужен сервер с Range. `python3 -m http.server` Range **не** умеет,
используйте:

```bash
python3 maps/serve.py 8080        # Range + CORS, раздаёт maps/
# открыть http://localhost:8080/demo/   (переключатели темы и языка подписей)
# другой файл:  /demo/?pmtiles=https://cdn.example.com/almaty.pmtiles
```

(Альтернатива при наличии Node: `npx http-server maps -p 8080 --cors`; он поддерживает Range.)
Демо использует MapLibre GL JS 4.7.1 и pmtiles 3.2.0 с unpkg.

## 3. Хостинг

Положить `almaty.pmtiles` в статический бакет/CDN (S3/R2/GCS/Nginx). Требования: `Range` -> `206`,
`Accept-Ranges: bytes`, CORS `Access-Control-Allow-Origin` + `Access-Control-Allow-Headers: Range, If-Match` +
`Access-Control-Expose-Headers: Content-Range, ETag` (для веба; нативному iOS CORS не нужен), долгий `Cache-Control`
с версией в имени файла (`almaty-2026-11.pmtiles`). Не сжимать файл на лету (тайлы уже gzip внутри).

## 4. Стили (Ш-12)

Файлы `maps/style/jol-light.json`, `jol-dark.json` (подписи ru → en → local) и `jol-light.en.json`, `jol-dark.en.json`
(подписи en → latin → local) **генерируются**: правим `maps/style/build_styles.py`, затем
`python3 maps/style/build_styles.py`.

- Палитра: спокойная подложка, акцент `#FF7A00` — маршрут и выбранные места. Дорожные классы, здания, парки,
  вода, подписи мест/улиц/пиков/POI. Слои схемы OpenMapTiles.
- **URL тайлов — заглушка:** `sources.openmaptiles.url = "pmtiles://https://tiles.example.com/almaty.pmtiles"`.
  Приложение/демо подменяет её на реальный адрес (в бандл iOS — подставлять на этапе сборки/при загрузке стиля).
  MapLibre Native поддерживает схему `pmtiles://` только в новых версиях (проверить в Ш-13 на выбранной версии;
  запасной вариант — раздавать тайлы через `/{z}/{x}/{y}.mvt` из pmtiles-сервера).
- Атрибуция: `© OpenStreetMap contributors` в `sources.openmaptiles.attribution`.
- **Язык подписей:** везде выражение
  `coalesce(get("name:ru"), get("name_ru"), get("name:en"), get("name_en"), get("name"))`. Переключение в клиенте —
  загрузить вариант стиля нужного языка (`jol-<theme>.json` для ru, `jol-<theme>.en.json` для en). Метаданные
  `metadata["jol:label-lang"]` / `["jol:theme"]` помогают определить текущий вариант. Новый язык — добавить в
  `name_expr()` и в цикл генерации.
- **Оверлей Jol:** пустые GeoJSON-источники `jol-route` (линия) и `jol-places` (точки со свойством `name`);
  приложение наполняет их через `setData`/`MLNShapeSource.shape`.
- **Glyphs (шрифты):** `https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf` (Noto Sans Regular/Bold,
  кириллица есть). **TODO: self-host** (публичный демо-сервер не для продакшена); `fonts.openmaptiles.org` больше
  не отдаёт шрифты.
- **Sprite (иконки категорий):** TODO — спрайта пока нет, слой `poi` показывает только подписи. Когда появится
  `maps/sprite/jol{,@2x}.{json,png}`, добавить `"sprite"` в генератор и `icon-image` в слой `poi`.
- Рельеф/hillshade (горы) — TODO, нужен DEM-источник.
