import { fireEvent, render, screen } from "@testing-library/react";
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
  deletePlan: vi.fn(),
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

  it("creates and selects a plan when recording stops from the plan library", async () => {
    const user = userEvent.setup();
    const api = createApi();
    api.startRecording = vi.fn().mockResolvedValue({ ok: true });
    api.stopRecording = vi.fn().mockResolvedValue({
      ok: true,
      path: "D:/plans/recorded.json",
      document: {
        name: "recorded-actions",
        serial: "ABC123",
        steps: [{ action: "tap", x: 10, y: 20 }],
      },
    });
    render(<App api={api} />);

    await user.click(await screen.findByRole("button", { name: /Pixel 8/ }));
    await user.click(screen.getByRole("button", { name: "录制新计划" }));
    await user.click(screen.getByRole("button", { name: "停止录制" }));

    expect(screen.getByLabelText("每日时间")).toHaveValue("21:00");
    expect(screen.getAllByText("1 个动作")).toHaveLength(1);
  });

  it("deletes a saved plan from the library", async () => {
    const user = userEvent.setup();
    const api = createApi();
    api.listPlans = vi.fn()
      .mockResolvedValueOnce([{ name: "morning", path: "D:/plans/morning.json", serial: "ABC123" }])
      .mockResolvedValue([]);
    api.deletePlan = vi.fn().mockResolvedValue({ ok: true, path: "D:/plans/morning.json" });
    render(<App api={api} />);

    await user.click(await screen.findByRole("button", { name: "删除计划：morning" }));

    expect(api.deletePlan).toHaveBeenCalledWith("D:/plans/morning.json");
    expect(screen.queryByRole("button", { name: "morning" })).not.toBeInTheDocument();
  });

  it("reorders action steps when the grip is dragged onto another step", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);
    await user.selectOptions(screen.getByLabelText("添加动作"), "wait");

    fireEvent.dragStart(screen.getByRole("button", { name: "拖拽步骤 2" }));
    fireEvent.dragOver(screen.getByRole("article", { name: "步骤 1：唤醒屏幕" }));
    fireEvent.drop(screen.getByRole("article", { name: "步骤 1：唤醒屏幕" }));

    const labels = Array.from(document.querySelectorAll(".step-card strong"), (node) => node.textContent);
    expect(labels).toEqual(["等待", "唤醒屏幕"]);
  });

  it("queries devices once when using the default WebView bridge", async () => {
    const api = createApi();
    window.pywebview = {
      api: {
        list_devices: api.listDevices,
        list_plans: api.listPlans,
        load_plan: api.loadPlan,
        save_plan: api.savePlan,
        delete_plan: api.deletePlan,
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
        delete_plan: api.deletePlan,
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
