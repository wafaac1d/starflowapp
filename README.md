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

`frontend/scripts/copy-logo.mjs` перед `dev` и `build` копирует логотип в `frontend/public/logo.png`, а SVG иконок и иллюстраций — в `frontend/public/icons` и `frontend/public/illustrations`. Vite забирает `public` в `frontend/dist`. Тот же `dist` попадает в образ `app` и отдаётся вместе с API. После сборки файлы проверяются в `frontend/dist/icons` и `frontend/dist/illustrations`, не только в dev-сервере.

## Проверки интерфейса

Из каталога `frontend`:

- `corepack pnpm typecheck`
- `corepack pnpm test`
- `corepack pnpm build`
- `corepack pnpm e2e`

Сборка должна содержать `/logo.png`, `/icons/sun.svg` и `/illustrations/three-circles-cream.svg`.
