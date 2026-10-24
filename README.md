# StarFlow

Telegram Mini App. API, статика и планировщик отдаются одним процессом. Правила и цикл работы: `rules.md`, `conventions.md`, `workflow.md`, `docs/DECISIONS.md`.

## Дизайн

Источник правды — `design/mockup.jpeg`. Спецификация: `docs/DESIGN.md`. Токены: `frontend/src/shared/styles/tokens.css`. Интерфейс тёмный. Сегмент темы сохраняет выбор, не подменяя палитру.

## Ассеты

Публичные файлы лежат в `static/`. Vite отдаёт этот каталог как `publicDir`.

- `static/icons/svg` — иконки, имена генерирует `frontend/scripts/gen-icon-names.ts`;
- `static/illustrations` — затмение, луна, натальный круг, схема совместимости, созвездие;
- `static/logo` — значок приложения для favicon и манифеста;
- `static/font` — Google Sans и лицензия;
- `static/logo.png` — файл, который образ всё ещё кладёт в `LOGO_PATH`.

## Проверки интерфейса

Менеджер — pnpm 10.18.0, Node 22. Из каталога `frontend`:

- `pnpm install --frozen-lockfile`
- `pnpm typecheck`
- `pnpm lint`
- `pnpm test`
- `pnpm test:e2e`
- `pnpm build`
