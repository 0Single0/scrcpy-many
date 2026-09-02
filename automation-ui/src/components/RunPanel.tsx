import { CalendarClock, CircleStop, FileText, Play, Save } from "lucide-react";

import type { BridgeResult, RunSummary } from "../api";
import type { UiCopy } from "../i18n";

type Props = {
  canAct: boolean;
  pending: string | null;
  result: BridgeResult | null;
  runs: RunSummary[];
  scheduled: boolean;
  running: boolean;
  cancelling: boolean;
  copy: UiCopy;
  onSave: () => void;
  onRun: (dryRun: boolean) => void;
  onCancelRun: () => void;
  onSchedule: () => void;
  onOpenArtifact: (path: string) => void;
};

const ResultMessage = ({ result, copy }: { result: BridgeResult | null; copy: UiCopy }) => {
  if (!result) return <p className="status-copy">{copy.saveBeforeRun}</p>;
  if (!result.ok) return <p className="result error">{result.code}: {result.message}</p>;
  if (result.cancelled) return <p className="result error">{copy.runCancelled}</p>;
  if (result.success === true) return <p className="result success">{copy.runSuccess} {result.completed_steps} {copy.completedActions}</p>;
  return <p className="result success">{copy.operationComplete}</p>;
};

export const RunPanel = ({ canAct, pending, result, runs, scheduled, running, cancelling, copy, onSave, onRun, onCancelRun, onSchedule, onOpenArtifact }: Props) => (
  <section className="run-panel" aria-label={copy.execution}>
    <div className="run-toolbar">
      <div className="run-toolbar-copy"><span className="eyebrow">{copy.commandEyebrow}</span><h3>{copy.execution}</h3></div>
      <div className="command-actions">
        {running ? <button className="stop-button" type="button" onClick={onCancelRun} disabled={cancelling}><CircleStop size={16} />{cancelling ? copy.cancelling : copy.cancelRun}</button> : <>
        <button className="secondary-button" type="button" onClick={onSave} disabled={!canAct || pending !== null}><Save size={16} />{copy.savePlan}</button>
        <button className="secondary-button" type="button" onClick={() => onRun(true)} disabled={!canAct || pending !== null} title={copy.dryRunHint}><Play size={16} />{copy.dryRun}</button>
        <button className="run-button" type="button" onClick={() => onRun(false)} disabled={!canAct || pending !== null}><Play size={16} />{copy.runNow}</button>
        <button className={`schedule-button${scheduled ? " active" : ""}`} type="button" onClick={onSchedule} disabled={!canAct || pending !== null}><CalendarClock size={16} />{scheduled ? copy.disableSchedule : copy.enableSchedule}</button>
        </>}
      </div>
    </div>
    {pending && <p className="pending-copy">{copy.pending}: {pending}</p>}
    <ResultMessage result={result} copy={copy} />
    <section className="history-section"><div className="history-heading"><FileText size={16} /><h3>{copy.recentRuns}</h3></div>{runs.length === 0 ? <p className="empty-copy">{copy.noRuns}</p> : <ul>{runs.slice(0, 1).map((run) => <li key={run.run_dir}><span className={`history-state ${run.status}`}>{run.status === "success" ? "OK" : "FAIL"}</span><small>{run.error || run.run_dir}</small><button type="button" className="artifact-button" onClick={() => onOpenArtifact(`${run.run_dir}/run.log`)}>{copy.openLog}</button></li>)}</ul>}</section>
  </section>
);
