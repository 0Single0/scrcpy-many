import { CalendarClock, History, Play, Save } from "lucide-react";

import type { BridgeResult, RunSummary } from "../api";

type Props = {
  canAct: boolean;
  pending: string | null;
  result: BridgeResult | null;
  runs: RunSummary[];
  onSave: () => void;
  onRun: (dryRun: boolean) => void;
  onSchedule: () => void;
  onRemoveSchedule: () => void;
  onOpenArtifact: (path: string) => void;
};

const ResultMessage = ({ result }: { result: BridgeResult | null }) => {
  if (!result) return <p className="status-copy">保存后可试运行，确认步骤无误再执行。</p>;
  if (!result.ok) return <p className="result error">{result.code}: {result.message}</p>;
  if (result.success === true) return <p className="result success">执行成功，完成 {result.completed_steps} 个动作</p>;
  return <p className="result success">操作已完成</p>;
};

export const RunPanel = ({ canAct, pending, result, runs, onSave, onRun, onSchedule, onRemoveSchedule, onOpenArtifact }: Props) => (
  <aside className="run-panel" aria-label="执行控制">
    <div className="section-title"><div><span className="eyebrow">COMMAND CENTER</span><h2>执行</h2></div></div>
    <div className="command-stack">
      <button className="primary-button" type="button" onClick={onSave} disabled={!canAct || pending !== null}><Save size={17} />保存计划</button>
      <button className="secondary-button" type="button" onClick={() => onRun(true)} disabled={!canAct || pending !== null}><Play size={17} />试运行</button>
      <button className="run-button" type="button" onClick={() => onRun(false)} disabled={!canAct || pending !== null}><Play size={17} />立即运行</button>
      <button className="secondary-button" type="button" onClick={onSchedule} disabled={!canAct || pending !== null}><CalendarClock size={17} />启用定时</button>
      <button className="text-button" type="button" onClick={onRemoveSchedule} disabled={!canAct || pending !== null}>禁用定时</button>
    </div>
    {pending && <p className="pending-copy">正在处理：{pending}</p>}
    <ResultMessage result={result} />
    <section className="history-section"><div className="history-heading"><History size={16} /><h3>最近运行</h3></div>{runs.length === 0 ? <p className="empty-copy">尚无执行记录</p> : <ul>{runs.map((run) => <li key={run.run_dir}><span className={`history-state ${run.status}`}>{run.status === "success" ? "成功" : "失败"}</span><small>{run.error || run.run_dir}</small><button type="button" className="artifact-button" onClick={() => onOpenArtifact(`${run.run_dir}/run.log`)}>打开日志</button></li>)}</ul>}</section>
  </aside>
);
