import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { WifiOff } from "lucide-react";

import type { MapRenderPayload, PublicMapToken } from "../types";

function gridLinePositions(length: number, size: number, offset: number): number[] {
  if (!Number.isFinite(length) || !Number.isFinite(size) || size <= 0) return [];
  const positions: number[] = [];
  let start = offset % size;
  if (start < 0) start += size;
  for (let position = start; position <= length; position += size) positions.push(position);
  return positions.slice(0, 1000);
}

function mapStageSize(
  payload: MapRenderPayload,
  containerSize: { width: number; height: number } | null
): { width: number; height: number } {
  const fallback = { width: payload.width, height: payload.height };
  if (!containerSize || containerSize.width <= 0 || containerSize.height <= 0) return fallback;
  if (payload.fit_mode === "stretch") {
    return { width: containerSize.width, height: containerSize.height };
  }
  const scaleX = containerSize.width / payload.width;
  const scaleY = containerSize.height / payload.height;
  const scale =
    payload.fit_mode === "fill"
      ? Math.max(scaleX, scaleY)
      : payload.fit_mode === "actual_size"
        ? Math.min(1, scaleX, scaleY)
        : Math.min(scaleX, scaleY);
  return {
    width: payload.width * scale,
    height: payload.height * scale
  };
}

function drawFoggedMap(canvas: HTMLCanvasElement, payload: MapRenderPayload, renderMode: "gm" | "player", onFailure: () => void) {
  const context = canvas.getContext("2d");
  if (!context) return;
  const ctx = context;
  const image = new Image();
  const mask = new Image();
  image.crossOrigin = "anonymous";
  mask.crossOrigin = "anonymous";
  let imageReady = false;
  let maskReady = false;

  function maybeDraw() {
    if (!imageReady || !maskReady) return;
    canvas.width = payload.width;
    canvas.height = payload.height;
    ctx.clearRect(0, 0, payload.width, payload.height);
    ctx.drawImage(image, 0, 0, payload.width, payload.height);

    const maskCanvas = document.createElement("canvas");
    maskCanvas.width = payload.width;
    maskCanvas.height = payload.height;
    const maskContext = maskCanvas.getContext("2d");
    if (!maskContext) return;
    maskContext.drawImage(mask, 0, 0, payload.width, payload.height);
    const maskData = maskContext.getImageData(0, 0, payload.width, payload.height);

    if (renderMode === "player") {
      for (let index = 0; index < maskData.data.length; index += 4) {
        const alpha = maskData.data[index];
        maskData.data[index] = 255;
        maskData.data[index + 1] = 255;
        maskData.data[index + 2] = 255;
        maskData.data[index + 3] = alpha;
      }
      maskContext.putImageData(maskData, 0, 0);
      ctx.globalCompositeOperation = "destination-in";
      ctx.drawImage(maskCanvas, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      if (payload.grid.visible) {
        const gridCanvas = document.createElement("canvas");
        gridCanvas.width = payload.width;
        gridCanvas.height = payload.height;
        const gridContext = gridCanvas.getContext("2d");
        if (gridContext) {
          gridContext.strokeStyle = payload.grid.color;
          gridContext.globalAlpha = payload.grid.opacity;
          gridContext.lineWidth = 1;
          for (const x of gridLinePositions(payload.width, payload.grid.size_px, payload.grid.offset_x)) {
            gridContext.beginPath();
            gridContext.moveTo(x, 0);
            gridContext.lineTo(x, payload.height);
            gridContext.stroke();
          }
          for (const y of gridLinePositions(payload.height, payload.grid.size_px, payload.grid.offset_y)) {
            gridContext.beginPath();
            gridContext.moveTo(0, y);
            gridContext.lineTo(payload.width, y);
            gridContext.stroke();
          }
          gridContext.globalAlpha = 1;
          gridContext.globalCompositeOperation = "destination-in";
          gridContext.drawImage(maskCanvas, 0, 0);
          gridContext.globalCompositeOperation = "source-over";
          ctx.drawImage(gridCanvas, 0, 0);
        }
      }
      return;
    }

    for (let index = 0; index < maskData.data.length; index += 4) {
      const hiddenAlpha = 255 - maskData.data[index];
      maskData.data[index] = 5;
      maskData.data[index + 1] = 8;
      maskData.data[index + 2] = 12;
      maskData.data[index + 3] = Math.round(hiddenAlpha * 0.68);
    }
    maskContext.putImageData(maskData, 0, 0);
    ctx.drawImage(maskCanvas, 0, 0);
  }

  image.onload = () => {
    imageReady = true;
    maybeDraw();
  };
  mask.onload = () => {
    maskReady = true;
    maybeDraw();
  };
  image.onerror = onFailure;
  mask.onerror = onFailure;
  image.src = payload.asset_url;
  mask.src = payload.fog?.mask_url ?? "";
}

function FogCanvas({
  payload,
  renderMode,
  onFailure
}: {
  payload: MapRenderPayload;
  renderMode: "gm" | "player";
  onFailure: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    if (!payload.fog?.enabled || !canvasRef.current) return;
    try {
      drawFoggedMap(canvasRef.current, payload, renderMode, onFailure);
    } catch {
      onFailure();
    }
  }, [onFailure, payload, renderMode]);
  return <canvas ref={canvasRef} className="map-canvas" aria-label={payload.title} width={payload.width} height={payload.height} />;
}

function TokenMarker({ token, mapWidth, mapHeight }: { token: PublicMapToken; mapWidth: number; mapHeight: number }) {
  const [assetFailed, setAssetFailed] = useState(false);
  useEffect(() => setAssetFailed(false), [token.asset_url]);
  const left = `${(token.x / mapWidth) * 100}%`;
  const top = `${(token.y / mapHeight) * 100}%`;
  const width = `${(token.width / mapWidth) * 100}%`;
  const height = `${(token.height / mapHeight) * 100}%`;
  const shapeClass = token.style.shape === "portrait" && token.asset_url && !assetFailed ? "portrait" : token.style.shape;
  return (
    <div
      className={`map-token shape-${shapeClass}`}
      style={{
        left,
        top,
        width,
        height,
        transform: `translate(-50%, -50%) rotate(${token.rotation}deg)`,
        opacity: token.style.opacity,
        color: token.style.color,
        borderColor: token.style.border_color,
        backgroundColor: token.style.shape === "portrait" ? token.style.color : token.style.color
      }}
      data-token-id={token.id}
    >
      {token.style.shape === "portrait" && token.asset_url && !assetFailed ? (
        <div className="map-token-portrait-frame">
          <img src={token.asset_url} alt={token.name ?? "Token portrait"} onError={() => setAssetFailed(true)} />
        </div>
      ) : null}
      {token.name ? <span>{token.name}</span> : null}
    </div>
  );
}

function TokenLayer({ payload }: { payload: MapRenderPayload }) {
  const tokens = payload.tokens ?? [];
  if (!tokens.length) return null;
  return (
    <div className="map-token-layer" aria-label="Map tokens">
      {tokens.map((token) => (
        <TokenMarker key={token.id} token={token} mapWidth={payload.width} mapHeight={payload.height} />
      ))}
    </div>
  );
}

export function MapRenderer({
  payload,
  reconnecting = false,
  renderMode = "player",
  interactionLayer
}: {
  payload: MapRenderPayload | null;
  reconnecting?: boolean;
  renderMode?: "gm" | "player";
  interactionLayer?: ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [payload?.asset_url, payload?.fog?.mask_url, renderMode]);
  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const updateSize = (rect: DOMRectReadOnly | DOMRect) => {
      setContainerSize({ width: rect.width, height: rect.height });
    };
    updateSize(element.getBoundingClientRect());
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) updateSize(entry.contentRect);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  if (!payload || !payload.width || !payload.height || failed) {
    return (
      <div className="map-unavailable">
        <WifiOff size={28} />
        <strong>Map unavailable</strong>
        <span>Reconnecting to local map asset.</span>
      </div>
    );
  }
  const usesFog = Boolean(payload.fog?.enabled && payload.fog.mask_url);
  const showSvgGrid = payload.grid.visible && !(renderMode === "player" && usesFog);
  const xLines = showSvgGrid ? gridLinePositions(payload.width, payload.grid.size_px, payload.grid.offset_x) : [];
  const yLines = showSvgGrid ? gridLinePositions(payload.height, payload.grid.size_px, payload.grid.offset_y) : [];
  const aspectRatio = `${payload.width} / ${payload.height}`;
  const stageSize = mapStageSize(payload, containerSize);
  const stageStyle: CSSProperties = {
    aspectRatio,
    width: stageSize.width,
    height: stageSize.height
  };
  return (
    <div ref={containerRef} className={`map-renderer fit-${payload.fit_mode} render-${renderMode}`} style={renderMode === "gm" ? { aspectRatio } : undefined}>
      <div className="map-stage" style={stageStyle}>
        {usesFog ? (
          <FogCanvas payload={payload} renderMode={renderMode} onFailure={() => setFailed(true)} />
        ) : (
          <img src={payload.asset_url} alt={payload.title} onError={() => setFailed(true)} />
        )}
        {showSvgGrid ? (
          <svg className="map-grid" viewBox={`0 0 ${payload.width} ${payload.height}`} aria-hidden="true">
            <g stroke={payload.grid.color} strokeOpacity={payload.grid.opacity} strokeWidth={1}>
              {xLines.map((x) => (
                <line key={`x-${x}`} x1={x} y1={0} x2={x} y2={payload.height} />
              ))}
              {yLines.map((y) => (
                <line key={`y-${y}`} x1={0} y1={y} x2={payload.width} y2={y} />
              ))}
            </g>
          </svg>
        ) : null}
        <TokenLayer payload={payload} />
        {interactionLayer}
      </div>
      {reconnecting ? <div className="player-reconnecting">Reconnecting</div> : null}
    </div>
  );
}
