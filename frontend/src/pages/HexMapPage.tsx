import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type { HexMap, HexTerrain, HexTile } from "../api/types";

// --- hex geometry (pointy-top, axial coords) — see redblobgames.com/grids/hexagons
const SIZE = 30; // hex circumradius in SVG units
const SQRT3 = Math.sqrt(3);

function axialToPixel(q: number, r: number): { x: number; y: number } {
  return { x: SIZE * SQRT3 * (q + r / 2), y: SIZE * (3 / 2) * r };
}

function hexPoints(cx: number, cy: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 180) * (60 * i - 30);
    pts.push(`${(cx + SIZE * Math.cos(angle)).toFixed(2)},${(cy + SIZE * Math.sin(angle)).toFixed(2)}`);
  }
  return pts.join(" ");
}

// Axial hex distance — the foundation for future ship movement/range.
function hexDistance(aq: number, ar: number, bq: number, br: number): number {
  return (Math.abs(aq - bq) + Math.abs(ar - br) + Math.abs(aq + ar - bq - br)) / 2;
}

interface TerrainMeta {
  label: string;
  fill: string;
  marker?: string; // marker dot colour for non-empty sectors
}

const TERRAIN: Record<HexTerrain, TerrainMeta> = {
  deep_space: { label: "Deep space", fill: "#1c2136" },
  asteroid_field: { label: "Asteroid field", fill: "#3a3f52", marker: "#a8b0c0" },
  nebula: { label: "Nebula", fill: "#3a2b57", marker: "#b18cf0" },
  ice_field: { label: "Ice field", fill: "#233f4d", marker: "#79cfe8" },
  planet: { label: "Planet", fill: "#22432f", marker: "#5fce8a" },
  star_system: { label: "Star system", fill: "#4a3a1a", marker: "#f0b64a" },
};

const TERRAIN_ORDER: HexTerrain[] = [
  "deep_space",
  "asteroid_field",
  "nebula",
  "ice_field",
  "planet",
  "star_system",
];

export default function HexMapPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const map = useQuery({ queryKey: ["hex-map"], queryFn: api.getHexMap });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [regenOpen, setRegenOpen] = useState(false);

  const selected = map.data?.tiles.find((t) => t.id === selectedId) ?? null;

  return (
    <div>
      <PageHeader
        title="Sector Map"
        subtitle="The campaign's hex grid. Sectors will host stations and ship movements."
        action={
          isAdmin && (
            <button className="btn-primary" onClick={() => setRegenOpen(true)}>
              Regenerate grid
            </button>
          )
        }
      />

      {map.isLoading ? (
        <Spinner label="Loading sector map…" />
      ) : !map.data || !map.data.tiles.length ? (
        <EmptyState
          title="No sectors yet"
          hint={isAdmin ? "Regenerate the grid to lay out the campaign map." : ""}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <HexGrid map={map.data} selectedId={selectedId} onSelect={setSelectedId} />
          <SectorPanel tile={selected} isAdmin={isAdmin} onDeselect={() => setSelectedId(null)} />
        </div>
      )}

      {regenOpen && map.data && (
        <RegenerateModal
          map={map.data}
          onClose={() => setRegenOpen(false)}
          onSaved={() => {
            setSelectedId(null);
            setRegenOpen(false);
          }}
        />
      )}
    </div>
  );
}

function HexGrid({
  map,
  selectedId,
  onSelect,
}: {
  map: HexMap;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { placed, viewBox } = useMemo(() => {
    const placed = map.tiles.map((t) => {
      const { x, y } = axialToPixel(t.q, t.r);
      return { tile: t, x, y };
    });
    const pad = SIZE + 4;
    const xs = placed.map((p) => p.x);
    const ys = placed.map((p) => p.y);
    const minX = Math.min(...xs) - pad;
    const minY = Math.min(...ys) - pad;
    const w = Math.max(...xs) - Math.min(...xs) + pad * 2;
    const h = Math.max(...ys) - Math.min(...ys) + pad * 2;
    return { placed, viewBox: `${minX} ${minY} ${w} ${h}` };
  }, [map.tiles]);

  return (
    <Card className="!p-3 bg-[#0d1020] border-[#232a44]">
      <svg viewBox={viewBox} className="w-full h-auto max-h-[70vh]" role="img" aria-label="Campaign sector map">
        {placed.map(({ tile, x, y }) => {
          const meta = TERRAIN[tile.terrain];
          const isSel = tile.id === selectedId;
          return (
            <g
              key={tile.id}
              onClick={() => onSelect(tile.id)}
              className="cursor-pointer"
              style={{ transition: "opacity .1s" }}
            >
              <polygon
                points={hexPoints(x, y)}
                fill={meta.fill}
                stroke={isSel ? "#f0b64a" : "#39415f"}
                strokeWidth={isSel ? 3 : 1}
              />
              {meta.marker && (
                <circle
                  cx={x}
                  cy={y}
                  r={tile.terrain === "star_system" ? 6 : 4}
                  fill={meta.marker}
                />
              )}
              {tile.name && (
                <text
                  x={x}
                  y={y + SIZE * 0.62}
                  textAnchor="middle"
                  fontSize="7"
                  fill="#c7ccdd"
                >
                  {tile.name.length > 12 ? `${tile.name.slice(0, 11)}…` : tile.name}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </Card>
  );
}

function SectorPanel({
  tile,
  isAdmin,
  onDeselect,
}: {
  tile: HexTile | null;
  isAdmin: boolean;
  onDeselect: () => void;
}) {
  if (!tile) {
    return (
      <Card>
        <div className="text-muted text-sm">
          Select a sector to inspect it{isAdmin ? " or edit its terrain" : ""}.
        </div>
      </Card>
    );
  }
  const meta = TERRAIN[tile.terrain];
  const distance = hexDistance(0, 0, tile.q, tile.r);

  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-bold">{tile.name || "Unnamed sector"}</h3>
          <div className="text-xs text-muted mt-0.5">
            axial ({tile.q}, {tile.r}) · {distance} {distance === 1 ? "jump" : "jumps"} from home
          </div>
        </div>
        <button className="text-xs text-muted hover:text-ink" onClick={onDeselect}>
          Clear
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span
          className="inline-block h-3 w-3 rounded-full"
          style={{ background: meta.marker ?? "#39415f" }}
        />
        <span className="text-sm font-medium">{meta.label}</span>
      </div>

      {/* Placeholders for the systems this map is being built to host. */}
      <div className="mt-4 space-y-3 border-t border-border pt-3">
        <FutureSection title="Station">
          No station here — construction arrives in a future update.
        </FutureSection>
        <FutureSection title="Ships">
          No ships in this sector — movement arrives in a future update.
        </FutureSection>
      </div>

      {isAdmin && <TileEditor tile={tile} />}
    </Card>
  );
}

function FutureSection({ title, children }: { title: string; children: string }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      <p className="text-xs text-muted/80 mt-0.5">{children}</p>
    </div>
  );
}

function TileEditor({ tile }: { tile: HexTile }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [terrain, setTerrain] = useState<HexTerrain>(tile.terrain);
  const [name, setName] = useState(tile.name);

  // Re-sync the form when the selected tile changes.
  const key = tile.id;
  const [lastKey, setLastKey] = useState(key);
  if (key !== lastKey) {
    setLastKey(key);
    setTerrain(tile.terrain);
    setName(tile.name);
  }

  const save = useMutation({
    mutationFn: () => api.updateHexTile(tile.id, { terrain, name }),
    onSuccess: () => {
      toast("Sector updated.", "success");
      qc.invalidateQueries({ queryKey: ["hex-map"] });
    },
    onError: (e: any) => toast(e.message ?? "Could not update the sector", "error"),
  });

  const dirty = terrain !== tile.terrain || name !== tile.name;

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">Edit sector</div>
      <div>
        <label className="label">Terrain</label>
        <select
          className="input"
          value={terrain}
          onChange={(e) => setTerrain(e.target.value as HexTerrain)}
        >
          {TERRAIN_ORDER.map((t) => (
            <option key={t} value={t}>
              {TERRAIN[t].label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="label">Name (optional)</label>
        <input
          className="input"
          value={name}
          placeholder="e.g. Kepler Belt"
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <button
        className="btn-primary w-full"
        disabled={!dirty || save.isPending}
        onClick={() => save.mutate()}
      >
        {save.isPending ? "Saving…" : "Save sector"}
      </button>
    </div>
  );
}

function RegenerateModal({
  map,
  onClose,
  onSaved,
}: {
  map: HexMap;
  onClose: () => void;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [radius, setRadius] = useState(map.radius);
  const [name, setName] = useState(map.name);

  const tileCount = 3 * radius * (radius + 1) + 1;

  const save = useMutation({
    mutationFn: () => api.regenerateHexMap(radius, name),
    onSuccess: () => {
      toast(`Sector map regenerated (${tileCount} sectors).`, "success");
      qc.invalidateQueries({ queryKey: ["hex-map"] });
      onSaved();
    },
    onError: (e: any) => toast(e.message ?? "Could not regenerate the map", "error"),
  });

  return (
    <Modal open onClose={onClose} title="Regenerate sector map">
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Rebuilds the grid as a hexagon of the chosen radius. This replaces every
          existing sector (terrain and names are reset).
        </p>
        <div>
          <label className="label">Map name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Radius (rings from centre): {radius}</label>
          <input
            type="range"
            min={1}
            max={8}
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            className="w-full"
          />
          <div className="text-xs text-muted mt-1">{tileCount} sectors</div>
        </div>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Regenerating…" : "Regenerate"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
