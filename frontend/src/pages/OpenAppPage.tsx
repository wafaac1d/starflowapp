import { text } from "../resources";

export function OpenAppPage() {
  return (
    <main className="shell">
      <section className="surface">
        <h1>{text("ui.open.title")}</h1>
        <p className="lead">{text("ui.open.lead")}</p>
      </section>
    </main>
  );
}
