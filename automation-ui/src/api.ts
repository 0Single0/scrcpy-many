export type Device = {
  serial: string;
  state: string;
  transport: string;
  model: string;
  product: string;
};

export type AutomationStep = {
  action: string;
  [key: string]: string | number;
};

export type PlanDocument = {
  name: string;
  serial: string;
  schedule: { time: string; days: string[] };
  steps: AutomationStep[];
};

export type PlanSummary = { name: string; path: string; serial: string };
export type RunSummary = { run_dir: string; status: string; error: string };
export type BridgeResult = {
  ok: boolean;
  code?: string;
  message?: string;
  path?: string;
  task_name?: string;
  success?: boolean;
  completed_steps?: number;
  error?: string | null;
  run_dir?: string;
  document?: PlanDocument;
};

export type AutomationApi = {
  listDevices: () => Promise<Device[]>;
  listPlans: () => Promise<PlanSummary[]>;
  loadPlan: (path: string) => Promise<BridgeResult>;
  savePlan: (document: PlanDocument, path?: string) => Promise<BridgeResult>;
  startRecording: (serial: string) => Promise<BridgeResult>;
  stopRecording: () => Promise<BridgeResult>;
  runPlanNow: (path: string, dryRun: boolean) => Promise<BridgeResult>;
  setSchedule: (path: string) => Promise<BridgeResult>;
  removeSchedule: (name: string) => Promise<BridgeResult>;
  listRuns: (name: string) => Promise<RunSummary[]>;
  openArtifact: (path: string) => Promise<BridgeResult>;
};

type PyWebViewApi = {
  list_devices: () => Promise<Device[]>;
  list_plans: () => Promise<PlanSummary[]>;
  load_plan: (path: string) => Promise<BridgeResult>;
  save_plan: (document: PlanDocument, path?: string) => Promise<BridgeResult>;
  start_recording: (serial: string) => Promise<BridgeResult>;
  stop_recording: () => Promise<BridgeResult>;
  run_plan_now: (path: string, dryRun: boolean) => Promise<BridgeResult>;
  set_schedule: (path: string) => Promise<BridgeResult>;
  remove_schedule: (name: string) => Promise<BridgeResult>;
  list_runs: (name: string) => Promise<RunSummary[]>;
  open_artifact: (path: string) => Promise<BridgeResult>;
};

declare global {
  interface Window {
    pywebview?: { api?: PyWebViewApi };
  }
}

const unavailable = async (): Promise<never> => {
  throw new Error("自动化中心桥接尚未就绪");
};

export const createWebViewApi = (): AutomationApi => {
  const bridge = window.pywebview?.api;
  if (!bridge) {
    return {
      listDevices: unavailable,
      listPlans: unavailable,
      loadPlan: unavailable,
      savePlan: unavailable,
      startRecording: unavailable,
      stopRecording: unavailable,
      runPlanNow: unavailable,
      setSchedule: unavailable,
      removeSchedule: unavailable,
      listRuns: unavailable,
      openArtifact: unavailable,
    };
  }
  return {
    listDevices: () => bridge.list_devices(),
    listPlans: () => bridge.list_plans(),
    loadPlan: (path) => bridge.load_plan(path),
    savePlan: (document, path) => bridge.save_plan(document, path),
    startRecording: (serial) => bridge.start_recording(serial),
    stopRecording: () => bridge.stop_recording(),
    runPlanNow: (path, dryRun) => bridge.run_plan_now(path, dryRun),
    setSchedule: (path) => bridge.set_schedule(path),
    removeSchedule: (name) => bridge.remove_schedule(name),
    listRuns: (name) => bridge.list_runs(name),
    openArtifact: (path) => bridge.open_artifact(path),
  };
};
