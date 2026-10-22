# StarFlow

Telegram Mini App. API, статика и планировщик отдаются одним процессом. Правила и цикл работы: `rules.md`, `conventions.md`, `workflow.md`, `docs/DECISIONS.md`.

## Дизайн

Визуальный язык — типографический альманах. Спецификация: `docs/DESIGN.md`. Токены: `frontend/src/styles/tokens.css`.

Тема переключается на экране «настройки»: светлая, тёмная или «как в telegram». Выбор хранится в `localStorage` под ключом `starflow-theme`.

## Ассеты

Готовые иконки и иллюстрации лежат в `static`:

- `static/logo.png` — единственный логотип, его не заменяют и не перерисовывают;
- `static/icons/svg` — иконки интерфейса, предпочтительнее соседних PNG;
- `static/illustrations` — иллюстрация трёх окружностей;
- `static/font` — Google Sans и лицензия.

Новую иконку кладут SVG-файлом в `static/icons/svg` и добавляют имя в реестр `frontend/src/components/ui/icons.tsx`. Страницы путь к файлу не пишут.

`frontend/scripts/copy-logo.mjs` перед `dev` и `build` копирует логотип в `frontend/public/logo.png`, а иллюстрации — в `frontend/public/illustrations`. Иконки компонент берёт прямо из `static/icons/svg`, и Vite кладёт их в `frontend/dist/assets`. `public` и `assets` попадают в `dist`, тот же каталог отдаёт образ `app`. После сборки проверяются `frontend/dist/assets` и `frontend/dist/illustrations`, не только dev-сервер.

## Проверки интерфейса

Из каталога `frontend`:

- `corepack pnpm typecheck`
- `corepack pnpm test`
- `corepack pnpm build`
- `corepack pnpm e2e`

Сборка должна содержать `/logo.png` и `/illustrations/three-circles-cream.svg`. Иконки из `static/icons/svg` вшиваются в клиентский бандл как изображения этих файлов.
