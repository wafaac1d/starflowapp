# Ход StarFlow

Каркас, сессия, локальный расчёт, premium-разборы, диалог помощника, уведомления и страница админа исполняются в коде. Публичный запуск закрыт: лицензия Swiss Ephemeris не выбрана. Живой DeepSeek, живой платёж Stars и живая отправка Telegram не проверялись. Ретроспектива периода подписки не собрана.

## Этапы

| Этап | Статус | Содержание |
| --- | --- | --- |
| 0. Документы и правила | сделано | `idea.md`, `conventions.md`, `rules.md`, `workflow.md`, `.cursor/rules/starflow.mdc`, `docs/DECISIONS.md`, `docs/PROGRESS.md` |
| 1. Каркас | сделано | ASGI, polling/webhook, миграции, UoW, OpenAPI-клиент, образ, smoke-тесты |
| 2. Сессия и профиль | сделано | cookie-сессия, черновик, бот, тексты, Playwright |
| 3. Эфемериды | расчёт есть, запуск закрыт | `pyswisseph` 2.10.3.2, только `FLG_MOSEPH`, без `.se1`; AGPL или профессиональная лицензия не выбраны |
| 4. Бесплатный контур | не начат | квота совместимости и небо дня есть; тексты дня, недели, совета и Луны нет |
| 5. Подписка и подарки | код есть, живой платёж не проверялся | invoice link, `openInvoice`, `successful_payment`, подарок, пробный период, возврат |
| 6. Premium-контент | код есть, живой DeepSeek не вызывался | сегодня/завтра, персональные день/неделя/месяц, четыре темы, разделы карты, календарь, синастрия с согласием |
| 7. Помощник и ретро | диалог есть, ретроспектива не начата | 20 вопросов на период, история на сервере; отказ вне темы и injection без списания |
| 8. Удержание | код есть, живая рассылка не проверялась | рефералы, streak, слоты уведомлений, outbox и прогрев кэша; share нет |
| 9. Админ и приёмка | страница есть, публичная приёмка не начата | сводка, выдача и возврат с подтверждением; команды бота не заменяют страницу |

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

## Повторная проверка домена и доступа, 2026-10-21

Код среза не менялся. Прогон подтвердил, что расчёт, квоты и экран карты живы после правок интерфейса.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations scripts` | 0 |
| `uv run ruff format --check src tests migrations scripts` | 0, 84 файла |
| `uv run mypy` | 0, 67 файлов |
| `uv run pytest` | 0, 44 теста, 10.85 с |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 6 тестов Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 1.3 с, прогон 6.6 с |

Образ Docker этим прогоном не пересобирался. Выбор лицензии Swiss Ephemeris не сделан. Живые Telegram, DeepSeek и Nominatim не вызывались.

## Бесплатные тексты и общий кэш, 2026-10-21

День, неделя, совет, луна и совместимость идут через `POST /readings/{kind}` и опрос `GET`. Общий кэш хранит репрезентативные факты сегмента. Имя подставляется после чтения. Ошибка модели показывает запасной текст и не списывает квоту совместимости. История, избранное, близкие, оценка SVG, серия и ссылка приглашения открыты из главной. Награда реферала не начисляется.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations scripts` | 0 |
| `uv run ruff format --check src tests migrations scripts` | 0, 94 файла |
| `uv run mypy` | 0, 75 файлов |
| `uv run pytest` | 0, 55 тестов, 9.14 с |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 8 тестов Vitest |
| `corepack pnpm openapi:check` | 0 |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 3.2 с, прогон 7.6 с |

E2e после онбординга открывает «сегодня». На живом ключе теста модель не отвечает, экран показывает запасной текст строчными буквами, `text-transform: none`. В странице нет `TESTTOKEN` и `initData`. Vitest отдельно проверяет загрузку, ошибку с новым ключом повтора и fallback без HTML. Живой DeepSeek и Telegram не вызывались. Образ Docker не пересобирался. Лицензия Swiss Ephemeris не выбрана.

## Шапка, фраза и загрузка, 2026-10-21

Слово «загрузка» стоит по центру, точки не сдвигают его. Фраза на главной держится 10 секунд и сменяется за 1.4 с. Капсула знака, профиля и отметки плана стоит по центру шапки. Бесплатный план — 🆓, premium — ✨.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 8 тестов Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 3.3 с, прогон 8.7 с |

E2e держит сессию и сверяет центр слова «загрузка» с центром логотипа. На главной капсула по центру `main`, знак левее круга профиля, отметка «бесплатная» правее круга и внутри капсулы. Живой Telegram не открывался.

## Стартовый экран и анкета, 2026-10-21

Первый экран — логотип, кнопка «начать» и серые фразы внизу. Анкета без карточки, текст слева. У имени один заголовок с вопросительным знаком. «отмена» и «не знаю» убраны. Дата принимает только цифры, точки ставятся сами. Пустое время — неизвестное.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 9 тестов Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 3.2 с, прогон 7.4 с |

E2e проверяет центр кнопки «начать», логотип над ней, серую фразу ниже, левый текст «добро пожаловать» по центру экрана по вертикали, одну надпись имени, ввод `32131990` как `32.13.1990`, отсутствие «отмена» и «не знаю», пустое время и выход на главную. Живой Telegram не открывался.

## Stars, 2026-10-21

Счёт создаёт защищённый API и открывается через `WebApp.openInvoice`. Доступ пишет только `successful_payment`. Клиентский статус `paid` оставляет экран в ожидании, пока сервер не подтвердит charge. Подписка — XTR, пустой `provider_token`, один `LabeledPrice`, период 2592000. Подарок без `subscription_period`. Пробный период один. Отмена и возврат согласуются отдельными состояниями, не одной распределённой транзакцией. Ограничения Bot API записаны в D-043. Ручной чек-лист — `docs/PAYMENTS.md`. Живой платёж Stars не выполнялся.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations` | 0 |
| `uv run ruff format --check src tests migrations` | 0, 102 файла |
| `uv run mypy` | 0, 81 файл |
| `uv run pytest` | 0, 62 теста, 11.88 с |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 11 тестов Vitest |
| `corepack pnpm openapi:check` | 0 |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 5.5 с, прогон 16.1 с |

Автоматические тесты ходят в подменённый шлюз Telegram. E2e по-прежнему проходит онбординг и не открывает экран premium внутри Telegram. Vitest проверяет, что на экране до оплаты видны цена, 30 дней и автопродление, а статус `pending` не показывает успех. Образ Docker не пересобирался. Лицензия Swiss Ephemeris не выбрана.

## Плитки на главной, 2026-10-21

История, избранное, близкие, код приглашения, настройки, premium, справка, условия и поддержка платежей стоят в той же сетке, что день и карта: квадратная плитка и цветной emoji. Круг профиля в шапке остаётся кругом.

| Команда | Код |
| --- | --- |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 1 тест Playwright, 3.7 с, прогон 7.9 с |

E2e на главной проверяет, что «настройки» и «поддержка платежей» — плитки с emoji, затем открывает «карта». Живой Telegram не открывался.

## Роль в промптах, 2026-10-21

Во все системные промпты дня, недели, совета, луны, совместимости и помощника добавлено «ты - профессиональный астролог». Версия прогнозов поднята с 1 до 2, чтобы ключ кэша не отдавал тексты старого промпта. Ограничения развлекательного текста оставлены.

| Команда | Код |
| --- | --- |
| `uv run python -c` загрузка `forecasts.yaml` и `assistant_system.txt` | 0, фраза есть во всех шести, версия прогнозов 2 |

Живой DeepSeek не вызывался.

## Альманах, 2026-10-22

Главная, календарь и premium собраны как типографический альманах. Иконки и иллюстрация берутся из `static` и после сборки лежат в `frontend/dist`. Тёмная тема и режим «как в telegram» переключаются в настройках.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 14 тестов Vitest |
| `corepack pnpm build` | 0; в `dist` есть `logo.png`, `icons/sun.svg`, `illustrations/three-circles-cream.svg`, оба файла Google Sans |
| `corepack pnpm exec playwright install chromium` | 0 |
| `corepack pnpm e2e` | 0, 1 тест, 3.6 с, прогон 10.2 с |

Отдельный прогон Playwright на `127.0.0.1:4173` снял главную, календарь и premium. Горизонтального скролла нет на 320, 390 и 430. Иллюстрация premium загрузилась (`naturalWidth > 0`). Светлая и тёмная темы применились. Живой Telegram не открывался. Образ Docker не пересобирался.

## Иконки из `static/icons/svg`, 2026-10-22

Компонент иконки импортирует файлы из `static/icons/svg` и показывает их как изображение. CSS-маска и копия в `frontend/public/icons` больше не используются.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/components/ui/icons.test.tsx src/pages/PremiumPage.test.tsx src/App.test.tsx` | 0, 4 теста |
| `corepack pnpm build` | 0, SVG вшиты в бандл |

## Premium-разборы и диалог, 2026-10-22

Подробные сегодня и завтра, персональные периоды, четыре темы, разделы натальной карты, астрокалендарь месяца и синастрия идут через `QuotaService`. Календарный JSON без полного месяца не становится платным текстом. Синастрия требует согласие на данные близкого и пишет ограничения, если нет времени или места. Помощник хранит вопрос как введён, не склеивает его с system и не списывает попытку за off-topic, injection или негодный JSON. Чат не кэшируется. Клавиатура сдвигает поле ввода через `--keyboard-inset`.

Кэш в тестах доступа смотрит на момент сценария, а не на живые часы: срок дня `2026-10-22 03:00 UTC` к моменту прогона уже прошёл, и без этого каждый вызов снова шёл в модель.

| Команда | Код |
| --- | --- |
| `uv run ruff check src/starflow/services/forecast.py tests/integration/test_access.py` | 0 |
| `uv run ruff format --check src/starflow/services/forecast.py tests/integration/test_access.py` | 0 |
| `uv run mypy` | 0, 86 файлов |
| `uv run pytest -q` | 0, 71 тест, 13.1 с, testcontainers `postgres:16` |
| `corepack pnpm build` | 0 |
| `corepack pnpm test` | 0, 18 тестов Vitest |
| `corepack pnpm openapi:check` | 0, diff пустой |
| `corepack pnpm e2e` | первый прогон: 1 из 2 упал, локатор искал видимый текст `легенда оценок`, а это подпись списка; после правки спеки повтор 0, 2 теста, 7.4 с |

Playwright поднимает `scripts/e2e_serve.py` и подменяет `telegram-web-app.js`, сессию, помощника, `personal_day` и календарь. Онбординг и premium-путь проходят на этом фейке. Живой Telegram, живой DeepSeek и живой платёж Stars не открывались. Образ Docker не пересобирался.

## Уведомления, станции и админ, 2026-10-22

Планировщик в процессе `app` ставит аренду outbox, планирует день, луну и premium-ретро, прогревает общий кэш и чистит сроки хранения. Страницы настроек, ретро, удаления и админа есть в Mini App. Рассылка читает только кэш. Exactly-once не обещается: обрыв после send и до commit может повторить сообщение. Удаление оставляет тонкий платёжный след и не называется юридической сертификацией.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations` | 0 |
| `uv run ruff format --check src tests migrations` | 0 |
| `uv run mypy` | 0, 94 файла |
| `uv run pytest -q` | 0, 81 тест, 15.77 с, testcontainers `postgres:16` |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 22 теста Vitest |
| `corepack pnpm openapi:check` | 0, diff пустой |
| `corepack pnpm build` | 0 |

Vitest открывает настройки, проверяет 48 слотов и поле пояса без принудительного нижнего регистра, держит удаление выключенным до подтверждения и не даёт выдачу или возврат без подтверждения. Отдельный браузер против живого API не запускался. Живой Telegram, живой DeepSeek и живой платёж Stars не вызывались. Образ Docker не пересобирался.

## Образ и иконки, 2026-10-22

Стадия frontend копировала логотип и шрифт, но не `static/icons` и `static/illustrations`. Vite в образе не находил `../../../../static/icons/svg/arrow-left.svg`. В стадию сборки клиента добавлены оба каталога. Итоговый образ по-прежнему отдаёт уже собранный `frontend/dist`.

| Команда | Код |
| --- | --- |
| `docker build -t starflow:icons .` | 0, `pnpm build` в стадии frontend собрал 131 модуль |

## Цена подписки из окружения, 2026-10-22

`PREMIUM_PRICE_STARS` больше не сверяется с `plans.yaml`. Сумма подписки и подарка берётся из этой переменной, от 1 до 10000. В файле тарифа поля цены нет. Уже созданный заказ сверяет платёж со своей сохранённой суммой.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по `plans.py`, `config.py` и затронутым тестам | 0 |
| `uv run ruff format --check` по тем же файлам | 0 |
| `uv run mypy` | 0, 94 файла |
| `uv run pytest -q` | 0, 81 тест, 15.07 с, testcontainers `postgres:16` |

## Запасной текст вместо ответа модели, 2026-10-22

`deepseek-flash` думает по умолчанию, а `max_tokens` разбора короткий. Рассуждение занимает бюджет, `content` пустой, разбор становится запасным и остаётся в общем кэше до конца окна. Вызов теперь отправляет `thinking: {type: disabled}` и `reasoning_effort: none`. Строка с `source: fallback` не считается попаданием и не записывается; следующее открытие зовёт модель снова.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по клиенту, кэшу и двум тестам | 0 |
| `uv run ruff format --check` по тем же файлам | 0 |
| `uv run mypy` | 0, 94 файла |
| `uv run pytest -q tests/unit/test_readings.py tests/unit/test_contract.py` | 0, 10 тестов, 2.06 с |
| `uv run pytest -q tests/integration/test_access.py` | 0, 14 тестов, 5.27 с, testcontainers `postgres:16` |

Живой вызов DeepSeek не делался. Процесс, который уже запущен, этот код не подхватит сам.

## Цена открытого счёта и лог ошибок модели, 2026-10-22

Кнопка покупки открывала уже созданную ссылку на 250 звёзд. Неоплаченный заказ, сумма которого отличается от `PREMIUM_PRICE_STARS`, теперь получает новую ссылку на текущую цену. Платёж по старой сумме не проходит. Оплаченный заказ не меняется.

Ошибка вызова модели пишется в лог: модель, тип исключения, код статуса и короткий текст ответа API. Промпт и факты рождения в эту строку не входят. Негодный JSON и запасной разбор пишутся отдельными событиями без текста модели.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по клиенту, биллингу, прогнозу, помощнику и тестам | 0 |
| `uv run ruff format --check` по тем же файлам | 0 |
| `uv run mypy` | 0, 94 файла |
| `uv run pytest -q tests/unit/test_readings.py tests/unit/test_contract.py` | 0, 11 тестов |
| `uv run pytest -q tests/integration/test_billing.py` | 0, 6 тестов, 3.01 с, testcontainers `postgres:16` |

Живой DeepSeek и живой платёж Stars не вызывались. Уже запущенный процесс этот код не подхватит сам.

## Имя модели в запросе DeepSeek, 2026-10-22

Живой ответ API: `400`, поддерживаются только `deepseek-flash` и `deepseek-v4-pro`, а в поле `model` ушёл посторонний идентификатор из окружения. Старт теперь отклоняет любое другое имя. Запасной текст в этом случае больше не маскирует неверную настройку: процесс не поднимается, пока `DEEPSEEK_MODEL_FAST` и `DEEPSEEK_MODEL_PRO` не стоят из этой пары.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по `config.py` и `test_skeleton.py` | 0 |
| `uv run ruff format` по `config.py` | 0, файл уже был отформатирован |
| `uv run mypy` | 0, 94 файла |
| `uv run pytest -q` на два теста имён моделей | 0, 2 теста, 1.80 с |

## Шесть экранов альманаха, 2026-10-22

Профиль, прогноз, астропомощник, близкие, натальная карта и настройки собраны на тех же токенах и нижней навигации. Имя, дата, остаток вопросов и текст прогноза берутся из ответа API. Знак `static/icons/svg/natal-chart.svg` подписан как иллюстрация раздела. Отдельной иконки отправки в `static` нет, кнопка вопроса использует `arrow-right.svg`.

Снимки шести экранов сняты в Chromium на Vite, ширины 320 и 390, светлая и тёмная темы. Мост Telegram и ответы API в этом прогоне подменены. Это не файл эскиза.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 22 теста Vitest |
| `corepack pnpm build` | 0 |
| `corepack pnpm e2e` | 0, 2 теста Playwright, testcontainers `postgres:16` |

Отдельного lint-скрипта у frontend нет. Python этих экранов не менялся. Живой DeepSeek и живой платёж Stars не вызывались.

## Обсерватория по макету, 2026-10-24

Двенадцать экранов собраны по `design/mockup.jpeg`. Палитра одна, тёмная. Шрифт Google Sans не менялся. `frontend/public` удалён, Vite отдаёт корневой `static/`. Светлая палитра не задана: сегмент её запоминает и не красит экран.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 44 теста Vitest |
| `corepack pnpm exec playwright test` | 0 после обновления снимка premium; до этого 13 из 14, снимок устарел из-за вёрстки |
| `corepack pnpm build` | 0 |

`pnpm lint` — тот же `tsc --noEmit`. Живой DeepSeek и живой платёж Stars не вызывались.

## Регистр больше не принуждается, 2026-10-24

D-051 отменяет D-009 в части строчных букв. Промпты не просят нижний регистр, ответ модели не приводится к нему и не отвергается из-за прописных. Emoji по-прежнему запрещены. Версии промптов прогноза увеличены.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по затронутым файлам | 0 |
| `uv run ruff format` по `forecast.py` | 0 |
| `uv run pytest -q` на `test_skeleton`, `test_readings`, `test_contract` | 0, 26 тестов, 3.09 с |

Живой DeepSeek не вызывался.

## Сетка натальной карты, 2026-10-24

D-052. Внутренние лучи домов и аспекты рисуются по долготам поверх новой иллюстрации. Овен на картинке сверху, долгота идёт по часовой. `house_cusps` добавлен в ответ карты.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по `chart.py`, `chart_http.py`, `test_chart_access.py` | 0 |
| `uv run ruff format --check` по тем же файлам | 0 |
| `uv run mypy` по `chart.py` и `chart_http.py` | 0 |
| `uv run pytest -q` на `test_chart_access` и `test_contract` | 0, 12 тестов, 2.58 с |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 48 тестов Vitest |
| `corepack pnpm openapi:check` | 0 |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot natal" --update-snapshots` | 0, снимок `natal.png` обновлён |

Живой DeepSeek и живой платёж Stars не вызывались.

## Чат астропомощника, 2026-10-24

D-053. Один ответ больше не дублируется пузырём поверх истории. Остаток вопросов читается из `GET /api/v1/assistant/messages`, заглушка «5» убрана.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по `assistant.py` и `assistant_http.py` | 0 |
| `uv run ruff format` по тем же файлам | 0, правок нет |
| `uv run mypy` по тем же файлам | 0 |
| `uv run pytest -q` на `test_contract` | 0, 2 теста |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 48 тестов Vitest |
| `corepack pnpm openapi:check` | 0 |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "tab bar\|screenshot chat"` | 0, снимок `chat.png` переснят |

Живой DeepSeek не вызывался.

## Профиль, фигура карты и регистр промптов, 2026-10-24

D-054. «Удалить данные» стоит внизу вкладки «Профиль». Линии натальной карты соединены в замкнутую фигуру. Промпты просят обычный русский регистр, версии увеличены.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по `forecast.py` и `assistant.py` | 0 |
| `uv run ruff format` по тем же файлам | 0, правок нет |
| `uv run pytest -q` на `test_skeleton` и `test_readings` | 0, 24 теста, 2.38 с |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 48 тестов Vitest |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot natal\|screenshot profile" --update-snapshots` | 0, снимки пересняты |

Живой DeepSeek не вызывался: новый регистр ответа модели на живом ключе не проверялся.

## Отправка в чате видна сразу, 2026-10-24

D-055. Вопрос рисуется отправленным сразу, рядом стоит пузырь астропомощника с индикатором. Текст ответа занимает этот пузырь, когда POST возвращается. Если история сервера уже содержит пару, локальные пузыри уступают ей место.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 49 тестов Vitest |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx` | 0, 13 тестов |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "chat shows the sent line\|tab bar, calendar"` | 0, 2 теста |

Живой DeepSeek не вызывался. Задержку ответа в браузере держал тестовый маршрут: вопрос и индикатор видны до ответа, затем индикатор сменяется текстом.

## Отступ под шапку Telegram, 2026-10-24

D-056. Экран и таб-бар прибавляют безопасную зону устройства и зону шапки Telegram. Без этих переменных отступ макета не меняется.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "today content starts below\|screenshot today"` | 0, 2 теста |

Живой клиент Telegram на телефоне этим прогоном не открывался: зону задал тестовый маршрут, приветствие оказалось ниже суммы отступов.

## Заглавная буква в текстовках, 2026-10-24

D-057. Строки интерфейса, бота и ошибок начинаются с заглавной буквы, как и следующее предложение. Знаки и планеты на экране пишутся с заглавной при показе.

| Команда | Код |
| --- | --- |
| `uv run ruff check` по `chart_sections.py`, `forecast.py`, `assistant.py` | 0 |
| `uv run pytest -q` на `test_premium_content`, `test_billing_rules`, `test_bot_reply` | 0, 9 тестов |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm test` | 0, 49 тестов Vitest |

## Время рождения в профиле, 2026-10-24

D-058. Тумблер «Не знаю время» убран с экрана рождения. Пустое поле сохраняется как неизвестное время, заполненное — как время профиля. Готовый профиль уходит в PATCH `/profile`.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx` | 0, 15 тестов |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "profile edit saves the birth time"` | 0, 1 тест |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "onboarding leads to today"` | 0, 1 тест |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot birth" --update-snapshots` | 0, снимок `birth.png` обновлён |
| `corepack pnpm typecheck` | 0 |

## Отступ знака на профиле, 2026-10-24

Знак и дата рождения стоят сразу под именем, как на макете. Лишний верхний отступ подписи убран только у этой строки.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot profile" --update-snapshots` | 0, снимок `profile.png` обновлён |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t "links the subscription"` | 0, 1 тест |

## Совместимость без заранее сохранённого близкого, 2026-10-24

D-059. На «Сегодня» внизу кнопка «Совместимость». Экран принимает двоих сразу: себя, близкого или новые данные. Тумблер сохраняет нового человека, только если его ещё нет в списке. Пустое время сохраняется как неизвестное.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx src/calendarSign.test.ts` | 0, 18 тестов |
| `corepack pnpm typecheck` | 0 |
| `uv run ruff check` по `forecast_http.py`, `onboarding.py`, `records.py`, `sql.py`, `test_onboarding.py` | 0 |
| `uv run pytest -q tests/unit/test_onboarding.py` | 0, 6 тестов |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "today opens compatibility"` | 0, 1 тест |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot today\|screenshot compatibility" --update-snapshots` | 0, снимки `today.png` и `compatibility.png` обновлены |

## Разбор темы и Premium, 2026-10-24

D-060. Кнопки «Любовь», «Работа», «Диалог», «Эмоции» и соседние темы открывают текст разбора при Premium. Без подписки показывается сообщение, что функция только с Premium, и запрос не уходит.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx` | 0, 18 тестов |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "a free topic opens the premium alert"` | 0, 1 тест |

## Пустой чат, 2026-10-24

Если сообщений нет, по центру чата стоит короткий блок: это чат с астропомощником, можно спросить про день, карту или совместимость, ответ развлекательный.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t "draws the sent question"` | 0 |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "empty chat explains itself"` | 0 |

## Чат без Premium, 2026-10-24

D-061. Без подписки поле и кнопка отправки закрыты, запрос не уходит. Пустой чат пишет об этом в легенде. Если переписка уже есть, та же фраза стоит над полем. Старые сообщения остаются.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t "assistant reply\|sent question\|composer closed"` | 0, 3 теста |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "empty chat explains itself\|chat shows the sent line\|tab bar, calendar"` | 0, 3 теста |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot chat" --update-snapshots` | 0, снимок `chat.png` обновлён |

## Совместимость через связь со звёздами, 2026-10-27

D-062. Сначала выбираются двое, внизу «Проверить». Две секунды на экране «Связь со звёздами», затем карточки пары, схема и три строки. «Назад» возвращает к выбору. При `prefers-reduced-motion` пауза пропускается.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t "two people\|compatibility cards\|star link"` | 0, 3 теста |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "today opens compatibility\|screenshot compatibility"` | 0, 2 теста, снимок `compatibility.png` обновлён |

## Текст только после ответа, 2026-10-27

D-063. Пока чтение ждёт кэш или модель, на месте текста загрузка. Статус `ready` заполняет поле. Ошибка, обрыв и запасной текст показывают «Не удалось связаться со звёздами». Повтор того же чтения не создаёт новый вызов, пока первый не закончился: клиент опрашивает сохранённый результат.

Кэш на сервере уже отдаёт сохранённую строку до вызова модели (`ForecastService.start` читает историю, `TwoLevelCache` не вызывает генерацию при попадании). Загрузка на экране закрывает и это ожидание базы.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx src/pages/ReadingPage.test.tsx` | 0, 23 теста |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot today\|screenshot forecast\|screenshot natal\|screenshot calendar"` | 0, снимок `natal.png` обновлён: сетка рисуется после ответа карты |

## Стрелка и тема на Сегодня, 2026-10-27

D-064. Стрелка в карточке прогноза прижата к правому краю. Окно темы держит загрузку, пока модель не ответит: запасной текст больше не закрывает чтение до следующей попытки.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t "topic\|day title"` | 0, 4 теста |
| `uv run ruff check src/starflow/services/forecast.py` | 0 |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot today" --update-snapshots` | 0, снимок `today.png` обновлён |

## Поле чата на месте, 2026-10-27

D-065. Лента сообщений листается отдельно, поле ввода остаётся над таб-баром. Аватар астропомощника стоит у нижнего края сообщения.

| Команда | Код |
| --- | --- |
| `corepack pnpm typecheck` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'assistant\|question\|composer'` | 0, 3 теста |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "chat field stays\|empty chat\|screenshot chat\|sent line" --update-snapshots` | 0, 4 теста, снимок `chat.png` обновлён |

## Список людей в админке, 2026-10-27

D-066. Администратор видит открытые учётные записи и выбирает человека в выдачу Premium. В списке имя, имя Telegram, числовой id и признак Premium. Даты рождения и переписки нет.

| Команда | Код |
| --- | --- |
| `uv run ruff check src/starflow/api/ops_http.py src/starflow/services/ops.py src/starflow/repositories/sql.py src/starflow/domain/records.py` | 0 |
| `corepack pnpm exec vitest run src/pages/OpsPages.test.tsx` | 0, 5 тестов |
| `corepack pnpm typecheck` | 0 |
| `uv run pytest tests/unit/test_contract.py tests/integration/test_ops.py::test_admin_overview_hides_people_and_delete_keeps_a_thin_charge -q` | 0, 3 теста |

## Строка «Админ» на профиле, 2026-10-27

D-067. На вкладке «Профиль» строка «Админ» ведёт на `/admin`, если сессия администратора. У остальных её нет.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'subscription\|admin page'` | 0, 2 теста |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot profile"` | 0 |

## Профиль: подписка, правка и зазоры, 2026-10-27

D-068. Аватар открывает правку даты и времени. «Добавить близкого» открывает форму человека. Действующая подписка показывает возможности и оставшиеся дни. Имя, дата и предсказание раздвинуты.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'subscription\|admin page\|premium\|relative form'` | 0, 8 тестов |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot profile\|screenshot premium" --update-snapshots` | 0, снимок `profile.png` обновлён |

## Тема и зазоры настроек, 2026-10-27

D-069. По умолчанию выбрана «Тёмная». «Светлая» подменяет токены и красит экран. Тема, уведомления, время, пояс и помощь разделены зазором 24px.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'settings switch'` | 0, 1 тест |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `corepack pnpm exec playwright test e2e/observatory.spec.ts -g "screenshot settings" --update-snapshots` | 0, снимок `settings.png` обновлён |

## Запросы пары и подробный разбор карты, 2026-10-27

D-070. Строки совместимости спрашивают синастрию с целью и двумя знаками. Натальный «Разбор» при открытой карте ждёт отдельный подробный текст. Без Premium остаются более длинные подписи точек. Живой DeepSeek не вызывался.

| Команда | Код |
| --- | --- |
| `uv run ruff check src/starflow/services/forecast.py src/starflow/api/forecast_http.py src/starflow/domain/chart_sections.py tests/unit/test_readings.py tests/unit/test_premium_content.py` | 0 |
| `uv run pytest tests/unit/test_readings.py tests/unit/test_premium_content.py tests/unit/test_contract.py -q` | 0, 18 тестов |
| `node scripts/compile-texts.mjs --check` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'pair focus\|natal reading\|compatibility cards\|star link\|topic dialog\|topic text\|premium'` | 0, 10 тестов |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |

## Админ-панель только с выдачей Premium, 2026-10-27

D-071. Со страницы убраны счётчики, даты и возврат. После успешной выдачи поля очищаются, а список людей запрашивается снова. Живая сессия администратора в браузере не открывалась.

| Команда | Код |
| --- | --- |
| `node scripts/compile-texts.mjs --check` | 0 |
| `corepack pnpm exec vitest run src/pages/OpsPages.test.tsx` | 0, 5 тестов |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |

## Таблица пользователей в админке, 2026-10-27

D-072. Список людей стал таблицей. Сервер отдаёт страницу и общее число, на экране по 10 человек. Живая сессия администратора в браузере не открывалась.

| Команда | Код |
| --- | --- |
| `uv run ruff check src/starflow/repositories/sql.py src/starflow/services/ops.py src/starflow/api/ops_http.py` | 0 |
| `corepack pnpm exec vitest run src/pages/OpsPages.test.tsx` | 0, 6 тестов |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `uv run pytest tests/unit/test_contract.py::test_openapi_document_matches_the_committed_contract -q` | 0, 1 тест |
| `uv run pytest tests/integration/test_ops.py::test_admin_overview_hides_people_and_delete_keeps_a_thin_charge -q` | 0, 1 тест |

## Тема по умолчанию как в Telegram, 2026-10-27

D-073. Пустой выбор темы значит «Авто» и берёт `colorScheme` Telegram. Явный выбор «Светлая» или «Тёмная» не сбрасывается.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'settings switch'` | 0, 1 тест |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'screenshot settings'` | 1, 8130 px, ratio 0.03: выбран «Авто» |
| та же команда с `--update-snapshots` | 0, снимок `settings.png` перезаписан |

## Карта на «Сегодня», история вне профиля, избранное, 2026-10-28

D-074. На «Сегодня» кнопка «Натальная карта» открывает `/natal`. Строка «История» с профиля убрана. Избранное собрано шапкой и строками списка.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'opens today\|links the subscription\|favorites'` | 0, 4 теста |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'screenshot today\|screenshot profile\|screenshot favorites' --update-snapshots` | 0, 3 теста |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'screenshot today\|screenshot profile\|screenshot favorites\|tab bar, calendar'` | 0, 4 теста |

Живой клиент Telegram не открывался.

## Поля близкого и блик загрузки, 2026-10-28

D-075. На «Близких» строки, поля и кнопки делят зазор 24px. Силуэты загрузки переливаются.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'lists people\|row silhouettes'` | 0, 2 теста |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'adding a person'` | 0, 1 тест: зазоры 24px, у силуэтов animation-name с `skeleton-shine` |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'add relative fields\|screenshot people'` | 0, 2 теста |

Живой клиент Telegram не открывался.

## Общий зазор между блоками, 2026-10-28

D-076. Крупные блоки экрана делят зазор 24px. Списки с разделителем остаются вместе.

| Команда | Код |
| --- | --- |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'screenshot\|add relative\|adding a person' --update-snapshots` | 0, 15 тестов; перезаписаны снимки welcome, birth, today, forecast, calendar, natal, compatibility, chat, profile, premium |

Живой клиент Telegram не открывался.

## Баланс звёзд без Premium, 2026-10-28

D-077. Без подписки совместимость и натальная карта стоят 40 звёзд, вопрос астрологу — 20. Баланс пополняет только проверенный `successful_payment`. На «Сегодня» справа сверху баланс и окно 10 / 20 / 50 / 100 или своя сумма.

| Команда | Код |
| --- | --- |
| `uv run ruff check src tests migrations` | 0 |
| `uv run mypy` | 1, два старых замечания в `forecast.py` около `remember`: `dict[str, str]` против `dict[str, object]`. Новые файлы в списке нет |
| `uv run pytest tests/unit/test_star_balance.py tests/unit/test_contract.py -q` | 0, 5 тестов |
| `corepack pnpm exec tsc --noEmit --pretty false` | 0 |
| `corepack pnpm exec vitest run src/screens/screens.test.tsx -t 'opens a top-up\|asks for 40 stars\|lets a question\|shows compatibility cards\|holds the star'` | 0, 5 тестов |
| `PLAYWRIGHT_BROWSERS_PATH=…/playwright corepack pnpm exec playwright test e2e/observatory.spec.ts -g 'today content starts\|today opens compatibility\|empty chat\|screenshot today\|screenshot chat'` | 0, 5 тестов. Перезаписаны `today.png` и `chat.png` |

Живой DeepSeek, живой клиент Telegram и живой платёж Stars не проверялись. Статус окна оплаты баланс не увеличивает.

## Следующий этап

Ретроспектива периода подписки. Перед публичным запуском расчёта всё ещё нужно решение о лицензии Swiss Ephemeris. Живой чек-лист Stars из `docs/PAYMENTS.md` ещё не пройден.
