import { ChevronDown, ChevronUp, GripVertical, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import type { AutomationStep, PlanDocument } from "../api";

const actionLabels: Record<string, string> = {
  wait: "等待",
  wake: "唤醒屏幕",
  dismiss_keyguard: "关闭非安全锁屏",
  launch: "打开应用",
  tap: "点击坐标",
  swipe: "滑动",
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
  const [menuOpen, setMenuOpen] = useState(false);
  const updateDocument = (key: "name" | "serial", value: string) => onChange({ ...document, [key]: value });
  const updateStep = (index: number, key: string, value: string) => {
    const definition = (fieldDefinitions[document.steps[index].action] ?? []).find(([field]) => field === key);
    const nextValue = definition && /^\d+$/.test(definition[2]) ? Number(value || 0) : value;
    onChange({ ...document, steps: document.steps.map((step, position) => position === index ? { ...step, [key]: nextValue } : step) });
  };
  const moveStep = (index: number, direction: number) => {
    const target = index + direction;
    if (target < 0 || target >= document.steps.length) return;
    const steps = [...document.steps];
    [steps[index], steps[target]] = [steps[target], steps[index]];
    onChange({ ...document, steps });
  };
  const removeStep = (index: number) => onChange({ ...document, steps: document.steps.filter((_, position) => position !== index) });
  const addStep = (action: string) => {
    onChange({ ...document, steps: [...document.steps, createStep(action)] });
    setMenuOpen(false);
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
          <article className="step-card" key={`${step.action}-${index}`}>
            <div className="step-number"><GripVertical size={16} aria-hidden="true" />{String(index + 1).padStart(2, "0")}</div>
            <div className="step-body">
              <strong>{actionLabels[step.action] ?? step.action}</strong>
              <div className="step-fields">
                {(fieldDefinitions[step.action] ?? []).map(([key, label, placeholder]) => (
                  <label key={key}>{label}<input value={String(step[key] ?? "")} placeholder={placeholder} onChange={(event) => updateStep(index, key, event.target.value)} /></label>
                ))}
              </div>
            </div>
            <div className="step-actions">
              <button className="icon-button" type="button" onClick={() => moveStep(index, -1)} disabled={index === 0} aria-label="上移步骤" title="上移步骤"><ChevronUp size={16} /></button>
              <button className="icon-button" type="button" onClick={() => moveStep(index, 1)} disabled={index === document.steps.length - 1} aria-label="下移步骤" title="下移步骤"><ChevronDown size={16} /></button>
              <button className="icon-button danger" type="button" onClick={() => removeStep(index)} aria-label="删除步骤" title="删除步骤"><Trash2 size={16} /></button>
            </div>
          </article>
        ))}
      </div>
      <div className="add-step-wrap">
        <button className="secondary-button" type="button" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen}><Plus size={17} />添加动作</button>
        {menuOpen && <div className="action-menu" role="menu">{Object.entries(actionLabels).map(([action, label]) => <button type="button" role="menuitem" key={action} onClick={() => addStep(action)}>{label}</button>)}</div>}
      </div>
    </section>
  );
};
