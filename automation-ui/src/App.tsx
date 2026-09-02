import { CircleStop, FilePlus2, FolderOpen, Radio, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createWebViewApi, type AutomationApi, type BridgeResult, type Device, type PlanDocument, type PlanSummary, type RunSummary } from "./api";
import { DeviceList } from "./components/DeviceList";
import { PlanEditor } from "./components/PlanEditor";
import { RunPanel } from "./components/RunPanel";
import { ui, type Locale } from "./i18n";

const emptyPlan = (): PlanDocument => ({ name: "未命名计划", serial: "", schedule: { time: "21:00", days: ["daily"] }, steps: [{ action: "wake" }] });
const normalizePlan = (plan: PlanDocument): PlanDocument => ({ ...plan, schedule: plan.schedule ?? { time: "21:00", days: ["daily"] }, steps: plan.steps ?? [] });

type Props = { api?: AutomationApi };

export const App = ({ api }: Props) => {
  const defaultApi = useMemo(() => createWebViewApi(), []);
  const activeApi = api ?? defaultApi;
  const [locale, setLocale] = useState<Locale>("zh");
  const [devices, setDevices] = useState<Device[]>([]);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [document, setDocument] = useState<PlanDocument>(emptyPlan);
  const [path, setPath] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [recording, setRecording] = useState(false);
  const [scheduled, setScheduled] = useState(false);
  const [running, setRunning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const planRetryTimer = useRef<number | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [result, setResult] = useState<BridgeResult | null>(null);
  const copy = ui[locale];

  const refreshDevices = useCallback(async (showPending = true) => {
    if (showPending) setPending(copy.refreshDevices);
    try { setDevices(await activeApi.listDevices()); } catch (error) { setResult({ ok: false, code: "device_list_error", message: String(error) }); } finally { if (showPending) setPending(null); }
  }, [activeApi, copy.refreshDevices]);
  const refreshPlans = useCallback(async (attempt = 0) => {
    try {
      setPlans(await activeApi.listPlans());
    } catch (error) {
      setResult({ ok: false, code: "plan_list_error", message: String(error) });
      if (attempt < 5) {
        if (planRetryTimer.current !== null) window.clearTimeout(planRetryTimer.current);
        planRetryTimer.current = window.setTimeout(() => {
          planRetryTimer.current = null;
          void refreshPlans(attempt + 1);
        }, 1_000);
      }
    }
  }, [activeApi]);
  const refreshRuns = useCallback(async (name: string) => {
    try { setRuns(await activeApi.listRuns(name)); } catch { setRuns([]); }
  }, [activeApi]);
  useEffect(() => { void refreshDevices(false); void refreshPlans(); }, [refreshDevices, refreshPlans]);
  useEffect(() => () => {
    if (planRetryTimer.current !== null) window.clearTimeout(planRetryTimer.current);
  }, []);
  useEffect(() => {
    const interval = window.setInterval(() => { void refreshDevices(false); }, 10_000);
    return () => window.clearInterval(interval);
  }, [refreshDevices]);

  const canAct = editing && document.serial !== "" && document.name.trim() !== "" && document.steps.length > 0;
  const currentPlan = useMemo(() => plans.find((plan) => plan.path === path), [path, plans]);
  const applyResult = useCallback((next: BridgeResult) => { setResult(next); return next; }, []);
  const chooseDevice = (device: Device) => setDocument((draft) => ({ ...draft, serial: device.serial }));
  const createPlan = () => { setDocument(emptyPlan()); setPath(null); setRuns([]); setResult(null); setScheduled(false); setEditing(true); };
  const clearSelection = () => { setDocument(emptyPlan()); setPath(null); setRuns([]); setResult(null); setScheduled(false); setEditing(false); };
  const openPlan = async (plan: PlanSummary) => {
    setPending(copy.plan);
    try { const loaded = applyResult(await activeApi.loadPlan(plan.path)); if (loaded.ok && loaded.document) { const normalized = normalizePlan(loaded.document); setDocument(normalized); setPath(plan.path); setScheduled(false); setEditing(true); await refreshRuns(normalized.name); } } finally { setPending(null); }
  };
  const save = async () => {
    setPending(copy.savePlan);
    try { const saved = applyResult(await activeApi.savePlan(document, path ?? undefined)); if (saved.ok && saved.path) { setPath(saved.path); await refreshPlans(); await refreshRuns(document.name); } } finally { setPending(null); }
  };
  const deletePlan = async (plan: PlanSummary) => {
    setPending(copy.deletePlan);
    try { const deleted = applyResult(await activeApi.deletePlan(plan.path)); if (deleted.ok) { if (path === plan.path) clearSelection(); await refreshPlans(); } } finally { setPending(null); }
  };
  const record = async () => {
    setPending(recording ? copy.stopRecording : copy.recordNew);
    try {
      const response = recording ? await activeApi.stopRecording() : await activeApi.startRecording(document.serial);
      applyResult(response);
      if (response.ok && recording && response.document) { setDocument(normalizePlan(response.document)); setPath(response.path ?? null); setEditing(true); await refreshPlans(); }
      if (response.ok) setRecording((active) => !active);
    } finally { setPending(null); }
  };
  const run = async (dryRun: boolean) => {
    if (!path) { await save(); return; }
    setPending(dryRun ? copy.dryRun : copy.runNow);
    try {
      const response = await activeApi.startPlanRun(path, dryRun);
      if (response.ok) {
        setResult(null);
        setCancelling(false);
        setRunning(true);
      } else {
        applyResult(response);
      }
    } catch (error) {
      setResult({ ok: false, code: "run_start_error", message: String(error) });
    } finally { setPending(null); }
  };
  const cancelRun = async () => {
    setCancelling(true);
    try {
      const response = await activeApi.cancelPlanRun();
      if (!response.ok) { applyResult(response); setCancelling(false); }
    } catch (error) {
      setResult({ ok: false, code: "run_cancel_error", message: String(error) });
      setCancelling(false);
    }
  };
  useEffect(() => {
    if (!running) return;
    let disposed = false;
    const checkRun = async () => {
      try {
        const status = await activeApi.getPlanRunStatus();
        if (disposed) return;
        if (!status.ok) {
          setResult(status);
          setRunning(false);
          setCancelling(false);
          return;
        }
        if (!status.running) {
          applyResult(status);
          setRunning(false);
          setCancelling(false);
          await refreshRuns(document.name);
        }
      } catch (error) {
        if (!disposed) {
          setResult({ ok: false, code: "run_status_error", message: String(error) });
          setRunning(false);
          setCancelling(false);
        }
      }
    };
    const interval = window.setInterval(() => { void checkRun(); }, 400);
    return () => { disposed = true; window.clearInterval(interval); };
  }, [activeApi, applyResult, document.name, refreshRuns, running]);
  const toggleSchedule = async () => {
    if (!path) { await save(); return; }
    setPending(scheduled ? copy.disableSchedule : copy.enableSchedule);
    try {
      const response = applyResult(scheduled ? await activeApi.removeSchedule(document.name) : await activeApi.setSchedule(path));
      if (response.ok) setScheduled((active) => !active);
    } finally { setPending(null); }
  };
  const openArtifact = async (artifactPath: string) => {
    setPending(copy.openLog);
    try { applyResult(await activeApi.openArtifact(artifactPath)); } finally { setPending(null); }
  };

  return <main className="application-shell">
    <DeviceList devices={devices} selectedSerial={document.serial} pending={pending === copy.refreshDevices} copy={copy} onRefresh={() => void refreshDevices()} onSelect={chooseDevice} onToggleLocale={() => setLocale((active) => active === "zh" ? "en" : "zh")} />
    <div className="workspace">
      <header className="app-header"><div><span className="eyebrow">{copy.eyebrow}</span><h1>{copy.automationCenter}</h1></div><div className="header-actions"><button type="button" className="header-button" onClick={createPlan}><FilePlus2 size={17} />{copy.newPlan}</button><span className="current-plan"><FolderOpen size={16} />{currentPlan?.name ?? copy.unsaved}</span></div></header>
      <div className="automation-workspace">
        <nav className="plan-rail" aria-label={copy.planLibrary}>
          <div className="rail-heading"><div><span className="eyebrow">{copy.savedPlansEyebrow}</span><h2>{copy.planLibrary}</h2></div><button className="library-record-button" type="button" onClick={() => void record()} disabled={!document.serial || pending !== null}>{recording ? <CircleStop size={16} /> : <Radio size={16} />}{recording ? copy.stopRecording : copy.recordNew}</button></div>
          <div className="plan-list">{plans.length === 0 ? <p className="empty-copy">{copy.saveHint}</p> : plans.map((plan) => <article key={plan.path} className={`plan-row${plan.path === path ? " active" : ""}`}><button className="plan-open-button" type="button" onClick={() => void openPlan(plan)}><strong>{plan.name}</strong><small>{plan.serial}</small></button><button className="plan-delete-button" type="button" onClick={() => void deletePlan(plan)} aria-label={`${copy.deletePlan}: ${plan.name}`} title={`${copy.deletePlan}: ${plan.name}`} disabled={pending !== null}><Trash2 size={15} /></button></article>)}</div>
        </nav>
        {editing ? <div className="plan-workbench">
          <PlanEditor document={document} devices={devices} copy={copy} onChange={setDocument} />
          <RunPanel canAct={canAct} pending={pending} result={result} runs={runs} scheduled={scheduled} running={running} cancelling={cancelling} copy={copy} onSave={() => void save()} onRun={(dryRun) => void run(dryRun)} onCancelRun={() => void cancelRun()} onSchedule={() => void toggleSchedule()} onOpenArtifact={(artifactPath) => void openArtifact(artifactPath)} />
        </div> : <section className="workbench-empty" aria-label={copy.plan} />}
      </div>
    </div>
  </main>;
};
