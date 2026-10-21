# Ход StarFlow

Каркас, сессия и локальный расчёт исполняются. Публичный запуск закрыт: лицензия Swiss Ephemeris не выбрана. Прогнозы, счета Stars, диалог помощника и админка не собраны.

## Этапы

| Этап | Статус | Содержание |
| --- | --- | --- |
| 0. Документы и правила | сделано | `idea.md`, `conventions.md`, `rules.md`, `workflow.md`, `.cursor/rules/starflow.mdc`, `docs/DECISIONS.md`, `docs/PROGRESS.md` |
| 1. Каркас | сделано | ASGI, polling/webhook, миграции, UoW, OpenAPI-клиент, образ, smoke-тесты |
| 2. Сессия и профиль | сделано | cookie-сессия, черновик, бот, тексты, Playwright |
| 3. Эфемериды | расчёт есть, запуск закрыт | `pyswisseph` 2.10.3.2, только `FLG_MOSEPH`, без `.se1`; AGPL или профессиональная лицензия не выбраны |
| 4. Бесплатный контур | не начат | квота совместимости и небо дня есть; тексты дня, недели, совета и Луны нет |
| 5. Подписка и подарки | не начат | YAML цены читается, счёт Stars не выставляется и оплата premium не проводится |
| 6. Premium-контент | не начат | карта и paywall есть; тексты прогнозов, тем, календаря и синастрии нет |
| 7. Помощник и ретро | не начат | окно вопросов считается, диалога и вызова модели нет |
| 8. Удержание | не начат | лимит избранного есть; рефералы, оценки, streak и share нет |
| 9. Админ и приёмка | не начат | аудит и админка; Playwright онбординга уже есть в срезе 2 |

## Проверки 2026-10-21

Команды запускались из корня репозитория, frontend-команды — из `frontend/`. Коды выхода записаны по факту.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations` | 0 |
| `uv run ruff format --check src tests migrations` | 0 |
| `uv run mypy` | 0, 46 файлов |
| `uv run pytest` | 0, 20 тестов |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 1 тест Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm openapi:check` | 0, diff пустой |
| `docker build -t starflow:skeleton .` | 0, повторная сборка после правки планировщика тоже 0 |

`pytest` включает testcontainers `postgres:16`: миграция с пустой базы, downgrade/upgrade, репозитории, уникальный `charge_id`, каскад удаления и сохранение charge/order, HTTP smoke. `APP_ENV=test` использует сессию, которая поднимает `TelegramNetworkError` и не возвращает успешный ответ Telegram.

Образ `starflow:skeleton`: пользователь `starflow`, uid 10001, entrypoint `/entrypoint.sh`, порт 8000, `--workers 1`, внутри есть `static/logo.png`, `frontend/dist/index.html` и строка `outbox_tick_failed`. Тег `ghcr.io/astral-sh/uv:0.9.5` скачался. `pnpm@10.18.0` в стадии frontend собрал клиент, postinstall `esbuild` завершился. `docker compose up` не запускался: `env_file: .env` — файл секретов пользователя, а `APP_ENV=local` открыл бы живой polling Telegram.

Локальный процесс на `127.0.0.1:8765` с `APP_ENV=test` и `SINGLETON_LOCK=false`:

- страница `/` открылась, кнопка «проверить связь» запросила `/api/v1/meta`;
- текст стал «сервис отвечает. premium, звёзд: 250», дисклеймер остался строчным, логотип отрисовался из `/logo.png`;
- `/api/v1/missing` — 404 `application/json`, не HTML;
- `/assets/missing.js` — 404 `text/plain`;
- `/reading` — 200 `text/html`;
- `/logo.png` — 200 `image/png`;
- `/liveness` — 200 `{"status":"live"}`;
- `/health` — 200 `{"status":"ready"}`, потому что PostgreSQL на `127.0.0.1:5432` принял `SELECT 1`. Это не контейнер compose. Следующий tick планировщика получил `UndefinedTableError`: таблицы `notification_outbox` в той базе нет. Миграции этим процессом не применялись. Процесс остановлен. После этого tick логирует только имя исключения.

Контраст, посчитанный ранее и не менянный: `#b8b8b8` на `#f5f0f0` — 1.757:1; `#9b2d30` на `#f5f0f0` — 6.617:1. Соответствие WCAG не заявляется.

Шрифт `Google Sans` в CSS указан, файлы OFL в репозиторий не положены. Требование к шрифту не выполнено.

Эфемериды не считаются. `pyswisseph` нет в зависимостях. Выбор AGPL или профессиональной лицензии не сделан.

Живые Telegram, DeepSeek и Nominatim не вызывались. Имена моделей в `.env.example` — `deepseek-flash` и `deepseek-v4-pro` по записи D-018. Playwright в этом прогоне каркаса не запускался.

## Проверки среза 2, 2026-10-21

Команды ниже запускались после сессии, онбординга и бота. Коды выхода записаны по факту.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations scripts` | 0 |
| `uv run ruff format --check src tests migrations scripts` | 0 |
| `uv run mypy` | 0, 57 файлов |
| `uv run pytest` | 0, 26 тестов |
| `corepack pnpm texts:check` | 0 |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 2 теста Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm openapi:check` | 0, diff пустой |
| `corepack pnpm e2e` | 0, 1 тест Playwright |

`pytest` снова поднимал testcontainers `postgres:16`. Новые проверки: подпись и окно `auth_date`, повторный обмен одной `initData`, cookie `HttpOnly`, отказ без `X-Starflow-Request`, чужие история, сообщение и заказ, `user_id` в query не даёт чужую запись, admin только для id из `ADMIN_IDS`, `APP_ENV=test` не принимает dev-auth, `APP_ENV=local` с флагом принимает, production-настройки с флагом не создаются, черновик имени `Мария` восстанавливается, плохая дата даёт поле ошибки, дата `02.01.1990` и «не знаю» приводят к календарной подписи `козерог`, стартовый параметр `Gift_1` сохраняется и premium не включает.

Playwright шёл против собранного `frontend/dist` и временного Postgres. Мост Telegram подставлялся только в браузере теста, скрипт `telegram-web-app.js` перехватывался и не затирал мост. Сценарий: приветствие, имя `Мария`, дата `32.13.1990` с ошибкой, назад с тем же именем, `02.01.1990`, «не знаю», `Europe/Moscow`, заголовок «Мария, ваш знак» и текст `козерог`. Время теста 1.1 с, весь прогон с сервером 9.8 с.

Вне Telegram `vite preview` на `http://127.0.0.1:4174`: `/`, `/profile` и `/help` показывают «откройте starflow в telegram» и не рисуют форму. Процесс preview остановлен.

Живые Telegram, DeepSeek и Nominatim этим срезом не вызывались. Шрифт `Google Sans` по-прежнему не положен в репозиторий. `pyswisseph` не установлен. Соответствие WCAG не заявляется. `docker compose up` не запускался.

## Проверки среза расчёта и доступа, 2026-10-21

Команды ниже запускались после домена, эфемерид, квот и страницы карты. Коды выхода записаны по факту.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations scripts` | 0 |
| `uv run ruff format --check src tests migrations scripts` | 0, 83 файла |
| `uv run mypy` | 0, 67 файлов |
| `uv run pytest` | 0, 42 теста |
| `corepack pnpm texts:check` | 0 |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 4 теста Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm openapi:check` | 0, diff пустой |
| `corepack pnpm e2e` | 0, 1 тест Playwright, сценарий 759 мс, прогон 7.1 с |
| `docker build -t starflow:domain .` | первый прогон 1: в стадии зависимостей не было `g++` |
| `docker build -t starflow:domain .` | повтор после `g++` — 0 |

`pytest` поднимал testcontainers `postgres:16`. Новые проверки: границы календарных знаков и деканы, пропуск и перекрытие DST в `Europe/Berlin`, неизвестное время без домов и точной луны, полные данные с эфемеридным Солнцем и paywall без углов, долгота Солнца `280.36891967534325` на `2000-01-01 12:00 UTC`, дома Плацидуса и лунный день 24 для Москвы, кэш и пауза геокодера, независимые источники premium и grace только у `subscription`, новое окно вопросов после нового гранта, сброс совместимости в понедельник, конкурентный резерв с одним списанием, отказ доставки без списания, HTTP-ключ избранного и совместимости, preview карты без записи квоты, одно небо на дату, сброс снимка карты при смене даты рождения.

Playwright после онбординга открывает «карта»: видно «время рождения неизвестно», «точный лунный знак не определён» и заголовок «этот разбор в premium». Роли `alert` нет.

Образ `starflow:domain`: внутри `python` на теории Мошье даёт ту же долготу Солнца `280.36891967534325`. `g++` в рантайме нет, пользователь `starflow` uid 10001. Файлы `.se1` в образ не клались. `docker compose up` не запускался.

Выбор AGPL на весь сервис или профессиональной лицензии не сделан. Публичный запуск закрыт. Шрифт `Google Sans` в репозиторий не положен. Соответствие WCAG не заявляется. Живые Telegram, DeepSeek и Nominatim не вызывались.

## Шрифт, 2026-10-21

В `static/font` лежат `GoogleSans-VariableFont_GRAD,opsz,wght.ttf` и `GoogleSans-Italic-VariableFont_GRAD,opsz,wght.ttf`. Таблица `name`: семейство `Google Sans`, версия `13.002`, copyright `Copyright 2025 The Google Sans Project Authors`, лицензия SIL OFL 1.1. Оси файла: `wght` 400–700, `opsz` 17–18. Рядом положены `OFL.txt` и `TRADEMARKS.md` из `ofl/googlesans`; первая строка лицензии совпадает с copyright бинарника.

`corepack pnpm build` в `frontend` завершился с кодом 0. В `frontend/dist/assets` попали оба файла: прямой `GoogleSans-VariableFont_GRAD_opsz_wght-DbREwBL3.ttf` и курсив `GoogleSans-Italic-VariableFont_GRAD_opsz_wght-Cm3YjXPr.ttf`.

`vite preview` на `http://127.0.0.1:4174`: на `/` у `body` вычисленный шрифт `"Google Sans", sans-serif`, вес 400, размер 16px; у заголовка вес 500. `document.fonts` отмечает прямое начертание как `loaded`, `check('400 16px "Google Sans"')` и `check('500 28px "Google Sans"')` истинны. Браузер запросил `GoogleSans-VariableFont_GRAD_opsz_wght-DbREwBL3.ttf`, 4785996 байт. На `/profile` то же семейство и тот же файл. На `/chart` вне Telegram тот же экран «откройте starflow в telegram»; после запроса курсива `italic 400 16px "Google Sans"` загрузился и второй файл, `GoogleSans-Italic-VariableFont_GRAD_opsz_wght-Cm3YjXPr.ttf`. Preview остановлен. Образ Docker этой проверкой не пересобирался.

## Экран, 2026-10-21

Кружок убран с кнопок действий. Вопрос про часовой пояс убран из онбординга: пояс пишется вместе со временем рождения, источник — пояс устройства или `Europe/Moscow`. Кнопка «проверить связь» и её статусы убраны. Загрузка сессии и карты — логотип по центру и строка «загрузка». Главный экран — шесть квадратных плиток по две в ряд и круг профиля справа сверху. Профиль редактирует имя, дату и время.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по изменённым Python-файлам | 0 |
| `uv run ruff format` по тем же файлам | 0, файлы без правок |
| `uv run mypy` по `profile.py`, `onboarding.py`, `bootstrap.py` | 0 |
| `uv run pytest tests/unit/test_onboarding.py tests/integration/test_database.py` | 0, 9 тестов |
| `corepack pnpm texts` | 0 |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 4 теста Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 2.1 с, прогон 9.5 с |

Playwright проходит онбординг без шага пояса и открывает «карта» кнопкой плитки. Снимок главного экрана: заголовок «Мария, ваш знак», круг «М» справа, плитки карта, настройки, premium, справка, условия, поддержка платежей. Снимок профиля: имя, дата, время, «не знаю», «сохранить», «удалить данные», «назад».

## Ответ бота и подчёркивание, 2026-10-21

`text-decoration: none` стоит на всех элементах страницы. Произвольный текст боту вызывает тот же ответ, что `/start`: при заданном `MINI_APP_URL` это кнопка `web_app`, без адреса — инструкция, где кнопка появится.

| Команда | Код |
| --- | --- |
| `uv run ruff check src/starflow/bot/handlers.py tests/unit/test_bot_reply.py` | 0 |
| `uv run ruff format` по тем же файлам | 0, файлы без правок |
| `uv run pytest tests/unit/test_bot_reply.py` | 0, 2 теста |
| `corepack pnpm texts` | 0 |

Живой чат Telegram этой проверкой не открывался.

## Главный экран и профиль, 2026-10-21

Кнопка «не знаю» убрана из профиля: пустое время рождения сохраняется как неизвестное. На главном экране нет заголовка и пояснения, одна из десяти фраз сменяется по кругу. Слева шарик со знаком, справа шарик профиля. Плитки с цветными emoji. Верхний отступ страницы не меньше 52px. На загрузке логотип пульсирует, у слова «загрузка» точки идут 1 → 2 → 3.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 4 теста Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 897 мс, прогон 6.3 с |

Проверка в браузере Playwright, 390×844, против временного сервера на `127.0.0.1:4173`. На загрузке `animation-name: logo-pulse`, масштаб около 1.12, текст сменился с «загрузка..» на «загрузка...». На главном экране нет `h1`, `padding-top` у `body` 52px, шрифт emoji `Apple Color Emoji`, знак «козерог», фраза сменилась с «что подскажет ваша карта?» на «звёзды уже на местах». В профиле кнопки «не знаю» нет, поле времени пустое. Сервер проверки остановлен. Живой Telegram не открывался.

## Свайп, плашка и капсула, 2026-10-21

Свайп от левого края вправо возвращает предыдущий экран и с главной приложение не закрывает. Плашка развлекательного материала стоит только внизу главной, 12px, `#b8b8b8`. Знак без своего круга лежит в серой капсуле слева от круга профиля. «удалить данные» прижата к низу профиля: белая, с красной обводкой и красным текстом; при наведении заливка красная, текст светлый.

| Команда | Код |
| --- | --- |
| `corepack pnpm test` | 0, 6 тестов Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm exec playwright install chromium` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 1.7 с, прогон 9.7 с |

E2e проходит онбординг, проверяет, что знак левее круга профиля, открывает карту без плашки, свайпом возвращается на главную, в профиле видит «удалить данные» ниже «сохранить» и смену цветов при наведении, затем свайпом снова на главную. На 390×844 низ плашки на 828px из 844, низ кнопки удаления тоже на 828px. Капсула справа, фон `rgb(184, 184, 184)`. Живой Telegram не открывался.

## Следующий этап

Тексты бесплатного контура. Перед ними нужно отдельное решение о лицензии Swiss Ephemeris, если расчёт пойдёт в публичный сервис.
