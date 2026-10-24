import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { Avatar } from "./Avatar/Avatar";
import { Button } from "./Button/Button";
import { ChatInput } from "./ChatInput/ChatInput";
import { Field } from "./Field/Field";
import { Icon } from "./Icon/Icon";
import { ListRow } from "./ListRow/ListRow";
import { LunarCalendar } from "./LunarCalendar/LunarCalendar";
import { SegmentedControl } from "./SegmentedControl/SegmentedControl";
import { TabBar } from "./TabBar/TabBar";
import { Toggle } from "./Toggle/Toggle";
import { TopBar } from "./TopBar/TopBar";

describe("shared ui", () => {
  it("renders a decorative icon and a named icon", () => {
    const { container } = render(
      <>
        <Icon name="gear" />
        <Icon name="send" title="отправить" />
      </>,
    );
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
    expect(screen.getByRole("img", { name: "отправить" })).toBeInTheDocument();
  });

  it("disables the primary button while loading", () => {
    render(
      <Button loading onClick={() => undefined}>
        Начать
      </Button>,
    );
    expect(screen.getByRole("button", { name: "Начать" })).toBeDisabled();
  });

  it("moves the segmented control with the keyboard", async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        label="период прогноза"
        value="day"
        options={[
          { id: "day", label: "День" },
          { id: "week", label: "Неделя" },
          { id: "month", label: "Месяц" },
        ]}
        onChange={onChange}
      />,
    );
    const day = screen.getByRole("tab", { name: "День" });
    day.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalledWith("week");
  });

  it("toggles a switch", async () => {
    const onChange = vi.fn();
    render(<Toggle label="Не знаю время" checked={false} onChange={onChange} />);
    await userEvent.click(screen.getByRole("switch", { name: "Не знаю время" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("links a list row", () => {
    render(
      <MemoryRouter>
        <ListRow title="Моя подписка" to="/premium" chevron />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: /Моя подписка/ })).toHaveAttribute("href", "/premium");
  });

  it("keeps a field value", () => {
    render(<Field label="Дата рождения" value="12.08.1995" onChange={() => undefined} />);
    expect(screen.getByRole("textbox", { name: "Дата рождения" })).toHaveValue("12.08.1995");
  });

  it("marks the active tab", () => {
    render(
      <MemoryRouter>
        <TabBar active="today" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Сегодня" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Календарь" })).not.toHaveAttribute("aria-current");
  });

  it("sends chat text on enter", async () => {
    const onSubmit = vi.fn();
    render(<ChatInput value="привет" onChange={() => undefined} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByRole("textbox", { name: "Написать сообщение…" }), "{Enter}");
    expect(onSubmit).toHaveBeenCalled();
  });

  it("shows initials and a back control", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <TopBar title="Настройки" back />
        <Avatar letters="А" size="l" />
      </MemoryRouter>,
    );
    expect(screen.getByText("А")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "назад" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "назад" }));
  });

  it("selects a lunar day", async () => {
    const onSelect = vi.fn();
    render(
      <LunarCalendar
        year={2025}
        month={8}
        selected="2025-08-12"
        onSelect={onSelect}
        onPrevious={() => undefined}
        onNext={() => undefined}
      />,
    );
    expect(screen.getByRole("heading", { name: "Август 2025" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "12" }));
    expect(onSelect).toHaveBeenCalledWith("2025-08-12");
  });
});
