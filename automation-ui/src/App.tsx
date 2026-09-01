import { FilePlus2, FolderOpen } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { createWebViewApi, type AutomationApi, type BridgeResult, type Device, type PlanDocument, type PlanSummary, type RunSummary } from "./api";
import { DeviceList } from "./components/DeviceList";
import { PlanEditor } from "./components/PlanEditor";
import { RunPanel } from "./components/RunPanel";

const emptyPlan = (): PlanDocument => ({ name: "未命名计划", serial: "", schedule: { time: "21:00", days: ["daily"] }, steps: [{ action: "wake" }] });

type Props = { api?: AutomationApi };

export const App = ({ api }: Props) => {
  const defaultApi = useMemo(() => createWebViewApi(), []);
  const activeApi = api ?? defaultApi;
  const [devices, setDevices] = useState<Device[]>([]);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [document, setDocument] = useState<PlanDocument>(emptyPlan);
  const [path, setPath] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [recording, setRecording] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [result, setResult] = useState<BridgeResult | null>(null);

  const refreshDevices = useCallback(async () => {
    setPending("刷新设备");
    try { setDevices(await activeApi.listDevices()); } catch (error) { setResult({ ok: false, code: "device_list_error", message: String(error) }); } finally { setPending(null); }
  }, [activeApi]);
  const refreshPlans = useCallback(async () => {
    try { setPlans(await activeApi.listPlans()); } catch (error) { setResult({ ok: false, code: "plan_list_error", message: String(error) }); }
  }, [activeApi]);
  const refreshRuns = useCallback(async (name: string) => {
    try { setRuns(await activeApi.listRuns(name)); } catch { setRuns([]); }
  }, [activeApi]);
  useEffect(() => { void refreshDevices(); void refreshPlans(); }, [refreshDevices, refreshPlans]);

  const canAct = document.serial !== "" && document.name.trim() !== "" && document.steps.length > 0;
  const currentPlan = useMemo(() => plans.find((plan) => plan.path === path), [path, plans]);
  const applyResult = useCallback((next: BridgeResult) => { setResult(next); return next; }, []);
  const chooseDevice = (device: Device) => setDocument((draft) => ({ ...draft, serial: device.serial }));
  const createPlan = () => { setDocument(emptyPlan()); setPath(null); setRuns([]); setResult(null); };
  const openPlan = async (plan: PlanSummary) => {
    setPending("打开计划");
    try { const loaded = applyResult(await activeApi.loadPlan(plan.path)); if (loaded.ok && loaded.document) { setDocument(loaded.document); setPath(plan.path); await refreshRuns(loaded.document.name); } } finally { setPending(null); }
  };
  const save = async () => {
    setPending("保存计划");
    try { const saved = applyResult(await activeApi.savePlan(document, path ?? undefined)); if (saved.ok && saved.path) { setPath(saved.path); await refreshPlans(); await refreshRuns(document.name); } } finally { setPending(null); }
  };
  const record = async () => {
    setPending(recording ? "停止录制" : "开始录制");
    try {
      const response = recording ? await activeApi.stopRecording() : await activeApi.startRecording(document.serial);
      applyResult(response);
      if (response.ok && recording && response.document) { setDocument(response.document); setPath(response.path ?? null); await refreshPlans(); }
      if (response.ok) setRecording((active) => !active);
    } finally { setPending(null); }
  };
  const run = async (dryRun: boolean) => {
    if (!path) { await save(); return; }
    setPending(dryRun ? "试运行" : "立即运行");
    try { const response = applyResult(await activeApi.runPlanNow(path, dryRun)); if (response.ok) await refreshRuns(document.name); } finally { setPending(null); }
  };
  const schedule = async (remove = false) => {
    if (!path) { await save(); return; }
    setPending(remove ? "禁用定时" : "启用定时");
    try { applyResult(remove ? await activeApi.removeSchedule(document.name) : await activeApi.setSchedule(path)); } finally { setPending(null); }
  };
  const openArtifact = async (artifactPath: string) => {
    setPending("打开日志");
    try { applyResult(await activeApi.openArtifact(artifactPath)); } finally { setPending(null); }
  };

  return <main className="application-shell">
    <DeviceList devices={devices} selectedSerial={document.serial} pending={pending === "刷新设备"} onRefresh={() => void refreshDevices()} onSelect={chooseDevice} />
    <div className="workspace">
      <header className="app-header"><div><span className="eyebrow">SCRCPY MANY / AUTOMATION</span><h1>自动化中心</h1></div><div className="header-actions"><button type="button" className="header-button" onClick={createPlan}><FilePlus2 size={17} />新建计划</button><span className="current-plan"><FolderOpen size={16} />{currentPlan?.name ?? "未保存"}</span></div></header>
      <div className="content-grid">
        <nav className="plans-column" aria-label="已保存计划"><div className="section-title"><div><span className="eyebrow">SAVED PLANS</span><h2>计划库</h2></div></div><div className="plan-list">{plans.length === 0 ? <p className="empty-copy">保存后会显示在这里</p> : plans.map((plan) => <button key={plan.path} className={`plan-row${plan.path === path ? " active" : ""}`} type="button" onClick={() => void openPlan(plan)}><strong>{plan.name}</strong><small>{plan.serial}</small></button>)}</div></nav>
        <PlanEditor document={document} onChange={setDocument} />
        <RunPanel canAct={canAct} recording={recording} pending={pending} result={result} runs={runs} onSave={() => void save()} onRecord={() => void record()} onRun={(dryRun) => void run(dryRun)} onSchedule={() => void schedule()} onRemoveSchedule={() => void schedule(true)} onOpenArtifact={(artifactPath) => void openArtifact(artifactPath)} />
      </div>
    </div>
  </main>;
};
