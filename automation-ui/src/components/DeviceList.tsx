import { RefreshCw, Smartphone } from "lucide-react";

import type { Device } from "../api";

type Props = {
  devices: Device[];
  selectedSerial: string;
  pending: boolean;
  onRefresh: () => void;
  onSelect: (device: Device) => void;
};

export const DeviceList = ({ devices, selectedSerial, pending, onRefresh, onSelect }: Props) => (
  <aside className="device-sidebar" aria-label="设备列表">
    <div className="sidebar-heading">
      <div>
        <span className="eyebrow">ADB TARGETS</span>
        <h2>设备</h2>
      </div>
      <button className="icon-button" type="button" onClick={onRefresh} disabled={pending} aria-label="刷新设备" title="刷新设备">
        <RefreshCw size={17} aria-hidden="true" />
      </button>
    </div>
    <div className="device-list">
      {devices.length === 0 ? <p className="empty-copy">未发现设备</p> : devices.map((device) => {
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
            <Smartphone size={17} aria-hidden="true" />
            <span className="device-copy">
              <strong>{device.model || device.serial}</strong>
              <small>{device.serial}</small>
            </span>
            <span className={`state-tag ${ready ? "ready" : "not-ready"}`}>{ready ? "可用" : device.state}</span>
          </button>
        );
      })}
    </div>
  </aside>
);
