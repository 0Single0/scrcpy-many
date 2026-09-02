import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MenuSelect } from "./MenuSelect";

describe("MenuSelect", () => {
  afterEach(() => vi.restoreAllMocks());

  it("opens upward when the viewport has no room below the trigger", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: 700, bottom: 735, left: 100, right: 290, width: 190, height: 35,
      x: 100, y: 700, toJSON: () => ({}),
    });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    const user = userEvent.setup();
    render(<MenuSelect ariaLabel="Actions" value="" options={[{ value: "tap", label: "Tap" }, { value: "swipe", label: "Swipe" }]} placeholder="Add action" onChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Actions" }));

    expect(screen.getByRole("listbox")).toHaveClass("placement-top");
  });

  it("keeps the menu below the trigger when there is enough room", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      top: 100, bottom: 135, left: 100, right: 290, width: 190, height: 35,
      x: 100, y: 100, toJSON: () => ({}),
    });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    const user = userEvent.setup();
    render(<MenuSelect ariaLabel="Actions" value="" options={[{ value: "tap", label: "Tap" }]} placeholder="Add action" onChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Actions" }));

    expect(screen.getByRole("listbox")).toHaveClass("placement-bottom");
  });
});
