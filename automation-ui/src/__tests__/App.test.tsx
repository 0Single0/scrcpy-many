import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { AutomationApi } from "../api";

const createApi = (): AutomationApi => ({
  listDevices: vi.fn().mockResolvedValue([
    { serial: "ABC123", state: "device", transport: "USB", model: "Pixel 8", product: "shiba" },
  ]),
  listPlans: vi.fn().mockResolvedValue([]),
  loadPlan: vi.fn(),
  savePlan: vi.fn(),
  startRecording: vi.fn(),
  stopRecording: vi.fn(),
  runPlanNow: vi.fn(),
  setSchedule: vi.fn(),
  removeSchedule: vi.fn(),
  listRuns: vi.fn().mockResolvedValue([]),
  openArtifact: vi.fn(),
});

describe("App", () => {
  it("sets the explicit target serial when a ready device is selected", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);

    await user.click(await screen.findByRole("button", { name: /Pixel 8/ }));

    expect(screen.getByLabelText("目标设备")).toHaveValue("ABC123");
  });
});
