import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { createWebViewApi, type AutomationApi } from "../api";

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

  it("adds an unlock swipe action from the visible action picker", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);

    await user.selectOptions(screen.getByLabelText("添加动作"), "unlock_swipe");

    expect(screen.getByText(/PIN、图案和生物识别仍需在手机上完成/)).toBeInTheDocument();
    expect(screen.getAllByText("2 个动作")).toHaveLength(1);
  });

  it("queries devices once when using the default WebView bridge", async () => {
    const api = createApi();
    window.pywebview = {
      api: {
        list_devices: api.listDevices,
        list_plans: api.listPlans,
        load_plan: api.loadPlan,
        save_plan: api.savePlan,
        start_recording: api.startRecording,
        stop_recording: api.stopRecording,
        run_plan_now: api.runPlanNow,
        set_schedule: api.setSchedule,
        remove_schedule: api.removeSchedule,
        list_runs: api.listRuns,
        open_artifact: api.openArtifact,
      },
    };

    render(<App />);

    await screen.findByRole("button", { name: /Pixel 8/ });
    await new Promise((resolve) => setTimeout(resolve, 25));
    expect(api.listDevices).toHaveBeenCalledTimes(1);
    expect(api.listPlans).toHaveBeenCalledTimes(1);
  });

  it("resolves the WebView bridge when it becomes available after creation", async () => {
    window.pywebview = undefined;
    const bridge = createWebViewApi();
    const api = createApi();
    window.pywebview = {
      api: {
        list_devices: api.listDevices,
        list_plans: api.listPlans,
        load_plan: api.loadPlan,
        save_plan: api.savePlan,
        start_recording: api.startRecording,
        stop_recording: api.stopRecording,
        run_plan_now: api.runPlanNow,
        set_schedule: api.setSchedule,
        remove_schedule: api.removeSchedule,
        list_runs: api.listRuns,
        open_artifact: api.openArtifact,
      },
    };

    await expect(bridge.listDevices()).resolves.toEqual([
      { serial: "ABC123", state: "device", transport: "USB", model: "Pixel 8", product: "shiba" },
    ]);
  });
});
