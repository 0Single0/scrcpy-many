import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

export type MenuOption = { value: string; label: string; disabled?: boolean };

type Props = {
  ariaLabel: string;
  value: string;
  options: MenuOption[];
  placeholder: string;
  disabled?: boolean;
  onChange: (value: string) => void;
};

export const MenuSelect = ({ ariaLabel, value, options, placeholder, disabled = false, onChange }: Props) => {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState<"top" | "bottom">("bottom");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const selected = options.find((option) => option.value === value);

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const trigger = triggerRef.current.getBoundingClientRect();
    const menuHeight = Math.min(270, options.length * 36 + 8);
    const gap = 5;
    const below = window.innerHeight - trigger.bottom - gap;
    const above = trigger.top - gap;
    setPlacement(below < menuHeight && above > below ? "top" : "bottom");
  }, [open, options.length]);

  useEffect(() => {
    const closeOnOutsidePress = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsidePress);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsidePress);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  return <div className="menu-select" ref={rootRef}>
    <button
      type="button"
      className="menu-select-trigger"
      ref={triggerRef}
      aria-label={ariaLabel}
      aria-haspopup="listbox"
      aria-controls={listId}
      aria-expanded={open}
      disabled={disabled}
      onClick={() => setOpen((visible) => !visible)}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setOpen(true);
        }
      }}
    >
      <span>{selected?.label ?? placeholder}</span>
      <ChevronDown size={15} aria-hidden="true" />
    </button>
    {open && <div id={listId} className={`menu-select-options placement-${placement}`} role="listbox" aria-label={ariaLabel}>
      {options.map((option) => <button
        type="button"
        role="option"
        aria-selected={option.value === value}
        disabled={option.disabled}
        key={option.value}
        onClick={() => { onChange(option.value); setOpen(false); }}
      >
        <span>{option.label}</span>
        {option.value === value && <Check size={15} aria-hidden="true" />}
      </button>)}
    </div>}
  </div>;
};
