# Соглашения StarFlow

Этот документ задаёт устройство кода. Запреты собраны в `rules.md`. Причины развилок — в `docs/DECISIONS.md`.

## Архитектура

Один репозиторий. Один образ `app` и одна база PostgreSQL 16. В контейнере `app` работают ASGI-приложение, webhook бота, `AsyncIOScheduler` и статика Mini App.

Зависимости собираются вручную в composition root. Контейнер внедрения — обычный объект, который создаёт `bootstrap`. Репозитории снаружи описаны как `Protocol`. Сценарии получают протоколы и unit of work, а не сессию SQLAlchemy и не глобальные синглтоны.

Слои:

| Слой | Каталог | Ответственность |
| --- | --- | --- |
| Транспорт HTTP | `src/starflow/api` | Разбор запроса, вызов сценария, код ответа |
| Транспорт бота | `src/starflow/bot` | Разбор update, вызов сценария, ответ Telegram |
| Планировщик | `src/starflow/scheduler` | Запуск уже описанного сценария по расписанию |
| Сценарии | `src/starflow/services` | Правила продукта, граница транзакции, квоты |
| Домен | `src/starflow/domain` | Сущности, инварианты, чистые расчёты периода и streak |
| Данные | `src/starflow/db`, `src/starflow/repositories` | SQLAlchemy, unit of work, запросы |
| Внешние порты | `src/starflow/ai`, `src/starflow/astro`, `src/starflow/cache` | DeepSeek, чистая астрометрия, память процесса |
| Тексты | `resources/texts/ru`, `resources/prompts`, `src/starflow/i18n` | Копирайт, промпты, загрузка |
| Тарифы | `resources/plans.yaml` | Длительности и лимиты. Цена Stars — `PREMIUM_PRICE_STARS` |

Frontend живёт в `frontend/` и в рантайме является набором статических файлов. Отдельного frontend-сервиса нет.

Поток чтения: транспорт собирает DTO, сценарий открывает unit of work, репозиторий читает, домен или астроадаптер считает, сценарий возвращает DTO. Поток записи коммитит только unit of work. Вызов Telegram, DeepSeek или Nominatim выполняется до открытия записи либо после успешного коммита. Сетевой вызов внутри открытой транзакции не делается.

Повторная доставка webhook, платежа и задания планировщика безопасна. Ключ идемпотентности платежа — `telegram_payment_charge_id`. Ключ уведомления — пользователь, тип и местная дата.

Второй процесс не становится рабочей копией. На старте процесс берёт PostgreSQL advisory lock `starflow_singleton`. Если lock занят, процесс завершается с ошибкой. Production-команда ASGI запускает один worker.

## Дерево репозитория

```text
starflowapp/
  idea.md
  conventions.md
  rules.md
  workflow.md
  docs/DECISIONS.md
  docs/PROGRESS.md
  static/logo.png
  pyproject.toml
  uv.lock
  alembic.ini
  migrations/versions/
  docker-compose.yml
  Dockerfile
  resources/
    texts/ru/
    prompts/
    plans.yaml
  src/starflow/
    bootstrap.py
    asgi.py
    config.py
    logging.py
    domain/
    astro/
    ai/
    services/
    cache/
    repositories/
    db/
    api/
    bot/
    scheduler/
    i18n/
  tests/
    unit/
    integration/
  frontend/
    package.json
    pnpm-lock.yaml
    openapi.json
    index.html
    vite.config.ts
    tsconfig.json
    public/
    src/
      main.tsx
      app/
      pages/
      components/ui/
      api/
      styles/tokens.css
    e2e/
```

`static/logo.png` остаётся файлом пользователя. Сборка копирует его в `frontend/dist`, а образ `app` забирает уже собранный каталог. Код не создаёт другой логотип.

Шрифт лежит в `static/font`: оба variable-файла `Google Sans`, `OFL.txt` и `TRADEMARKS.md`. Сборка frontend забирает начертания в `frontend/dist`, а образ дополнительно копирует каталог в `/app/static/font`.

## Backend

- Python 3.12+, менеджер `uv`, lockfile `uv.lock`.
- HTTP и webhook: FastAPI на ASGI. Локальный и production-запуск — один worker.
- Бот: aiogram 3.x. По умолчанию процесс забирает update через polling. Webhook включается только непустым `WEBHOOK_URL` и тогда требует `WEBHOOK_SECRET`. Оба режима в одном процессе не работают.
- База: PostgreSQL 16, SQLAlchemy 2 async, драйвер asyncpg, миграции Alembic в каталоге `migrations`. Схема меняется только миграцией.
- Настройки: Pydantic Settings, имена переменных без префикса, как в `.env.example`. Секреты читаются из окружения и не пишутся в репозиторий, логи и `VITE_*`.
- Помощник: пакет `openai`, `base_url` и имена моделей DeepSeek только из настроек. Тексты промптов читаются из `resources/prompts/`.
- Эфемериды: порт `Ephemeris` в домене, реализация на `pyswisseph` в инфраструктуре. `kerykeion` зависимостью не становится.
- Геокодер: `geopy` и Nominatim за переключаемым базовым URL. Кэш пар «запрос → координаты и подпись» хранится в PostgreSQL. Пояс считается `timezonefinder` без сети.
- Планировщик: APScheduler 3 `AsyncIOScheduler`. Определение задания живёт в коде, долговечность рассылки — в таблице `notification_outbox`.
- Логи: structlog, одна JSON-строка на событие. В журнал не попадают токен бота, ключ DeepSeek, сырой `initData`, дата рождения и текст помощника.

Имена модулей, функций и переменных — `snake_case`. Классы и `Protocol` — `PascalCase`. Репозиторий называется по агрегату: `UserRepository`, `SubscriptionRepository`. Таблицы и колонки — `snake_case`, таблицы во множественном числе. Миграция Alembic получает осмысленный slug.

Типы публичных функций явные. `mypy` работает в strict. `Any` в рабочем коде не используется. Глобальное отключение проверки строки не используется.

Имена настроек каркаса перечислены в `.env.example`. Режим бота выводится из `WEBHOOK_URL`, отдельной переменной режима нет. Цена подписки и подарка берётся из `PREMIUM_PRICE_STARS` и в `plans.yaml` не дублируется.

## Транзакции и unit of work

`UnitOfWork` — `Protocol` с асинхронным контекстным менеджером, `commit` и `rollback`. Реализация держит одну `AsyncSession`. Репозитории этой операции получают ту же сессию через unit of work.

Коммит находится в сценарии. Репозиторий не коммитит и не открывает собственную сессию. Транспорт не коммитит.

Одна пользовательская операция — один unit of work. Чтение для HTTP GET может закончиться без коммита. Запись истечения подписки, streak, квоты помощника и платежа коммитится одним unit of work вместе с журналом изменений.

После успешного коммита сценарий может отправить сообщение Telegram. Ошибка отправки не откатывает уже сохранённый платёж: доставка повторяется планировщиком по ключу идемпотентности.

Деньги и квоты считаются в базе, сравнением и ограничением уникальности, а не только проверкой в памяти процесса.

## Контракт API

Базовый префикс — `/api/v1`. Контракт описан схемами Pydantic и публикуется как OpenAPI. TypeScript-клиент генерируется из этой схемы пакетом `openapi-typescript` и вызывается через тонкую обёртку. Ручные дубли типов ответа не ведутся.

JSON-поля — `snake_case`. Время в API — ISO-8601 с зоной. Идентификаторы — строки UUID. Telegram id на сервере берётся из сессии, выпущенной после проверки `initData`, а не из поля тела или URL.

Сессия Mini App: `POST /api/v1/session` один раз принимает `Authorization: TMA <initData>`. Сервер проверяет HMAC-SHA256 по схеме Telegram, сравнивает подпись постоянным по времени способом и отклоняет `auth_date` вне окна возраста и небольшого сдвига часов. В пределах этого окна ту же строку можно обменять снова. Ответ ставит cookie `starflow_session`. Дальше пользователя опознаёт только она. Подробности — D-026.

Ошибка:

```json
{
  "error": {
    "code": "compatibility_already_used",
    "message": "совместимость на этой неделе уже открыта"
  }
}
```

`code` стабилен и набран `snake_case`. `message` приходит из ресурса и показан пользователю как есть. Тело ошибки не содержит traceback, SQL и секретов.

Коды, которые появляются вместе с соответствующим срезом: `unauthorized`, `profile_incomplete`, `validation_error`, `not_found`, `compatibility_already_used`, `premium_required`, `assistant_quota_exhausted`, `payment_not_confirmed`, `gift_self_forbidden`, `rate_limited`.

Успешная оплата в API не принимается от клиента как флаг. Клиент только запрашивает счёт. Продление периода делает обработчик `successful_payment` после проверки payload счёта.

Статика Mini App отдаётся тем же приложением. Маршруты `/api` не перехватываются SPA-fallback. `index.html` не кэшируется надолго. Имя файла логотипа в клиенте — `/logo.png`, источник при сборке — корневой `static/logo.png`.

## Тесты backend

- `pytest`, `pytest-asyncio`, `testcontainers[postgres]`, `time-machine`.
- Доменные тесты не поднимают базу.
- Репозитории и сценарии с SQL поднимают PostgreSQL через testcontainers и применяют миграции Alembic.
- Границы суток, недели, периода подписки и streak сдвигаются `time-machine`.
- Проверка `initData` в тестах считает настоящий HMAC тестовым токеном.
- Платёжный тест передаёт в обработчик структуру подтверждённого update. Отдельной функции «сделать оплаченным» в тестовом коде нет.
- Эфемериды сверяются с контрольными положениями и допуском. Тест не подменяет результат заранее выбранным знаком без расчёта.
- Геокодер в интеграционном тесте сценария получает записанный ответ транспорта. Сценарий сохраняет координаты из этого ответа.

Команда проверки backend: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest`.

## Frontend

Менеджер пакетов — pnpm. Точная версия фиксируется полем `packageManager` в `frontend/package.json`. Lockfile — `frontend/pnpm-lock.yaml`. Установка в CI и Docker идёт с `--frozen-lockfile`.

Стек: React, TypeScript в `strict`, Vite, React Router, TanStack Query. Отдельной библиотеки компонентов с собственным визуальным языком нет.

Каталоги:

- `src/pages` — экраны и состояния экрана;
- `src/components/ui` — кнопки, поля, поверхности, типографика, иконки;
- `src/api` — сгенерированный клиент и функции запросов;
- `src/resources/ru.ts` — все авторские строки интерфейса;
- `src/styles/tokens.css` — дизайн-токены.

Компоненты функциональные. Данные сервера читаются через TanStack Query. Ключ запроса включает пользователя и тип ресурса. Секреты и `initData` не попадают в persistent storage сверх того, что требует текущая сессия Telegram WebApp.

`tsconfig` включает `strict`, `noUncheckedIndexedAccess` и `exactOptionalPropertyTypes`. Тип `any` в рабочем коде не используется.

Проверки: `pnpm exec tsc --noEmit`, `pnpm exec vitest run`, `pnpm exec vite build`. Сквозные пути — Playwright в `frontend/e2e`.

## Ресурсы текстов

Каждая авторская строка страницы, кнопки, ошибки, пустого состояния, paywall, уведомления и дисклеймера лежит в `frontend/src/resources/ru.ts`. Серверные пользовательские сообщения лежат в `src/starflow/resources/`. Промпты помощника лежат файлами в `src/starflow/resources/prompts/`. Тарифы и числовые лимиты лежат в `src/starflow/tariffs/tariffs.yaml`.

Подписи двенадцати экранов совпадают с `design/mockup.jpeg`. Регистр авторского текста не меняется. `text-transform: lowercase` на документ не вешается. Имя, код реферала, URL, email и технический идентификатор не проходят через `lower()`.

Промпт помощника запрещает emoji и обещание точного события. Ответ с emoji отклоняется и один раз запрашивается снова. После второй неудачи пользователь видит строку ошибки из ресурса. Регистр ответа модели сохраняется.

Строка, что материал развлекательный, видна внизу главного экрана мелким вторичным шрифтом. На остальных экранах эта плашка не повторяется. Экран «условия» показывает собственную формулировку из ресурса.

## Компоненты и токены

Базовые компоненты живут в `frontend/src/shared/ui`: `Button`, `SegmentedControl`, `ListRow`, `Field`, `Toggle`, `TabBar`, `TopBar`, `Avatar`, `ChatBubble`, `ChatInput`, `Chip`, `Stepper`, `LunarCalendar`, `Skeleton`, `ErrorState`, `Icon`. Новый экран собирается из них и из токенов. UI-кит и сторонний набор иконок не подключаются.

Токены — `frontend/src/shared/styles/tokens.css` и `tokens.ts`. Палитра одна, тёмная, как в `design/mockup.jpeg`. Светлая палитра не задана.

Шкала веса `Google Sans` в официальном OFL-файле — 400–700. `@font-face` именует семейство именно `Google Sans` и ставит `font-display: block`. Прямое начертание и курсив — отдельные файлы одного семейства. `sans-serif` остаётся в каскаде на случай, если файл не загрузился. Файлы шрифта и `@font-face` не меняются.

Вёрстка mobile-first. Ширина макета рассчитана на WebView Telegram. Отступы учитывают `safe-area-inset`. Корневой контейнер использует стабильную высоту viewport Telegram. Фокус видимый: контур 2px основного цвета с отступом 2px. При `prefers-reduced-motion: reduce` длительность переходов обнуляется. Анимация — CSS и SVG. Emoji в анимации не используются.

Клавиатура не перекрывает активное поле: экран сдвигается по `visualViewport`. Управляющие элементы не ближе 8px к краю безопасной зоны.

## Compose и образ

`docker-compose.yml` содержит сервисы `app` и `postgres` и ничего больше. `postgres` использует образ `postgres:16`, именованный volume и healthcheck. `app` стартует после здоровой базы.

Dockerfile образа `app` сначала собирает frontend через pnpm, затем собирает runtime через `uv sync --frozen`. В runtime копируются виртуальное окружение, исходники Python, миграции, `frontend/dist` и лицензия шрифта. Команда процесса явно задаёт один worker.

Production-реплика одна. Масштабирование `app` больше единицы считается нарушением, пока нет отдельного решения о координации polling и планировщика.
