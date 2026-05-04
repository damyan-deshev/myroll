import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, PointerEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Rnd } from "react-rnd";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  CheckCircle2,
  CircleDashed,
  Download,
  Dices,
  Eye,
  EyeOff,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  LayoutDashboard,
  Map,
  Minus,
  PanelTop,
  Paintbrush,
  Plus,
  Radio,
  RotateCcw,
  Search,
  Send,
  Swords,
  Trash2,
  Upload,
  Users,
  WifiOff
} from "lucide-react";
import { api, ApiError } from "./api";
import {
  broadcastTransportMessage,
  makeTransportMessage,
  parseTransportData,
  parseWindowMessage,
  PLAYER_DISPLAY_CHANNEL
} from "./playerDisplayTransport";
import { MapRenderer } from "./map/MapRenderer";
import { PlayerDisplayApp } from "./player-display/PlayerDisplayApp";
import { SafeMarkdownRenderer } from "./SafeMarkdownRenderer";
import type {
  Asset,
  AssetBatchUploadResult,
  AssetKind,
  AssetVisibility,
  BuildBranchResult,
  BuildRecapResult,
  BundledMap,
  Campaign,
  CombatantDisposition,
  CombatantRecord,
  CombatEncounter,
  CombatEncounterStatus,
  CustomFieldDefinition,
  CustomFieldType,
  DisplayFitMode,
  EntityKind,
  EntityRecord,
  FogMask,
  FogOperation,
  FogPayload,
  MapRecord,
  MapRenderPayload,
  MemoryCandidate,
  Note,
  PlayerDisplayState,
  PlanningMarker,
  PartyLayout,
  PartyTrackerConfig,
  ProposalOption,
  ProposalSetDetail,
  ProposalSetSummary,
  PublicSafetyWarning,
  PublicSnippet,
  PublicMapToken,
  RuntimeState,
  Scene,
  SceneEntityRole,
  SceneStagedDisplayMode,
  SceneMap,
  SceneMapToken,
  Session,
  SessionTranscriptEvent,
  StorageArtifact,
  WidgetPatch,
  WorkspaceWidget
} from "./types";

type SaveStatus = "saved" | "saving" | "error";
type PublicSafetyCurationAck = {
  kind: "recap" | "memory";
  id: string;
  contentHash: string;
  warnings: PublicSafetyWarning[];
};
type WidgetStatusMap = Record<string, SaveStatus>;

const placeholderCopy: Record<string, string> = {
  map_display: "Unwired placeholder. Future asset, map, and player-display slices will own this.",
  notes: "Unwired placeholder. Future notes/snippets slice will connect markdown and public reveals.",
  party_tracker: "Unwired placeholder. Future entities/custom fields slice will power party cards.",
  combat_tracker: "Unwired placeholder. Future combat state slice will power initiative and turns.",
  dice_roller: "Unwired placeholder. Future local tool slice will add roll parsing and history."
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  if (error instanceof Error) return error.message;
  return "Unknown error";
}

export function App() {
  const path = window.location.pathname;
  if (path === "/player") return <PlayerDisplayApp />;
  if (path === "/gm/floating") return <FloatingGmShell />;
  if (path === "/gm/map") return <GmMapSurface />;
  if (path === "/gm/library") return <GmLibrarySurface />;
  if (path === "/gm/actors") return <GmActorsSurface />;
  if (path === "/gm/combat") return <GmCombatSurface />;
  if (path === "/gm/scene") return <GmSceneSurface />;
  return <GmOverviewSurface />;
}

type GmWorkspaceState = {
  campaignsQuery: ReturnType<typeof useQuery<Campaign[]>>;
  runtimeQuery: ReturnType<typeof useQuery<RuntimeState>>;
  sessionsQuery: ReturnType<typeof useQuery<Session[]>>;
  scenesQuery: ReturnType<typeof useQuery<Scene[]>>;
  shared: SharedWidgetProps;
};

function useGmWorkspaceState(): GmWorkspaceState {
  const campaignsQuery = useQuery({ queryKey: ["campaigns"], queryFn: api.campaigns });
  const runtimeQuery = useQuery({ queryKey: ["runtime"], queryFn: api.runtime });
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);

  useEffect(() => {
    if (selectedCampaignId) return;
    if (runtimeQuery.data === undefined && runtimeQuery.isFetching) return;
    const campaigns = campaignsQuery.data ?? [];
    const runtimeCampaignId = runtimeQuery.data?.active_campaign_id;
    if (runtimeCampaignId) {
      setSelectedCampaignId(runtimeCampaignId);
      return;
    }
    if (campaigns.length > 0) {
      setSelectedCampaignId(campaigns[0].id);
    }
  }, [campaignsQuery.data, runtimeQuery.data, runtimeQuery.isFetching, selectedCampaignId]);

  const selectedCampaign = useMemo(
    () => campaignsQuery.data?.find((campaign) => campaign.id === selectedCampaignId) ?? null,
    [campaignsQuery.data, selectedCampaignId]
  );

  const sessionsQuery = useQuery({
    queryKey: ["sessions", selectedCampaignId],
    queryFn: () => api.sessions(selectedCampaignId!),
    enabled: Boolean(selectedCampaignId)
  });

  const scenesQuery = useQuery({
    queryKey: ["scenes", selectedCampaignId],
    queryFn: () => api.scenes(selectedCampaignId!),
    enabled: Boolean(selectedCampaignId)
  });

  useEffect(() => {
    if (sessionsQuery.isFetching) return;
    const runtimeSessionId = runtimeQuery.data?.active_session_id;
    const sessions = sessionsQuery.data ?? [];
    if (selectedSessionId && sessions.some((session) => session.id === selectedSessionId)) return;
    if (runtimeSessionId && sessions.some((session) => session.id === runtimeSessionId)) {
      setSelectedSessionId(runtimeSessionId);
      return;
    }
    setSelectedSessionId(sessions[0]?.id ?? null);
  }, [runtimeQuery.data?.active_session_id, selectedSessionId, sessionsQuery.data, sessionsQuery.isFetching]);

  useEffect(() => {
    if (scenesQuery.isFetching) return;
    const runtimeSceneId = runtimeQuery.data?.active_scene_id;
    const scenes = scenesQuery.data ?? [];
    if (selectedSceneId && scenes.some((scene) => scene.id === selectedSceneId)) return;
    if (runtimeSceneId && scenes.some((scene) => scene.id === runtimeSceneId)) {
      setSelectedSceneId(runtimeSceneId);
      return;
    }
    const sessionScene = selectedSessionId
      ? scenes.find((scene) => scene.session_id === selectedSessionId)
      : undefined;
    setSelectedSceneId(sessionScene?.id ?? scenes[0]?.id ?? null);
  }, [runtimeQuery.data?.active_scene_id, scenesQuery.data, scenesQuery.isFetching, selectedSceneId, selectedSessionId]);

  const shared = {
    campaigns: campaignsQuery.data ?? [],
    sessions: sessionsQuery.data ?? [],
    scenes: scenesQuery.data ?? [],
    runtime: runtimeQuery.data,
    selectedCampaign,
    selectedCampaignId,
    selectedSessionId,
    selectedSceneId,
    setSelectedCampaignId,
    setSelectedSessionId,
    setSelectedSceneId
  };

  return { campaignsQuery, runtimeQuery, sessionsQuery, scenesQuery, shared };
}

function GmTopbar({
  title,
  runtimeQuery,
  action
}: {
  title: string;
  runtimeQuery: ReturnType<typeof useQuery<RuntimeState>>;
  action?: ReactNode;
}) {
  const path = window.location.pathname;
  const links = [
    { href: "/gm", label: "Overview", icon: <LayoutDashboard size={15} /> },
    { href: "/gm/map", label: "Map", icon: <Map size={15} /> },
    { href: "/gm/library", label: "Library", icon: <FileText size={15} /> },
    { href: "/gm/actors", label: "Actors", icon: <Users size={15} /> },
    { href: "/gm/combat", label: "Combat", icon: <Swords size={15} /> },
    { href: "/gm/scene", label: "Scene", icon: <Eye size={15} /> },
    { href: "/gm/floating", label: "Floating", icon: <PanelTop size={15} /> }
  ];
  return (
    <header className="topbar">
      <div className="topbar-title">
        <span className="brand">Myroll</span>
        <span className="muted">{title}</span>
      </div>
      <nav className="surface-nav" aria-label="GM surfaces">
        {links.map((link) => (
          <a key={link.href} className={path === link.href ? "active" : ""} href={link.href}>
            {link.icon}
            {link.label}
          </a>
        ))}
      </nav>
      <div className="topbar-actions">
        {action}
        <span className={runtimeQuery.isError ? "status-pill danger" : "status-pill"}>
          {runtimeQuery.isError ? <WifiOff size={14} /> : <CheckCircle2 size={14} />}
          {runtimeQuery.isError ? "Backend unavailable" : "Backend linked"}
        </span>
      </div>
    </header>
  );
}

function WorkbenchPanel({
  kind,
  title,
  children,
  className = ""
}: {
  kind: string;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`workbench-panel ${className}`} data-widget-kind={kind}>
      <div className="workbench-panel-title">
        <span>{title}</span>
      </div>
      <div className="workbench-panel-content">{children}</div>
    </section>
  );
}

function SurfaceUnavailable({ error }: { error: unknown }) {
  return (
    <div className="degraded">
      <WifiOff size={24} />
      <div>
        <strong>Workspace data unavailable</strong>
        <p>{errorMessage(error)}</p>
      </div>
    </div>
  );
}

function GmOverviewSurface() {
  const state = useGmWorkspaceState();
  const { shared, runtimeQuery, campaignsQuery } = state;
  const selectedScene = shared.scenes.find((scene) => scene.id === shared.selectedSceneId) ?? null;
  return (
    <div className="gm-shell gm-workbench-shell">
      <GmTopbar title="GM Overview" runtimeQuery={runtimeQuery} />
      {campaignsQuery.isError ? <SurfaceUnavailable error={campaignsQuery.error} /> : null}
      <main className="gm-overview-grid">
        <aside className="gm-left-rail">
          <WorkbenchPanel kind="campaigns" title="Campaigns">
            <CampaignsWidget {...shared} />
          </WorkbenchPanel>
          <WorkbenchPanel kind="sessions" title="Sessions">
            <SessionsWidget {...shared} />
          </WorkbenchPanel>
          <WorkbenchPanel kind="scenes" title="Scenes">
            <ScenesWidget {...shared} />
          </WorkbenchPanel>
        </aside>
        <section className="gm-center-stage">
          <div className="hero-workbench-card">
            <span className="player-kicker">Active workbench</span>
            <h1>{selectedScene?.title ?? shared.runtime?.active_scene_title ?? "No active scene"}</h1>
            <p>{selectedScene?.summary ?? "Choose or activate a scene, then open a focused workbench for map, notes, actors, or combat."}</p>
            <div className="surface-launch-grid">
              <a href="/gm/map">
                <Map size={18} />
                <span>Open Map Workbench</span>
              </a>
              <a href="/gm/library">
                <FileText size={18} />
                <span>Open Library</span>
              </a>
              <a href="/gm/actors">
                <Users size={18} />
                <span>Open Actors</span>
              </a>
              <a href="/gm/combat">
                <Swords size={18} />
                <span>Open Combat</span>
              </a>
            </div>
          </div>
          <WorkbenchPanel kind="scene_context" title="Scene Context" className="scene-overview-panel">
            <SceneContextWidget {...shared} />
          </WorkbenchPanel>
        </section>
        <aside className="gm-right-rail">
          <WorkbenchPanel kind="scribe" title="Scribe">
            <ScribeWidget {...shared} />
          </WorkbenchPanel>
          <WorkbenchPanel kind="runtime" title="Runtime">
            <RuntimeWidget {...shared} />
          </WorkbenchPanel>
          <WorkbenchPanel kind="player_display" title="Player Display">
            <PlayerDisplayWidget />
          </WorkbenchPanel>
          <WorkbenchPanel kind="storage_demo" title="Storage / Demo">
            <StorageDemoWidget />
          </WorkbenchPanel>
          <WorkbenchPanel kind="backend_status" title="Backend Status">
            <BackendStatusWidget />
          </WorkbenchPanel>
        </aside>
      </main>
    </div>
  );
}

function GmMapSurface() {
  const { shared, runtimeQuery } = useGmWorkspaceState();
  return (
    <div className="gm-shell gm-workbench-shell">
      <GmTopbar title="Map Workbench" runtimeQuery={runtimeQuery} />
      <main className="gm-map-surface">
        <section className="map-focus-panel" data-widget-kind="map_display">
          <div className="workbench-panel-title">
            <span>Map Display</span>
            <span className="muted">full surface</span>
          </div>
          <MapDisplayWidget {...shared} />
        </section>
        <aside className="map-inspector-rail">
          <WorkbenchPanel kind="player_display" title="Player Display">
            <PlayerDisplayWidget />
          </WorkbenchPanel>
          <WorkbenchPanel kind="scene_context" title="Scene Context">
            <SceneContextWidget {...shared} />
          </WorkbenchPanel>
        </aside>
      </main>
    </div>
  );
}

function GmLibrarySurface() {
  const { shared, runtimeQuery } = useGmWorkspaceState();
  return (
    <div className="gm-shell gm-workbench-shell">
      <GmTopbar title="Library" runtimeQuery={runtimeQuery} />
      <main className="two-column-surface">
        <WorkbenchPanel kind="asset_library" title="Asset Library">
          <AssetLibraryWidget {...shared} />
        </WorkbenchPanel>
        <WorkbenchPanel kind="notes" title="Notes / Public Snippets">
          <NotesWidget {...shared} />
        </WorkbenchPanel>
      </main>
    </div>
  );
}

function GmActorsSurface() {
  const { shared, runtimeQuery } = useGmWorkspaceState();
  return (
    <div className="gm-shell gm-workbench-shell">
      <GmTopbar title="Actors" runtimeQuery={runtimeQuery} />
      <main className="single-surface">
        <WorkbenchPanel kind="party_tracker" title="Party Tracker">
          <PartyTrackerWidget {...shared} />
        </WorkbenchPanel>
      </main>
    </div>
  );
}

function GmCombatSurface() {
  const { shared, runtimeQuery } = useGmWorkspaceState();
  return (
    <div className="gm-shell gm-workbench-shell">
      <GmTopbar title="Combat" runtimeQuery={runtimeQuery} />
      <main className="single-surface">
        <WorkbenchPanel kind="combat_tracker" title="Combat Tracker">
          <CombatTrackerWidget {...shared} />
        </WorkbenchPanel>
      </main>
    </div>
  );
}

function GmSceneSurface() {
  const { shared, runtimeQuery } = useGmWorkspaceState();
  return (
    <div className="gm-shell gm-workbench-shell">
      <GmTopbar title="Scene Orchestration" runtimeQuery={runtimeQuery} />
      <main className="two-column-surface scene-surface">
        <WorkbenchPanel kind="scene_context" title="Scene Context">
          <SceneContextWidget {...shared} />
        </WorkbenchPanel>
        <div className="stacked-panels">
          <WorkbenchPanel kind="runtime" title="Runtime">
            <RuntimeWidget {...shared} />
          </WorkbenchPanel>
          <WorkbenchPanel kind="player_display" title="Player Display">
            <PlayerDisplayWidget />
          </WorkbenchPanel>
        </div>
      </main>
    </div>
  );
}

function FloatingGmShell() {
  const queryClient = useQueryClient();
  const { shared, runtimeQuery } = useGmWorkspaceState();
  const widgetsQuery = useQuery({ queryKey: ["workspace-widgets"], queryFn: api.workspaceWidgets });
  const [localWidgets, setLocalWidgets] = useState<WorkspaceWidget[]>([]);
  const [saveStatus, setSaveStatus] = useState<WidgetStatusMap>({});

  useEffect(() => {
    if (widgetsQuery.data?.widgets) setLocalWidgets(widgetsQuery.data.widgets);
  }, [widgetsQuery.data]);

  const patchWidgetMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: WidgetPatch }) => api.patchWorkspaceWidget(id, patch),
    onSuccess: (updated) => {
      setLocalWidgets((widgets) => widgets.map((widget) => (widget.id === updated.id ? updated : widget)));
      setSaveStatus((statuses) => ({ ...statuses, [updated.id]: "saved" }));
      void queryClient.invalidateQueries({ queryKey: ["workspace-widgets"] });
    },
    onError: (_error, variables) => {
      setSaveStatus((statuses) => ({ ...statuses, [variables.id]: "error" }));
    }
  });

  const resetWidgetsMutation = useMutation({
    mutationFn: api.resetWorkspaceWidgets,
    onSuccess: (data) => {
      setLocalWidgets(data.widgets);
      setSaveStatus({});
      void queryClient.invalidateQueries({ queryKey: ["workspace-widgets"] });
    }
  });

  function updateLocalWidget(id: string, patch: WidgetPatch) {
    setLocalWidgets((widgets) => applyWidgetPatch(widgets, id, patch));
  }

  function persistWidget(id: string, patch: WidgetPatch) {
    setSaveStatus((statuses) => ({ ...statuses, [id]: "saving" }));
    patchWidgetMutation.mutate({ id, patch });
  }

  return (
    <div className="gm-shell">
      <GmTopbar
        title="Floating Workspace"
        runtimeQuery={runtimeQuery}
        action={
          <button className="icon-text" onClick={() => resetWidgetsMutation.mutate()} title="Reset workspace layout">
            <RotateCcw size={16} /> Reset layout
          </button>
        }
      />

      {widgetsQuery.isError ? (
        <div className="degraded">
          <WifiOff size={24} />
          <div>
            <strong>Workspace layout unavailable</strong>
            <p>{errorMessage(widgetsQuery.error)}</p>
          </div>
        </div>
      ) : null}

      <main className="workspace-canvas" aria-label="GM workspace canvas">
        {(localWidgets.length > 0 ? localWidgets : fallbackWidgets()).map((widget) => (
          <Rnd
            key={widget.id}
            bounds="parent"
            minWidth={220}
            minHeight={160}
            position={{ x: widget.x, y: widget.y }}
            size={{ width: widget.width, height: widget.height }}
            style={{ zIndex: widget.z_index }}
            dragHandleClassName="widget-titlebar"
            disableDragging={widget.locked}
            enableResizing={!widget.locked}
            onDrag={(_event, data) => updateLocalWidget(widget.id, { x: data.x, y: data.y })}
            onDragStop={(_event, data) => persistWidget(widget.id, { x: data.x, y: data.y })}
            onResize={(_event, _direction, ref, _delta, position) =>
              updateLocalWidget(widget.id, {
                width: Number.parseInt(ref.style.width, 10),
                height: Number.parseInt(ref.style.height, 10),
                x: position.x,
                y: position.y
              })
            }
            onResizeStop={(_event, _direction, ref, _delta, position) =>
              persistWidget(widget.id, {
                width: Number.parseInt(ref.style.width, 10),
                height: Number.parseInt(ref.style.height, 10),
                x: position.x,
                y: position.y
              })
            }
          >
            <WidgetFrame widget={widget} saveStatus={saveStatus[widget.id] ?? "saved"}>
              <WidgetBody widget={widget} shared={shared} />
            </WidgetFrame>
          </Rnd>
        ))}
      </main>
    </div>
  );
}

export function applyWidgetPatch(widgets: WorkspaceWidget[], id: string, patch: WidgetPatch): WorkspaceWidget[] {
  return widgets.map((widget) => (widget.id === id ? { ...widget, ...patch } : widget));
}

export function WidgetFrame({
  widget,
  saveStatus,
  children
}: {
  widget: WorkspaceWidget;
  saveStatus: SaveStatus;
  children: ReactNode;
}) {
  return (
    <section className="widget" data-widget-kind={widget.kind}>
      <div className="widget-titlebar">
        <span>{widget.title}</span>
        {saveStatus === "saving" ? <span className="save-indicator">Saving</span> : null}
        {saveStatus === "error" ? <span className="save-indicator error">Unsaved</span> : null}
      </div>
      <div className="widget-content">{children}</div>
    </section>
  );
}

type SharedWidgetProps = {
  campaigns: Campaign[];
  sessions: Session[];
  scenes: Scene[];
  runtime?: RuntimeState;
  selectedCampaign: Campaign | null;
  selectedCampaignId: string | null;
  selectedSessionId: string | null;
  selectedSceneId: string | null;
  setSelectedCampaignId: (id: string | null) => void;
  setSelectedSessionId: (id: string | null) => void;
  setSelectedSceneId: (id: string | null) => void;
};

function WidgetBody({ widget, shared }: { widget: WorkspaceWidget; shared: SharedWidgetProps }) {
  if (widget.kind === "map_display") return <MapDisplayWidget {...shared} />;
  if (widget.kind === "notes") return <NotesWidget {...shared} />;
  if (widget.kind === "party_tracker") return <PartyTrackerWidget {...shared} />;
  if (widget.kind === "combat_tracker") return <CombatTrackerWidget {...shared} />;
  if (widget.kind === "scene_context") return <SceneContextWidget {...shared} />;
  if (widget.kind === "scribe") return <ScribeWidget {...shared} />;
  if (widget.config.placeholder) return <PlaceholderWidget kind={widget.kind} />;
  switch (widget.kind) {
    case "backend_status":
      return <BackendStatusWidget />;
    case "campaigns":
      return <CampaignsWidget {...shared} />;
    case "sessions":
      return <SessionsWidget {...shared} />;
    case "scenes":
      return <ScenesWidget {...shared} />;
    case "runtime":
      return <RuntimeWidget {...shared} />;
    case "player_display":
      return <PlayerDisplayWidget />;
    case "asset_library":
      return <AssetLibraryWidget {...shared} />;
    case "storage_demo":
      return <StorageDemoWidget />;
    default:
      return <PlaceholderWidget kind={widget.kind} />;
  }
}

export function BackendStatusWidget() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 10_000, retry: false });
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, retry: false });
  if (health.isError || meta.isError) {
    return (
      <div className="empty-state danger">
        <WifiOff size={22} />
        <strong>Backend unavailable</strong>
        <span>{errorMessage(health.error ?? meta.error)}</span>
      </div>
    );
  }
  return (
    <div className="status-grid">
      <InfoRow label="App" value={meta.data?.app ?? "myroll"} />
      <InfoRow label="Backend" value={health.data?.status ?? "checking"} />
      <InfoRow label="DB" value={health.data?.db ?? "checking"} />
      <InfoRow label="Schema" value={meta.data?.schema_version ?? "unknown"} />
      <InfoRow label="Seed" value={meta.data?.seed_version ?? "unknown"} />
      <InfoRow label="Path" value={meta.data?.db_path ?? "-"} />
    </div>
  );
}

function formatBytes(value: number | undefined): string {
  if (value === undefined) return "-";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MiB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GiB`;
}

function artifactLabel(artifact: StorageArtifact | null | undefined): string {
  if (!artifact) return "none";
  return `${artifact.archive_name} (${formatBytes(artifact.byte_size)})`;
}

export function StorageDemoWidget() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({ queryKey: ["storage-status"], queryFn: api.storageStatus, refetchInterval: 15_000, retry: false });
  const backupMutation = useMutation({
    mutationFn: api.createStorageBackup,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["storage-status"] });
    }
  });
  const exportMutation = useMutation({
    mutationFn: () => api.createStorageExport(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["storage-status"] });
    }
  });

  if (statusQuery.isError) {
    return (
      <div className="empty-state danger">
        <WifiOff size={22} />
        <strong>Storage status unavailable</strong>
        <span>{errorMessage(statusQuery.error)}</span>
      </div>
    );
  }

  const latestExport = exportMutation.data ?? statusQuery.data?.latest_export ?? null;
  return (
    <div className="storage-widget">
      <div className="status-grid">
        <InfoRow label="Profile" value={statusQuery.data?.profile ?? "checking"} />
        <InfoRow label="DB" value={`${formatBytes(statusQuery.data?.db_size_bytes)} · ${statusQuery.data?.db_path ?? "-"}`} />
        <InfoRow label="Assets" value={`${formatBytes(statusQuery.data?.asset_size_bytes)} · ${statusQuery.data?.asset_dir ?? "-"}`} />
        <InfoRow label="Private map" value={statusQuery.data?.private_demo_name_map_active ? "active" : "inactive"} />
        <InfoRow label="Backup" value={artifactLabel(statusQuery.data?.latest_backup)} />
        <InfoRow label="Export" value={artifactLabel(latestExport)} />
      </div>
      <div className="storage-actions">
        <button onClick={() => backupMutation.mutate()} disabled={backupMutation.isPending}>
          <CheckCircle2 size={15} /> Backup DB
        </button>
        <button onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending}>
          <FileText size={15} /> Export
        </button>
        <button
          disabled={!latestExport?.download_url}
          onClick={() => {
            if (latestExport?.download_url) window.open(latestExport.download_url, "_blank", "noopener,noreferrer");
          }}
        >
          <Download size={15} /> Download
        </button>
      </div>
      {backupMutation.isError ? <ErrorLine error={backupMutation.error} /> : null}
      {exportMutation.isError ? <ErrorLine error={exportMutation.error} /> : null}
      {exportMutation.data ? <p className="muted-block">Created export: {exportMutation.data.archive_name}</p> : null}
    </div>
  );
}

function CampaignsWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.createCampaign({ name, description: "" }),
    onSuccess: (campaign) => {
      setName("");
      props.setSelectedCampaignId(campaign.id);
      void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    }
  });
  return (
    <div className="stack">
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) mutation.mutate();
        }}
      >
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="New campaign" />
        <button type="submit">Create</button>
      </form>
      <EntityList
        items={props.campaigns}
        activeId={props.runtime?.active_campaign_id}
        selectedId={props.selectedCampaignId}
        label={(campaign) => campaign.name}
        onSelect={(campaign) => props.setSelectedCampaignId(campaign.id)}
      />
      {mutation.isError ? <ErrorLine error={mutation.error} /> : null}
    </div>
  );
}

function SessionsWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.createSession(props.selectedCampaignId!, { title }),
    onSuccess: (session) => {
      setTitle("");
      props.setSelectedSessionId(session.id);
      void queryClient.invalidateQueries({ queryKey: ["sessions", props.selectedCampaignId] });
    }
  });
  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to manage sessions." />;
  return (
    <div className="stack">
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (title.trim()) mutation.mutate();
        }}
      >
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="New session" />
        <button type="submit">Create</button>
      </form>
      <EntityList
        items={props.sessions}
        activeId={props.runtime?.active_session_id}
        selectedId={props.selectedSessionId}
        label={(session) => session.title}
        onSelect={(session) => props.setSelectedSessionId(session.id)}
      />
      {mutation.isError ? <ErrorLine error={mutation.error} /> : null}
    </div>
  );
}

function ScenesWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api.createScene(props.selectedCampaignId!, {
        title,
        summary: "",
        session_id: props.selectedSessionId
      }),
    onSuccess: (scene) => {
      setTitle("");
      props.setSelectedSceneId(scene.id);
      void queryClient.invalidateQueries({ queryKey: ["scenes", props.selectedCampaignId] });
    }
  });
  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to manage scenes." />;
  return (
    <div className="stack">
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (title.trim()) mutation.mutate();
        }}
      >
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="New scene" />
        <button type="submit">Create</button>
      </form>
      <EntityList
        items={props.scenes}
        activeId={props.runtime?.active_scene_id}
        selectedId={props.selectedSceneId}
        label={(scene) => scene.title}
        onSelect={(scene) => props.setSelectedSceneId(scene.id)}
      />
      {mutation.isError ? <ErrorLine error={mutation.error} /> : null}
    </div>
  );
}

function RuntimeWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const activateCampaign = useMutation({
    mutationFn: (id: string) => api.activateCampaign(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["runtime"] })
  });
  const activateSession = useMutation({
    mutationFn: (id: string) => api.activateSession(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["runtime"] })
  });
  const activateScene = useMutation({
    mutationFn: (id: string) => api.activateScene(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["runtime"] })
  });
  const clearRuntime = useMutation({
    mutationFn: api.clearRuntime,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["runtime"] })
  });
  const selectedScene = props.scenes.find((scene) => scene.id === props.selectedSceneId) ?? null;
  return (
    <div className="stack">
      <div className="status-grid">
        <InfoRow label="Campaign" value={props.runtime?.active_campaign_name ?? "None"} />
        <InfoRow label="Session" value={props.runtime?.active_session_title ?? "None"} />
        <InfoRow label="Scene" value={props.runtime?.active_scene_title ?? "None"} />
      </div>
      <div className="button-grid">
        <button disabled={!props.selectedCampaignId} onClick={() => activateCampaign.mutate(props.selectedCampaignId!)}>
          Activate campaign
        </button>
        <button disabled={!props.selectedSessionId} onClick={() => activateSession.mutate(props.selectedSessionId!)}>
          Activate session
        </button>
        <button disabled={!selectedScene} onClick={() => selectedScene && activateScene.mutate(selectedScene.id)}>
          Activate scene
        </button>
        <button onClick={() => clearRuntime.mutate()}>Clear</button>
      </div>
      {[activateCampaign, activateSession, activateScene, clearRuntime].some((mutation) => mutation.isError) ? (
        <ErrorLine error={[activateCampaign, activateSession, activateScene, clearRuntime].find((m) => m.error)?.error} />
      ) : null}
    </div>
  );
}

function sourceRefLabel(ref: Record<string, unknown>): string {
  return `${String(ref.kind ?? "source")}:${String(ref.id ?? "").slice(0, 8)} · ${String(ref.lane ?? "lane")}`;
}

function sourceRefKey(ref: Record<string, unknown>): string {
  return `${String(ref.kind ?? "source")}:${String(ref.id ?? "")}`;
}

function proposalOptionLabel(status: ProposalOption["status"]): string {
  if (status === "selected") return "Selected";
  if (status === "rejected") return "Rejected by GM";
  if (status === "saved_for_later") return "Saved for later";
  if (status === "superseded") return "Not chosen in this pass";
  if (status === "canonized") return "Canonized via memory";
  return "Proposed";
}

function ScribeWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [captureBody, setCaptureBody] = useState("");
  const [correctionTarget, setCorrectionTarget] = useState<SessionTranscriptEvent | null>(null);
  const [correctionBody, setCorrectionBody] = useState("");
  const [providerId, setProviderId] = useState<string | null>(null);
  const [providerLabel, setProviderLabel] = useState("Local model");
  const [providerVendor, setProviderVendor] = useState<"openai" | "ollama" | "lmstudio" | "kobold" | "openrouter" | "custom">("custom");
  const [providerBaseUrl, setProviderBaseUrl] = useState("http://127.0.0.1:11434/v1");
  const [providerModelId, setProviderModelId] = useState("llama3");
  const [providerKeySource, setProviderKeySource] = useState<"none" | "env">("none");
  const [providerKeyRef, setProviderKeyRef] = useState("MYROLL_LLM_API_KEY");
  const [gmInstruction, setGmInstruction] = useState("");
  const [contextPackage, setContextPackage] = useState<null | Awaited<ReturnType<typeof api.createContextPreview>>>(null);
  const [recapDraft, setRecapDraft] = useState<BuildRecapResult | null>(null);
  const [recapTitle, setRecapTitle] = useState("");
  const [recapBody, setRecapBody] = useState("");
  const [recallQuery, setRecallQuery] = useState("");
  const [aliasText, setAliasText] = useState("");
  const [inspectionOpen, setInspectionOpen] = useState(false);
  const [branchScope, setBranchScope] = useState<"campaign" | "session" | "scene">("scene");
  const [branchInstruction, setBranchInstruction] = useState("");
  const [branchContextPackage, setBranchContextPackage] = useState<null | Awaited<ReturnType<typeof api.createContextPreview>>>(null);
  const [branchDraft, setBranchDraft] = useState<BuildBranchResult | null>(null);
  const [selectedProposalSetId, setSelectedProposalSetId] = useState<string | null>(null);
  const [adoptOption, setAdoptOption] = useState<ProposalOption | null>(null);
  const [markerTitle, setMarkerTitle] = useState("");
  const [markerText, setMarkerText] = useState("");
  const [markerConfirmWarnings, setMarkerConfirmWarnings] = useState(false);
  const [linkedCandidateConfirmId, setLinkedCandidateConfirmId] = useState<string | null>(null);
  const [playerSafeInstruction, setPlayerSafeInstruction] = useState("");
  const [includeUnshownPublicSnippets, setIncludeUnshownPublicSnippets] = useState(false);
  const [excludedPublicSafeRefs, setExcludedPublicSafeRefs] = useState<string[]>([]);
  const [playerSafeContextPackage, setPlayerSafeContextPackage] = useState<null | Awaited<ReturnType<typeof api.createContextPreview>>>(null);
  const [playerSafeDraft, setPlayerSafeDraft] = useState<Awaited<ReturnType<typeof api.buildPlayerSafeRecap>> | null>(null);
  const [playerSafeTitle, setPlayerSafeTitle] = useState("");
  const [playerSafeBody, setPlayerSafeBody] = useState("");
  const [playerSafeSourceDraftHash, setPlayerSafeSourceDraftHash] = useState<string | null>(null);
  const [publicSafetyScan, setPublicSafetyScan] = useState<Awaited<ReturnType<typeof api.scanPublicSafetyWarnings>> | null>(null);
  const [publicSafetyAckHash, setPublicSafetyAckHash] = useState<string | null>(null);
  const [publicSafetyCurationAck, setPublicSafetyCurationAck] = useState<PublicSafetyCurationAck | null>(null);

  const transcriptQuery = useQuery({
    queryKey: ["scribe-transcript", props.selectedCampaignId, props.selectedSessionId],
    queryFn: () => api.transcriptEvents(props.selectedCampaignId!, props.selectedSessionId),
    enabled: Boolean(props.selectedCampaignId && props.selectedSessionId)
  });
  const providersQuery = useQuery({ queryKey: ["llm-provider-profiles"], queryFn: api.llmProviderProfiles });
  const candidatesQuery = useQuery({
    queryKey: ["memory-candidates", props.selectedCampaignId],
    queryFn: () => api.memoryCandidates(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const aliasesQuery = useQuery({
    queryKey: ["entity-aliases", props.selectedCampaignId],
    queryFn: () => api.entityAliases(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const proposalSetsQuery = useQuery({
    queryKey: ["proposal-sets", props.selectedCampaignId],
    queryFn: () => api.proposalSets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const proposalDetailQuery = useQuery({
    queryKey: ["proposal-set", selectedProposalSetId],
    queryFn: () => api.proposalSet(selectedProposalSetId!),
    enabled: Boolean(selectedProposalSetId)
  });
  const planningMarkersQuery = useQuery({
    queryKey: ["planning-markers", props.selectedCampaignId],
    queryFn: () => api.planningMarkers(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const publicSnippetsQuery = useQuery({
    queryKey: ["public-snippets", props.selectedCampaignId],
    queryFn: () => api.publicSnippets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const sessionRecapsQuery = useQuery({
    queryKey: ["session-recaps", props.selectedCampaignId, props.selectedSessionId],
    queryFn: () => api.sessionRecaps(props.selectedCampaignId!, props.selectedSessionId),
    enabled: Boolean(props.selectedCampaignId && props.selectedSessionId)
  });
  const memoryEntriesQuery = useQuery({
    queryKey: ["memory-entries", props.selectedCampaignId, props.selectedSessionId],
    queryFn: () => api.memoryEntries(props.selectedCampaignId!, props.selectedSessionId),
    enabled: Boolean(props.selectedCampaignId && props.selectedSessionId)
  });
  const recallResult = useMutation({
    mutationFn: () => api.recall(props.selectedCampaignId!, { query: recallQuery })
  });

  const providers = providersQuery.data?.profiles ?? [];
  const selectedProvider = providers.find((profile) => profile.id === providerId) ?? providers[0] ?? null;

  useEffect(() => {
    if (!selectedProvider) return;
    setProviderId(selectedProvider.id);
    setProviderLabel(selectedProvider.label);
    setProviderVendor(selectedProvider.vendor);
    setProviderBaseUrl(selectedProvider.base_url);
    setProviderModelId(selectedProvider.model_id);
    setProviderKeySource(selectedProvider.key_source.type);
    setProviderKeyRef(selectedProvider.key_source.ref ?? "MYROLL_LLM_API_KEY");
  }, [selectedProvider?.id]);

  const capture = useMutation({
    mutationFn: () =>
      api.createTranscriptEvent(props.selectedCampaignId!, {
        session_id: props.selectedSessionId!,
        scene_id: props.selectedSceneId,
        body: captureBody,
        source: "typed"
      }),
    onSuccess: () => {
      setCaptureBody("");
      setContextPackage(null);
      setBranchContextPackage(null);
      setRecapDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["scribe-transcript", props.selectedCampaignId, props.selectedSessionId] });
    }
  });
  const correct = useMutation({
    mutationFn: () => api.correctTranscriptEvent(correctionTarget!.id, { body: correctionBody }),
    onSuccess: () => {
      setCorrectionTarget(null);
      setCorrectionBody("");
      setContextPackage(null);
      setBranchContextPackage(null);
      setRecapDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["scribe-transcript", props.selectedCampaignId, props.selectedSessionId] });
    }
  });
  const saveProvider = useMutation({
    mutationFn: () => {
      const payload = {
        label: providerLabel,
        vendor: providerVendor,
        base_url: providerBaseUrl,
        model_id: providerModelId,
        key_source: { type: providerKeySource, ref: providerKeySource === "env" ? providerKeyRef : null }
      };
      return selectedProvider ? api.patchLlmProviderProfile(selectedProvider.id, payload) : api.createLlmProviderProfile(payload);
    },
    onSuccess: (profile) => {
      setProviderId(profile.id);
      void queryClient.invalidateQueries({ queryKey: ["llm-provider-profiles"] });
    }
  });
  const testProvider = useMutation({
    mutationFn: () => api.testLlmProviderProfile(selectedProvider!.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["llm-provider-profiles"] })
  });
  const previewContext = useMutation({
    mutationFn: () =>
      api.createContextPreview(props.selectedCampaignId!, {
        session_id: props.selectedSessionId!,
        task_kind: "session.build_recap",
        visibility_mode: "gm_private",
        gm_instruction: gmInstruction
      }),
    onSuccess: (preview) => {
      setContextPackage(preview);
      setInspectionOpen(true);
    }
  });
  const previewBranchContext = useMutation({
    mutationFn: () =>
      api.createContextPreview(props.selectedCampaignId!, {
        session_id: branchScope === "campaign" ? null : props.selectedSessionId,
        scene_id: branchScope === "scene" ? props.selectedSceneId : null,
        task_kind: "scene.branch_directions",
        scope_kind: branchScope,
        visibility_mode: "gm_private",
        gm_instruction: branchInstruction
      }),
    onSuccess: (preview) => {
      setBranchContextPackage(preview);
      setBranchDraft(null);
    }
  });
  const previewPlayerSafeContext = useMutation({
    mutationFn: () =>
      api.createContextPreview(props.selectedCampaignId!, {
        session_id: props.selectedSessionId!,
        task_kind: "session.player_safe_recap",
        visibility_mode: "public_safe",
        gm_instruction: playerSafeInstruction,
        include_unshown_public_snippets: includeUnshownPublicSnippets,
        excluded_source_refs: excludedPublicSafeRefs
      }),
    onSuccess: (preview) => {
      setPlayerSafeContextPackage(preview);
      setPlayerSafeDraft(null);
      setPublicSafetyScan(null);
      setPublicSafetyAckHash(null);
    }
  });
  const reviewContext = useMutation({
    mutationFn: () => api.reviewContextPackage(contextPackage!.id),
    onSuccess: (preview) => setContextPackage(preview)
  });
  const reviewBranchContext = useMutation({
    mutationFn: () => api.reviewContextPackage(branchContextPackage!.id),
    onSuccess: (preview) => setBranchContextPackage(preview)
  });
  const reviewPlayerSafeContext = useMutation({
    mutationFn: () => api.reviewContextPackage(playerSafeContextPackage!.id),
    onSuccess: (preview) => setPlayerSafeContextPackage(preview)
  });
  const publicSafetyAckFromError = (error: unknown, kind: PublicSafetyCurationAck["kind"], id: string): boolean => {
    if (!(error instanceof ApiError) || error.code !== "public_safety_ack_required") return false;
    const detail = error.details?.[0];
    const contentHash = typeof detail?.content_hash === "string" ? detail.content_hash : null;
    const warnings = Array.isArray(detail?.warnings) ? (detail.warnings as PublicSafetyWarning[]) : [];
    if (!contentHash) return false;
    setPublicSafetyCurationAck({ kind, id, contentHash, warnings });
    return true;
  };
  const buildRecap = useMutation({
    mutationFn: () =>
      api.buildSessionRecap(props.selectedCampaignId!, {
        session_id: props.selectedSessionId!,
        provider_profile_id: selectedProvider!.id,
        context_package_id: contextPackage!.id
      }),
    onSuccess: (result) => {
      setRecapDraft(result);
      setRecapTitle(result.bundle.privateRecap?.title ?? "Session recap");
      setRecapBody(result.bundle.privateRecap?.bodyMarkdown ?? "");
      void queryClient.invalidateQueries({ queryKey: ["memory-candidates", props.selectedCampaignId] });
    }
  });
  const saveRecap = useMutation({
    mutationFn: () =>
      api.saveSessionRecap(props.selectedCampaignId!, {
        session_id: props.selectedSessionId!,
        title: recapTitle,
        body_markdown: recapBody,
        source_llm_run_id: recapDraft?.run.id ?? null,
        evidence_refs: contextPackage?.source_refs ?? []
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["memory-candidates", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["session-recaps", props.selectedCampaignId, props.selectedSessionId] });
    }
  });
  const buildBranch = useMutation({
    mutationFn: () =>
      api.buildBranchDirections(props.selectedCampaignId!, {
        provider_profile_id: selectedProvider!.id,
        context_package_id: branchContextPackage!.id
      }),
    onSuccess: (result) => {
      setBranchDraft(result);
      if (result.proposal_set) setSelectedProposalSetId(result.proposal_set.proposal_set.id);
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["planning-markers", props.selectedCampaignId] });
    }
  });
  const buildPlayerSafe = useMutation({
    mutationFn: () =>
      api.buildPlayerSafeRecap(props.selectedCampaignId!, {
        session_id: props.selectedSessionId!,
        provider_profile_id: selectedProvider!.id,
        context_package_id: playerSafeContextPackage!.id
      }),
    onSuccess: (result) => {
      setPlayerSafeDraft(result);
      setPlayerSafeTitle(result.public_snippet_draft.title);
      setPlayerSafeBody(result.public_snippet_draft.bodyMarkdown);
      setPlayerSafeSourceDraftHash(result.source_draft_hash);
      setPublicSafetyScan(null);
      setPublicSafetyAckHash(null);
    }
  });
  const scanPlayerSafeDraft = useMutation({
    mutationFn: () => api.scanPublicSafetyWarnings(props.selectedCampaignId!, { title: playerSafeTitle, body_markdown: playerSafeBody }),
    onSuccess: (scan) => {
      setPublicSafetyScan(scan);
      setPublicSafetyAckHash(scan.ack_required ? null : scan.content_hash);
    }
  });
  const createPlayerSafeSnippet = useMutation({
    mutationFn: () =>
      api.createPublicSnippet(props.selectedCampaignId!, {
        title: playerSafeTitle,
        body: playerSafeBody,
        format: "markdown",
        creation_source: "llm_scribe",
        source_llm_run_id: playerSafeDraft!.run.id,
        source_draft_hash: playerSafeSourceDraftHash,
        warning_content_hash: publicSafetyScan?.content_hash ?? null,
        warning_ack_content_hash: publicSafetyAckHash
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["public-snippets", props.selectedCampaignId] });
    }
  });
  const patchRecapSafety = useMutation({
    mutationFn: ({ recapId, publicSafe, warningHash }: { recapId: string; publicSafe: boolean; warningHash?: string | null }) =>
      api.patchSessionRecapPublicSafety(recapId, {
        campaign_id: props.selectedCampaignId,
        public_safe: publicSafe,
        sensitivity_reason: publicSafe ? null : "private_note",
        warning_content_hash: warningHash ?? null,
        warning_ack_content_hash: warningHash ?? null
      }),
    onSuccess: () => {
      setPlayerSafeContextPackage(null);
      setPublicSafetyCurationAck(null);
      void queryClient.invalidateQueries({ queryKey: ["session-recaps", props.selectedCampaignId, props.selectedSessionId] });
    },
    onError: (error, variables) => publicSafetyAckFromError(error, "recap", variables.recapId)
  });
  const patchMemorySafety = useMutation({
    mutationFn: ({ entryId, publicSafe, warningHash }: { entryId: string; publicSafe: boolean; warningHash?: string | null }) =>
      api.patchMemoryEntryPublicSafety(entryId, {
        campaign_id: props.selectedCampaignId,
        public_safe: publicSafe,
        sensitivity_reason: publicSafe ? null : "private_note",
        warning_content_hash: warningHash ?? null,
        warning_ack_content_hash: warningHash ?? null
      }),
    onSuccess: () => {
      setPlayerSafeContextPackage(null);
      setPublicSafetyCurationAck(null);
      void queryClient.invalidateQueries({ queryKey: ["memory-entries", props.selectedCampaignId, props.selectedSessionId] });
    },
    onError: (error, variables) => publicSafetyAckFromError(error, "memory", variables.entryId)
  });
  const acceptCandidate = useMutation({
    mutationFn: (candidate: MemoryCandidate) =>
      api.acceptMemoryCandidate(candidate.id, {
        confirm_linked_marker_canonization: linkedCandidateConfirmId === candidate.id
      }),
    onSuccess: () => {
      setLinkedCandidateConfirmId(null);
      void queryClient.invalidateQueries({ queryKey: ["memory-candidates", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["memory-entries", props.selectedCampaignId, props.selectedSessionId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-set", selectedProposalSetId] });
      void queryClient.invalidateQueries({ queryKey: ["planning-markers", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["scribe-recall", props.selectedCampaignId] });
    }
  });
  const rejectCandidate = useMutation({
    mutationFn: (candidateId: string) => api.rejectMemoryCandidate(candidateId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["memory-candidates", props.selectedCampaignId] })
  });
  const createAlias = useMutation({
    mutationFn: () => api.createEntityAlias(props.selectedCampaignId!, { alias_text: aliasText }),
    onSuccess: () => {
      setAliasText("");
      void queryClient.invalidateQueries({ queryKey: ["entity-aliases", props.selectedCampaignId] });
    }
  });
  const rejectOption = useMutation({
    mutationFn: (optionId: string) => api.rejectProposalOption(optionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-set", selectedProposalSetId] });
    }
  });
  const saveOptionForLater = useMutation({
    mutationFn: (optionId: string) => api.saveProposalOptionForLater(optionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-set", selectedProposalSetId] });
    }
  });
  const createPlanningMarker = useMutation({
    mutationFn: () =>
      api.createPlanningMarkerFromOption(adoptOption!.id, {
        title: markerTitle,
        marker_text: markerText,
        scope_kind: branchDraft?.proposal_set?.proposal_set.scope_kind ?? branchScope,
        session_id: branchScope === "campaign" ? null : props.selectedSessionId,
        scene_id: branchScope === "scene" ? props.selectedSceneId : null,
        confirm_warnings: markerConfirmWarnings
      }),
    onSuccess: () => {
      setAdoptOption(null);
      setMarkerTitle("");
      setMarkerText("");
      setMarkerConfirmWarnings(false);
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-set", selectedProposalSetId] });
      void queryClient.invalidateQueries({ queryKey: ["planning-markers", props.selectedCampaignId] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "marker_lint_confirmation_required") {
        setMarkerConfirmWarnings(true);
      }
    }
  });
  const expireMarker = useMutation({
    mutationFn: (markerId: string) => api.expirePlanningMarker(markerId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-set", selectedProposalSetId] });
      void queryClient.invalidateQueries({ queryKey: ["planning-markers", props.selectedCampaignId] });
    }
  });
  const discardMarker = useMutation({
    mutationFn: (markerId: string) => api.discardPlanningMarker(markerId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["proposal-sets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["proposal-set", selectedProposalSetId] });
      void queryClient.invalidateQueries({ queryKey: ["planning-markers", props.selectedCampaignId] });
    }
  });
  const markersById = new globalThis.Map((planningMarkersQuery.data?.planning_markers ?? []).map((marker) => [marker.id, marker]));

  function submitCapture() {
    if (!props.selectedCampaignId || !props.selectedSessionId || !captureBody.trim()) return;
    capture.mutate();
  }

  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to use Scribe." />;
  if (!props.selectedSessionId) return <EmptyText text="Select or create a session before capturing notes." />;

  const activeError =
    transcriptQuery.error ??
    providersQuery.error ??
    candidatesQuery.error ??
    aliasesQuery.error ??
    proposalSetsQuery.error ??
    proposalDetailQuery.error ??
    planningMarkersQuery.error ??
    publicSnippetsQuery.error ??
    sessionRecapsQuery.error ??
    memoryEntriesQuery.error ??
    capture.error ??
    correct.error ??
    saveProvider.error ??
    testProvider.error ??
    previewContext.error ??
    previewBranchContext.error ??
    previewPlayerSafeContext.error ??
    reviewContext.error ??
    reviewBranchContext.error ??
    reviewPlayerSafeContext.error ??
    buildRecap.error ??
    buildBranch.error ??
    buildPlayerSafe.error ??
    scanPlayerSafeDraft.error ??
    createPlayerSafeSnippet.error ??
    patchRecapSafety.error ??
    patchMemorySafety.error ??
    saveRecap.error ??
    acceptCandidate.error ??
    rejectCandidate.error ??
    createAlias.error ??
    rejectOption.error ??
    saveOptionForLater.error ??
    createPlanningMarker.error ??
    expireMarker.error ??
    discardMarker.error ??
    recallResult.error;

  const projection = transcriptQuery.data?.projection ?? [];
  const pendingCandidates = (candidatesQuery.data?.candidates ?? []).filter((candidate) => candidate.status !== "accepted" && candidate.status !== "rejected");
  const proposalSets = proposalSetsQuery.data?.proposal_sets ?? [];
  const currentProposalDetail = branchDraft?.proposal_set ?? proposalDetailQuery.data ?? null;
  const activeMarkers = (planningMarkersQuery.data?.planning_markers ?? []).filter((marker) => marker.status === "active");
  const canonizedMarkers = (planningMarkersQuery.data?.planning_markers ?? []).filter((marker) => marker.status === "canonized");
  const publicSafeRecaps = sessionRecapsQuery.data?.recaps ?? [];
  const publicSafeMemoryEntries = memoryEntriesQuery.data?.entries ?? [];
  const publicSnippetArtifacts = publicSnippetsQuery.data?.snippets ?? [];
  const playerSafeAckRequired = publicSafetyScan?.ack_required ?? false;
  const playerSafeScanCurrent = Boolean(publicSafetyScan && publicSafetyScan.content_hash === publicSafetyAckHash);
  const branchScopeAvailable =
    branchScope === "campaign" ||
    (branchScope === "session" && Boolean(props.selectedSessionId)) ||
    (branchScope === "scene" && Boolean(props.selectedSceneId));

  return (
    <div className="scribe-widget">
      <div className="scribe-capture">
        <textarea
          value={captureBody}
          onChange={(event) => setCaptureBody(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              submitCapture();
            }
          }}
          placeholder="Live DM note. Enter for newline, Cmd/Ctrl+Enter to save."
          aria-label="Live DM note"
        />
        <div className="token-actions">
          <button onClick={submitCapture} disabled={!captureBody.trim() || capture.isPending}>
            <CheckCircle2 size={14} /> Save
          </button>
          <button onClick={() => setInspectionOpen((open) => !open)}>
            <Search size={14} /> Inspect
          </button>
        </div>
        <span className="muted">⌘↵ to save · Enter keeps dictation/newlines safe</span>
      </div>

      <div className="scribe-feed" aria-label="Live capture feed">
        {projection.slice(-4).map((event) => (
          <div key={event.id} className="scribe-feed-row">
            <span>#{event.order_index + 1}</span>
            <p>{event.body}</p>
            <button
              onClick={() => {
                setCorrectionTarget(event);
                setCorrectionBody(event.body);
              }}
            >
              Correct
            </button>
          </div>
        ))}
        {!projection.length ? <span className="muted">No live captures yet.</span> : null}
      </div>

      {correctionTarget ? (
        <div className="scribe-review-block">
          <strong>Correction for #{correctionTarget.order_index + 1}</strong>
          <textarea value={correctionBody} onChange={(event) => setCorrectionBody(event.target.value)} aria-label="Correction body" />
          <div className="token-actions">
            <button onClick={() => correct.mutate()} disabled={!correctionBody.trim() || correct.isPending}>
              Save correction
            </button>
            <button onClick={() => setCorrectionTarget(null)}>Cancel</button>
          </div>
        </div>
      ) : null}

      <div className="scribe-actions-row">
        <button onClick={() => previewContext.mutate()} disabled={previewContext.isPending}>
          Build Context Preview
        </button>
        <button onClick={() => reviewContext.mutate()} disabled={!contextPackage || contextPackage.review_status === "reviewed" || reviewContext.isPending}>
          Review Context
        </button>
        <button
          onClick={() => buildRecap.mutate()}
          disabled={!selectedProvider || !contextPackage || contextPackage.review_status !== "reviewed" || buildRecap.isPending}
        >
          Build Recap
        </button>
      </div>

      <details className="scribe-details">
        <summary>Provider</summary>
        <div className="scribe-provider-grid">
          <label>
            <span>Profile</span>
            <select value={selectedProvider?.id ?? ""} onChange={(event) => setProviderId(event.target.value || null)} aria-label="LLM provider profile">
              <option value="">New provider</option>
              {providers.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.label} · {profile.conformance_level}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Label</span>
            <input value={providerLabel} onChange={(event) => setProviderLabel(event.target.value)} />
          </label>
          <label>
            <span>Vendor</span>
            <select value={providerVendor} onChange={(event) => setProviderVendor(event.target.value as typeof providerVendor)}>
              {["custom", "openai", "ollama", "lmstudio", "kobold", "openrouter"].map((vendor) => (
                <option key={vendor} value={vendor}>
                  {vendor}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Base URL</span>
            <input value={providerBaseUrl} onChange={(event) => setProviderBaseUrl(event.target.value)} />
          </label>
          <label>
            <span>Model</span>
            <input value={providerModelId} onChange={(event) => setProviderModelId(event.target.value)} />
          </label>
          <label>
            <span>Key source</span>
            <select value={providerKeySource} onChange={(event) => setProviderKeySource(event.target.value as "none" | "env")}>
              <option value="none">none</option>
              <option value="env">env</option>
            </select>
          </label>
          {providerKeySource === "env" ? (
            <label>
              <span>Env var</span>
              <input value={providerKeyRef} onChange={(event) => setProviderKeyRef(event.target.value)} />
            </label>
          ) : null}
        </div>
        <div className="token-actions">
          <button onClick={() => saveProvider.mutate()} disabled={!providerLabel.trim() || !providerBaseUrl.trim() || !providerModelId.trim() || saveProvider.isPending}>
            Save provider
          </button>
          <button onClick={() => selectedProvider && testProvider.mutate()} disabled={!selectedProvider || testProvider.isPending}>
            Test provider
          </button>
        </div>
        <p className="muted">
          Provider test sends a real request. API keys stay in the backend and are never returned to the browser.
        </p>
      </details>

      <label className="scribe-instruction">
        <span>GM instruction for recap</span>
        <textarea value={gmInstruction} onChange={(event) => setGmInstruction(event.target.value)} placeholder="Optional focus for the recap." />
      </label>

      {recapDraft ? (
        <div className="scribe-review-block">
          <strong>Reviewed Recap Draft</strong>
          <input value={recapTitle} onChange={(event) => setRecapTitle(event.target.value)} aria-label="Recap title" />
          <textarea value={recapBody} onChange={(event) => setRecapBody(event.target.value)} aria-label="Recap body" />
          <div className="token-actions">
            <button onClick={() => saveRecap.mutate()} disabled={!recapTitle.trim() || !recapBody.trim() || saveRecap.isPending}>
              Save Recap
            </button>
            <span className="muted">{recapDraft.candidates.length} memory drafts · {recapDraft.rejected_drafts.length} validation rejects</span>
          </div>
        </div>
      ) : null}

      <div className="scribe-memory">
        <div className="section-heading">
          <strong>Memory Inbox</strong>
          <span className="muted">{pendingCandidates.length} pending</span>
        </div>
        {pendingCandidates.slice(0, 3).map((candidate: MemoryCandidate) => {
          const linkedMarker = candidate.source_planning_marker_id ? markersById.get(candidate.source_planning_marker_id) ?? null : null;
          const droppedLink = candidate.normalization_warnings.includes("planning_marker_link_ignored");
          const markerInactive = Boolean(candidate.source_planning_marker_id && (!linkedMarker || linkedMarker.status !== "active"));
          const editedLinkedCandidate = Boolean(candidate.source_planning_marker_id && candidate.status === "edited");
          return (
            <div key={candidate.id} className="scribe-candidate">
              <strong>{candidate.title}</strong>
              <p>{candidate.body}</p>
              <div className="scribe-source-list">
                <span className={candidate.claim_strength === "strong_inference" ? "status-pill warning" : "status-pill"}>
                  {candidate.claim_strength}
                </span>
                {linkedMarker ? <span className="status-pill warning">Proposed confirmation of planning direction</span> : null}
                {droppedLink ? <span className="status-pill warning">Planning marker link ignored</span> : null}
                {candidate.normalization_warnings
                  .filter((warning) => warning !== "planning_marker_link_ignored")
                  .map((warning) => (
                    <span key={warning} className="status-pill warning">
                      {warning === "candidate_body_resembles_planning_marker" ? "Candidate wording resembles planning marker" : warning}
                    </span>
                  ))}
              </div>
              {linkedMarker ? (
                <div className="muted-block">
                  <strong>{linkedMarker.status === "canonized" ? "Canonized via memory" : "Planning marker"}</strong>
                  <p>{linkedMarker.title}: {linkedMarker.marker_text}</p>
                  <span className="muted">Marker status: {linkedMarker.status}{linkedMarker.source_proposal_option_id ? ` · Option ${linkedMarker.source_proposal_option_id.slice(0, 8)}` : " · No source option"}</span>
                </div>
              ) : candidate.source_planning_marker_id ? (
                <p className="muted-block">Source planning marker no longer available. Memory entry can only be accepted if the backend still considers the link valid.</p>
              ) : null}
              {candidate.evidence_refs.length ? (
                <details>
                  <summary>Played evidence refs</summary>
                  <div className="scribe-source-list">
                    {candidate.evidence_refs.map((ref, index) => (
                      <span key={index}>
                        {String(ref.kind ?? "source")}:{String(ref.id ?? "").slice(0, 8)}
                        {ref.quote ? ` · ${String(ref.quote).slice(0, 120)}` : ""}
                      </span>
                    ))}
                  </div>
                </details>
              ) : null}
              {editedLinkedCandidate ? (
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={linkedCandidateConfirmId === candidate.id}
                    onChange={(event) => setLinkedCandidateConfirmId(event.target.checked ? candidate.id : null)}
                  />
                  I understand this will canonize the linked planning marker.
                </label>
              ) : null}
              {markerInactive ? <p className="muted-block">Linked marker is no longer active; accept is disabled for this linked candidate.</p> : null}
              <div className="token-actions">
                <button onClick={() => acceptCandidate.mutate(candidate)} disabled={acceptCandidate.isPending || markerInactive || (editedLinkedCandidate && linkedCandidateConfirmId !== candidate.id)}>
                  Accept into Memory
                </button>
                <button onClick={() => rejectCandidate.mutate(candidate.id)} disabled={rejectCandidate.isPending}>
                  Reject
                </button>
                {linkedMarker && linkedMarker.status === "active" ? (
                  <button onClick={() => expireMarker.mutate(linkedMarker.id)} disabled={expireMarker.isPending}>
                    Expire linked planning marker
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <div className="scribe-recall">
        <div className="inline-form">
          <input value={recallQuery} onChange={(event) => setRecallQuery(event.target.value)} placeholder="Recall accepted memory" aria-label="Scribe recall query" />
          <button onClick={() => recallResult.mutate()} disabled={!recallQuery.trim() || recallResult.isPending}>
            Recall
          </button>
        </div>
        {recallResult.data?.hits.map((hit) => (
          <div key={`${hit.source_kind}-${hit.source_id}`} className="scribe-hit">
            <strong>{hit.title}</strong>
            <p>{hit.excerpt}</p>
            <span className="muted">{hit.source_kind} · {hit.lane} · score {hit.score}</span>
          </div>
        ))}
        <div className="inline-form">
          <input value={aliasText} onChange={(event) => setAliasText(event.target.value)} placeholder="Add recall alias" aria-label="Recall alias" />
          <button onClick={() => createAlias.mutate()} disabled={!aliasText.trim() || createAlias.isPending}>
            Add alias
          </button>
        </div>
        {aliasesQuery.data?.length ? <span className="muted">{aliasesQuery.data.length} campaign aliases</span> : null}
      </div>

      <div className="scribe-player-safe" aria-label="Player-safe recap">
        <div className="section-heading">
          <strong>Player-Safe Recap</strong>
          <span className="muted">Eligible context is not guaranteed safe to publish</span>
        </div>
        <p className="muted-block">
          public_safe means eligible for public-safe context, not publish-safe. Shown on player display does not prove players know it.
        </p>

        <details className="scribe-details" open>
          <summary>Curate public-safe sources</summary>
          <div className="scribe-proposal-grid">
            <div className="scribe-candidate">
              <strong>Reviewed Recaps</strong>
              <span className="muted">Review full recap text before enabling; it may summarize private memory.</span>
              {publicSafeRecaps.slice(0, 5).map((recap) => (
                <div key={recap.id} className="party-field-row">
                  <span>
                    <strong>{recap.title}</strong>
                    <small className="muted">{recap.public_safe ? "Eligible for public-safe context" : "Private by default"}</small>
                  </span>
                  <button onClick={() => patchRecapSafety.mutate({ recapId: recap.id, publicSafe: !recap.public_safe })} disabled={patchRecapSafety.isPending}>
                    {recap.public_safe ? "Mark private" : "Mark eligible"}
                  </button>
                </div>
              ))}
              {!publicSafeRecaps.length ? <span className="muted">No saved recaps for this session yet.</span> : null}
            </div>
            <div className="scribe-candidate">
              <strong>Accepted Memory</strong>
              <span className="muted">No bulk enable in v1; review each memory entry.</span>
              {publicSafeMemoryEntries.slice(0, 5).map((entry) => (
                <div key={entry.id} className="party-field-row">
                  <span>
                    <strong>{entry.title}</strong>
                    <small className="muted">{entry.public_safe ? "Eligible for public-safe context" : "Private by default"}</small>
                  </span>
                  <button onClick={() => patchMemorySafety.mutate({ entryId: entry.id, publicSafe: !entry.public_safe })} disabled={patchMemorySafety.isPending}>
                    {entry.public_safe ? "Mark private" : "Mark eligible"}
                  </button>
                </div>
              ))}
              {!publicSafeMemoryEntries.length ? <span className="muted">No accepted memory entries yet.</span> : null}
            </div>
          </div>
          {publicSafetyCurationAck ? (
            <div className="muted-block">
              <strong>Public-safety warnings require explicit acknowledgment.</strong>
              <div className="scribe-source-list">
                {publicSafetyCurationAck.warnings.map((warning, index) => (
                  <span key={index} className={warning.severity === "high" || warning.severity === "medium" ? "status-pill warning" : "status-pill"}>
                    {warning.severity}: {warning.code}
                  </span>
                ))}
              </div>
              <button
                onClick={() => {
                  if (publicSafetyCurationAck.kind === "recap") {
                    patchRecapSafety.mutate({ recapId: publicSafetyCurationAck.id, publicSafe: true, warningHash: publicSafetyCurationAck.contentHash });
                  } else {
                    patchMemorySafety.mutate({ entryId: publicSafetyCurationAck.id, publicSafe: true, warningHash: publicSafetyCurationAck.contentHash });
                  }
                }}
                disabled={patchRecapSafety.isPending || patchMemorySafety.isPending}
              >
                Acknowledge and mark eligible
              </button>
            </div>
          ) : null}
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={includeUnshownPublicSnippets}
              onChange={(event) => {
                setIncludeUnshownPublicSnippets(event.target.checked);
                setPlayerSafeContextPackage(null);
                setPlayerSafeDraft(null);
              }}
            />
            Include unshown/manual public snippets
          </label>
          <div className="scribe-source-list">
            {publicSnippetArtifacts.slice(0, 6).map((snippet) => (
              <span key={snippet.id}>
                {snippet.title || "Untitled snippet"} · {snippet.creation_source === "manual" ? "manual artifact" : "Scribe-created"} ·{" "}
                {snippet.last_published_at ? "shown on display" : "not shown"}
              </span>
            ))}
          </div>
        </details>

        <label className="scribe-instruction">
          <span>GM instruction for player-safe draft</span>
          <textarea
            value={playerSafeInstruction}
            onChange={(event) => {
              setPlayerSafeInstruction(event.target.value);
              setPlayerSafeContextPackage(null);
              setPlayerSafeDraft(null);
            }}
            placeholder="Public-facing focus. With no curated sources, provide at least 40 characters."
          />
        </label>
        <div className="token-actions">
          <button onClick={() => previewPlayerSafeContext.mutate()} disabled={previewPlayerSafeContext.isPending}>
            Preview Public-Safe Context
          </button>
          <button
            onClick={() => reviewPlayerSafeContext.mutate()}
            disabled={!playerSafeContextPackage || playerSafeContextPackage.review_status === "reviewed" || reviewPlayerSafeContext.isPending}
          >
            Review Public-Safe Context
          </button>
          <button
            onClick={() => buildPlayerSafe.mutate()}
            disabled={!selectedProvider || !playerSafeContextPackage || playerSafeContextPackage.review_status !== "reviewed" || buildPlayerSafe.isPending}
          >
            Run Player-Safe Recap
          </button>
        </div>
        {playerSafeContextPackage ? (
          <div className="muted-block">
            <InfoRow
              label="Public-safe context"
              value={`${playerSafeContextPackage.review_status} · ${playerSafeContextPackage.source_refs.length} included · ${playerSafeContextPackage.token_estimate} est. tokens`}
            />
            {playerSafeContextPackage.warnings.map((warning, index) => (
              <span key={index} className="status-pill warning">
                {String(warning.code ?? "warning")}
                {warning.message ? `: ${String(warning.message)}` : ""}
              </span>
            ))}
            <div className="scribe-source-list">
              {playerSafeContextPackage.source_refs.map((ref, index) => {
                const key = sourceRefKey(ref);
                return (
                  <button
                    key={`${key}-${index}`}
                    className="link-button"
                    onClick={() => {
                      setExcludedPublicSafeRefs((refs) => Array.from(new Set([...refs, key])));
                      setPlayerSafeContextPackage(null);
                    }}
                  >
                    Exclude {sourceRefLabel(ref)}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {playerSafeDraft ? (
          <div className="scribe-review-block">
            <div className="section-heading">
              <strong>Draft Public Snippet</strong>
              {playerSafeDraft.warnings.some((warning) => warning.code === "instruction_only_public_safe_draft") ? (
                <span className="status-pill warning">instruction_only_public_safe_draft</span>
              ) : (
                <span className="status-pill">GM review required</span>
              )}
            </div>
            <input
              value={playerSafeTitle}
              onChange={(event) => {
                setPlayerSafeTitle(event.target.value);
                setPublicSafetyScan(null);
                setPublicSafetyAckHash(null);
              }}
              aria-label="Player-safe snippet title"
            />
            <textarea
              value={playerSafeBody}
              onChange={(event) => {
                setPlayerSafeBody(event.target.value);
                setPublicSafetyScan(null);
                setPublicSafetyAckHash(null);
              }}
              aria-label="Player-safe snippet body"
            />
            <div className="snippet-preview" aria-label="Player-safe snippet preview">
              <span className="muted">Player display preview uses the same safe Markdown renderer.</span>
              <SafeMarkdownRenderer body={playerSafeBody} />
            </div>
            <div className="token-actions">
              <button onClick={() => scanPlayerSafeDraft.mutate()} disabled={!playerSafeBody.trim() || scanPlayerSafeDraft.isPending}>
                Scan Warnings
              </button>
              {playerSafeAckRequired ? (
                <button onClick={() => setPublicSafetyAckHash(publicSafetyScan!.content_hash)} disabled={!publicSafetyScan || publicSafetyAckHash === publicSafetyScan.content_hash}>
                  Acknowledge Warnings
                </button>
              ) : null}
              <button
                onClick={() => createPlayerSafeSnippet.mutate()}
                disabled={!playerSafeTitle.trim() || !playerSafeBody.trim() || !playerSafeScanCurrent || createPlayerSafeSnippet.isPending}
              >
                Create PublicSnippet
              </button>
            </div>
            {publicSafetyScan ? (
              <div className="scribe-source-list">
                {publicSafetyScan.warnings.length ? (
                  publicSafetyScan.warnings.map((warning, index) => (
                    <span key={index} className={warning.severity === "high" || warning.severity === "medium" ? "status-pill warning" : "status-pill"}>
                      {warning.severity}: {warning.code}
                    </span>
                  ))
                ) : (
                  <span className="status-pill success">No deterministic warnings. This is not proof of safety.</span>
                )}
              </div>
            ) : (
              <p className="muted">Warning scan is required after every title/body edit.</p>
            )}
            {createPlayerSafeSnippet.data ? <p className="muted-block">Created snippet. It is not published until you use the existing display action.</p> : null}
          </div>
        ) : null}

        <details className="scribe-details">
          <summary>Player-Safe Diagnostics</summary>
          {playerSafeContextPackage ? (
            <>
              <InfoRow label="Hash" value={playerSafeContextPackage.source_ref_hash.slice(0, 16)} />
              <InfoRow label="Source classes" value={playerSafeContextPackage.source_classes.join(", ") || "none"} />
              <textarea readOnly value={playerSafeContextPackage.rendered_prompt || "Rendered prompt unavailable."} aria-label="Player-safe rendered prompt preview" />
            </>
          ) : (
            <span className="muted">Preview public-safe context to inspect sources and prompt.</span>
          )}
          {playerSafeDraft ? (
            <textarea readOnly value={JSON.stringify(playerSafeDraft, null, 2)} aria-label="Player-safe normalized output JSON" />
          ) : null}
        </details>
      </div>

      <div className="scribe-proposals" aria-label="Proposal cockpit">
        <div className="section-heading">
          <strong>Proposal Cockpit</strong>
          <span className="muted">Planning, not canon</span>
        </div>
        <div className="scribe-provider-grid">
          <label>
            <span>Scope</span>
            <select
              value={branchScope}
              onChange={(event) => {
                setBranchScope(event.target.value as typeof branchScope);
                setBranchContextPackage(null);
                setBranchDraft(null);
              }}
              aria-label="Branch proposal scope"
            >
              <option value="campaign">Campaign-wide</option>
              <option value="session" disabled={!props.selectedSessionId}>
                Current session
              </option>
              <option value="scene" disabled={!props.selectedSceneId}>
                Current scene
              </option>
            </select>
          </label>
          <label>
            <span>Branch focus</span>
            <textarea
              value={branchInstruction}
              onChange={(event) => {
                setBranchInstruction(event.target.value);
                setBranchContextPackage(null);
                setBranchDraft(null);
              }}
              placeholder="What kind of directions should Scribe explore?"
            />
          </label>
        </div>
        <div className="token-actions">
          <button onClick={() => previewBranchContext.mutate()} disabled={!branchScopeAvailable || previewBranchContext.isPending}>
            Preview Branch Context
          </button>
          <button
            onClick={() => reviewBranchContext.mutate()}
            disabled={!branchContextPackage || branchContextPackage.review_status === "reviewed" || reviewBranchContext.isPending}
          >
            Review Branch Context
          </button>
          <button
            onClick={() => buildBranch.mutate()}
            disabled={!selectedProvider || !branchContextPackage || branchContextPackage.review_status !== "reviewed" || buildBranch.isPending}
          >
            Run Branch Directions
          </button>
        </div>
        {!selectedProvider ? <p className="muted-block">Configure a provider before running branch directions.</p> : null}
        {selectedProvider && !["level_1_json_best_effort", "level_2_json_validated", "level_3_tool_capable"].includes(selectedProvider.conformance_level) ? (
          <p className="muted-block">Provider must pass structured JSON testing before branch directions.</p>
        ) : null}
        {branchContextPackage?.warnings?.length ? (
          <p className="muted-block">{String(branchContextPackage.warnings[0]?.message ?? "Campaign-wide branch directions work best with a specific focus.")}</p>
        ) : null}

        {currentProposalDetail ? (
          <div className="scribe-proposal-set">
            <div className="section-heading">
              <strong>{currentProposalDetail.proposal_set.title}</strong>
              <span className={currentProposalDetail.proposal_set.degraded ? "status-pill warning" : "status-pill"}>
                {currentProposalDetail.proposal_set.degraded ? `Degraded output: ${currentProposalDetail.proposal_set.option_count} options` : currentProposalDetail.proposal_set.status}
              </span>
            </div>
            {currentProposalDetail.normalization_warnings.length ? (
              <p className="muted-block">{currentProposalDetail.normalization_warnings.length} normalization warning(s). See Diagnostics.</p>
            ) : null}
            <div className="scribe-proposal-grid">
              {currentProposalDetail.options.map((option: ProposalOption) => (
                <div key={option.id} className="scribe-proposal-card">
                  <div className="section-heading">
                    <strong>{option.title}</strong>
                    <span className={option.active_planning_marker_id ? "status-pill success" : option.status === "rejected" ? "status-pill danger" : "status-pill"}>
                      {option.active_planning_marker_id ? "Active planning" : proposalOptionLabel(option.status)}
                    </span>
                  </div>
                  <p>{option.summary}</p>
                  <InfoRow label="Possible consequences if played" value={option.consequences || "Not specified"} />
                  <InfoRow label="May reveal" value={option.reveals || "Not specified"} />
                  <InfoRow label="Stays hidden" value={option.stays_hidden || "Not specified"} />
                  <details>
                    <summary>Draft body</summary>
                    <p>{option.body}</p>
                  </details>
                  <div className="muted-block">
                    <strong>Marker preview</strong>
                    <p>{option.planning_marker_text}</p>
                  </div>
                  <div className="token-actions">
                    <button
                      disabled={option.status === "canonized"}
                      onClick={() => {
                        setAdoptOption(option);
                        setMarkerTitle(option.title);
                        setMarkerText(option.planning_marker_text);
                        setMarkerConfirmWarnings(false);
                      }}
                    >
                      Adopt as Planning Direction
                    </button>
                    <button onClick={() => saveOptionForLater.mutate(option.id)} disabled={saveOptionForLater.isPending || Boolean(option.active_planning_marker_id) || option.status === "canonized"}>
                      Save for later
                    </button>
                    <button onClick={() => rejectOption.mutate(option.id)} disabled={rejectOption.isPending || Boolean(option.active_planning_marker_id) || option.status === "canonized"}>
                      Reject
                    </button>
                  </div>
                  {option.status === "canonized" ? <span className="muted">Canonized via memory; proposal actions are closed.</span> : null}
                  {option.active_planning_marker_id ? <span className="muted">Expire or discard the active marker before rejecting or saving this option.</span> : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {adoptOption ? (
          <div className="scribe-review-block">
            <strong>Adopt planning marker</strong>
            <span className="status-pill warning">Planning, not canon</span>
            <input value={markerTitle} onChange={(event) => setMarkerTitle(event.target.value)} aria-label="Planning marker title" />
            <textarea value={markerText} onChange={(event) => setMarkerText(event.target.value)} aria-label="Planning marker text" />
            {markerText !== adoptOption.planning_marker_text ? (
              <details open>
                <summary>Edited from proposal</summary>
                <p>{adoptOption.planning_marker_text}</p>
              </details>
            ) : null}
            {markerText.length > 500 ? <p className="muted-block">Marker is over 500 characters. Keep planning context concise.</p> : null}
            {markerConfirmWarnings ? <p className="muted-block">Marker wording has planning/canon warnings. Confirm again to adopt anyway.</p> : null}
            <div className="token-actions">
              <button onClick={() => createPlanningMarker.mutate()} disabled={!markerTitle.trim() || !markerText.trim() || createPlanningMarker.isPending}>
                {markerConfirmWarnings ? "Confirm and Adopt" : "Create Planning Marker"}
              </button>
              <button onClick={() => setAdoptOption(null)}>Cancel</button>
            </div>
          </div>
        ) : null}

        <div className="scribe-memory">
          <div className="section-heading">
            <strong>Active Planning Markers</strong>
            <span className="muted">{activeMarkers.length} active</span>
          </div>
          {activeMarkers.map((marker: PlanningMarker) => (
            <div key={marker.id} className="scribe-candidate">
              <div className="section-heading">
                <strong>{marker.title}</strong>
                <span className="status-pill success">Active planning</span>
              </div>
              <p>{marker.marker_text}</p>
              {marker.edited_from_source ? <span className="muted">Edited from proposal</span> : null}
              {marker.lint_warnings.length ? <span className="status-pill warning">{marker.lint_warnings.length} warning(s)</span> : null}
              <div className="token-actions">
                <button onClick={() => expireMarker.mutate(marker.id)} disabled={expireMarker.isPending}>
                  Expire Marker
                </button>
                <button onClick={() => discardMarker.mutate(marker.id)} disabled={discardMarker.isPending}>
                  Discard Marker
                </button>
              </div>
            </div>
          ))}
          {canonizedMarkers.slice(0, 3).map((marker: PlanningMarker) => (
            <div key={marker.id} className="scribe-candidate">
              <div className="section-heading">
                <strong>{marker.title}</strong>
                <span className="status-pill">Canonized via memory</span>
              </div>
              <p>{marker.marker_text}</p>
              <span className="muted">
                {marker.canon_memory_entry_id ? `Memory ${marker.canon_memory_entry_id.slice(0, 8)}` : "Source planning marker no longer available"}
              </span>
            </div>
          ))}
        </div>

        <details className="scribe-details">
          <summary>Proposal History</summary>
          {proposalSets.map((proposalSet: ProposalSetSummary) => (
            <button key={proposalSet.id} className="link-button" onClick={() => setSelectedProposalSetId(proposalSet.id)}>
              {proposalSet.title} · {proposalSet.scope_kind} · {proposalSet.option_count} options
              {proposalSet.has_warnings ? ` · ${proposalSet.warning_count} warning(s)` : ""}
            </button>
          ))}
          {!proposalSets.length ? <span className="muted">No proposal sets yet.</span> : null}
        </details>

        <details className="scribe-details">
          <summary>Branch Diagnostics</summary>
          {branchContextPackage ? (
            <>
              <InfoRow label="Context" value={`${branchContextPackage.scope_kind} · ${branchContextPackage.review_status} · ${branchContextPackage.token_estimate} est. tokens`} />
              <InfoRow label="Source classes" value={branchContextPackage.source_classes.join(", ") || "none"} />
              <div className="scribe-source-list">
                {branchContextPackage.source_refs.map((ref, index) => (
                  <span key={`${String(ref.id)}-${index}`}>{sourceRefLabel(ref)}</span>
                ))}
              </div>
              <textarea readOnly value={branchContextPackage.rendered_prompt || "Rendered prompt unavailable."} aria-label="Branch rendered prompt preview" />
            </>
          ) : (
            <span className="muted">Preview branch context to inspect sources and prompt.</span>
          )}
          {branchDraft ? (
            <>
              <InfoRow label="Run" value={`${branchDraft.run.status} · ${branchDraft.run.duration_ms ?? "-"}ms`} />
              {branchDraft.run.parse_failure_reason ? <InfoRow label="Parse failure" value={branchDraft.run.parse_failure_reason} /> : null}
              <textarea readOnly value={JSON.stringify(branchDraft.proposal_set ?? branchDraft.warnings, null, 2)} aria-label="Branch normalized output JSON" />
            </>
          ) : null}
        </details>
      </div>

      {inspectionOpen ? (
        <div className="scribe-inspection" aria-label="Scribe inspection mode">
          <div className="section-heading">
            <strong>Inspection Mode</strong>
            <span className="muted">GM-private</span>
          </div>
          {contextPackage ? (
            <>
              <InfoRow label="Context" value={`${contextPackage.review_status} · ${contextPackage.token_estimate} est. tokens`} />
              <InfoRow label="Hash" value={contextPackage.source_ref_hash.slice(0, 16)} />
              <div className="scribe-source-list">
                {contextPackage.source_refs.map((ref, index) => (
                  <span key={`${String(ref.id)}-${index}`}>{sourceRefLabel(ref)}</span>
                ))}
              </div>
              <textarea readOnly value={contextPackage.rendered_prompt} aria-label="Rendered prompt preview" />
            </>
          ) : (
            <span className="muted">Build a context preview to inspect sources and rendered prompt.</span>
          )}
          {recapDraft?.run ? (
            <>
              <InfoRow label="Run" value={`${recapDraft.run.status} · ${recapDraft.run.duration_ms ?? "-"}ms`} />
              {recapDraft.run.parse_failure_reason ? <InfoRow label="Parse failure" value={recapDraft.run.parse_failure_reason} /> : null}
              <textarea readOnly value={JSON.stringify(recapDraft.bundle, null, 2)} aria-label="Normalized output JSON" />
            </>
          ) : null}
        </div>
      ) : null}

      {testProvider.data ? <p className="muted-block">{testProvider.data.message}</p> : null}
      {saveRecap.data ? <p className="muted-block">Saved recap: {saveRecap.data.title}</p> : null}
      {activeError ? <ErrorLine error={activeError} /> : null}
    </div>
  );
}

export function SceneContextWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [entityId, setEntityId] = useState<string | null>(null);
  const [entityRole, setEntityRole] = useState<SceneEntityRole>("supporting");
  const [entityLinkNotes, setEntityLinkNotes] = useState("");
  const [snippetId, setSnippetId] = useState<string | null>(null);
  const [activeEncounterId, setActiveEncounterId] = useState<string | null>(null);
  const [stagedMode, setStagedMode] = useState<SceneStagedDisplayMode>("none");
  const [stagedSnippetId, setStagedSnippetId] = useState<string | null>(null);

  const contextQuery = useQuery({
    queryKey: ["scene-context", props.selectedSceneId],
    queryFn: () => api.sceneContext(props.selectedSceneId!),
    enabled: Boolean(props.selectedSceneId)
  });
  const entitiesQuery = useQuery({
    queryKey: ["entities", props.selectedCampaignId],
    queryFn: () => api.entities(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const snippetsQuery = useQuery({
    queryKey: ["public-snippets", props.selectedCampaignId],
    queryFn: () => api.publicSnippets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const encountersQuery = useQuery({
    queryKey: ["combat-encounters", props.selectedCampaignId],
    queryFn: () => api.combatEncounters(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });

  const context = contextQuery.data;
  const sceneEncounters = useMemo(
    () => (encountersQuery.data?.encounters ?? []).filter((encounter) => encounter.scene_id === props.selectedSceneId),
    [encountersQuery.data, props.selectedSceneId]
  );
  const linkedEntityIds = useMemo(() => new Set((context?.entities ?? []).map((link) => link.entity_id)), [context?.entities]);
  const linkedSnippetIds = useMemo(
    () => new Set((context?.public_snippets ?? []).map((link) => link.public_snippet_id)),
    [context?.public_snippets]
  );
  const availableEntities = (entitiesQuery.data?.entities ?? []).filter((entity) => !linkedEntityIds.has(entity.id));
  const availableSnippets = (snippetsQuery.data?.snippets ?? []).filter((snippet) => !linkedSnippetIds.has(snippet.id));

  useEffect(() => {
    if (!context) return;
    setActiveEncounterId(context.context.active_encounter_id);
    setStagedMode(context.context.staged_display_mode);
    setStagedSnippetId(context.context.staged_public_snippet_id);
  }, [context]);

  useEffect(() => {
    if (entityId && availableEntities.some((entity) => entity.id === entityId)) return;
    setEntityId(availableEntities[0]?.id ?? null);
  }, [availableEntities, entityId]);

  useEffect(() => {
    if (snippetId && availableSnippets.some((snippet) => snippet.id === snippetId)) return;
    setSnippetId(availableSnippets[0]?.id ?? null);
  }, [availableSnippets, snippetId]);

  function refreshContext(data?: unknown) {
    if (data) queryClient.setQueryData(["scene-context", props.selectedSceneId], data);
    void queryClient.invalidateQueries({ queryKey: ["scene-context", props.selectedSceneId] });
  }

  const activateScene = useMutation({
    mutationFn: () => api.activateScene(props.selectedSceneId!),
    onSuccess: (runtime) => {
      queryClient.setQueryData(["runtime"], runtime);
      void queryClient.invalidateQueries({ queryKey: ["runtime"] });
    }
  });
  const saveContext = useMutation({
    mutationFn: () =>
      api.patchSceneContext(props.selectedSceneId!, {
        active_encounter_id: activeEncounterId,
        staged_display_mode: stagedMode,
        staged_public_snippet_id: stagedMode === "public_snippet" ? stagedSnippetId : null
      }),
    onSuccess: refreshContext
  });
  const linkEntity = useMutation({
    mutationFn: () =>
      api.linkSceneEntity(props.selectedSceneId!, {
        entity_id: entityId!,
        role: entityRole,
        notes: entityLinkNotes
      }),
    onSuccess: (data) => {
      setEntityLinkNotes("");
      refreshContext(data);
    }
  });
  const unlinkEntity = useMutation({
    mutationFn: (linkId: string) => api.unlinkSceneEntity(linkId),
    onSuccess: refreshContext
  });
  const linkSnippet = useMutation({
    mutationFn: () => api.linkScenePublicSnippet(props.selectedSceneId!, { public_snippet_id: snippetId! }),
    onSuccess: refreshContext
  });
  const unlinkSnippet = useMutation({
    mutationFn: (linkId: string) => api.unlinkScenePublicSnippet(linkId),
    onSuccess: refreshContext
  });
  const publishStagedDisplay = useMutation({
    mutationFn: () => api.publishSceneStagedDisplay(props.selectedSceneId!),
    onSuccess: (state) => {
      queryClient.setQueryData(["player-display"], state);
      broadcastDisplayChange(state);
      void queryClient.invalidateQueries({ queryKey: ["player-display"] });
    }
  });

  if (!props.selectedCampaignId || !props.selectedSceneId) return <EmptyText text="Select a campaign and scene to stage scene context." />;

  const error =
    contextQuery.error ??
    entitiesQuery.error ??
    snippetsQuery.error ??
    encountersQuery.error ??
    activateScene.error ??
    saveContext.error ??
    linkEntity.error ??
    unlinkEntity.error ??
    linkSnippet.error ??
    unlinkSnippet.error ??
    publishStagedDisplay.error;

  return (
    <div className="scene-context-widget">
      <div className="party-section">
        <strong>{context?.scene.title ?? props.scenes.find((scene) => scene.id === props.selectedSceneId)?.title ?? "Selected scene"}</strong>
        <div className="status-grid">
          <InfoRow label="Runtime scene" value={props.runtime?.active_scene_title ?? "None"} />
          <InfoRow label="Active map" value={context?.active_map?.map.name ?? "None"} />
          <InfoRow label="Linked notes" value={String(context?.notes.length ?? 0)} />
          <InfoRow label="Active encounter" value={context?.active_encounter?.title ?? "None"} />
        </div>
        <button onClick={() => activateScene.mutate()} disabled={activateScene.isPending}>
          <Eye size={14} /> Activate privately
        </button>
      </div>

      <div className="party-section">
        <strong>Linked notes</strong>
        {(context?.notes ?? []).length > 0 ? (
          <EntityList items={context?.notes ?? []} selectedId={null} label={(note) => note.title} onSelect={() => undefined} />
        ) : (
          <EmptyText text="No notes are linked through note.scene_id." />
        )}
      </div>

      <div className="party-section">
        <strong>Linked entities</strong>
        <div className="asset-list">
          {(context?.entities ?? []).map((link) => (
            <div key={link.id} className="party-field-row">
              <span>
                <strong>{link.entity.display_name || link.entity.name}</strong>
                <small className="muted">
                  {link.role} · {link.entity.kind}
                </small>
              </span>
              <button onClick={() => unlinkEntity.mutate(link.id)} disabled={unlinkEntity.isPending} title="Unlink entity">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <div className="inline-form">
          <select value={entityId ?? ""} onChange={(event) => setEntityId(event.target.value || null)} aria-label="Scene entity link">
            <option value="">No available entity</option>
            {availableEntities.map((entity) => (
              <option key={entity.id} value={entity.id}>
                {entity.display_name || entity.name}
              </option>
            ))}
          </select>
          <button onClick={() => linkEntity.mutate()} disabled={!entityId || linkEntity.isPending}>
            <Plus size={14} /> Link
          </button>
        </div>
        <div className="inline-form">
          <select value={entityRole} onChange={(event) => setEntityRole(event.target.value as SceneEntityRole)} aria-label="Scene entity role">
            {sceneEntityRoles.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          <input value={entityLinkNotes} onChange={(event) => setEntityLinkNotes(event.target.value)} placeholder="GM-only link note" />
        </div>
      </div>

      <div className="party-section">
        <strong>Linked public snippets</strong>
        <div className="asset-list">
          {(context?.public_snippets ?? []).map((link) => (
            <div key={link.id} className="party-field-row">
              <span>
                <strong>{link.snippet.title || "Untitled snippet"}</strong>
                <small className="muted">{link.snippet.body.slice(0, 60)}</small>
              </span>
              <button onClick={() => unlinkSnippet.mutate(link.id)} disabled={unlinkSnippet.isPending} title="Unlink snippet">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <div className="inline-form">
          <select value={snippetId ?? ""} onChange={(event) => setSnippetId(event.target.value || null)} aria-label="Scene public snippet link">
            <option value="">No available snippet</option>
            {availableSnippets.map((snippet) => (
              <option key={snippet.id} value={snippet.id}>
                {snippet.title || "Untitled snippet"}
              </option>
            ))}
          </select>
          <button onClick={() => linkSnippet.mutate()} disabled={!snippetId || linkSnippet.isPending}>
            <Plus size={14} /> Link
          </button>
        </div>
      </div>

      <div className="party-section">
        <strong>Staged public display</strong>
        <label className="check-row">
          Active encounter
          <select value={activeEncounterId ?? ""} onChange={(event) => setActiveEncounterId(event.target.value || null)}>
            <option value="">No active encounter</option>
            {sceneEncounters.map((encounter) => (
              <option key={encounter.id} value={encounter.id}>
                {encounter.title}
              </option>
            ))}
          </select>
        </label>
        <div className="inline-form">
          <select value={stagedMode} onChange={(event) => setStagedMode(event.target.value as SceneStagedDisplayMode)} aria-label="Staged display mode">
            {sceneDisplayModes.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
          <button onClick={() => saveContext.mutate()} disabled={saveContext.isPending}>
            Save staging
          </button>
        </div>
        {stagedMode === "public_snippet" ? (
          <select
            value={stagedSnippetId ?? ""}
            onChange={(event) => setStagedSnippetId(event.target.value || null)}
            aria-label="Staged public snippet"
          >
            <option value="">No staged snippet</option>
            {(context?.public_snippets ?? []).map((link) => (
              <option key={link.public_snippet_id} value={link.public_snippet_id}>
                {link.snippet.title || "Untitled snippet"}
              </option>
            ))}
          </select>
        ) : null}
        <button
          className="publish-staged-button"
          onClick={() => publishStagedDisplay.mutate()}
          disabled={stagedMode === "none" || publishStagedDisplay.isPending}
        >
          <Send size={14} /> Publish staged display
        </button>
      </div>
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

const assetKinds: AssetKind[] = ["handout_image", "map_image", "scene_image", "npc_portrait", "token_image", "item_image"];
const assetVisibilities: AssetVisibility[] = ["private", "public_displayable"];
const fitModes: DisplayFitMode[] = ["fit", "fill", "stretch", "actual_size"];
const entityKinds: EntityKind[] = ["pc", "npc", "creature", "location", "item", "handout", "faction", "vehicle", "generic"];
const customFieldTypes: CustomFieldType[] = ["short_text", "long_text", "number", "boolean", "select", "multi_select", "radio", "resource", "image"];
const partyLayouts: PartyLayout[] = ["compact", "standard", "wide"];
const combatStatuses: CombatEncounterStatus[] = ["active", "paused", "ended"];
const combatDispositions: CombatantDisposition[] = ["pc", "ally", "neutral", "enemy", "hazard", "other"];
const sceneDisplayModes: SceneStagedDisplayMode[] = [
  "none",
  "blackout",
  "intermission",
  "scene_title",
  "active_map",
  "initiative",
  "public_snippet"
];
const sceneEntityRoles: SceneEntityRole[] = ["featured", "supporting", "location", "clue", "threat", "other"];

function splitTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function broadcastDisplayChange(state: PlayerDisplayState, targetWindow?: Window | null) {
  broadcastTransportMessage(makeTransportMessage("display-state-changed", "gm-control", state), targetWindow);
}

export function AssetLibraryWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [kind, setKind] = useState<AssetKind>("handout_image");
  const [visibility, setVisibility] = useState<AssetVisibility>("private");
  const [tags, setTags] = useState("");
  const [autoCreateMaps, setAutoCreateMaps] = useState(false);
  const [batchResults, setBatchResults] = useState<AssetBatchUploadResult[]>([]);
  const [caption, setCaption] = useState("");
  const [fitMode, setFitMode] = useState<DisplayFitMode>("fit");
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  const assetsQuery = useQuery({
    queryKey: ["assets", props.selectedCampaignId],
    queryFn: () => api.assets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });

  const selectedAsset = useMemo(
    () => assetsQuery.data?.find((asset) => asset.id === selectedAssetId) ?? assetsQuery.data?.[0] ?? null,
    [assetsQuery.data, selectedAssetId]
  );

  useEffect(() => {
    if (!selectedAssetId && selectedAsset) setSelectedAssetId(selectedAsset.id);
  }, [selectedAsset, selectedAssetId]);

  const upload = useMutation({
    mutationFn: () =>
      api.uploadAssetsBatch(props.selectedCampaignId!, {
        files,
        kind,
        visibility,
        tags,
        auto_create_maps: kind === "map_image" && autoCreateMaps
      }),
    onSuccess: (response) => {
      setFiles([]);
      setTags("");
      setBatchResults(response.results);
      const firstAsset = response.results.find((result) => result.asset)?.asset ?? null;
      if (firstAsset) setSelectedAssetId(firstAsset.id);
      void queryClient.invalidateQueries({ queryKey: ["assets", props.selectedCampaignId] });
      if (response.results.some((result) => result.map)) {
        void queryClient.invalidateQueries({ queryKey: ["maps", props.selectedCampaignId] });
      }
    }
  });

  const sendImage = useMutation({
    mutationFn: () =>
      api.playerDisplayShowImage({
        asset_id: selectedAsset!.id,
        title: selectedAsset!.name,
        caption: caption || null,
        fit_mode: fitMode
      }),
    onSuccess: (state) => {
      queryClient.setQueryData(["player-display"], state);
      broadcastDisplayChange(state);
      void queryClient.invalidateQueries({ queryKey: ["player-display"] });
    }
  });

  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to manage assets." />;
  const error = upload.error ?? sendImage.error ?? assetsQuery.error;

  return (
    <div className="stack">
      <form
        className="asset-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (files.length > 0) upload.mutate();
        }}
      >
        <input aria-label="Asset tags" value={tags} onChange={(event) => setTags(event.target.value)} placeholder="tags, comma separated" />
        <div className="inline-form">
          <select
            value={kind}
            onChange={(event) => {
              const nextKind = event.target.value as AssetKind;
              setKind(nextKind);
              if (nextKind !== "map_image") setAutoCreateMaps(false);
            }}
            aria-label="Asset kind"
          >
            {assetKinds.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select value={visibility} onChange={(event) => setVisibility(event.target.value as AssetVisibility)} aria-label="Asset visibility">
            {assetVisibilities.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        {kind === "map_image" ? (
          <label className="checkbox-row">
            <input
              aria-label="Auto-create maps"
              type="checkbox"
              checked={autoCreateMaps}
              onChange={(event) => setAutoCreateMaps(event.target.checked)}
            />{" "}
            Auto-create maps
          </label>
        ) : null}
        <div className="inline-form">
          <input
            aria-label="Asset files"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
          <button type="submit" disabled={!files.length || upload.isPending}>
            <Upload size={14} /> Upload
          </button>
        </div>
      </form>
      {batchResults.length ? (
        <div className="upload-results" aria-label="Upload results">
          {batchResults.map((result) => (
            <div key={result.filename} className={result.error ? "upload-result error" : "upload-result"}>
              {result.error ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
              <span>
                <strong>{result.filename}</strong>
                <small>
                  {result.error
                    ? result.error.message
                    : result.map
                      ? `Uploaded · map created: ${result.map.name}`
                      : `Uploaded · ${result.asset?.name ?? "asset"}`}
                </small>
              </span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="asset-list">
        {(assetsQuery.data ?? []).map((asset) => (
          <button
            key={asset.id}
            className={asset.id === selectedAsset?.id ? "asset-row selected" : "asset-row"}
            onClick={() => setSelectedAssetId(asset.id)}
          >
            <ImageIcon size={16} />
            <span>
              <strong>{asset.name}</strong>
              <small>
                {asset.visibility} · {asset.width ?? "?"}x{asset.height ?? "?"} · {formatBytes(asset.byte_size)}
              </small>
            </span>
          </button>
        ))}
      </div>

      <div className="asset-send">
        <select value={fitMode} onChange={(event) => setFitMode(event.target.value as DisplayFitMode)} aria-label="Image fit mode">
          {fitModes.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <input value={caption} onChange={(event) => setCaption(event.target.value)} placeholder="Public caption" />
        <button
          onClick={() => sendImage.mutate()}
          disabled={!selectedAsset || selectedAsset.visibility !== "public_displayable" || sendImage.isPending}
        >
          <Send size={14} /> Send to player
        </button>
      </div>
      {selectedAsset && selectedAsset.visibility !== "public_displayable" ? (
        <span className="muted">Private assets cannot be sent to the player display.</span>
      ) : null}
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

export function NotesWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const noteBodyRef = useRef<HTMLTextAreaElement | null>(null);
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [selectedSnippetId, setSelectedSnippetId] = useState<string | null>(null);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [noteTags, setNoteTags] = useState("");
  const [noteSessionId, setNoteSessionId] = useState<string | null>(null);
  const [noteSceneId, setNoteSceneId] = useState<string | null>(null);
  const [noteAssetId, setNoteAssetId] = useState<string | null>(null);
  const [snippetTitle, setSnippetTitle] = useState("");
  const [snippetBody, setSnippetBody] = useState("");
  const [selectedNoteText, setSelectedNoteText] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [sceneOnly, setSceneOnly] = useState(true);

  const notesQuery = useQuery({
    queryKey: ["notes", props.selectedCampaignId],
    queryFn: () => api.notes(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const noteQuery = useQuery({
    queryKey: ["note", selectedNoteId],
    queryFn: () => api.note(selectedNoteId!),
    enabled: Boolean(selectedNoteId)
  });
  const snippetsQuery = useQuery({
    queryKey: ["public-snippets", props.selectedCampaignId],
    queryFn: () => api.publicSnippets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const assetsQuery = useQuery({
    queryKey: ["assets", props.selectedCampaignId],
    queryFn: () => api.assets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });

  const visibleNotes = useMemo(() => {
    const notes = notesQuery.data?.notes ?? [];
    if (!sceneOnly || !props.selectedSceneId) return notes;
    return notes.filter((note) => note.scene_id === props.selectedSceneId);
  }, [notesQuery.data, props.selectedSceneId, sceneOnly]);

  useEffect(() => {
    const notes = visibleNotes;
    if (selectedNoteId && notes.some((note) => note.id === selectedNoteId)) return;
    setSelectedNoteId(notes[0]?.id ?? null);
  }, [selectedNoteId, visibleNotes]);

  useEffect(() => {
    const snippets = snippetsQuery.data?.snippets ?? [];
    if (selectedSnippetId && snippets.some((snippet) => snippet.id === selectedSnippetId)) return;
    setSelectedSnippetId(snippets[0]?.id ?? null);
  }, [selectedSnippetId, snippetsQuery.data]);

  useEffect(() => {
    if (!noteQuery.data) return;
    setNoteTitle(noteQuery.data.title);
    setNoteBody(noteQuery.data.private_body);
    setNoteTags(noteQuery.data.tags.join(", "));
    setNoteSessionId(noteQuery.data.session_id);
    setNoteSceneId(noteQuery.data.scene_id);
    setNoteAssetId(noteQuery.data.asset_id);
    setSelectedNoteText("");
  }, [noteQuery.data]);

  const selectedSnippet = useMemo(
    () => snippetsQuery.data?.snippets.find((snippet) => snippet.id === selectedSnippetId) ?? null,
    [selectedSnippetId, snippetsQuery.data]
  );

  useEffect(() => {
    if (!selectedSnippet) return;
    setSnippetTitle(selectedSnippet.title ?? "");
    setSnippetBody(selectedSnippet.body);
  }, [selectedSnippet]);

  function refreshNotes(note?: Note) {
    if (note) {
      setSelectedNoteId(note.id);
      queryClient.setQueryData(["note", note.id], note);
    }
    void queryClient.invalidateQueries({ queryKey: ["notes", props.selectedCampaignId] });
  }

  function refreshSnippets(snippet?: PublicSnippet) {
    if (snippet) setSelectedSnippetId(snippet.id);
    void queryClient.invalidateQueries({ queryKey: ["public-snippets", props.selectedCampaignId] });
  }

  const createNote = useMutation({
    mutationFn: () =>
      api.createNote(props.selectedCampaignId!, {
        title: noteTitle || "Untitled note",
        private_body: noteBody,
        tags: splitTags(noteTags),
        session_id: noteSessionId,
        scene_id: noteSceneId ?? (sceneOnly ? props.selectedSceneId : null),
        asset_id: noteAssetId
      }),
    onSuccess: refreshNotes
  });
  const saveNote = useMutation({
    mutationFn: () =>
      api.patchNote(selectedNoteId!, {
        title: noteTitle,
        private_body: noteBody,
        tags: splitTags(noteTags),
        session_id: noteSessionId,
        scene_id: noteSceneId,
        asset_id: noteAssetId
      }),
    onSuccess: refreshNotes
  });
  const uploadNote = useMutation({
    mutationFn: () =>
      api.importNoteUpload(props.selectedCampaignId!, {
        file: importFile!,
        title: noteTitle,
        tags: noteTags,
        session_id: noteSessionId,
        scene_id: noteSceneId ?? (sceneOnly ? props.selectedSceneId : null),
        asset_id: noteAssetId
      }),
    onSuccess: (note) => {
      setImportFile(null);
      refreshNotes(note);
    }
  });
  const createSnippet = useMutation({
    mutationFn: (body?: string) =>
      api.createPublicSnippet(props.selectedCampaignId!, {
        note_id: selectedNoteId,
        title: snippetTitle || noteTitle || null,
        body: body ?? snippetBody,
        format: "markdown"
      }),
    onSuccess: refreshSnippets
  });
  const saveSnippet = useMutation({
    mutationFn: () => api.patchPublicSnippet(selectedSnippetId!, { title: snippetTitle || null, body: snippetBody, format: "markdown" }),
    onSuccess: refreshSnippets
  });
  const publishSnippet = useMutation({
    mutationFn: () => api.playerDisplayShowSnippet(selectedSnippetId!),
    onSuccess: (state) => {
      queryClient.setQueryData(["player-display"], state);
      broadcastDisplayChange(state);
      void queryClient.invalidateQueries({ queryKey: ["player-display"] });
    }
  });

  function updateSelectedText() {
    const element = noteBodyRef.current;
    if (!element) return;
    const text = element.value.slice(element.selectionStart, element.selectionEnd);
    setSelectedNoteText(text);
  }

  function readSelectedNoteText(): string {
    const element = noteBodyRef.current;
    if (!element) return "";
    return element.value.slice(element.selectionStart, element.selectionEnd);
  }

  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to manage notes." />;

  const error =
    notesQuery.error ??
    noteQuery.error ??
    snippetsQuery.error ??
    assetsQuery.error ??
    createNote.error ??
    saveNote.error ??
    uploadNote.error ??
    createSnippet.error ??
    saveSnippet.error ??
    publishSnippet.error;

  return (
    <div className="notes-widget">
      <div className="notes-columns">
        <div className="notes-list">
          <div className="section-heading">
            <strong>Notes</strong>
            <label className="checkbox-row">
              <input type="checkbox" checked={sceneOnly} onChange={(event) => setSceneOnly(event.target.checked)} />
              Scene
            </label>
          </div>
          <EntityList
            items={visibleNotes}
            selectedId={selectedNoteId}
            label={(note) => note.title}
            onSelect={(note) => setSelectedNoteId(note.id)}
          />
        </div>
        <div className="notes-list">
          <strong>Public snippets</strong>
          <EntityList
            items={snippetsQuery.data?.snippets ?? []}
            selectedId={selectedSnippetId}
            label={(snippet) => snippet.title || "Untitled snippet"}
            onSelect={(snippet) => setSelectedSnippetId(snippet.id)}
          />
        </div>
      </div>

      <div className="notes-editor">
        <label>
          <span>Note title</span>
          <input value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} placeholder="Private note title" />
        </label>
        <label>
          <span>Tags</span>
          <input value={noteTags} onChange={(event) => setNoteTags(event.target.value)} placeholder="private, clue" />
        </label>
        <div className="note-link-grid">
          <label>
            <span>Session</span>
            <select value={noteSessionId ?? ""} onChange={(event) => setNoteSessionId(event.target.value || null)} aria-label="Note session link">
              <option value="">No session</option>
              {props.sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Scene</span>
            <select value={noteSceneId ?? ""} onChange={(event) => setNoteSceneId(event.target.value || null)} aria-label="Note scene link">
              <option value="">No scene</option>
              {props.scenes.map((scene) => (
                <option key={scene.id} value={scene.id}>
                  {scene.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Asset</span>
            <select value={noteAssetId ?? ""} onChange={(event) => setNoteAssetId(event.target.value || null)} aria-label="Note asset link">
              <option value="">No asset</option>
              {(assetsQuery.data ?? []).map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <textarea
          ref={noteBodyRef}
          value={noteBody}
          onChange={(event) => setNoteBody(event.target.value)}
          onSelect={updateSelectedText}
          onKeyUp={updateSelectedText}
          onMouseUp={updateSelectedText}
          placeholder="Private GM note. Select safe text to snapshot as public snippet."
          aria-label="Private note body"
        />
        <div className="token-actions">
          <button onClick={() => createNote.mutate()} disabled={!noteTitle.trim() || createNote.isPending}>
            <Plus size={14} /> New note
          </button>
          <button onClick={() => saveNote.mutate()} disabled={!selectedNoteId || !noteTitle.trim() || saveNote.isPending}>
            Save note
          </button>
        </div>
      </div>

      <div className="note-imports">
        <div className="inline-form">
          <input aria-label="Markdown note file" type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={(event) => setImportFile(event.target.files?.[0] ?? null)} />
          <button onClick={() => uploadNote.mutate()} disabled={!importFile || uploadNote.isPending}>
            <Upload size={14} /> Import file
          </button>
        </div>
      </div>

      <div className="snippet-editor">
        <label>
          <span>Snippet title</span>
          <input value={snippetTitle} onChange={(event) => setSnippetTitle(event.target.value)} placeholder="Public title" />
        </label>
        <textarea
          value={snippetBody}
          onChange={(event) => setSnippetBody(event.target.value)}
          placeholder="Public snippet body only"
          aria-label="Public snippet body"
        />
        <div className="token-actions">
          <button onClick={() => createSnippet.mutate(undefined)} disabled={!snippetBody.trim() || createSnippet.isPending}>
            Create snippet
          </button>
          <button
            onClick={() => {
              const text = readSelectedNoteText();
              setSelectedNoteText(text);
              if (text.trim()) createSnippet.mutate(text);
            }}
            disabled={!selectedNoteId || createSnippet.isPending}
          >
            Copy selection to snippet
          </button>
          <button onClick={() => saveSnippet.mutate()} disabled={!selectedSnippetId || !snippetBody.trim() || saveSnippet.isPending}>
            Save snippet
          </button>
          <button onClick={() => publishSnippet.mutate()} disabled={!selectedSnippetId || publishSnippet.isPending}>
            <Send size={14} /> Publish
          </button>
        </div>
        <div className="snippet-preview" aria-label="Public snippet preview">
          <span className="muted">Preview uses public snippet text only.</span>
          <SafeMarkdownRenderer body={snippetBody || selectedSnippet?.body || ""} />
        </div>
      </div>
      {selectedNoteText.trim() ? <p className="muted">Selected text ready: {selectedNoteText.length} characters.</p> : null}
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

function renderTokensFromSceneTokens(tokens: SceneMapToken[] = []): PublicMapToken[] {
  return tokens.map((token) => ({
    id: token.id,
    entity_id: token.entity_id,
    asset_id: token.asset_id,
    asset_url: token.asset_url,
    name: token.label_visibility === "hidden" ? null : token.name,
    x: token.x,
    y: token.y,
    width: token.width,
    height: token.height,
    rotation: token.rotation,
    style: {
      shape: token.shape,
      color: token.color,
      border_color: token.border_color,
      opacity: token.opacity
    },
    status: token.status
  }));
}

function fieldValueToDraft(field: CustomFieldDefinition, value: unknown): string {
  if (value === null || value === undefined) return "";
  if (field.field_type === "resource" && typeof value === "object") {
    const resource = value as { current?: unknown; max?: unknown };
    return `${resource.current ?? ""}/${resource.max ?? ""}`;
  }
  if (field.field_type === "multi_select" && Array.isArray(value)) return value.join(", ");
  return String(value);
}

function draftToFieldValue(field: CustomFieldDefinition, draft: string): unknown | null {
  const value = draft.trim();
  if (!value) return null;
  if (field.field_type === "number") return Number(value);
  if (field.field_type === "boolean") return value === "true";
  if (field.field_type === "multi_select") return splitTags(value);
  if (field.field_type === "resource") {
    const [current, maximum] = value.split("/");
    return { current: Number(current || 0), max: maximum ? Number(maximum) : undefined };
  }
  return value;
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

export function PartyTrackerWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [creatingField, setCreatingField] = useState(false);
  const [entityKind, setEntityKind] = useState<EntityKind>("pc");
  const [entityName, setEntityName] = useState("");
  const [entityDisplayName, setEntityDisplayName] = useState("");
  const [entityVisibility, setEntityVisibility] = useState<"private" | "public_known">("private");
  const [entityPortraitId, setEntityPortraitId] = useState<string | null>(null);
  const [entityTags, setEntityTags] = useState("");
  const [entityNotes, setEntityNotes] = useState("");
  const [fieldKey, setFieldKey] = useState("");
  const [fieldLabel, setFieldLabel] = useState("");
  const [fieldType, setFieldType] = useState<CustomFieldType>("short_text");
  const [fieldAppliesTo, setFieldAppliesTo] = useState<EntityKind[]>(["pc"]);
  const [fieldOptions, setFieldOptions] = useState("");
  const [fieldDefaultValue, setFieldDefaultValue] = useState("");
  const [fieldPublicByDefault, setFieldPublicByDefault] = useState(false);
  const [fieldRequired, setFieldRequired] = useState(false);
  const [fieldSortOrder, setFieldSortOrder] = useState(0);
  const [fieldValueDrafts, setFieldValueDrafts] = useState<Record<string, string>>({});
  const [memberIds, setMemberIds] = useState<string[]>([]);
  const [partyFieldState, setPartyFieldState] = useState<Record<string, { selected: boolean; public_visible: boolean }>>({});
  const [partyLayout, setPartyLayout] = useState<PartyLayout>("standard");

  const entitiesQuery = useQuery({
    queryKey: ["entities", props.selectedCampaignId],
    queryFn: () => api.entities(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const fieldsQuery = useQuery({
    queryKey: ["custom-fields", props.selectedCampaignId],
    queryFn: () => api.customFields(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const partyQuery = useQuery({
    queryKey: ["party-tracker", props.selectedCampaignId],
    queryFn: () => api.partyTracker(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const assetsQuery = useQuery({
    queryKey: ["assets", props.selectedCampaignId],
    queryFn: () => api.assets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });

  const entities = entitiesQuery.data?.entities ?? [];
  const fields = fieldsQuery.data?.fields ?? [];
  const party = partyQuery.data;
  const selectedEntity = useMemo(() => entities.find((entity) => entity.id === selectedEntityId) ?? null, [entities, selectedEntityId]);
  const selectedField = useMemo(() => (creatingField ? null : fields.find((field) => field.id === selectedFieldId) ?? null), [creatingField, fields, selectedFieldId]);
  const portraitAssets = (assetsQuery.data ?? []).filter((asset) => asset.kind === "npc_portrait" || asset.kind === "handout_image" || asset.kind === "scene_image");

  useEffect(() => {
    if (selectedEntityId && entities.some((entity) => entity.id === selectedEntityId)) return;
    setSelectedEntityId(entities[0]?.id ?? null);
  }, [entities, selectedEntityId]);

  useEffect(() => {
    if (creatingField) return;
    if (selectedFieldId && fields.some((field) => field.id === selectedFieldId)) return;
    setSelectedFieldId(fields[0]?.id ?? null);
  }, [creatingField, fields, selectedFieldId]);

  useEffect(() => {
    if (!selectedEntity) return;
    setEntityKind(selectedEntity.kind);
    setEntityName(selectedEntity.name);
    setEntityDisplayName(selectedEntity.display_name ?? "");
    setEntityVisibility(selectedEntity.visibility);
    setEntityPortraitId(selectedEntity.portrait_asset_id);
    setEntityTags(selectedEntity.tags.join(", "));
    setEntityNotes(selectedEntity.notes);
    const nextDrafts: Record<string, string> = {};
    for (const field of fields) nextDrafts[field.key] = fieldValueToDraft(field, selectedEntity.field_values[field.key] ?? field.default_value);
    setFieldValueDrafts(nextDrafts);
  }, [fields, selectedEntity]);

  useEffect(() => {
    if (!selectedField) return;
    setFieldKey(selectedField.key);
    setFieldLabel(selectedField.label);
    setFieldType(selectedField.field_type);
    setFieldAppliesTo(selectedField.applies_to);
    setFieldOptions(selectedField.options.join(", "));
    setFieldDefaultValue(fieldValueToDraft(selectedField, selectedField.default_value));
    setFieldPublicByDefault(selectedField.public_by_default);
    setFieldRequired(selectedField.required);
    setFieldSortOrder(selectedField.sort_order);
  }, [selectedField]);

  useEffect(() => {
    if (!party) return;
    setPartyLayout(party.layout);
    setMemberIds(party.members.map((member) => member.entity_id));
    const next: Record<string, { selected: boolean; public_visible: boolean }> = {};
    for (const field of fields) next[field.id] = { selected: false, public_visible: field.public_by_default };
    for (const partyField of party.fields) next[partyField.field_definition_id] = { selected: true, public_visible: partyField.public_visible };
    setPartyFieldState(next);
  }, [fields, party]);

  function invalidatePartyData(entity?: EntityRecord) {
    if (entity) setSelectedEntityId(entity.id);
    void queryClient.invalidateQueries({ queryKey: ["entities", props.selectedCampaignId] });
    void queryClient.invalidateQueries({ queryKey: ["party-tracker", props.selectedCampaignId] });
  }

  function invalidateFields(field?: CustomFieldDefinition) {
    setCreatingField(false);
    if (field) setSelectedFieldId(field.id);
    void queryClient.invalidateQueries({ queryKey: ["custom-fields", props.selectedCampaignId] });
    void queryClient.invalidateQueries({ queryKey: ["party-tracker", props.selectedCampaignId] });
  }

  const createEntity = useMutation({
    mutationFn: () =>
      api.createEntity(props.selectedCampaignId!, {
        kind: entityKind,
        name: entityName,
        display_name: entityDisplayName || null,
        visibility: entityVisibility,
        portrait_asset_id: entityPortraitId,
        tags: splitTags(entityTags),
        notes: entityNotes
      }),
    onSuccess: invalidatePartyData
  });
  const saveEntity = useMutation({
    mutationFn: () =>
      api.patchEntity(selectedEntityId!, {
        kind: entityKind,
        name: entityName,
        display_name: entityDisplayName || null,
        visibility: entityVisibility,
        portrait_asset_id: entityPortraitId,
        tags: splitTags(entityTags),
        notes: entityNotes
      }),
    onSuccess: invalidatePartyData
  });
  const createField = useMutation({
    mutationFn: () =>
      api.createCustomField(props.selectedCampaignId!, {
        key: fieldKey,
        label: fieldLabel,
        field_type: fieldType,
        applies_to: fieldAppliesTo,
        required: fieldRequired,
        default_value: draftToFieldValue({ ...(selectedField ?? fields[0]), field_type: fieldType, options: splitTags(fieldOptions) } as CustomFieldDefinition, fieldDefaultValue),
        options: splitTags(fieldOptions),
        public_by_default: fieldPublicByDefault,
        sort_order: fieldSortOrder
      }),
    onSuccess: invalidateFields
  });
  const saveField = useMutation({
    mutationFn: () =>
      api.patchCustomField(selectedFieldId!, {
        label: fieldLabel,
        applies_to: fieldAppliesTo,
        required: fieldRequired,
        default_value: draftToFieldValue(selectedField!, fieldDefaultValue),
        options: splitTags(fieldOptions),
        public_by_default: fieldPublicByDefault,
        sort_order: fieldSortOrder
      }),
    onSuccess: invalidateFields
  });
  const saveFieldValues = useMutation({
    mutationFn: () => {
      const values: Record<string, unknown | null> = {};
      for (const field of fields.filter((item) => item.applies_to.includes(entityKind))) {
        values[field.key] = draftToFieldValue(field, fieldValueDrafts[field.key] ?? "");
      }
      return api.patchEntityFieldValues(selectedEntityId!, values);
    },
    onSuccess: invalidatePartyData
  });
  const saveParty = useMutation({
    mutationFn: () =>
      api.patchPartyTracker(props.selectedCampaignId!, {
        layout: partyLayout,
        member_ids: memberIds,
        fields: fields
          .filter((field) => partyFieldState[field.id]?.selected)
          .map((field) => ({ field_definition_id: field.id, public_visible: Boolean(partyFieldState[field.id]?.public_visible) }))
      }),
    onSuccess: (result) => {
      queryClient.setQueryData(["party-tracker", props.selectedCampaignId], result);
    }
  });
  const publishParty = useMutation({
    mutationFn: () => api.playerDisplayShowParty(props.selectedCampaignId!),
    onSuccess: (state) => {
      queryClient.setQueryData(["player-display"], state);
      broadcastDisplayChange(state);
      void queryClient.invalidateQueries({ queryKey: ["player-display"] });
    }
  });

  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to manage party entities." />;

  const error =
    entitiesQuery.error ??
    fieldsQuery.error ??
    partyQuery.error ??
    assetsQuery.error ??
    createEntity.error ??
    saveEntity.error ??
    createField.error ??
    saveField.error ??
    saveFieldValues.error ??
    saveParty.error ??
    publishParty.error;

  const partyMembers = memberIds.map((id) => entities.find((entity) => entity.id === id)).filter((entity): entity is EntityRecord => Boolean(entity));
  const partyFields = fields.filter((field) => partyFieldState[field.id]?.selected);

  return (
    <div className="party-widget">
      <div className="notes-columns">
        <div className="notes-list">
          <strong>Entities</strong>
          <EntityList items={entities} selectedId={selectedEntityId} label={(entity) => `${entity.name} · ${entity.kind}`} onSelect={(entity) => setSelectedEntityId(entity.id)} />
        </div>
        <div className="notes-list">
          <strong>Fields</strong>
          <EntityList
            items={fields}
            selectedId={creatingField ? null : selectedFieldId}
            label={(field) => `${field.label} · ${field.field_type}`}
            onSelect={(field) => {
              setCreatingField(false);
              setSelectedFieldId(field.id);
            }}
          />
        </div>
      </div>

      <div className="party-section">
        <strong>Entity</strong>
        <div className="token-grid">
          <label>
            <span>Kind</span>
            <select value={entityKind} onChange={(event) => setEntityKind(event.target.value as EntityKind)} aria-label="Entity kind">
              {entityKinds.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Name</span>
            <input value={entityName} onChange={(event) => setEntityName(event.target.value)} aria-label="Entity name" />
          </label>
          <label>
            <span>Display</span>
            <input value={entityDisplayName} onChange={(event) => setEntityDisplayName(event.target.value)} aria-label="Entity display name" />
          </label>
          <label>
            <span>Visibility</span>
            <select value={entityVisibility} onChange={(event) => setEntityVisibility(event.target.value as "private" | "public_known")} aria-label="Entity visibility">
              <option value="private">Private</option>
              <option value="public_known">Public known</option>
            </select>
          </label>
          <label>
            <span>Portrait</span>
            <select value={entityPortraitId ?? ""} onChange={(event) => setEntityPortraitId(event.target.value || null)} aria-label="Entity portrait">
              <option value="">No portrait</option>
              {portraitAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.name} · {asset.visibility}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Tags</span>
            <input value={entityTags} onChange={(event) => setEntityTags(event.target.value)} aria-label="Entity tags" />
          </label>
        </div>
        <textarea value={entityNotes} onChange={(event) => setEntityNotes(event.target.value)} placeholder="Private entity notes" aria-label="Entity notes" />
        <div className="token-actions">
          <button onClick={() => createEntity.mutate()} disabled={!entityName.trim() || createEntity.isPending}>
            <Plus size={14} /> New entity
          </button>
          <button onClick={() => saveEntity.mutate()} disabled={!selectedEntityId || !entityName.trim() || saveEntity.isPending}>
            Save entity
          </button>
        </div>
      </div>

      <div className="party-section">
        <strong>Custom field</strong>
        <div className="token-grid">
          <label>
            <span>Key</span>
            <input value={fieldKey} onChange={(event) => setFieldKey(event.target.value)} aria-label="Custom field key" disabled={Boolean(selectedField)} />
          </label>
          <label>
            <span>Label</span>
            <input value={fieldLabel} onChange={(event) => setFieldLabel(event.target.value)} aria-label="Custom field label" />
          </label>
          <label>
            <span>Type</span>
            <select value={fieldType} onChange={(event) => setFieldType(event.target.value as CustomFieldType)} aria-label="Custom field type" disabled={Boolean(selectedField)}>
              {customFieldTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Applies</span>
            <input value={fieldAppliesTo.join(", ")} onChange={(event) => setFieldAppliesTo(splitTags(event.target.value) as EntityKind[])} aria-label="Custom field applies to" />
          </label>
          <label>
            <span>Options</span>
            <input value={fieldOptions} onChange={(event) => setFieldOptions(event.target.value)} aria-label="Custom field options" />
          </label>
          <label>
            <span>Default</span>
            <input value={fieldDefaultValue} onChange={(event) => setFieldDefaultValue(event.target.value)} aria-label="Custom field default value" />
          </label>
          <label>
            <span>Sort</span>
            <input type="number" value={fieldSortOrder} onChange={(event) => setFieldSortOrder(Number(event.target.value))} aria-label="Custom field sort order" />
          </label>
          <label className="check-row">
            <input type="checkbox" checked={fieldPublicByDefault} onChange={(event) => setFieldPublicByDefault(event.target.checked)} />
            <span>Public by default</span>
          </label>
          <label className="check-row">
            <input type="checkbox" checked={fieldRequired} onChange={(event) => setFieldRequired(event.target.checked)} />
            <span>Required</span>
          </label>
        </div>
        <div className="token-actions">
          <button onClick={() => createField.mutate()} disabled={!fieldKey.trim() || !fieldLabel.trim() || createField.isPending}>
            <Plus size={14} /> New field
          </button>
          <button onClick={() => saveField.mutate()} disabled={!selectedFieldId || !fieldLabel.trim() || saveField.isPending}>
            Save field
          </button>
          <button
            onClick={() => {
              setCreatingField(true);
              setSelectedFieldId(null);
              setFieldKey("");
              setFieldLabel("");
              setFieldType("short_text");
              setFieldAppliesTo(["pc"]);
              setFieldOptions("");
              setFieldDefaultValue("");
              setFieldPublicByDefault(false);
              setFieldRequired(false);
              setFieldSortOrder(0);
            }}
          >
            Clear field form
          </button>
        </div>
      </div>

      <div className="party-section">
        <strong>Values</strong>
        <div className="token-grid">
          {fields
            .filter((field) => field.applies_to.includes(entityKind))
            .map((field) => (
              <label key={field.id}>
                <span>{field.label}</span>
                {field.field_type === "boolean" ? (
                  <select value={fieldValueDrafts[field.key] ?? ""} onChange={(event) => setFieldValueDrafts((current) => ({ ...current, [field.key]: event.target.value }))}>
                    <option value="">Unset</option>
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : field.field_type === "select" || field.field_type === "radio" ? (
                  <select value={fieldValueDrafts[field.key] ?? ""} onChange={(event) => setFieldValueDrafts((current) => ({ ...current, [field.key]: event.target.value }))}>
                    <option value="">Unset</option>
                    {field.options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : field.field_type === "image" ? (
                  <select value={fieldValueDrafts[field.key] ?? ""} onChange={(event) => setFieldValueDrafts((current) => ({ ...current, [field.key]: event.target.value }))}>
                    <option value="">Unset</option>
                    {portraitAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={fieldValueDrafts[field.key] ?? ""}
                    onChange={(event) => setFieldValueDrafts((current) => ({ ...current, [field.key]: event.target.value }))}
                    placeholder={field.field_type === "resource" ? "current/max" : field.field_type}
                  />
                )}
              </label>
            ))}
        </div>
        <button onClick={() => saveFieldValues.mutate()} disabled={!selectedEntityId || saveFieldValues.isPending}>
          Save values
        </button>
      </div>

      <div className="party-section">
        <strong>Party tracker</strong>
        <div className="token-actions">
          <select value={partyLayout} onChange={(event) => setPartyLayout(event.target.value as PartyLayout)} aria-label="Party layout">
            {partyLayouts.map((layout) => (
              <option key={layout} value={layout}>
                {layout}
              </option>
            ))}
          </select>
          <button
            onClick={() => selectedEntity && selectedEntity.kind === "pc" && !memberIds.includes(selectedEntity.id) && setMemberIds((current) => [...current, selectedEntity.id])}
            disabled={!selectedEntity || selectedEntity.kind !== "pc"}
          >
            Add selected PC
          </button>
          <button onClick={() => saveParty.mutate()} disabled={saveParty.isPending}>
            Save party
          </button>
          <button onClick={() => publishParty.mutate()} disabled={publishParty.isPending}>
            <Send size={14} /> Publish party
          </button>
        </div>
        <div className="party-roster">
          {partyMembers.map((entity) => (
            <button key={entity.id} className="entity selected" onClick={() => setMemberIds((current) => current.filter((id) => id !== entity.id))}>
              <span>{entity.display_name || entity.name}</span>
              <Trash2 size={13} />
            </button>
          ))}
        </div>
        <div className="party-field-list">
          {fields.map((field) => {
            const state = partyFieldState[field.id] ?? { selected: false, public_visible: field.public_by_default };
            return (
              <div key={field.id} className="party-field-row">
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={state.selected}
                    onChange={(event) => setPartyFieldState((current) => ({ ...current, [field.id]: { ...state, selected: event.target.checked } }))}
                  />
                  <span>{field.label}</span>
                </label>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={state.public_visible}
                    onChange={(event) => setPartyFieldState((current) => ({ ...current, [field.id]: { ...state, public_visible: event.target.checked } }))}
                  />
                  <span>Public</span>
                </label>
              </div>
            );
          })}
        </div>
        <div className={`party-card-preview layout-${partyLayout}`}>
          {partyMembers.map((entity) => (
            <div key={entity.id} className="party-card">
              <strong>{entity.display_name || entity.name}</strong>
              <span>{entity.kind} · {entity.visibility}</span>
              {partyFields.map((field) => (
                <span key={field.id}>
                  {field.label}: {formatPartyValue(entity.field_values[field.key]) || "unset"}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

function statusItemLabel(item: string | { label: string } | unknown): string {
  if (typeof item === "string") return item;
  if (item && typeof item === "object" && "label" in item && typeof (item as { label?: unknown }).label === "string") {
    return (item as { label: string }).label;
  }
  return "";
}

function statusDraft(items: Array<string | { label: string }> = []): string {
  return items.map(statusItemLabel).filter(Boolean).join(", ");
}

function conditionsDraft(items: Array<Record<string, unknown>> = []): string {
  return items
    .map((item) => (typeof item.label === "string" ? item.label : ""))
    .filter(Boolean)
    .join(", ");
}

function draftToConditionObjects(value: string): Array<Record<string, unknown>> {
  return splitTags(value).map((label) => ({ label }));
}

function draftToPublicStatus(value: string): Array<string> {
  return splitTags(value);
}

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function CombatTrackerWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [selectedEncounterId, setSelectedEncounterId] = useState<string | null>(null);
  const [selectedCombatantId, setSelectedCombatantId] = useState<string | null>(null);
  const [encounterTitle, setEncounterTitle] = useState("");
  const [encounterStatus, setEncounterStatus] = useState<CombatEncounterStatus>("active");
  const [combatantName, setCombatantName] = useState("");
  const [combatantDisposition, setCombatantDisposition] = useState<CombatantDisposition>("enemy");
  const [combatantEntityId, setCombatantEntityId] = useState<string | null>(null);
  const [combatantTokenId, setCombatantTokenId] = useState<string | null>(null);
  const [initiative, setInitiative] = useState("");
  const [armorClass, setArmorClass] = useState("");
  const [hpCurrent, setHpCurrent] = useState("");
  const [hpMax, setHpMax] = useState("");
  const [hpTemp, setHpTemp] = useState("0");
  const [conditions, setConditions] = useState("");
  const [publicStatus, setPublicStatus] = useState("");
  const [combatNotes, setCombatNotes] = useState("");
  const [publicVisible, setPublicVisible] = useState(false);
  const [isDefeated, setIsDefeated] = useState(false);

  const encountersQuery = useQuery({
    queryKey: ["combat-encounters", props.selectedCampaignId],
    queryFn: () => api.combatEncounters(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const sceneContextQuery = useQuery({
    queryKey: ["scene-context", props.selectedSceneId],
    queryFn: () => api.sceneContext(props.selectedSceneId!),
    enabled: Boolean(props.selectedSceneId)
  });
  const entitiesQuery = useQuery({
    queryKey: ["entities", props.selectedCampaignId],
    queryFn: () => api.entities(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const selectedSceneBelongsToCampaign = Boolean(
    props.selectedCampaignId &&
      props.selectedSceneId &&
      props.scenes.some((scene) => scene.id === props.selectedSceneId && scene.campaign_id === props.selectedCampaignId)
  );
  const sceneMapsQuery = useQuery({
    queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId],
    queryFn: () => api.sceneMaps(props.selectedCampaignId!, props.selectedSceneId!),
    enabled: selectedSceneBelongsToCampaign
  });

  const selectedSceneMap = sceneMapsQuery.data?.find((sceneMap) => sceneMap.is_active) ?? sceneMapsQuery.data?.[0] ?? null;
  const tokensQuery = useQuery({
    queryKey: ["scene-map-tokens", selectedSceneMap?.id],
    queryFn: () => api.sceneMapTokens(selectedSceneMap!.id),
    enabled: Boolean(selectedSceneMap?.id)
  });

  const encounters = encountersQuery.data?.encounters ?? [];
  const selectedEncounter = useMemo(
    () => encounters.find((encounter) => encounter.id === selectedEncounterId) ?? encounters[0] ?? null,
    [encounters, selectedEncounterId]
  );
  const selectedCombatant = useMemo(
    () => selectedEncounter?.combatants.find((combatant) => combatant.id === selectedCombatantId) ?? selectedEncounter?.combatants[0] ?? null,
    [selectedCombatantId, selectedEncounter]
  );
  const entities = entitiesQuery.data?.entities ?? [];
  const tokens = tokensQuery.data?.tokens ?? [];

  useEffect(() => {
    const activeEncounterId = sceneContextQuery.data?.context?.active_encounter_id;
    if (activeEncounterId && encounters.some((encounter) => encounter.id === activeEncounterId)) {
      setSelectedEncounterId(activeEncounterId);
    }
  }, [encounters, sceneContextQuery.data?.context?.active_encounter_id]);

  useEffect(() => {
    if (selectedEncounterId && encounters.some((encounter) => encounter.id === selectedEncounterId)) return;
    setSelectedEncounterId(encounters[0]?.id ?? null);
  }, [encounters, selectedEncounterId]);

  useEffect(() => {
    if (!selectedEncounter) return;
    setEncounterTitle(selectedEncounter.title);
    setEncounterStatus(selectedEncounter.status);
    if (selectedCombatantId && selectedEncounter.combatants.some((combatant) => combatant.id === selectedCombatantId)) return;
    setSelectedCombatantId(selectedEncounter.combatants[0]?.id ?? null);
  }, [selectedCombatantId, selectedEncounter]);

  useEffect(() => {
    if (!selectedCombatant) return;
    setCombatantName(selectedCombatant.name);
    setCombatantDisposition(selectedCombatant.disposition);
    setCombatantEntityId(selectedCombatant.entity_id);
    setCombatantTokenId(selectedCombatant.token_id);
    setInitiative(selectedCombatant.initiative === null ? "" : String(selectedCombatant.initiative));
    setArmorClass(selectedCombatant.armor_class === null ? "" : String(selectedCombatant.armor_class));
    setHpCurrent(selectedCombatant.hp_current === null ? "" : String(selectedCombatant.hp_current));
    setHpMax(selectedCombatant.hp_max === null ? "" : String(selectedCombatant.hp_max));
    setHpTemp(String(selectedCombatant.hp_temp));
    setConditions(conditionsDraft(selectedCombatant.conditions));
    setPublicStatus(statusDraft(selectedCombatant.public_status));
    setCombatNotes(selectedCombatant.notes);
    setPublicVisible(selectedCombatant.public_visible);
    setIsDefeated(selectedCombatant.is_defeated);
  }, [selectedCombatant]);

  function refreshEncounter(encounter: CombatEncounter) {
    setSelectedEncounterId(encounter.id);
    void queryClient.invalidateQueries({ queryKey: ["combat-encounters", props.selectedCampaignId] });
  }

  const createEncounter = useMutation({
    mutationFn: () =>
      api.createCombatEncounter(props.selectedCampaignId!, {
        title: encounterTitle || "New encounter",
        status: encounterStatus,
        session_id: props.selectedSessionId,
        scene_id: props.selectedSceneId
      }),
    onSuccess: refreshEncounter
  });
  const saveEncounter = useMutation({
    mutationFn: () =>
      api.patchCombatEncounter(selectedEncounter!.id, {
        title: encounterTitle,
        status: encounterStatus,
        session_id: props.selectedSessionId,
        scene_id: props.selectedSceneId
      }),
    onSuccess: refreshEncounter
  });
  const createCombatant = useMutation({
    mutationFn: () =>
      api.createCombatant(selectedEncounter!.id, {
        name: combatantName || null,
        disposition: combatantDisposition,
        entity_id: combatantEntityId,
        token_id: combatantTokenId,
        initiative: numberOrNull(initiative),
        armor_class: numberOrNull(armorClass),
        hp_current: numberOrNull(hpCurrent),
        hp_max: numberOrNull(hpMax),
        hp_temp: numberOrNull(hpTemp) ?? 0,
        conditions: draftToConditionObjects(conditions),
        public_status: draftToPublicStatus(publicStatus),
        notes: combatNotes,
        public_visible: publicVisible,
        is_defeated: isDefeated
      }),
    onSuccess: refreshEncounter
  });
  const saveCombatant = useMutation({
    mutationFn: () =>
      api.patchCombatant(selectedCombatant!.id, {
        name: combatantName,
        disposition: combatantDisposition,
        entity_id: combatantEntityId,
        token_id: combatantTokenId,
        initiative: numberOrNull(initiative),
        armor_class: numberOrNull(armorClass),
        hp_current: numberOrNull(hpCurrent),
        hp_max: numberOrNull(hpMax),
        hp_temp: numberOrNull(hpTemp) ?? 0,
        conditions: draftToConditionObjects(conditions),
        public_status: draftToPublicStatus(publicStatus),
        notes: combatNotes,
        public_visible: publicVisible,
        is_defeated: isDefeated
      }),
    onSuccess: refreshEncounter
  });
  const deleteCombatant = useMutation({
    mutationFn: () => api.deleteCombatant(selectedCombatant!.id),
    onSuccess: (result) => {
      setSelectedCombatantId(null);
      refreshEncounter(result.encounter);
    }
  });
  const reorder = useMutation({
    mutationFn: (ids: string[]) => api.reorderCombatants(selectedEncounter!.id, ids),
    onSuccess: refreshEncounter
  });
  const nextTurn = useMutation({
    mutationFn: () => api.nextCombatTurn(selectedEncounter!.id),
    onSuccess: refreshEncounter
  });
  const previousTurn = useMutation({
    mutationFn: () => api.previousCombatTurn(selectedEncounter!.id),
    onSuccess: refreshEncounter
  });
  const publishInitiative = useMutation({
    mutationFn: () => api.playerDisplayShowInitiative(selectedEncounter!.id),
    onSuccess: (state) => {
      queryClient.setQueryData(["player-display"], state);
      broadcastDisplayChange(state);
      void queryClient.invalidateQueries({ queryKey: ["player-display"] });
    }
  });

  function moveCombatant(combatant: CombatantRecord, direction: -1 | 1) {
    if (!selectedEncounter) return;
    const ids = selectedEncounter.combatants.map((item) => item.id);
    const index = ids.indexOf(combatant.id);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= ids.length) return;
    const next = [...ids];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    reorder.mutate(next);
  }

  if (!props.selectedCampaignId) return <EmptyText text="Select a campaign to manage combat." />;

  const error =
    encountersQuery.error ??
    sceneContextQuery.error ??
    entitiesQuery.error ??
    sceneMapsQuery.error ??
    tokensQuery.error ??
    createEncounter.error ??
    saveEncounter.error ??
    createCombatant.error ??
    saveCombatant.error ??
    deleteCombatant.error ??
    reorder.error ??
    nextTurn.error ??
    previousTurn.error ??
    publishInitiative.error;

  return (
    <div className="combat-widget">
      <div className="notes-columns">
        <div className="notes-list">
          <strong>Encounters</strong>
          <EntityList
            items={encounters}
            selectedId={selectedEncounter?.id ?? null}
            label={(encounter) => `${encounter.title} · round ${encounter.round}`}
            onSelect={(encounter) => setSelectedEncounterId(encounter.id)}
          />
        </div>
        <div className="notes-list">
          <strong>Combatants</strong>
          <EntityList
            items={selectedEncounter?.combatants ?? []}
            selectedId={selectedCombatant?.id ?? null}
            label={(combatant) => `${combatant.order_index + 1}. ${combatant.name} · ${combatant.disposition}`}
            onSelect={(combatant) => setSelectedCombatantId(combatant.id)}
          />
        </div>
      </div>

      <div className="party-section">
        <strong>Encounter</strong>
        <div className="token-grid">
          <label>
            <span>Title</span>
            <input value={encounterTitle} onChange={(event) => setEncounterTitle(event.target.value)} aria-label="Encounter title" />
          </label>
          <label>
            <span>Status</span>
            <select value={encounterStatus} onChange={(event) => setEncounterStatus(event.target.value as CombatEncounterStatus)} aria-label="Encounter status">
              {combatStatuses.map((statusValue) => (
                <option key={statusValue} value={statusValue}>
                  {statusValue}
                </option>
              ))}
            </select>
          </label>
          <InfoRow label="Round" value={String(selectedEncounter?.round ?? 1)} />
          <InfoRow label="Active" value={selectedEncounter?.combatants.find((item) => item.id === selectedEncounter.active_combatant_id)?.name ?? "None"} />
        </div>
        <div className="token-actions">
          <button onClick={() => createEncounter.mutate()} disabled={!encounterTitle.trim() || createEncounter.isPending}>
            <Plus size={14} /> New encounter
          </button>
          <button onClick={() => saveEncounter.mutate()} disabled={!selectedEncounter || !encounterTitle.trim() || saveEncounter.isPending}>
            Save encounter
          </button>
          <button onClick={() => previousTurn.mutate()} disabled={!selectedEncounter || previousTurn.isPending}>
            Previous turn
          </button>
          <button onClick={() => nextTurn.mutate()} disabled={!selectedEncounter || nextTurn.isPending}>
            Next turn
          </button>
          <button onClick={() => publishInitiative.mutate()} disabled={!selectedEncounter || publishInitiative.isPending}>
            <Send size={14} /> Publish initiative
          </button>
        </div>
      </div>

      <div className="party-section">
        <strong>Combatant</strong>
        <div className="token-grid">
          <label>
            <span>Name</span>
            <input value={combatantName} onChange={(event) => setCombatantName(event.target.value)} aria-label="Combatant name" />
          </label>
          <label>
            <span>Disposition</span>
            <select value={combatantDisposition} onChange={(event) => setCombatantDisposition(event.target.value as CombatantDisposition)} aria-label="Combatant disposition">
              {combatDispositions.map((disposition) => (
                <option key={disposition} value={disposition}>
                  {disposition}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Entity</span>
            <select value={combatantEntityId ?? ""} onChange={(event) => setCombatantEntityId(event.target.value || null)} aria-label="Combatant entity">
              <option value="">Manual</option>
              {entities.map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name} · {entity.kind}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Token</span>
            <select value={combatantTokenId ?? ""} onChange={(event) => setCombatantTokenId(event.target.value || null)} aria-label="Combatant token">
              <option value="">No token</option>
              {tokens.map((token) => (
                <option key={token.id} value={token.id}>
                  {token.name} · {token.visibility}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Initiative</span>
            <input type="number" value={initiative} onChange={(event) => setInitiative(event.target.value)} aria-label="Combatant initiative" />
          </label>
          <label>
            <span>AC</span>
            <input type="number" value={armorClass} onChange={(event) => setArmorClass(event.target.value)} aria-label="Combatant AC" />
          </label>
          <label>
            <span>HP</span>
            <input value={hpCurrent} onChange={(event) => setHpCurrent(event.target.value)} aria-label="Combatant HP current" />
          </label>
          <label>
            <span>Max HP</span>
            <input value={hpMax} onChange={(event) => setHpMax(event.target.value)} aria-label="Combatant HP max" />
          </label>
          <label>
            <span>Temp HP</span>
            <input value={hpTemp} onChange={(event) => setHpTemp(event.target.value)} aria-label="Combatant temp HP" />
          </label>
          <label>
            <span>Public status</span>
            <input value={publicStatus} onChange={(event) => setPublicStatus(event.target.value)} aria-label="Combatant public status" />
          </label>
          <label>
            <span>Private conditions</span>
            <input value={conditions} onChange={(event) => setConditions(event.target.value)} aria-label="Combatant private conditions" />
          </label>
          <label className="check-row">
            <input type="checkbox" checked={publicVisible} onChange={(event) => setPublicVisible(event.target.checked)} />
            <span>Public initiative</span>
          </label>
          <label className="check-row">
            <input type="checkbox" checked={isDefeated} onChange={(event) => setIsDefeated(event.target.checked)} />
            <span>Defeated</span>
          </label>
        </div>
        <textarea value={combatNotes} onChange={(event) => setCombatNotes(event.target.value)} placeholder="Private combat notes" aria-label="Combatant notes" />
        <div className="token-actions">
          <button onClick={() => createCombatant.mutate()} disabled={!selectedEncounter || createCombatant.isPending}>
            <Plus size={14} /> Add combatant
          </button>
          <button onClick={() => saveCombatant.mutate()} disabled={!selectedCombatant || !combatantName.trim() || saveCombatant.isPending}>
            Save combatant
          </button>
          <button onClick={() => deleteCombatant.mutate()} disabled={!selectedCombatant || deleteCombatant.isPending}>
            <Trash2 size={14} /> Delete combatant
          </button>
        </div>
      </div>

      <div className="combat-order-list">
        {(selectedEncounter?.combatants ?? []).map((combatant) => (
          <div key={combatant.id} className={`combat-order-row ${combatant.id === selectedEncounter?.active_combatant_id ? "active" : ""}`}>
            <button onClick={() => setSelectedCombatantId(combatant.id)}>
              <strong>{combatant.name}</strong>
              <span>
                {combatant.initiative ?? "-"} · {combatant.disposition}
                {combatant.public_visible ? " · public" : " · private"}
                {combatant.is_defeated ? " · defeated" : ""}
              </span>
            </button>
            <button aria-label={`Move ${combatant.name} up`} onClick={() => moveCombatant(combatant, -1)} disabled={reorder.isPending}>
              ↑
            </button>
            <button aria-label={`Move ${combatant.name} down`} onClick={() => moveCombatant(combatant, 1)} disabled={reorder.isPending}>
              ↓
            </button>
          </div>
        ))}
      </div>
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

function mapPayloadFromSceneMap(sceneMap: SceneMap, fog?: FogMask | null, tokens?: SceneMapToken[]): MapRenderPayload {
  const fogPayload =
    fog && fog.enabled
      ? {
          enabled: true,
          mask_id: fog.id,
          mask_url: fog.mask_url,
          revision: fog.revision,
          width: fog.width,
          height: fog.height
        }
      : undefined;
  return {
    type: "map",
    scene_map_id: sceneMap.id,
    map_id: sceneMap.map_id,
    asset_id: sceneMap.map.asset_id,
    asset_url: sceneMap.map.asset_url,
    width: sceneMap.map.width,
    height: sceneMap.map.height,
    title: sceneMap.map.name,
    fit_mode: sceneMap.player_fit_mode,
    grid: {
      type: "square",
      visible: sceneMap.player_grid_visible && sceneMap.map.grid_enabled,
      size_px: sceneMap.map.grid_size_px,
      offset_x: sceneMap.map.grid_offset_x,
      offset_y: sceneMap.map.grid_offset_y,
      color: sceneMap.map.grid_color,
      opacity: sceneMap.map.grid_opacity
    },
    fog: fogPayload,
    tokens: renderTokensFromSceneTokens(tokens)
  };
}

export function MapDisplayWidget(props: SharedWidgetProps) {
  const queryClient = useQueryClient();
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedMapId, setSelectedMapId] = useState<string | null>(null);
  const [selectedSceneMapId, setSelectedSceneMapId] = useState<string | null>(null);
  const [selectedBundledPackId, setSelectedBundledPackId] = useState<string | null>(null);
  const [bundledCollection, setBundledCollection] = useState("");
  const [bundledCategory, setBundledCategory] = useState("");
  const [bundledSearch, setBundledSearch] = useState("");
  const [selectedBundledMapId, setSelectedBundledMapId] = useState<string | null>(null);
  const [gridSize, setGridSize] = useState(70);
  const [gridOffsetX, setGridOffsetX] = useState(0);
  const [gridOffsetY, setGridOffsetY] = useState(0);
  const [gridColor, setGridColor] = useState("#FFFFFF");
  const [gridOpacity, setGridOpacity] = useState(0.35);
  const [gridEnabled, setGridEnabled] = useState(false);
  const [playerFitMode, setPlayerFitMode] = useState<DisplayFitMode>("fit");
  const [playerGridVisible, setPlayerGridVisible] = useState(true);
  const [fogTool, setFogTool] = useState<"rect" | "brush">("rect");
  const [fogMode, setFogMode] = useState<"reveal" | "hide">("reveal");
  const [brushRadius, setBrushRadius] = useState(24);
  const [fogSaveStatus, setFogSaveStatus] = useState<SaveStatus>("saved");
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);
  const [tokenName, setTokenName] = useState("Token");
  const [tokenVisibility, setTokenVisibility] = useState<SceneMapToken["visibility"]>("gm_only");
  const [tokenLabelVisibility, setTokenLabelVisibility] = useState<SceneMapToken["label_visibility"]>("gm_only");
  const [tokenShape, setTokenShape] = useState<SceneMapToken["shape"]>("circle");
  const [tokenColor, setTokenColor] = useState("#D94841");
  const [tokenBorderColor, setTokenBorderColor] = useState("#FFFFFF");
  const [tokenOpacity, setTokenOpacity] = useState(1);
  const [tokenWidth, setTokenWidth] = useState(70);
  const [tokenHeight, setTokenHeight] = useState(70);
  const [tokenRotation, setTokenRotation] = useState(0);
  const [selectedTokenAssetId, setSelectedTokenAssetId] = useState<string | null>(null);
  const [selectedTokenEntityId, setSelectedTokenEntityId] = useState<string | null>(null);
  const [tokenSaveStatus, setTokenSaveStatus] = useState<SaveStatus>("saved");
  const [localTokens, setLocalTokens] = useState<SceneMapToken[]>([]);
  const [placingToken, setPlacingToken] = useState(false);
  const [draftFog, setDraftFog] = useState<
    | { kind: "rect"; start: { x: number; y: number }; current: { x: number; y: number } }
    | { kind: "brush"; points: Array<{ x: number; y: number }> }
    | null
  >(null);
  const dragRef = useRef<typeof draftFog>(null);
  const tokenDragRef = useRef<
    | {
        kind: "move" | "resize";
        tokenId: string;
        start: { x: number; y: number };
        token: SceneMapToken;
      }
    | null
  >(null);

  const assetsQuery = useQuery({
    queryKey: ["assets", props.selectedCampaignId],
    queryFn: () => api.assets(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const entitiesQuery = useQuery({
    queryKey: ["entities", props.selectedCampaignId],
    queryFn: () => api.entities(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const mapsQuery = useQuery({
    queryKey: ["maps", props.selectedCampaignId],
    queryFn: () => api.maps(props.selectedCampaignId!),
    enabled: Boolean(props.selectedCampaignId)
  });
  const selectedSceneBelongsToCampaign = Boolean(
    props.selectedCampaignId &&
      props.selectedSceneId &&
      props.scenes.some((scene) => scene.id === props.selectedSceneId && scene.campaign_id === props.selectedCampaignId)
  );
  const sceneMapsQuery = useQuery({
    queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId],
    queryFn: () => api.sceneMaps(props.selectedCampaignId!, props.selectedSceneId!),
    enabled: selectedSceneBelongsToCampaign
  });
  const bundledPacksQuery = useQuery({
    queryKey: ["bundled-asset-packs"],
    queryFn: api.bundledAssetPacks
  });
  const bundledMapsQuery = useQuery({
    queryKey: ["bundled-asset-packs", selectedBundledPackId, "maps"],
    queryFn: () => api.bundledAssetPackMaps(selectedBundledPackId!),
    enabled: Boolean(selectedBundledPackId)
  });

  const mapAssets = useMemo(() => (assetsQuery.data ?? []).filter((asset) => asset.kind === "map_image"), [assetsQuery.data]);
  const tokenAssets = useMemo(
    () => (assetsQuery.data ?? []).filter((asset) => asset.kind !== "map_image" && asset.width && asset.height),
    [assetsQuery.data]
  );
  const selectedBundledPack = useMemo(
    () => bundledPacksQuery.data?.find((pack) => pack.id === selectedBundledPackId) ?? bundledPacksQuery.data?.[0] ?? null,
    [bundledPacksQuery.data, selectedBundledPackId]
  );
  const bundledCollectionOptions = useMemo(
    () => Array.from(new Set((bundledMapsQuery.data ?? []).map((map) => map.collection))).sort((a, b) => a.localeCompare(b)),
    [bundledMapsQuery.data]
  );
  const bundledCategoryOptions = useMemo(() => {
    const options = (bundledMapsQuery.data ?? [])
      .filter((map) => !bundledCollection || map.collection === bundledCollection)
      .reduce<Array<{ key: string; label: string }>>((items, map) => {
        if (items.some((item) => item.key === map.category_key)) return items;
        return [...items, { key: map.category_key, label: `${map.category_label} · ${map.group}` }];
      }, []);
    return options.sort((a, b) => a.label.localeCompare(b.label));
  }, [bundledCollection, bundledMapsQuery.data]);
  const filteredBundledMaps = useMemo(() => {
    const search = bundledSearch.trim().toLowerCase();
    return (bundledMapsQuery.data ?? [])
      .filter((map) => !bundledCollection || map.collection === bundledCollection)
      .filter((map) => !bundledCategory || map.category_key === bundledCategory)
      .filter((map) => {
        if (!search) return true;
        const haystack = [map.title, map.collection, map.group, map.category_label, ...map.tags].join(" ").toLowerCase();
        return haystack.includes(search);
      })
      .sort((a, b) => a.title.localeCompare(b.title));
  }, [bundledCategory, bundledCollection, bundledMapsQuery.data, bundledSearch]);
  const selectedBundledMap = useMemo(
    () => filteredBundledMaps.find((map) => map.id === selectedBundledMapId) ?? filteredBundledMaps[0] ?? null,
    [filteredBundledMaps, selectedBundledMapId]
  );
  const tokenEntities = entitiesQuery.data?.entities ?? [];
  const selectedMap = useMemo(
    () => mapsQuery.data?.find((map) => map.id === selectedMapId) ?? mapsQuery.data?.[0] ?? null,
    [mapsQuery.data, selectedMapId]
  );
  const activeSceneMap = sceneMapsQuery.data?.find((sceneMap) => sceneMap.is_active) ?? null;
  const selectedSceneMap = useMemo(
    () =>
      sceneMapsQuery.data?.find((sceneMap) => sceneMap.id === selectedSceneMapId) ??
      activeSceneMap ??
      sceneMapsQuery.data?.[0] ??
      null,
    [activeSceneMap, sceneMapsQuery.data, selectedSceneMapId]
  );
  const fogQuery = useQuery({
    queryKey: ["scene-map-fog", selectedSceneMap?.id],
    queryFn: () => api.sceneMapFog(selectedSceneMap!.id),
    enabled: Boolean(selectedSceneMap?.id)
  });
  const tokensQuery = useQuery({
    queryKey: ["scene-map-tokens", selectedSceneMap?.id],
    queryFn: () => api.sceneMapTokens(selectedSceneMap!.id),
    enabled: Boolean(selectedSceneMap?.id)
  });

  useEffect(() => {
    if (!selectedAssetId && mapAssets[0]) setSelectedAssetId(mapAssets[0].id);
  }, [mapAssets, selectedAssetId]);

  useEffect(() => {
    const packs = bundledPacksQuery.data ?? [];
    if (!packs.length) {
      setSelectedBundledPackId(null);
      return;
    }
    if (!selectedBundledPackId || !packs.some((pack) => pack.id === selectedBundledPackId)) {
      setSelectedBundledPackId(packs[0].id);
    }
  }, [bundledPacksQuery.data, selectedBundledPackId]);

  useEffect(() => {
    setBundledCollection("");
    setBundledCategory("");
    setBundledSearch("");
    setSelectedBundledMapId(null);
  }, [selectedBundledPackId]);

  useEffect(() => {
    if (bundledCategory && !bundledCategoryOptions.some((option) => option.key === bundledCategory)) {
      setBundledCategory("");
    }
  }, [bundledCategory, bundledCategoryOptions]);

  useEffect(() => {
    if (!filteredBundledMaps.length) {
      setSelectedBundledMapId(null);
      return;
    }
    if (!selectedBundledMapId || !filteredBundledMaps.some((map) => map.id === selectedBundledMapId)) {
      setSelectedBundledMapId(filteredBundledMaps[0].id);
    }
  }, [filteredBundledMaps, selectedBundledMapId]);

  useEffect(() => {
    if (selectedMap) {
      setGridEnabled(selectedMap.grid_enabled);
      setGridSize(selectedMap.grid_size_px);
      setGridOffsetX(selectedMap.grid_offset_x);
      setGridOffsetY(selectedMap.grid_offset_y);
      setGridColor(selectedMap.grid_color);
      setGridOpacity(selectedMap.grid_opacity);
    }
  }, [selectedMap]);

  useEffect(() => {
    if (selectedSceneMap) {
      setPlayerFitMode(selectedSceneMap.player_fit_mode);
      setPlayerGridVisible(selectedSceneMap.player_grid_visible);
      setSelectedMapId(selectedSceneMap.map_id);
    }
  }, [selectedSceneMap]);

  useEffect(() => {
    setLocalTokens(tokensQuery.data?.tokens ?? []);
  }, [tokensQuery.data]);

  useEffect(() => {
    if (!selectedTokenId && localTokens[0]) setSelectedTokenId(localTokens[0].id);
    if (selectedTokenId && !localTokens.some((token) => token.id === selectedTokenId)) {
      setSelectedTokenId(localTokens[0]?.id ?? null);
    }
  }, [localTokens, selectedTokenId]);

  const selectedToken = useMemo(
    () => localTokens.find((token) => token.id === selectedTokenId) ?? null,
    [localTokens, selectedTokenId]
  );

  useEffect(() => {
    if (!selectedToken) return;
    setTokenName(selectedToken.name);
    setTokenVisibility(selectedToken.visibility);
    setTokenLabelVisibility(selectedToken.label_visibility);
    setTokenShape(selectedToken.shape);
    setTokenColor(selectedToken.color);
    setTokenBorderColor(selectedToken.border_color);
    setTokenOpacity(selectedToken.opacity);
    setTokenWidth(selectedToken.width);
    setTokenHeight(selectedToken.height);
    setTokenRotation(selectedToken.rotation);
    setSelectedTokenAssetId(selectedToken.asset_id);
    setSelectedTokenEntityId(selectedToken.entity_id);
  }, [selectedToken]);

  function reconcileToken(token: SceneMapToken) {
    setLocalTokens((current) => {
      const index = current.findIndex((item) => item.id === token.id);
      if (index === -1) return [...current, token].sort((a, b) => a.z_index - b.z_index || a.name.localeCompare(b.name));
      const next = [...current];
      next[index] = token;
      return next.sort((a, b) => a.z_index - b.z_index || a.name.localeCompare(b.name));
    });
    queryClient.setQueryData(["scene-map-tokens", token.scene_map_id], (old: unknown) => {
      if (!old || typeof old !== "object") return old;
      const response = old as { tokens?: SceneMapToken[]; updated_at?: string };
      const tokens = response.tokens ?? [];
      const index = tokens.findIndex((item) => item.id === token.id);
      const next = index === -1 ? [...tokens, token] : tokens.map((item) => (item.id === token.id ? token : item));
      return { ...response, tokens: next.sort((a, b) => a.z_index - b.z_index || a.name.localeCompare(b.name)), updated_at: token.updated_at };
    });
  }

  function applyPlayerDisplayResult(state: PlayerDisplayState | null) {
    if (!state) return;
    queryClient.setQueryData(["player-display"], state);
    broadcastDisplayChange(state);
    void queryClient.invalidateQueries({ queryKey: ["player-display"] });
  }

  function tokenPayloadAt(point?: { x: number; y: number }) {
    return {
      name: tokenName || "Token",
      x: point?.x,
      y: point?.y,
      width: tokenWidth,
      height: tokenHeight,
      rotation: tokenRotation,
      visibility: tokenVisibility,
      label_visibility: tokenLabelVisibility,
      shape: tokenShape,
      color: tokenColor,
      border_color: tokenBorderColor,
      opacity: tokenOpacity,
      asset_id: selectedTokenAssetId || null,
      entity_id: selectedTokenEntityId || null
    };
  }

  const createMap = useMutation({
    mutationFn: () => {
      const asset = mapAssets.find((item) => item.id === selectedAssetId);
      return api.createMap(props.selectedCampaignId!, { asset_id: selectedAssetId!, name: asset?.name ?? "Map" });
    },
    onSuccess: (map) => {
      setSelectedMapId(map.id);
      void queryClient.invalidateQueries({ queryKey: ["maps", props.selectedCampaignId] });
    }
  });
  const addBundledMap = useMutation({
    mutationFn: () =>
      api.addBundledMapToCampaign(props.selectedCampaignId!, {
        pack_id: selectedBundledPack!.id,
        asset_id: selectedBundledMap!.id
      }),
    onSuccess: (result) => {
      setSelectedAssetId(result.asset.id);
      setSelectedMapId(result.map.id);
      setGridEnabled(result.map.grid_enabled);
      setGridSize(result.map.grid_size_px);
      setGridOffsetX(result.map.grid_offset_x);
      setGridOffsetY(result.map.grid_offset_y);
      setGridColor(result.map.grid_color);
      setGridOpacity(result.map.grid_opacity);
      void queryClient.invalidateQueries({ queryKey: ["assets", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["maps", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId] });
    }
  });
  const assignMap = useMutation({
    mutationFn: () =>
      api.assignSceneMap(props.selectedCampaignId!, props.selectedSceneId!, {
        map_id: selectedMap!.id,
        is_active: true,
        player_fit_mode: playerFitMode,
        player_grid_visible: playerGridVisible
      }),
    onSuccess: (sceneMap) => {
      setSelectedSceneMapId(sceneMap.id);
      void queryClient.invalidateQueries({ queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId] });
    }
  });
  const activateMap = useMutation({
    mutationFn: () => api.activateSceneMap(selectedSceneMap!.id),
    onSuccess: (sceneMap) => {
      setSelectedSceneMapId(sceneMap.id);
      void queryClient.invalidateQueries({ queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId] });
    }
  });
  const saveGrid = useMutation({
    mutationFn: () =>
      api.patchMapGrid(selectedMap!.id, {
        grid_enabled: gridEnabled,
        grid_size_px: gridSize,
        grid_offset_x: gridOffsetX,
        grid_offset_y: gridOffsetY,
        grid_color: gridColor,
        grid_opacity: gridOpacity
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["maps", props.selectedCampaignId] });
      void queryClient.invalidateQueries({ queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId] });
    }
  });
  const savePlayerSettings = useMutation({
    mutationFn: () => api.patchSceneMap(selectedSceneMap!.id, { player_fit_mode: playerFitMode, player_grid_visible: playerGridVisible }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["scene-maps", props.selectedCampaignId, props.selectedSceneId] })
  });
  const sendMap = useMutation({
    mutationFn: () => api.playerDisplayShowMap(selectedSceneMap?.id ?? null),
    onSuccess: (state) => {
      queryClient.setQueryData(["player-display"], state);
      broadcastDisplayChange(state);
      void queryClient.invalidateQueries({ queryKey: ["player-display"] });
    }
  });
  const enableFog = useMutation({
    mutationFn: () => api.enableSceneMapFog(selectedSceneMap!.id),
    onSuccess: (fog) => {
      setFogSaveStatus("saved");
      queryClient.setQueryData(["scene-map-fog", selectedSceneMap?.id], fog);
    },
    onError: () => setFogSaveStatus("error")
  });
  const applyFog = useMutation({
    mutationFn: (operations: FogOperation[]) => api.applySceneMapFogOperations(selectedSceneMap!.id, operations),
    onMutate: () => setFogSaveStatus("saving"),
    onSuccess: (result) => {
      setFogSaveStatus("saved");
      setDraftFog(null);
      dragRef.current = null;
      queryClient.setQueryData(["scene-map-fog", selectedSceneMap?.id], result.fog);
      if (result.player_display) {
        queryClient.setQueryData(["player-display"], result.player_display);
        broadcastDisplayChange(result.player_display);
      }
    },
    onError: () => setFogSaveStatus("error")
  });
  const createToken = useMutation({
    mutationFn: (point?: { x: number; y: number }) => api.createSceneMapToken(selectedSceneMap!.id, tokenPayloadAt(point)),
    onMutate: () => setTokenSaveStatus("saving"),
    onSuccess: (result) => {
      setTokenSaveStatus("saved");
      setPlacingToken(false);
      setSelectedTokenId(result.token.id);
      reconcileToken(result.token);
      applyPlayerDisplayResult(result.player_display);
    },
    onError: () => setTokenSaveStatus("error")
  });
  const patchToken = useMutation({
    mutationFn: ({ tokenId, payload }: { tokenId: string; payload: Partial<SceneMapToken> }) => api.patchToken(tokenId, payload),
    onMutate: () => setTokenSaveStatus("saving"),
    onSuccess: (result) => {
      setTokenSaveStatus("saved");
      reconcileToken(result.token);
      applyPlayerDisplayResult(result.player_display);
    },
    onError: () => setTokenSaveStatus("error")
  });
  const deleteToken = useMutation({
    mutationFn: (tokenId: string) => api.deleteToken(tokenId),
    onMutate: () => setTokenSaveStatus("saving"),
    onSuccess: (result) => {
      setTokenSaveStatus("saved");
      setLocalTokens((current) => current.filter((token) => token.id !== result.deleted_token_id));
      setSelectedTokenId((current) => (current === result.deleted_token_id ? null : current));
      void queryClient.invalidateQueries({ queryKey: ["scene-map-tokens", selectedSceneMap?.id] });
      applyPlayerDisplayResult(result.player_display);
    },
    onError: () => setTokenSaveStatus("error")
  });
  const previewPayload = useMemo(() => {
    if (!selectedSceneMap) return null;
    const payload = mapPayloadFromSceneMap(selectedSceneMap, fogQuery.data, localTokens);
    return {
      ...payload,
      fit_mode: playerFitMode,
      grid: {
        ...payload.grid,
        visible: gridEnabled,
        size_px: gridSize,
        offset_x: gridOffsetX,
        offset_y: gridOffsetY,
        color: gridColor,
        opacity: gridOpacity
      }
    };
  }, [fogQuery.data, gridColor, gridEnabled, gridOffsetX, gridOffsetY, gridOpacity, gridSize, localTokens, playerFitMode, selectedSceneMap]);

  if (!props.selectedCampaignId || !props.selectedSceneId || !selectedSceneBelongsToCampaign) {
    return <EmptyText text="Select a campaign and scene to manage maps." />;
  }
  const error =
    assetsQuery.error ??
    entitiesQuery.error ??
    mapsQuery.error ??
    sceneMapsQuery.error ??
    bundledPacksQuery.error ??
    bundledMapsQuery.error ??
    tokensQuery.error ??
    createMap.error ??
    addBundledMap.error ??
    assignMap.error ??
    activateMap.error ??
    saveGrid.error ??
    savePlayerSettings.error ??
    sendMap.error ??
    enableFog.error ??
    applyFog.error ??
    createToken.error ??
    patchToken.error ??
    deleteToken.error;

  function clampGridSize(value: number) {
    if (!Number.isFinite(value)) return 70;
    return Math.max(4, Math.min(500, Math.round(value)));
  }

  function adjustGridSize(delta: number) {
    setGridSize((value) => clampGridSize(value + delta));
  }

  function adjustGridOffset(dx: number, dy: number) {
    setGridOffsetX((value) => value + dx);
    setGridOffsetY((value) => value + dy);
  }

  function pointFromClient(element: HTMLElement, clientX: number, clientY: number): { x: number; y: number } | null {
    if (!previewPayload) return null;
    const bounds = element.getBoundingClientRect();
    if (bounds.width <= 0 || bounds.height <= 0) return null;
    return {
      x: Math.max(0, Math.min(previewPayload.width, ((clientX - bounds.left) / bounds.width) * previewPayload.width)),
      y: Math.max(0, Math.min(previewPayload.height, ((clientY - bounds.top) / bounds.height) * previewPayload.height))
    };
  }

  function pointFromEvent(event: PointerEvent<HTMLElement> | MouseEvent<HTMLElement>): { x: number; y: number } | null {
    return pointFromClient(event.currentTarget, event.clientX, event.clientY);
  }

  function operationFromDraft(draft: typeof draftFog): FogOperation | null {
    if (!draft) return null;
    if (draft.kind === "rect") {
      return {
        type: `${fogMode}_rect` as "reveal_rect" | "hide_rect",
        rect: {
          x: draft.start.x,
          y: draft.start.y,
          width: draft.current.x - draft.start.x,
          height: draft.current.y - draft.start.y
        }
      };
    }
    return {
      type: `${fogMode}_brush` as "reveal_brush" | "hide_brush",
      radius: brushRadius,
      points: draft.points
    };
  }

  function commitFogDraft(draft: typeof draftFog) {
    const operation = operationFromDraft(draft);
    if (operation) applyFog.mutate([operation]);
  }

  function handleFogPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (dragRef.current) return;
    if (!fogQuery.data?.enabled || applyFog.isPending) return;
    const point = pointFromEvent(event);
    if (!point) return;
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // The draft still works without capture; pointer-up will commit if it reaches the layer.
    }
    const draft = fogTool === "rect" ? { kind: "rect" as const, start: point, current: point } : { kind: "brush" as const, points: [point] };
    dragRef.current = draft;
    setDraftFog(draft);
    setFogSaveStatus("saved");
  }

  function handleFogPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    const point = pointFromEvent(event);
    if (!point) return;
    const draft =
      dragRef.current.kind === "rect"
        ? { ...dragRef.current, current: point }
        : { ...dragRef.current, points: [...dragRef.current.points, point].slice(-512) };
    dragRef.current = draft;
    setDraftFog(draft);
  }

  function handleFogPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    const draft = dragRef.current;
    dragRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be gone in browser automation or after cancelled drags.
    }
    commitFogDraft(draft);
  }

  function handleFogMouseDown(event: MouseEvent<HTMLDivElement>) {
    if (dragRef.current) return;
    if (!fogQuery.data?.enabled || applyFog.isPending) return;
    const point = pointFromEvent(event);
    if (!point) return;
    const draft = fogTool === "rect" ? { kind: "rect" as const, start: point, current: point } : { kind: "brush" as const, points: [point] };
    dragRef.current = draft;
    setDraftFog(draft);
    setFogSaveStatus("saved");
  }

  function handleFogMouseMove(event: MouseEvent<HTMLDivElement>) {
    if (!dragRef.current || event.buttons !== 1) return;
    const point = pointFromEvent(event);
    if (!point) return;
    const draft =
      dragRef.current.kind === "rect"
        ? { ...dragRef.current, current: point }
        : { ...dragRef.current, points: [...dragRef.current.points, point].slice(-512) };
    dragRef.current = draft;
    setDraftFog(draft);
  }

  function handleFogMouseUp() {
    if (!dragRef.current) return;
    const draft = dragRef.current;
    dragRef.current = null;
    commitFogDraft(draft);
  }

  function updateLocalToken(tokenId: string, patch: Partial<SceneMapToken>) {
    setLocalTokens((current) => current.map((token) => (token.id === tokenId ? { ...token, ...patch } : token)));
  }

  function handleTokenPointerDown(event: PointerEvent<HTMLElement>, token: SceneMapToken, kind: "move" | "resize") {
    if (!previewPayload || patchToken.isPending) return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedTokenId(token.id);
    const point = pointFromEvent(event);
    if (!point) return;
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best effort in browser automation.
    }
    tokenDragRef.current = { kind, tokenId: token.id, start: point, token };
    setTokenSaveStatus("saved");
  }

  function handleTokenPointerMove(event: PointerEvent<HTMLElement>) {
    const drag = tokenDragRef.current;
    if (!drag || !previewPayload) return;
    event.preventDefault();
    event.stopPropagation();
    const point = pointFromEvent(event);
    if (!point) return;
    const dx = point.x - drag.start.x;
    const dy = point.y - drag.start.y;
    if (drag.kind === "move") {
      updateLocalToken(drag.tokenId, {
        x: Math.max(0, Math.min(previewPayload.width, drag.token.x + dx)),
        y: Math.max(0, Math.min(previewPayload.height, drag.token.y + dy))
      });
      return;
    }
    updateLocalToken(drag.tokenId, {
      width: Math.max(8, Math.min(1000, drag.token.width + dx * 2)),
      height: Math.max(8, Math.min(1000, drag.token.height + dy * 2))
    });
  }

  function handleTokenPointerUp(event: PointerEvent<HTMLElement>) {
    const drag = tokenDragRef.current;
    if (!drag) return;
    event.preventDefault();
    event.stopPropagation();
    tokenDragRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be gone.
    }
    const token = localTokens.find((item) => item.id === drag.tokenId);
    if (!token) return;
    const payload =
      drag.kind === "move"
        ? { x: token.x, y: token.y }
        : { width: token.width, height: token.height };
    patchToken.mutate({ tokenId: token.id, payload });
  }

  function saveSelectedToken() {
    if (!selectedToken) return;
    patchToken.mutate({
      tokenId: selectedToken.id,
      payload: {
        name: tokenName,
        width: tokenWidth,
        height: tokenHeight,
        rotation: tokenRotation,
        visibility: tokenVisibility,
        label_visibility: tokenLabelVisibility,
        shape: tokenShape,
        color: tokenColor,
        border_color: tokenBorderColor,
        opacity: tokenOpacity,
        asset_id: selectedTokenAssetId,
        entity_id: selectedTokenEntityId
      }
    });
  }

  function reloadTokens() {
    setTokenSaveStatus("saved");
    void tokensQuery.refetch();
  }

  const tokenInteractionLayer =
    previewPayload && localTokens.length ? (
      <div className="token-interaction-layer" aria-label="Token interaction layer">
        {localTokens.map((token) => (
          <div
            key={token.id}
            className={`token-hitbox ${selectedTokenId === token.id ? "selected" : ""}`}
            style={{
              left: `${(token.x / previewPayload.width) * 100}%`,
              top: `${(token.y / previewPayload.height) * 100}%`,
              width: `${(token.width / previewPayload.width) * 100}%`,
              height: `${(token.height / previewPayload.height) * 100}%`,
              transform: `translate(-50%, -50%) rotate(${token.rotation}deg)`
            }}
            onPointerDown={(event) => handleTokenPointerDown(event, token, "move")}
            onPointerMove={handleTokenPointerMove}
            onPointerUp={handleTokenPointerUp}
          >
            <span
              className="token-resize-handle"
              onPointerDown={(event) => handleTokenPointerDown(event, token, "resize")}
              onPointerMove={handleTokenPointerMove}
              onPointerUp={handleTokenPointerUp}
            />
          </div>
        ))}
      </div>
    ) : null;

  const tokenPlacementLayer =
    placingToken && previewPayload ? (
      <div
        className="token-placement-layer"
        onPointerDown={(event) => {
          const point = pointFromEvent(event);
          if (point) createToken.mutate(point);
        }}
      />
    ) : null;

  const fogLayer =
    previewPayload && fogQuery.data?.enabled ? (
      <div
        className={`fog-interaction mode-${fogMode}`}
        onPointerDown={handleFogPointerDown}
        onPointerMove={handleFogPointerMove}
        onPointerUp={handleFogPointerUp}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
        onMouseDown={handleFogMouseDown}
        onMouseMove={handleFogMouseMove}
        onMouseUp={handleFogMouseUp}
      >
        {draftFog ? (
          <svg viewBox={`0 0 ${previewPayload.width} ${previewPayload.height}`} aria-hidden="true">
            {draftFog.kind === "rect" ? (
              <rect
                x={Math.min(draftFog.start.x, draftFog.current.x)}
                y={Math.min(draftFog.start.y, draftFog.current.y)}
                width={Math.abs(draftFog.current.x - draftFog.start.x)}
                height={Math.abs(draftFog.current.y - draftFog.start.y)}
              />
            ) : (
              <>
                <polyline points={draftFog.points.map((point) => `${point.x},${point.y}`).join(" ")} />
                {draftFog.points.map((point, index) => (
                  <circle key={`${point.x}-${point.y}-${index}`} cx={point.x} cy={point.y} r={brushRadius} />
                ))}
              </>
            )}
          </svg>
        ) : null}
      </div>
    ) : null;

  return (
    <div className="map-widget">
      <div className="map-controls">
        <label>
          <span>Map image asset</span>
          <select
            aria-label="Map image asset"
            value={selectedAssetId ?? ""}
            onChange={(event) => setSelectedAssetId(event.target.value || null)}
          >
            <option value="">No map image assets</option>
            {mapAssets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name} · {asset.visibility}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => createMap.mutate()} disabled={!selectedAssetId || createMap.isPending}>
          Create map
        </button>
        <label>
          <span>Campaign maps</span>
          <select
            aria-label="Campaign maps"
            value={selectedMap?.id ?? ""}
            onChange={(event) => setSelectedMapId(event.target.value || null)}
          >
            <option value="">No maps</option>
            {(mapsQuery.data ?? []).map((map) => (
              <option key={map.id} value={map.id}>
                {map.name}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => assignMap.mutate()} disabled={!selectedMap || assignMap.isPending}>
          Assign active
        </button>
        <label>
          <span>Scene maps</span>
          <select
            aria-label="Scene maps"
            value={selectedSceneMap?.id ?? ""}
            onChange={(event) => setSelectedSceneMapId(event.target.value || null)}
          >
            <option value="">No scene maps</option>
            {(sceneMapsQuery.data ?? []).map((sceneMap) => (
              <option key={sceneMap.id} value={sceneMap.id}>
                {sceneMap.is_active ? "Active · " : ""}
                {sceneMap.map.name}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => activateMap.mutate()} disabled={!selectedSceneMap || selectedSceneMap.is_active || activateMap.isPending}>
          Activate scene map
        </button>
      </div>
      <div className="bundled-map-browser">
        <div className="fog-header">
          <strong>Bundled maps</strong>
          <span className="muted">{selectedBundledPack ? `${selectedBundledPack.asset_count} maps` : "No bundled packs"}</span>
        </div>
        <div className="bundled-map-grid">
          <label>
            <span>Pack</span>
            <select
              aria-label="Bundled asset pack"
              value={selectedBundledPack?.id ?? ""}
              onChange={(event) => setSelectedBundledPackId(event.target.value || null)}
            >
              <option value="">No bundled packs</option>
              {(bundledPacksQuery.data ?? []).map((pack) => (
                <option key={pack.id} value={pack.id}>
                  {pack.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Collection</span>
            <select value={bundledCollection} onChange={(event) => setBundledCollection(event.target.value)} aria-label="Bundled collection">
              <option value="">All collections</option>
              {bundledCollectionOptions.map((collection) => (
                <option key={collection} value={collection}>
                  {collection}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Category</span>
            <select value={bundledCategory} onChange={(event) => setBundledCategory(event.target.value)} aria-label="Bundled category">
              <option value="">All categories</option>
              {bundledCategoryOptions.map((category) => (
                <option key={category.key} value={category.key}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Search</span>
            <span className="input-with-icon">
              <Search size={14} />
              <input
                aria-label="Bundled map search"
                value={bundledSearch}
                onChange={(event) => setBundledSearch(event.target.value)}
                placeholder="name, tag, category"
              />
            </span>
          </label>
          <label className="bundled-map-select">
            <span>Map</span>
            <select
              aria-label="Bundled map"
              value={selectedBundledMap?.id ?? ""}
              onChange={(event) => setSelectedBundledMapId(event.target.value || null)}
            >
              <option value="">No bundled maps</option>
              {filteredBundledMaps.map((map) => (
                <option key={map.id} value={map.id}>
                  {map.title} · {map.grid.px_per_cell}px
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => addBundledMap.mutate()}
            disabled={!selectedBundledPack || !selectedBundledMap || addBundledMap.isPending}
          >
            <Plus size={14} /> Add to campaign
          </button>
        </div>
        {selectedBundledMap ? (
          <p className="muted">
            {selectedBundledMap.collection} · {selectedBundledMap.category_label} · {selectedBundledMap.width}x{selectedBundledMap.height}
          </p>
        ) : null}
      </div>
      <MapRenderer
        payload={previewPayload}
        renderMode="gm"
        interactionLayer={
          <>
            {fogLayer}
            {tokenInteractionLayer}
            {tokenPlacementLayer}
          </>
        }
      />
      <div className="fog-editor">
        <div className="fog-header">
          <strong>Fog</strong>
          <span className={`fog-save-status status-${fogSaveStatus}`}>
            {fogSaveStatus === "saved" ? "Saved" : fogSaveStatus === "saving" ? "Saving" : "Unsaved"}
          </span>
        </div>
        <div className="fog-actions">
          <button onClick={() => enableFog.mutate()} disabled={!selectedSceneMap || enableFog.isPending}>
            <EyeOff size={14} /> Enable hidden fog
          </button>
          <select aria-label="Fog tool" value={fogTool} onChange={(event) => setFogTool(event.target.value as "rect" | "brush")}>
            <option value="rect">Rectangle</option>
            <option value="brush">Brush</option>
          </select>
          <select aria-label="Fog mode" value={fogMode} onChange={(event) => setFogMode(event.target.value as "reveal" | "hide")}>
            <option value="reveal">Reveal</option>
            <option value="hide">Hide</option>
          </select>
          <label>
            <span>Brush</span>
            <input
              aria-label="Brush radius"
              type="number"
              min={1}
              max={500}
              value={brushRadius}
              onChange={(event) => setBrushRadius(Number(event.target.value))}
            />
          </label>
        </div>
        <div className="fog-actions">
          <button
            onClick={() => applyFog.mutate([{ type: "reveal_all" }])}
            disabled={!fogQuery.data?.enabled || applyFog.isPending}
          >
            <Eye size={14} /> Reveal all
          </button>
          <button
            onClick={() => applyFog.mutate([{ type: "hide_all" }])}
            disabled={!fogQuery.data?.enabled || applyFog.isPending}
          >
            <EyeOff size={14} /> Hide all
          </button>
          <button onClick={() => commitFogDraft(draftFog)} disabled={!draftFog || applyFog.isPending}>
            <Paintbrush size={14} /> Retry save
          </button>
          <button
            onClick={() => {
              setDraftFog(null);
              dragRef.current = null;
              setFogSaveStatus("saved");
              void fogQuery.refetch();
            }}
            disabled={!selectedSceneMap}
          >
            <RotateCcw size={14} /> Reload fog
          </button>
        </div>
        <p className="muted">
          {fogQuery.data?.enabled
            ? `Revision ${fogQuery.data.revision} · draw on the map to ${fogMode}.`
            : "Enable fog to start from a fully hidden player map."}
        </p>
      </div>
      <div className="token-editor">
        <div className="fog-header">
          <strong>Tokens</strong>
          <span className={`fog-save-status status-${tokenSaveStatus}`}>
            {tokenSaveStatus === "saved" ? "Saved" : tokenSaveStatus === "saving" ? "Saving" : "Unsaved"}
          </span>
        </div>
        <div className="token-actions">
          <button onClick={() => createToken.mutate(undefined)} disabled={!selectedSceneMap || createToken.isPending}>
            <Plus size={14} /> Create center
          </button>
          <button onClick={() => setPlacingToken((value) => !value)} disabled={!selectedSceneMap || createToken.isPending}>
            <Map size={14} /> {placingToken ? "Click map..." : "Create by click"}
          </button>
          <button onClick={reloadTokens} disabled={!selectedSceneMap || tokensQuery.isFetching}>
            <RotateCcw size={14} /> Reload tokens
          </button>
          <button onClick={() => selectedToken && deleteToken.mutate(selectedToken.id)} disabled={!selectedToken || deleteToken.isPending}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
        <div className="token-grid">
          <label>
            <span>Token</span>
            <select value={selectedTokenId ?? ""} onChange={(event) => setSelectedTokenId(event.target.value || null)} aria-label="Token">
              <option value="">No tokens</option>
              {localTokens.map((token) => (
                <option key={token.id} value={token.id}>
                  {token.name} · {token.visibility}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Name</span>
            <input value={tokenName} onChange={(event) => setTokenName(event.target.value)} aria-label="Token name" />
          </label>
          <label>
            <span>Visibility</span>
            <select
              value={tokenVisibility}
              onChange={(event) => setTokenVisibility(event.target.value as SceneMapToken["visibility"])}
              aria-label="Token visibility"
            >
              <option value="gm_only">GM only</option>
              <option value="player_visible">Player visible</option>
              <option value="hidden_until_revealed">Hidden until revealed</option>
            </select>
          </label>
          <label>
            <span>Label</span>
            <select
              value={tokenLabelVisibility}
              onChange={(event) => setTokenLabelVisibility(event.target.value as SceneMapToken["label_visibility"])}
              aria-label="Token label visibility"
            >
              <option value="gm_only">GM only</option>
              <option value="player_visible">Player visible</option>
              <option value="hidden">Hidden</option>
            </select>
          </label>
          <label>
            <span>Shape</span>
            <select value={tokenShape} onChange={(event) => setTokenShape(event.target.value as SceneMapToken["shape"])} aria-label="Token shape">
              <option value="circle">Circle</option>
              <option value="square">Square</option>
              <option value="marker">Marker</option>
              <option value="portrait">Portrait</option>
            </select>
          </label>
          <label>
            <span>Portrait</span>
            <select
              value={selectedTokenAssetId ?? ""}
              onChange={(event) => setSelectedTokenAssetId(event.target.value || null)}
              aria-label="Token portrait asset"
            >
              <option value="">No portrait</option>
              {tokenAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.name} · {asset.visibility}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Entity</span>
            <select
              value={selectedTokenEntityId ?? ""}
              onChange={(event) => setSelectedTokenEntityId(event.target.value || null)}
              aria-label="Token entity"
            >
              <option value="">No entity</option>
              {tokenEntities.map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name} · {entity.kind}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>W</span>
            <input type="number" min={8} max={1000} value={tokenWidth} onChange={(event) => setTokenWidth(Number(event.target.value))} aria-label="Token width" />
          </label>
          <label>
            <span>H</span>
            <input type="number" min={8} max={1000} value={tokenHeight} onChange={(event) => setTokenHeight(Number(event.target.value))} aria-label="Token height" />
          </label>
          <label>
            <span>Rotate</span>
            <input type="number" value={tokenRotation} onChange={(event) => setTokenRotation(Number(event.target.value))} aria-label="Token rotation" />
          </label>
          <label>
            <span>Color</span>
            <input value={tokenColor} onChange={(event) => setTokenColor(event.target.value)} aria-label="Token color" />
          </label>
          <label>
            <span>Border</span>
            <input value={tokenBorderColor} onChange={(event) => setTokenBorderColor(event.target.value)} aria-label="Token border color" />
          </label>
          <label>
            <span>Opacity</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={tokenOpacity}
              onChange={(event) => setTokenOpacity(Number(event.target.value))}
              aria-label="Token opacity"
            />
          </label>
        </div>
        <div className="token-actions">
          <button onClick={saveSelectedToken} disabled={!selectedToken || patchToken.isPending}>
            Save token
          </button>
          {selectedToken ? (
            <span className="muted">
              Center {Math.round(selectedToken.x)}, {Math.round(selectedToken.y)} · drag token to move, corner to resize.
            </span>
          ) : (
            <span className="muted">Create a token or select one from the map.</span>
          )}
        </div>
      </div>
      <div className="grid-editor">
        <label className="checkbox-row">
          <input type="checkbox" checked={gridEnabled} onChange={(event) => setGridEnabled(event.target.checked)} /> GM grid
        </label>
        <label>
          <span>Size</span>
          <input
            aria-label="Grid size"
            type="number"
            min={4}
            max={500}
            value={gridSize}
            onChange={(event) => setGridSize(clampGridSize(Number(event.target.value)))}
          />
        </label>
        <div className="grid-stepper" aria-label="Grid size controls">
          <button type="button" aria-label="Decrease grid size by 5" onClick={() => adjustGridSize(-5)}>
            <Minus size={14} /> 5
          </button>
          <button type="button" aria-label="Decrease grid size by 1" onClick={() => adjustGridSize(-1)}>
            <Minus size={14} /> 1
          </button>
          <button type="button" aria-label="Increase grid size by 1" onClick={() => adjustGridSize(1)}>
            <Plus size={14} /> 1
          </button>
          <button type="button" aria-label="Increase grid size by 5" onClick={() => adjustGridSize(5)}>
            <Plus size={14} /> 5
          </button>
        </div>
        <label>
          <span>X</span>
          <input aria-label="Grid offset X" type="number" value={gridOffsetX} onChange={(event) => setGridOffsetX(Number(event.target.value))} />
        </label>
        <label>
          <span>Y</span>
          <input aria-label="Grid offset Y" type="number" value={gridOffsetY} onChange={(event) => setGridOffsetY(Number(event.target.value))} />
        </label>
        <div className="grid-nudge" aria-label="Grid nudge 1px">
          <button type="button" aria-label="Nudge grid up 1px" onClick={() => adjustGridOffset(0, -1)}>
            <ArrowUp size={14} />
          </button>
          <button type="button" aria-label="Nudge grid left 1px" onClick={() => adjustGridOffset(-1, 0)}>
            <ArrowLeft size={14} />
          </button>
          <button type="button" aria-label="Nudge grid right 1px" onClick={() => adjustGridOffset(1, 0)}>
            <ArrowRight size={14} />
          </button>
          <button type="button" aria-label="Nudge grid down 1px" onClick={() => adjustGridOffset(0, 1)}>
            <ArrowDown size={14} />
          </button>
        </div>
        <div className="grid-nudge" aria-label="Grid nudge 10px">
          <button type="button" aria-label="Nudge grid up 10px" onClick={() => adjustGridOffset(0, -10)}>
            <ArrowUp size={14} />
          </button>
          <button type="button" aria-label="Nudge grid left 10px" onClick={() => adjustGridOffset(-10, 0)}>
            <ArrowLeft size={14} />
          </button>
          <button type="button" aria-label="Nudge grid right 10px" onClick={() => adjustGridOffset(10, 0)}>
            <ArrowRight size={14} />
          </button>
          <button type="button" aria-label="Nudge grid down 10px" onClick={() => adjustGridOffset(0, 10)}>
            <ArrowDown size={14} />
          </button>
        </div>
        <label>
          <span>Color</span>
          <input aria-label="Grid color" value={gridColor} onChange={(event) => setGridColor(event.target.value)} />
        </label>
        <label>
          <span>Opacity</span>
          <input
            aria-label="Grid opacity"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={gridOpacity}
            onChange={(event) => setGridOpacity(Number(event.target.value))}
          />
        </label>
        <button onClick={() => saveGrid.mutate()} disabled={!selectedMap || saveGrid.isPending}>
          Save grid
        </button>
      </div>
      <div className="asset-send">
        <select value={playerFitMode} onChange={(event) => setPlayerFitMode(event.target.value as DisplayFitMode)} aria-label="Map fit mode">
          {fitModes.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <label className="checkbox-row">
          <input type="checkbox" checked={playerGridVisible} onChange={(event) => setPlayerGridVisible(event.target.checked)} /> Player grid
        </label>
        <button onClick={() => savePlayerSettings.mutate()} disabled={!selectedSceneMap || savePlayerSettings.isPending}>
          Save player
        </button>
        <button onClick={() => sendMap.mutate()} disabled={!selectedSceneMap || sendMap.isPending}>
          <Send size={14} /> Send map
        </button>
      </div>
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

type DisplayConnectionStatus = "unopened" | "connected" | "stale" | "disconnected";

function useDisplayHeartbeat() {
  const [heartbeat, setHeartbeat] = useState<{ displayWindowId: string; sentAt: string; revision: number } | null>(null);
  useEffect(() => {
    function accept(message: ReturnType<typeof parseTransportData>) {
      if (!message || message.type !== "heartbeat") return;
      setHeartbeat({
        displayWindowId: message.displayWindowId,
        sentAt: message.sentAt,
        revision: message.revision
      });
    }

    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(PLAYER_DISPLAY_CHANNEL);
    if (channel) channel.onmessage = (event) => accept(parseTransportData(event.data));
    const onMessage = (event: MessageEvent) => accept(parseWindowMessage(event, window.location.origin));
    window.addEventListener("message", onMessage);
    return () => {
      channel?.close();
      window.removeEventListener("message", onMessage);
    };
  }, []);
  return heartbeat;
}

export function PlayerDisplayWidget() {
  const queryClient = useQueryClient();
  const displayQuery = useQuery({
    queryKey: ["player-display"],
    queryFn: api.playerDisplay,
    refetchInterval: 2_000,
    retry: false
  });
  const heartbeat = useDisplayHeartbeat();
  const [now, setNow] = useState(() => Date.now());
  const [opened, setOpened] = useState(false);
  const [playerWindow, setPlayerWindow] = useState<Window | null>(null);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  const status = useMemo<DisplayConnectionStatus>(() => {
    if (heartbeat) {
      const age = now - Date.parse(heartbeat.sentAt);
      if (age <= 3_000) return "connected";
      return "stale";
    }
    const knownWindowClosed = opened && playerWindow?.closed;
    if (knownWindowClosed) return "disconnected";
    return opened ? "disconnected" : "unopened";
  }, [heartbeat, now, opened, playerWindow]);

  function broadcast(state: PlayerDisplayState) {
    broadcastDisplayChange(state, playerWindow);
  }

  function mutateDisplay(action: () => Promise<PlayerDisplayState>) {
    return {
      mutationFn: action,
      onSuccess: (state: PlayerDisplayState) => {
        queryClient.setQueryData(["player-display"], state);
        broadcast(state);
        void queryClient.invalidateQueries({ queryKey: ["player-display"] });
      }
    };
  }

  const blackout = useMutation(mutateDisplay(api.playerDisplayBlackout));
  const intermission = useMutation(mutateDisplay(api.playerDisplayIntermission));
  const sceneTitle = useMutation(mutateDisplay(() => api.playerDisplayShowSceneTitle()));
  const identify = useMutation(mutateDisplay(api.playerDisplayIdentify));

  function openPlayer() {
    const url = new URL("/player", window.location.href);
    const openedWindow = window.open(url.toString(), "myroll-player-display");
    if (openedWindow) {
      setOpened(true);
      setPlayerWindow(openedWindow);
      openedWindow.focus();
      if (displayQuery.data) broadcast(displayQuery.data);
    }
  }

  const error = blackout.error ?? intermission.error ?? sceneTitle.error ?? identify.error ?? displayQuery.error;
  const heartbeatAge = heartbeat ? Math.max(0, Math.round((now - Date.parse(heartbeat.sentAt)) / 1000)) : null;

  return (
    <div className="stack">
      <div className="status-grid">
        <InfoRow label="Mode" value={displayQuery.data?.mode ?? "unknown"} />
        <InfoRow label="Title" value={displayQuery.data?.title ?? "None"} />
        <InfoRow label="Status" value={status} />
        <InfoRow label="Heartbeat" value={heartbeatAge === null ? "None" : `${heartbeatAge}s ago`} />
      </div>
      <div className="button-grid">
        <button onClick={openPlayer}>
          <ExternalLink size={14} /> Open / Reconnect
        </button>
        <button onClick={() => identify.mutate()} disabled={!displayQuery.data}>
          <Radio size={14} /> Identify
        </button>
        <button onClick={() => blackout.mutate()}>Blackout</button>
        <button onClick={() => intermission.mutate()}>Intermission</button>
        <button className="wide-button" onClick={() => sceneTitle.mutate()}>
          Show active scene
        </button>
      </div>
      {error ? <ErrorLine error={error} /> : null}
    </div>
  );
}

function PlaceholderWidget({ kind }: { kind: string }) {
  const Icon = kind === "notes" ? FileText : kind === "party_tracker" ? Users : kind === "combat_tracker" ? Swords : kind === "dice_roller" ? Dices : Map;
  return (
    <div className="placeholder">
      <Icon size={26} />
      <strong>Not wired yet</strong>
      <span>{placeholderCopy[kind] ?? "Future widget placeholder."}</span>
    </div>
  );
}

function EntityList<T extends { id: string }>({
  items,
  activeId,
  selectedId,
  label,
  onSelect
}: {
  items: T[];
  activeId?: string | null;
  selectedId?: string | null;
  label: (item: T) => string;
  onSelect: (item: T) => void;
}) {
  if (items.length === 0) return <EmptyText text="Nothing here yet." />;
  return (
    <div className="entity-list">
      {items.map((item) => (
        <button
          key={item.id}
          className={item.id === activeId ? "entity active" : item.id === selectedId ? "entity selected" : "entity"}
          onClick={() => onSelect(item)}
        >
          <span>{label(item)}</span>
          {item.id === activeId ? <Activity size={14} /> : null}
        </button>
      ))}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyText({ text }: { text: string }) {
  return <p className="muted-block">{text}</p>;
}

function ErrorLine({ error }: { error: unknown }) {
  return (
    <div className="error-line">
      <AlertTriangle size={14} />
      {errorMessage(error)}
    </div>
  );
}

function fallbackWidgets(): WorkspaceWidget[] {
  const now = new Date().toISOString();
  return [
    {
      id: "fallback-status",
      scope_type: "global",
      scope_id: null,
      kind: "backend_status",
      title: "Backend Status",
      x: 24,
      y: 72,
      width: 340,
      height: 230,
      z_index: 1,
      locked: false,
      minimized: false,
      config: {},
      created_at: now,
      updated_at: now
    }
  ];
}
