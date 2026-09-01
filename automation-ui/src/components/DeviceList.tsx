import { Languages, RefreshCw, Smartphone } from "lucide-react";

import type { Device } from "../api";
import type { UiCopy } from "../i18n";

type Props = {
  devices: Device[];
  selectedSerial: string;
  pending: boolean;
  copy: UiCopy;
  onRefresh: () => void;
  onSelect: (device: Device) => void;
  onToggleLocale: () => void;
};

export const DeviceList = ({ devices, selectedSerial, pending, copy, onRefresh, onSelect, onToggleLocale }: Props) => (
  <aside className="device-sidebar" aria-label={copy.devices}>
    <div className="sidebar-heading">
      <div>
        <span className="eyebrow">{copy.devicesEyebrow}</span>
        <h2>{copy.devices}</h2>
      </div>
      <button className="icon-button" type="button" onClick={onRefresh} disabled={pending} aria-label={copy.refreshDevices} title={copy.refreshDevices}>
        <RefreshCw size={16} aria-hidden="true" />
      </button>
    </div>
    <div className="device-list">
      {devices.length === 0 ? <p className="empty-copy">{copy.noDevices}</p> : devices.map((device) => {
        const ready = device.state === "device";
        const active = device.serial === selectedSerial;
        return (
          <button
            className={`device-row${active ? " selected" : ""}`}
            key={device.serial}
            type="button"
            disabled={!ready}
            onClick={() => onSelect(device)}
            aria-pressed={active}
          >
            <Smartphone size={16} aria-hidden="true" />
            <span className="device-copy">
              <strong>{device.model || device.serial}</strong>
              <small>{device.serial}</small>
            </span>
            <span className={`state-tag ${ready ? "ready" : "not-ready"}`}>{ready ? copy.ready : device.state}</span>
          </button>
        );
      })}
    </div>
    <button className="locale-button" type="button" onClick={onToggleLocale} aria-label={copy.language}>
      <Languages size={16} aria-hidden="true" />
      <span>{copy.language}</span>
    </button>
  </aside>
);
