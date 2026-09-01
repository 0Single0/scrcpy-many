import { GripVertical, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import type { AutomationStep, PlanDocument } from "../api";

const actionLabels: Record<string, string> = {
  wait: "等待",
  wake: "唤醒屏幕",
  dismiss_keyguard: "关闭非安全锁屏",
  launch: "打开应用",
  tap: "点击坐标",
  swipe: "滑动",
  unlock_swipe: "向上滑动（显示解锁界面）",
  text: "输入文本",
  keyevent: "按键事件",
  tap_text: "点击文字",
  assert_text: "检查文字",
  screenshot: "截图",
};

const fieldDefinitions: Record<string, Array<[string, string, string]>> = {
  wait: [["ms", "等待毫秒", "500"]],
  wake: [],
  dismiss_keyguard: [],
  launch: [["package", "应用包名", "com.example.app"]],
  tap: [["x", "横坐标", "540"], ["y", "纵坐标", "1460"]],
  swipe: [["x1", "起点横坐标", "540"], ["y1", "起点纵坐标", "1500"], ["x2", "终点横坐标", "540"], ["y2", "终点纵坐标", "600"], ["duration_ms", "持续毫秒", "300"]],
  unlock_swipe: [["x1", "起点横坐标", "540"], ["y1", "起点纵坐标", "1800"], ["x2", "终点横坐标", "540"], ["y2", "终点纵坐标", "600"], ["duration_ms", "持续毫秒", "300"]],
  text: [["value", "文本", ""]],
  keyevent: [["code", "Android 键码", "4"]],
  tap_text: [["text", "目标文字", "打卡"]],
  assert_text: [["text", "预期文字", "打卡成功"]],
  screenshot: [["name", "文件名", "状态"]],
};

const createStep = (action: string): AutomationStep => {
  const fields = fieldDefinitions[action] ?? [];
  return fields.reduce<AutomationStep>((step, [key, , value]) => ({ ...step, [key]: /^\d+$/.test(value) ? Number(value) : value }), { action });
};

type Props = {
  document: PlanDocument;
  onChange: (document: PlanDocument) => void;
};

export const PlanEditor = ({ document, onChange }: Props) => {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const updateDocument = (key: "name" | "serial", value: string) => onChange({ ...document, [key]: value });
  const updateStep = (index: number, key: string, value: string) => {
    const definition = (fieldDefinitions[document.steps[index].action] ?? []).find(([field]) => field === key);
    const nextValue = definition && /^\d+$/.test(definition[2]) ? Number(value || 0) : value;
    onChange({ ...document, steps: document.steps.map((step, position) => position === index ? { ...step, [key]: nextValue } : step) });
  };
  const moveStep = (from: number, target: number) => {
    if (from === target || target < 0 || target >= document.steps.length) return;
    const steps = [...document.steps];
    const [step] = steps.splice(from, 1);
    steps.splice(target, 0, step);
    onChange({ ...document, steps });
  };
  const removeStep = (index: number) => onChange({ ...document, steps: document.steps.filter((_, position) => position !== index) });
  const addStep = (action: string) => {
    onChange({ ...document, steps: [...document.steps, createStep(action)] });
  };

  return (
    <section className="editor-column" aria-label="计划编辑器">
      <div className="section-title">
        <div>
          <span className="eyebrow">AUTOMATION PLAN</span>
          <h2>计划</h2>
        </div>
        <span className="step-count">{document.steps.length} 个动作</span>
      </div>
      <div className="metadata-grid">
        <label>计划名称<input value={document.name} onChange={(event) => updateDocument("name", event.target.value)} /></label>
        <label>目标设备<input aria-label="目标设备" value={document.serial} readOnly placeholder="从左侧选择设备" /></label>
        <label>每日时间<input value={document.schedule.time} inputMode="numeric" pattern="[0-9]{2}:[0-9]{2}" onChange={(event) => onChange({ ...document, schedule: { ...document.schedule, time: event.target.value } })} /></label>
      </div>
      <div className="timeline" aria-label="操作步骤">
        {document.steps.map((step, index) => (
          <article className={`step-card${draggedIndex === index ? " dragging" : ""}`} key={`${step.action}-${index}`} role="article" aria-label={`步骤 ${index + 1}：${actionLabels[step.action] ?? step.action}`} onDragOver={(event) => event.preventDefault()} onDrop={() => { if (draggedIndex !== null) moveStep(draggedIndex, index); setDraggedIndex(null); }}>
            <div className="step-number"><button className="step-drag-handle" type="button" draggable aria-label={`拖拽步骤 ${index + 1}`} title="按住并拖动步骤" onDragStart={(event) => { if (event.dataTransfer) event.dataTransfer.effectAllowed = "move"; setDraggedIndex(index); }} onDragEnd={() => setDraggedIndex(null)}><GripVertical size={16} aria-hidden="true" /></button><span>{String(index + 1).padStart(2, "0")}</span></div>
            <div className="step-body">
              <strong>{actionLabels[step.action] ?? step.action}</strong>
              {step.action === "unlock_swipe" && <p className="step-note">仅显示安全锁屏界面；PIN、图案和生物识别仍需在手机上完成。</p>}
              <div className="step-fields">
                {(fieldDefinitions[step.action] ?? []).map(([key, label, placeholder]) => (
                  <label key={key}>{label}<input value={String(step[key] ?? "")} placeholder={placeholder} onChange={(event) => updateStep(index, key, event.target.value)} /></label>
                ))}
              </div>
            </div>
            <div className="step-actions">
              <button className="icon-button danger" type="button" onClick={() => removeStep(index)} aria-label="删除步骤" title="删除步骤"><Trash2 size={16} /></button>
            </div>
          </article>
        ))}
      </div>
      <div className="add-step-wrap">
        <label className="action-picker" htmlFor="action-picker"><span><Plus size={17} aria-hidden="true" />添加动作</span><select id="action-picker" aria-label="添加动作" value="" onChange={(event) => { if (event.target.value) addStep(event.target.value); }}><option value="" disabled>选择一个动作</option>{Object.entries(actionLabels).map(([action, label]) => <option value={action} key={action}>{label}</option>)}</select></label>
      </div>
    </section>
  );
};
