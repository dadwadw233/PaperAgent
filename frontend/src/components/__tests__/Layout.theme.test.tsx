import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Layout } from "../Layout";

describe("Layout theme switcher", () => {
  it("emits theme changes from global toolbar controls", async () => {
    const user = userEvent.setup();
    const onThemeChange = vi.fn();

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Layout theme="dark" onThemeChange={onThemeChange} />}>
            <Route index element={<div>content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Light" }));
    expect(onThemeChange).toHaveBeenCalledWith("light");
  });
});
