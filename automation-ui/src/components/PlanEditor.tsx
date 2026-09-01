import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { useMemo, useRef } from "react";

import type { AutomationStep, Device, PlanDocument } from "../api";
import type { UiCopy } from "../i18n";
import { actionLabels } from "../i18n";
import { MenuSelect, type MenuOption } from "./MenuSelect";

type FieldDefinition = [string, keyof UiCopy, string];

const fieldDefinitions: Record<string, FieldDefinition[]> = {
  wait: [["ms", "waitMs", "500"]],
  wake: [],
  dismiss_keyguard: [],
  launch: [["package", "package", "com.example.app"]],
  tap: [["x", "x", "540"], ["y", "y", "1460"]],
  swipe: [["x1", "x1", "540"], ["y1", "y1", "1500"], ["x2", "x2", "540"], ["y2", "y2", "600"], ["duration_ms", "duration", "300"]],
  unlock_swipe: [["x1", "x1", "540"], ["y1", "y1", "1800"], ["x2", "x2", "540"], ["y2", "y2", "600"], ["duration_ms", "duration", "300"]],
  text: [["value", "value", ""]],
  keyevent: [["code", "code", "4"]],
  tap_text: [["text", "targetText", "打卡"]],
  assert_text: [["text", "expectedText", "打卡成功"]],
  screenshot: [["name", "fileName", "状态"]],
};

const createStep = (action: string): AutomationStep => (fieldDefinitions[action] ?? []).reduce<AutomationStep>((step, [key, , value]) => ({ ...step, [key]: /^\d+$/.test(value) ? Number(value) : value }), { action });
const timeOptions = (value: string): MenuOption[] => {
  const options: MenuOption[] = [];
  for (let hour = 0; hour < 24; hour += 1) {
    for (const minute of [0, 30]) {
      const time = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
      options.push({ value: time, label: time });
    }
  }
  return options.some((option) => option.value === value) ? options : [{ value, label: value }, ...options];
};

type SortableStepProps = {
  id: string;
  index: number;
  step: AutomationStep;
  copy: UiCopy;
  onChange: (key: string, value: string) => void;
  onRemove: () => void;
};

const SortableStep = ({ id, index, step, copy, onChange, onRemove }: SortableStepProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition };
  const labels = actionLabels(copy);
  const fields = fieldDefinitions[step.action] ?? [];

  return <article ref={setNodeRef} style={style} className={`step-card${isDragging ? " dragging" : ""}`} aria-label={`${copy.plan} ${index + 1}: ${labels[step.action] ?? step.action}`}>
    <div className="step-content">
      <div className="step-heading"><span className="step-index">{String(index + 1).padStart(2, "0")}</span><strong>{labels[step.action] ?? step.action}</strong></div>
      {step.action === "unlock_swipe" && <p className="step-note">{copy.pinNote}</p>}
      {fields.length > 0 && <div className="step-fields">
        {fields.map(([key, label, placeholder]) => <label key={key}>{copy[label]}<input value={String(step[key] ?? "")} placeholder={placeholder} onChange={(event) => onChange(key, event.target.value)} /></label>)}
      </div>}
    </div>
    <div className="step-tools">
      <button className="step-drag-handle" type="button" aria-label={`${copy.dragStep} ${index + 1}`} title={copy.dragStep} {...attributes} {...listeners}>
        <GripVertical size={17} aria-hidden="true" />
      </button>
      <button className="icon-button danger step-delete" type="button" onClick={onRemove} aria-label={`${copy.deleteStep} ${index + 1}`} title={copy.deleteStep}><Trash2 size={16} /></button>
    </div>
  </article>;
};

type Props = {
  document: PlanDocument;
  devices: Device[];
  copy: UiCopy;
  onChange: (document: PlanDocument) => void;
};

export const PlanEditor = ({ document, devices, copy, onChange }: Props) => {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  const stepIds = useRef(new WeakMap<AutomationStep, string>());
  const labels = actionLabels(copy);
  const deviceOptions = useMemo(() => devices.filter((device) => device.state === "device").map((device) => ({ value: device.serial, label: `${device.model || device.serial} (${device.serial})` })), [devices]);
  const sortableItems = document.steps.map((step) => {
    let id = stepIds.current.get(step);
    if (!id) {
      id = `${step.action}-${crypto.randomUUID()}`;
      stepIds.current.set(step, id);
    }
    return id;
  });
  const updateDocument = (key: "name", value: string) => onChange({ ...document, [key]: value });
  const updateStep = (index: number, key: string, value: string) => {
    const definition = (fieldDefinitions[document.steps[index].action] ?? []).find(([field]) => field === key);
    const nextValue = definition && /^\d+$/.test(definition[2]) ? Number(value || 0) : value;
    onChange({ ...document, steps: document.steps.map((step, position) => position === index ? { ...step, [key]: nextValue } : step) });
  };
  const addStep = (action: string) => onChange({ ...document, steps: [...document.steps, createStep(action)] });
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const oldIndex = sortableItems.indexOf(String(active.id));
    const newIndex = sortableItems.indexOf(String(over.id));
    if (oldIndex >= 0 && newIndex >= 0) onChange({ ...document, steps: arrayMove(document.steps, oldIndex, newIndex) });
  };

  return <section className="editor-column" aria-label={copy.plan}>
    <div className="plan-editor-heading">
      <div><span className="eyebrow">{copy.planEyebrow}</span><h2>{copy.plan}</h2></div>
      <span className="step-count">{document.steps.length} {copy.actions}</span>
    </div>
    <div className="plan-metadata">
      <label>{copy.planName}<input value={document.name} onChange={(event) => updateDocument("name", event.target.value)} /></label>
      <label>{copy.targetDevice}<MenuSelect ariaLabel={copy.targetDevice} value={document.serial} options={deviceOptions} placeholder={copy.selectReadyDevice} onChange={(serial) => onChange({ ...document, serial })} /></label>
      <label>{copy.dailyTime}<MenuSelect ariaLabel={copy.dailyTime} value={document.schedule.time} options={timeOptions(document.schedule.time)} placeholder="21:00" onChange={(time) => onChange({ ...document, schedule: { ...document.schedule, time } })} /></label>
    </div>
    <div className="timeline" aria-label={copy.actions}>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd} autoScroll={{ threshold: { x: 0.15, y: 0.15 }, acceleration: 12, interval: 5 }}>
        <SortableContext items={sortableItems} strategy={verticalListSortingStrategy}>
          {document.steps.map((step, index) => <SortableStep key={sortableItems[index]} id={sortableItems[index]} index={index} step={step} copy={copy} onChange={(key, value) => updateStep(index, key, value)} onRemove={() => onChange({ ...document, steps: document.steps.filter((_, position) => position !== index) })} />)}
        </SortableContext>
      </DndContext>
    </div>
    <div className="add-action-row">
      <MenuSelect ariaLabel={copy.addAction} value="" options={Object.entries(labels).map(([value, label]) => ({ value, label }))} placeholder={copy.addAction} onChange={addStep} />
    </div>
  </section>;
};
