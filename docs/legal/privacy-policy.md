# Политика конфиденциальности Jol / Jol Privacy Policy

> **ЧЕРНОВИК. Требует проверки владельцем и юристом до публикации.** Составлен по тому, что код
> реально собирает (см. `docs/legal/app-privacy.md`). Открытые вопросы владельца, которые меняют
> текст: (1) где хранятся персональные данные — закон РК о персональных данных может требовать
> хранения данных граждан РК на серверах в Казахстане (Ш-51); (2) выбор провайдеров LLM, SMS и
> e-mail (они становятся «обработчиками данных»); (3) название юрлица-оператора и контакт.
> Места, помеченные `[ЗАПОЛНИТЬ]`, — не заполнены.
>
> **DRAFT. Needs review by the owner and a lawyer before publication.** Open owner questions that
> change the text: data residency (Kazakhstan personal-data law), the choice of LLM / SMS / e-mail
> providers, the operator's legal name and contact. Items marked `[FILL IN]` are blank.

Дата редакции / Last updated: 2026-11-21 (черновик / draft)

---

## Русский

### 1. Кто мы
Jol — мобильное приложение для путешествий по Казахстану. Оператор данных: `[ЗАПОЛНИТЬ: юрлицо,
адрес]`. Контакт по вопросам данных: `[ЗАПОЛНИТЬ: e-mail]`.

### 2. Какие данные мы получаем

| Данные | Когда | Зачем |
|---|---|---|
| E-mail или номер телефона | при входе (одноразовый код) | войти в аккаунт, отправить код |
| Идентификатор аккаунта (Sign in with Apple — когда будет включён) | при входе | войти в аккаунт |
| Геопозиция (точные координаты) | только когда вы просите маршрут «Как добраться» или отмечаетесь в месте, и вы разрешили доступ | построить маршрут от вашей позиции; отметка «я здесь» и отчёты «людно/пусто» |
| Содержимое чата с ИИ | когда вы пишете в чат | построить маршрут. Чат гостя на сервере **не сохраняется**; чат зарегистрированного пользователя сохраняется (история, память) |
| Предпочтения поездки: даты, бюджет, жильё, пожелания, темп, отношение к людям | в чате | построить персональный маршрут |
| Маршруты, избранное, что вы убрали из маршрута | при использовании | показать маршруты, учитывать ваши вкусы («память») |
| Ваш вклад: отзывы, меню, фото, цены, данные о транспорте | когда вы их отправляете | показать другим путешественникам; начислить бонусы |
| Фото, которые вы отправляете | когда вы выбираете их | публикация у места. С фото **удаляются данные о местоположении (EXIF)** до загрузки |
| Идентификатор установки (случайный UUID) и токен push-уведомлений | при запуске / если разрешите уведомления | ограничение нагрузки, доставка уведомлений о ваших поездках |
| Технические события: установка, запуск, начало маршрута, вход, показанные места | при использовании | статистика использования приложения. События содержат только версию приложения, язык, способ транспорта |
| Бронирования | когда вы бронируете | передать запрос партнёру |
| IP-адрес | при запросах к серверу | защита от злоупотреблений: хранится только необратимый хэш, на ограниченное время |

Мы **не** продаём данные, **не** используем их для рекламы и **не** отслеживаем вас между
приложениями и сайтами других компаний. Рекламных SDK в приложении нет.

### 3. Кому передаём
- **Партнёры (заведения, отели)** — только данные брони, которую вы сами отправили.
- **Провайдеры инфраструктуры** — хостинг, база данных, хранилище фото `[ЗАПОЛНИТЬ: провайдеры, страна]`.
- **Провайдер ИИ (LLM)** — текст вашего сообщения для ответа `[ЗАПОЛНИТЬ: провайдер, страна]`.
- **Провайдеры SMS и e-mail** — номер/адрес и код `[ЗАПОЛНИТЬ]`.
- **Apple** — push-уведомления (APNs), вход через Apple.
- **Open-Meteo.com** — прогноз погоды по координатам места маршрута (не по вашей позиции).
- Карта: тайлы OpenStreetMap загружаются с нашего сервера `[ЗАПОЛНИТЬ: хост]`.

### 4. Срок хранения
Данные аккаунта — пока он существует. Статистические события и запросы-счётчики — ограниченное
время `[ЗАПОЛНИТЬ: срок]`. Отчёты о загруженности — по окну давности.

### 5. Ваши права и удаление аккаунта
В приложении: Профиль → «Удалить аккаунт». Удаляются все ваши персональные данные: профиль,
чаты, память, маршруты, избранное, брони. Опубликованные вами отзывы и фото мест остаются без указания автора; статистические события теряют связь с вами.
После удаления можно зарегистрироваться заново. Вопросы и запросы на доступ к данным —
`[ЗАПОЛНИТЬ: e-mail]`.

### 6. Дети
Приложение не предназначено для детей младше `[ЗАПОЛНИТЬ: возраст]`.

### 7. Изменения
О существенных изменениях сообщим в приложении.

### 8. Источники данных
© участники OpenStreetMap (ODbL, openstreetmap.org/copyright). Погода: Open-Meteo.com, CC BY 4.0.

---

## English

### 1. Who we are
Jol is a mobile app for travelling in Kazakhstan. Data controller: `[FILL IN: legal entity,
address]`. Contact for data questions: `[FILL IN: e-mail]`.

### 2. Data we receive

| Data | When | Why |
|---|---|---|
| E-mail or phone number | sign-in (one-time code) | sign you in, send the code |
| Account identifier (Sign in with Apple, once enabled) | sign-in | sign you in |
| Precise location | only when you ask for directions or check in at a place, and you allowed access | build a route from your position; "I am here" check-ins and "busy/quiet" reports |
| AI chat content | when you write in the chat | build the route. A guest chat is **not stored** on the server; a signed-in user's chat is stored (history, memory) |
| Trip preferences: dates, budget, accommodation, wishes, pace, crowd tolerance | in the chat | build a personal route |
| Routes, favourites, places you removed from a route | in use | show your routes, learn your taste ("memory") |
| Your contributions: reviews, menus, photos, prices, transport data | when you send them | show to other travellers; award bonuses |
| Photos you upload | when you choose them | published on the place. Location metadata (**EXIF**) is **removed** before upload |
| Install identifier (random UUID) and push token | at launch / if you allow notifications | rate limiting, delivering notifications about your trips |
| Technical events: install, launch, directions started, sign-in, places shown | in use | usage statistics. Events carry only app version, language, transport mode |
| Bookings | when you book | pass the request to the partner |
| IP address | on server requests | abuse protection: only an irreversible hash is kept, for a limited time |

We do **not** sell data, do **not** use it for advertising and do **not** track you across other
companies' apps and websites. The app contains no advertising SDKs.

### 3. Who receives it
- **Partners (venues, hotels)** — only the booking you submitted.
- **Infrastructure providers** — hosting, database, photo storage `[FILL IN: providers, country]`.
- **AI (LLM) provider** — the text of your message to produce a reply `[FILL IN: provider, country]`.
- **SMS and e-mail providers** — the number/address and the code `[FILL IN]`.
- **Apple** — push notifications (APNs), Sign in with Apple.
- **Open-Meteo.com** — weather forecast for the coordinates of route places (not your position).
- Map: OpenStreetMap tiles are served from our server `[FILL IN: host]`.

### 4. Retention
Account data — while the account exists. Statistics events and rate-limit counters — for a
limited time `[FILL IN: period]`. Crowd reports — within a recency window.

### 5. Your rights and account deletion
In the app: Profile → "Delete account". All your personal data is deleted: profile, chats,
memory, trips, favourites, bookings. Published reviews and place photos you contributed stay without an author; statistics events lose their link to you. You can
register again afterwards. Data access requests: `[FILL IN: e-mail]`.

### 6. Children
The app is not intended for children under `[FILL IN: age]`.

### 7. Changes
We will notify you in the app about material changes.

### 8. Data sources
© OpenStreetMap contributors (ODbL, openstreetmap.org/copyright). Weather: Open-Meteo.com, CC BY 4.0.
