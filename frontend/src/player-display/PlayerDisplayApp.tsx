import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Monitor, WifiOff } from "lucide-react";

import { api } from "../api";
import { MapRenderer } from "../map/MapRenderer";
import {
  makeTransportMessage,
  newDisplayWindowId,
  parseTransportData,
  parseWindowMessage,
  PLAYER_DISPLAY_CHANNEL
} from "../playerDisplayTransport";
import { SafeMarkdownRenderer } from "../SafeMarkdownRenderer";
import type {
  CombatantDisposition,
  CustomFieldType,
  DisplayFitMode,
  EntityKind,
  MapRenderPayload,
  PlayerDisplayState,
  PublicInitiativeCombatant,
  PublicMapToken,
  PublicPartyCard
} from "../types";

const fitModes: DisplayFitMode[] = ["fit", "fill", "stretch", "actual_size"];
const entityKinds: EntityKind[] = ["pc", "npc", "creature", "location", "item", "handout", "faction", "vehicle", "generic"];
const customFieldTypes: CustomFieldType[] = ["short_text", "long_text", "number", "boolean", "select", "multi_select", "radio", "resource", "image"];
const combatDispositions: CombatantDisposition[] = ["pc", "ally", "neutral", "enemy", "hazard", "other"];

function payloadString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value ? value : null;
}

function payloadNumber(payload: Record<string, unknown>, key: string): number | null {
  const value = payload[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function tokenPayloadFromUnknown(value: unknown): PublicMapToken | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const id = payloadString(raw, "id");
  const x = payloadNumber(raw, "x");
  const y = payloadNumber(raw, "y");
  const width = payloadNumber(raw, "width");
  const height = payloadNumber(raw, "height");
  const rotation = payloadNumber(raw, "rotation") ?? 0;
  const style = raw.style && typeof raw.style === "object" ? (raw.style as Record<string, unknown>) : {};
  const shape = payloadString(style, "shape");
  const safeShape = shape === "square" || shape === "portrait" || shape === "marker" || shape === "circle" ? shape : "circle";
  if (!id || x === null || y === null || width === null || height === null) return null;
  return {
    id,
    entity_id: payloadString(raw, "entity_id"),
    asset_id: payloadString(raw, "asset_id"),
    asset_url: payloadString(raw, "asset_url"),
    mime_type: payloadString(raw, "mime_type") ?? undefined,
    asset_width: payloadNumber(raw, "asset_width") ?? undefined,
    asset_height: payloadNumber(raw, "asset_height") ?? undefined,
    name: payloadString(raw, "name"),
    x,
    y,
    width,
    height,
    rotation,
    style: {
      shape: safeShape,
      color: payloadString(style, "color") ?? "#D94841",
      border_color: payloadString(style, "border_color") ?? "#FFFFFF",
      opacity: payloadNumber(style, "opacity") ?? 1
    },
    status: []
  };
}

function mapPayloadFromDisplayState(state: PlayerDisplayState): MapRenderPayload | null {
  const payload = state.payload;
  if (payload.type !== "map") return null;
  const sceneMapId = payloadString(payload, "scene_map_id");
  const mapId = payloadString(payload, "map_id");
  const assetId = payloadString(payload, "asset_id");
  const assetUrl = payloadString(payload, "asset_url");
  const title = payloadString(payload, "title") ?? state.title ?? "Map";
  const fitModeValue = payloadString(payload, "fit_mode");
  const fitMode = fitModes.includes(fitModeValue as DisplayFitMode) ? (fitModeValue as DisplayFitMode) : "fit";
  const width = payloadNumber(payload, "width");
  const height = payloadNumber(payload, "height");
  const grid = typeof payload.grid === "object" && payload.grid !== null ? (payload.grid as Record<string, unknown>) : {};
  const rawFog = typeof payload.fog === "object" && payload.fog !== null ? (payload.fog as Record<string, unknown>) : null;
  const rawTokens = Array.isArray(payload.tokens) ? payload.tokens : [];
  const fog =
    rawFog && payloadString(rawFog, "mask_id") && payloadString(rawFog, "mask_url")
      ? {
          enabled: Boolean(rawFog.enabled),
          mask_id: payloadString(rawFog, "mask_id")!,
          mask_url: payloadString(rawFog, "mask_url")!,
          revision: typeof rawFog.revision === "number" ? rawFog.revision : 1,
          width: typeof rawFog.width === "number" ? rawFog.width : width ?? 0,
          height: typeof rawFog.height === "number" ? rawFog.height : height ?? 0
        }
      : undefined;
  if (!sceneMapId || !mapId || !assetId || !assetUrl || !width || !height) return null;
  return {
    type: "map",
    scene_map_id: sceneMapId,
    map_id: mapId,
    asset_id: assetId,
    asset_url: assetUrl,
    width,
    height,
    title,
    fit_mode: fitMode,
    grid: {
      type: "square",
      visible: Boolean(grid.visible),
      size_px: typeof grid.size_px === "number" ? grid.size_px : 70,
      offset_x: typeof grid.offset_x === "number" ? grid.offset_x : 0,
      offset_y: typeof grid.offset_y === "number" ? grid.offset_y : 0,
      color: typeof grid.color === "string" ? grid.color : "#FFFFFF",
      opacity: typeof grid.opacity === "number" ? grid.opacity : 0.35
    },
    fog,
    tokens: rawTokens.map(tokenPayloadFromUnknown).filter((token): token is PublicMapToken => Boolean(token))
  };
}

function statusItemLabel(item: string | { label: string } | unknown): string {
  if (typeof item === "string") return item;
  if (item && typeof item === "object" && "label" in item && typeof (item as { label?: unknown }).label === "string") {
    return (item as { label: string }).label;
  }
  return "";
}

function formatPartyValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    const resource = value as { current?: unknown; max?: unknown };
    if ("current" in resource) return resource.max === undefined || resource.max === null ? String(resource.current) : `${resource.current}/${resource.max}`;
    return JSON.stringify(value);
  }
  return String(value);
}

function partyCardsFromPayload(payload: Record<string, unknown>): PublicPartyCard[] {
  const cards = payload.cards;
  if (!Array.isArray(cards)) return [];
  return cards
    .filter((card): card is Record<string, unknown> => Boolean(card && typeof card === "object"))
    .map((card) => ({
      entity_id: typeof card.entity_id === "string" ? card.entity_id : "",
      display_name: typeof card.display_name === "string" ? card.display_name : "Party member",
      kind: entityKinds.includes(card.kind as EntityKind) ? (card.kind as EntityKind) : "pc",
      portrait_asset_id: typeof card.portrait_asset_id === "string" ? card.portrait_asset_id : null,
      portrait_url: typeof card.portrait_url === "string" ? card.portrait_url : null,
      fields: Array.isArray(card.fields)
        ? card.fields
            .filter((field): field is Record<string, unknown> => Boolean(field && typeof field === "object"))
            .map((field) => ({
              key: typeof field.key === "string" ? field.key : "",
              label: typeof field.label === "string" ? field.label : "Field",
              type: customFieldTypes.includes(field.type as CustomFieldType) ? (field.type as CustomFieldType) : "short_text",
              value: field.value
            }))
        : []
    }))
    .filter((card) => card.entity_id);
}

function initiativeCombatantsFromPayload(payload: Record<string, unknown>): PublicInitiativeCombatant[] {
  const combatants = payload.combatants;
  if (!Array.isArray(combatants)) return [];
  return combatants
    .filter((combatant): combatant is Record<string, unknown> => Boolean(combatant && typeof combatant === "object"))
    .map((combatant) => ({
      id: typeof combatant.id === "string" ? combatant.id : "",
      name: typeof combatant.name === "string" ? combatant.name : "Combatant",
      disposition: combatDispositions.includes(combatant.disposition as CombatantDisposition)
        ? (combatant.disposition as CombatantDisposition)
        : "other",
      initiative: typeof combatant.initiative === "number" ? combatant.initiative : null,
      is_active: Boolean(combatant.is_active),
      portrait_asset_id: typeof combatant.portrait_asset_id === "string" ? combatant.portrait_asset_id : null,
      portrait_url: typeof combatant.portrait_url === "string" ? combatant.portrait_url : null,
      public_status: Array.isArray(combatant.public_status)
        ? combatant.public_status
            .map((item) => statusItemLabel(item))
            .filter(Boolean)
        : []
    }))
    .filter((combatant) => combatant.id);
}

function PartyPortrait({ card }: { card: PublicPartyCard }) {
  const [failed, setFailed] = useState(false);
  if (!card.portrait_url || failed) {
    return <div className="party-portrait-fallback">{card.display_name.slice(0, 1).toUpperCase()}</div>;
  }
  return <img className="party-portrait" src={card.portrait_url} alt={card.display_name} onError={() => setFailed(true)} />;
}

function InitiativePortrait({ combatant }: { combatant: PublicInitiativeCombatant }) {
  const [failed, setFailed] = useState(false);
  if (!combatant.portrait_url || failed) {
    return <div className="party-portrait-fallback">{combatant.name.slice(0, 1).toUpperCase()}</div>;
  }
  return <img className="party-portrait" src={combatant.portrait_url} alt={combatant.name} onError={() => setFailed(true)} />;
}

function PlayerDisplayFrame({ className, children }: { className: string; children: ReactNode }) {
  return <main className={`player-display ${className}`}>{children}</main>;
}

function IdentifyOverlay() {
  return (
    <div className="identify-overlay">
      <Monitor size={40} />
      <strong>Player Display</strong>
    </div>
  );
}

export function PlayerDisplayApp() {
  const displayWindowId = useMemo(() => newDisplayWindowId(), []);
  const [lastGoodState, setLastGoodState] = useState<PlayerDisplayState | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const displayQuery = useQuery({
    queryKey: ["player-display"],
    queryFn: api.playerDisplay,
    refetchInterval: 2_000,
    retry: false
  });

  useEffect(() => {
    if (displayQuery.data) setLastGoodState(displayQuery.data);
  }, [displayQuery.data]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    function onDisplayMessage(message: ReturnType<typeof parseTransportData>) {
      if (!message || message.type !== "display-state-changed") return;
      void displayQuery.refetch();
    }

    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(PLAYER_DISPLAY_CHANNEL);
    if (channel) channel.onmessage = (event) => onDisplayMessage(parseTransportData(event.data));
    const onMessage = (event: MessageEvent) => onDisplayMessage(parseWindowMessage(event, window.location.origin));
    window.addEventListener("message", onMessage);
    return () => {
      channel?.close();
      window.removeEventListener("message", onMessage);
    };
  }, [displayQuery.refetch]);

  useEffect(() => {
    function sendHeartbeat() {
      const state = lastGoodState ?? {
        revision: 0,
        identify_revision: 0
      };
      const message = makeTransportMessage("heartbeat", displayWindowId, state);
      if (typeof BroadcastChannel !== "undefined") {
        const channel = new BroadcastChannel(PLAYER_DISPLAY_CHANNEL);
        channel.postMessage(message);
        channel.close();
      }
      window.opener?.postMessage(message, window.location.origin);
    }

    sendHeartbeat();
    const id = window.setInterval(sendHeartbeat, 1_000);
    return () => window.clearInterval(id);
  }, [displayWindowId, lastGoodState]);

  const initialFailure = !lastGoodState && displayQuery.isError;
  if (initialFailure) {
    return (
      <PlayerDisplayFrame className="player-degraded">
        <WifiOff size={34} />
        <h1>Player display unavailable</h1>
        <p>Reconnecting to local display state.</p>
      </PlayerDisplayFrame>
    );
  }

  if (!lastGoodState) {
    return (
      <PlayerDisplayFrame className="player-loading">
        <Monitor size={30} />
        <h1>Connecting player display</h1>
      </PlayerDisplayFrame>
    );
  }

  return (
    <PlayerDisplaySurface
      state={lastGoodState}
      now={now}
      reconnecting={displayQuery.isError || displayQuery.isRefetchError}
    />
  );
}

export function PlayerDisplaySurface({
  state,
  now,
  reconnecting
}: {
  state: PlayerDisplayState;
  now: number;
  reconnecting: boolean;
}) {
  const [failedImageRevision, setFailedImageRevision] = useState<number | null>(null);
  const identifyActive = Boolean(state.identify_until && Date.parse(state.identify_until) > now);
  const showReconnectOverlay = reconnecting && state.mode !== "blackout";
  if (state.mode === "blackout") {
    return (
      <PlayerDisplayFrame className="player-blackout">
        {identifyActive ? <IdentifyOverlay /> : null}
      </PlayerDisplayFrame>
    );
  }

  if (state.mode === "image") {
    const assetUrl = payloadString(state.payload, "asset_url");
    const title = payloadString(state.payload, "title") ?? state.title ?? "Image";
    const caption = payloadString(state.payload, "caption");
    const fitModeValue = payloadString(state.payload, "fit_mode");
    const fitMode = fitModes.includes(fitModeValue as DisplayFitMode) ? (fitModeValue as DisplayFitMode) : "fit";
    const width = payloadNumber(state.payload, "width");
    const height = payloadNumber(state.payload, "height");
    const imageFailed = failedImageRevision === state.revision || !assetUrl;
    return (
      <PlayerDisplayFrame className="player-image">
        {imageFailed ? (
          <div className="player-image-error">
            <WifiOff size={32} />
            <h1>Image unavailable</h1>
            <p>Reconnecting to local asset storage.</p>
          </div>
        ) : (
          <img
            className={`player-image-media fit-${fitMode}`}
            src={assetUrl}
            alt={title}
            width={width ?? undefined}
            height={height ?? undefined}
            onError={() => setFailedImageRevision(state.revision)}
          />
        )}
        {caption && !imageFailed ? <div className="player-caption">{caption}</div> : null}
        {identifyActive ? <IdentifyOverlay /> : null}
        {showReconnectOverlay ? <div className="player-reconnecting">Reconnecting</div> : null}
      </PlayerDisplayFrame>
    );
  }

  if (state.mode === "map") {
    const mapPayload = mapPayloadFromDisplayState(state);
    return (
      <PlayerDisplayFrame className="player-map">
        <MapRenderer payload={mapPayload} reconnecting={showReconnectOverlay} />
        {identifyActive ? <IdentifyOverlay /> : null}
      </PlayerDisplayFrame>
    );
  }

  if (state.mode === "text") {
    const title = payloadString(state.payload, "title") ?? state.title ?? "Public note";
    const body = payloadString(state.payload, "body") ?? "";
    return (
      <PlayerDisplayFrame className="player-text">
        <div className="player-text-content">
          <span className="player-kicker">Public snippet</span>
          {title ? <h1>{title}</h1> : null}
          <SafeMarkdownRenderer body={body} />
        </div>
        {identifyActive ? <IdentifyOverlay /> : null}
        {showReconnectOverlay ? <div className="player-reconnecting">Reconnecting</div> : null}
      </PlayerDisplayFrame>
    );
  }

  if (state.mode === "party") {
    const cards = partyCardsFromPayload(state.payload);
    const layout = payloadString(state.payload, "layout") ?? "standard";
    return (
      <PlayerDisplayFrame className={`player-party layout-${layout}`}>
        <div className="player-party-content">
          <span className="player-kicker">Party</span>
          <h1>{state.title ?? "Party"}</h1>
          <div className="player-party-grid">
            {cards.map((card) => (
              <div key={card.entity_id} className="player-party-card">
                <PartyPortrait card={card} />
                <strong>{card.display_name}</strong>
                <span>{card.kind}</span>
                <div className="player-party-fields">
                  {card.fields.map((field) => (
                    <div key={field.key} className="player-party-field">
                      <span>{field.label}</span>
                      <strong>{formatPartyValue(field.value)}</strong>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        {identifyActive ? <IdentifyOverlay /> : null}
        {showReconnectOverlay ? <div className="player-reconnecting">Reconnecting</div> : null}
      </PlayerDisplayFrame>
    );
  }

  if (state.mode === "initiative") {
    const combatants = initiativeCombatantsFromPayload(state.payload);
    const round = payloadNumber(state.payload, "round") ?? 1;
    return (
      <PlayerDisplayFrame className="player-initiative">
        <div className="player-initiative-content">
          <span className="player-kicker">Initiative</span>
          <h1>{state.subtitle ?? state.title ?? "Combat"}</h1>
          <p>Round {round}</p>
          <div className="player-initiative-list">
            {combatants.map((combatant) => (
              <div key={combatant.id} className={`player-initiative-card ${combatant.is_active ? "active" : ""}`}>
                <InitiativePortrait combatant={combatant} />
                <div>
                  <strong>{combatant.name}</strong>
                  <span>
                    Initiative {combatant.initiative ?? "-"} · {combatant.disposition}
                  </span>
                  {combatant.public_status.length ? <small>{combatant.public_status.map(statusItemLabel).join(" · ")}</small> : null}
                </div>
              </div>
            ))}
          </div>
        </div>
        {identifyActive ? <IdentifyOverlay /> : null}
        {showReconnectOverlay ? <div className="player-reconnecting">Reconnecting</div> : null}
      </PlayerDisplayFrame>
    );
  }

  const title = state.mode === "intermission" ? state.title ?? "Intermission" : state.title ?? "Scene";
  const subtitle = state.subtitle ?? state.active_campaign_name ?? "";
  return (
    <PlayerDisplayFrame className={state.mode === "scene_title" ? "player-scene-title" : "player-intermission"}>
      <div className="player-display-content">
        <span className="player-kicker">{state.mode === "scene_title" ? "Scene" : "Intermission"}</span>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {identifyActive ? <IdentifyOverlay /> : null}
      {showReconnectOverlay ? <div className="player-reconnecting">Reconnecting</div> : null}
    </PlayerDisplayFrame>
  );
}
