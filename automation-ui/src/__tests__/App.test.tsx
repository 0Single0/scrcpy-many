import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { createWebViewApi, type AutomationApi } from "../api";

const createApi = (): AutomationApi => ({
  listDevices: vi.fn().mockResolvedValue([{ serial: "ABC123", state: "device", transport: "USB", model: "Pixel 8", product: "shiba" }]),
  listPlans: vi.fn().mockResolvedValue([]),
  loadPlan: vi.fn(), savePlan: vi.fn(), deletePlan: vi.fn(), startRecording: vi.fn(), stopRecording: vi.fn(), runPlanNow: vi.fn(), startPlanRun: vi.fn(), getPlanRunStatus: vi.fn(), cancelPlanRun: vi.fn(), setSchedule: vi.fn(), removeSchedule: vi.fn(), listRuns: vi.fn().mockResolvedValue([]), openArtifact: vi.fn(),
});

afterEach(() => vi.useRealTimers());

describe("App", () => {
  it("leaves the detail area empty until a plan is selected or created", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);

    expect(screen.queryByRole("heading", { name: "执行" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "新建计划" }));
    expect(screen.getByRole("heading", { name: "执行" })).toBeInTheDocument();
  });

  it("shows a stop action while a run is in progress", async () => {
    const user = userEvent.setup();
    const api = createApi();
    api.savePlan = vi.fn().mockResolvedValue({ ok: true, path: "D:/plans/new.json" });
    api.startPlanRun = vi.fn().mockResolvedValue({ ok: true, running: true });
    api.getPlanRunStatus = vi.fn().mockResolvedValue({ ok: true, running: true });
    render(<App api={api} />);

    await user.click(screen.getByRole("button", { name: "新建计划" }));
    await user.click(await screen.findByRole("button", { name: /Pixel 8/ }));
    await user.click(screen.getByRole("button", { name: "保存计划" }));
    await user.click(screen.getByRole("button", { name: "立即运行" }));

    expect(await screen.findByRole("button", { name: "终止执行" })).toBeInTheDocument();
  });

  it("sets the explicit target serial when a ready device is selected", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);
    await user.click(screen.getByRole("button", { name: "新建计划" }));
    await user.click(await screen.findByRole("button", { name: /Pixel 8/ }));
    expect(screen.getByRole("button", { name: "目标设备" })).toHaveTextContent("Pixel 8");
  });

  it("adds an unlock swipe action from the action menu", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);
    await user.click(screen.getByRole("button", { name: "新建计划" }));
    await user.click(screen.getByRole("button", { name: "+ 添加动作" }));
    expect(screen.queryByRole("option", { name: "向上滑动（显示解锁界面）" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "输入文本" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "按键事件" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "点击文字" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "检查文字" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "截图" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "滑动" })).toBeInTheDocument();
  });

  it("creates and selects a plan when recording stops from the plan library", async () => {
    const user = userEvent.setup();
    const api = createApi();
    api.startRecording = vi.fn().mockResolvedValue({ ok: true });
    api.stopRecording = vi.fn().mockResolvedValue({ ok: true, path: "D:/plans/recorded.json", document: { name: "recorded-actions", serial: "ABC123", steps: [{ action: "tap", x: 10, y: 20 }] } });
    render(<App api={api} />);
    await user.click(await screen.findByRole("button", { name: /Pixel 8/ }));
    await user.click(screen.getByRole("button", { name: "录制新计划" }));
    await user.click(screen.getByRole("button", { name: "停止录制" }));
    expect(screen.getByRole("button", { name: "每日时间" })).toHaveTextContent("21:00");
    expect(screen.getByText("1 个动作")).toBeInTheDocument();
  });

  it("deletes a saved plan from the library", async () => {
    const user = userEvent.setup();
    const api = createApi();
    api.listPlans = vi.fn().mockResolvedValueOnce([{ name: "morning", path: "D:/plans/morning.json", serial: "ABC123" }]).mockResolvedValue([]);
    api.deletePlan = vi.fn().mockResolvedValue({ ok: true, path: "D:/plans/morning.json" });
    render(<App api={api} />);
    const remove = await screen.findByRole("button", { name: "删除计划: morning" });
    await user.click(remove);
    expect(api.deletePlan).toHaveBeenCalledWith("D:/plans/morning.json");
    expect(screen.queryByText("morning")).not.toBeInTheDocument();
  });

  it("switches the interface language without changing the plan state", async () => {
    const user = userEvent.setup();
    render(<App api={createApi()} />);
    await user.click(screen.getByRole("button", { name: "新建计划" }));
    await user.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByRole("heading", { name: "Automation Center" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Target device" })).toBeInTheDocument();
  });

  it("refreshes the device list every ten seconds", async () => {
    vi.useFakeTimers();
    const api = createApi();
    render(<App api={api} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(api.listDevices).toHaveBeenCalledTimes(2);
  });

  it("retries loading plans when the bridge is not ready on first render", async () => {
    vi.useFakeTimers();
    const api = createApi();
    api.listPlans = vi.fn()
      .mockRejectedValueOnce(new Error("bridge not ready"))
      .mockResolvedValue([{ name: "recorded", path: "D:/plans/recorded.json", serial: "ABC123" }]);
    render(<App api={api} />);

    expect(screen.queryByText("recorded")).not.toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(screen.getByText("recorded")).toBeInTheDocument();
    expect(api.listPlans).toHaveBeenCalledTimes(2);
  });

  it("toggles the daily schedule command after saving a plan", async () => {
    const user = userEvent.setup();
    const api = createApi();
    api.savePlan = vi.fn().mockResolvedValue({ ok: true, path: "D:/plans/new.json" });
    api.setSchedule = vi.fn().mockResolvedValue({ ok: true });
    render(<App api={api} />);
    await user.click(screen.getByRole("button", { name: "新建计划" }));
    await user.click(await screen.findByRole("button", { name: /Pixel 8/ }));
    await user.click(screen.getByRole("button", { name: "保存计划" }));
    await user.click(screen.getByRole("button", { name: "启用每日定时" }));
    expect(api.setSchedule).toHaveBeenCalledWith("D:/plans/new.json");
    expect(screen.getByRole("button", { name: "关闭每日定时" })).toBeInTheDocument();
  });

  it("resolves the WebView bridge when it becomes available after creation", async () => {
    window.pywebview = undefined;
    const bridge = createWebViewApi();
    const api = createApi();
    window.pywebview = { api: { list_devices: api.listDevices, list_plans: api.listPlans, load_plan: api.loadPlan, save_plan: api.savePlan, delete_plan: api.deletePlan, start_recording: api.startRecording, stop_recording: api.stopRecording, run_plan_now: api.runPlanNow, start_plan_run: api.startPlanRun, get_plan_run_status: api.getPlanRunStatus, cancel_plan_run: api.cancelPlanRun, set_schedule: api.setSchedule, remove_schedule: api.removeSchedule, list_runs: api.listRuns, open_artifact: api.openArtifact } };
    await expect(bridge.listDevices()).resolves.toEqual([{ serial: "ABC123", state: "device", transport: "USB", model: "Pixel 8", product: "shiba" }]);
  });
});
