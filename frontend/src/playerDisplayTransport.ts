import type { PlayerDisplayState } from "./types";

export const PLAYER_DISPLAY_NAMESPACE = "myroll.playerDisplay";
export const PLAYER_DISPLAY_CHANNEL = "myroll.player-display.v1";

export type PlayerDisplayTransportType = "heartbeat" | "display-state-changed";

export type PlayerDisplayTransportMessage = {
  namespace: typeof PLAYER_DISPLAY_NAMESPACE;
  type: PlayerDisplayTransportType;
  displayWindowId: string;
  revision: number;
  identify_revision: number;
  sentAt: string;
};

const TRANSPORT_ENVELOPE_KEYS = new Set([
  "namespace",
  "type",
  "displayWindowId",
  "revision",
  "identify_revision",
  "sentAt"
]);

function nowIso(): string {
  return new Date().toISOString();
}

export function newDisplayWindowId(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `display-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function makeTransportMessage(
  type: PlayerDisplayTransportType,
  displayWindowId: string,
  state: Pick<PlayerDisplayState, "revision" | "identify_revision">
): PlayerDisplayTransportMessage {
  return {
    namespace: PLAYER_DISPLAY_NAMESPACE,
    type,
    displayWindowId,
    revision: state.revision,
    identify_revision: state.identify_revision,
    sentAt: nowIso()
  };
}

export function parseTransportData(data: unknown): PlayerDisplayTransportMessage | null {
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (Object.keys(record).some((key) => !TRANSPORT_ENVELOPE_KEYS.has(key))) return null;
  if (record.namespace !== PLAYER_DISPLAY_NAMESPACE) return null;
  if (record.type !== "heartbeat" && record.type !== "display-state-changed") return null;
  if (typeof record.displayWindowId !== "string" || !record.displayWindowId) return null;
  if (!Number.isSafeInteger(record.revision) || !Number.isSafeInteger(record.identify_revision)) return null;
  if (typeof record.sentAt !== "string") return null;
  return record as PlayerDisplayTransportMessage;
}

export function parseWindowMessage(event: MessageEvent, expectedOrigin: string): PlayerDisplayTransportMessage | null {
  if (event.origin !== expectedOrigin) return null;
  return parseTransportData(event.data);
}

export function broadcastTransportMessage(message: PlayerDisplayTransportMessage, targetWindow?: Window | null) {
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel(PLAYER_DISPLAY_CHANNEL);
    channel.postMessage(message);
    channel.close();
  }
  if (targetWindow && !targetWindow.closed) {
    targetWindow.postMessage(message, window.location.origin);
  }
}
