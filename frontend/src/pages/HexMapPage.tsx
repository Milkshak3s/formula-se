import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type {
  GameMap,
  HexMap,
  HexTerrain,
  HexTile,
  ResourceType,
  Ship,
  ShipBuildOrder,
  Station,
  StationType,
  TerrainMap,
} from "../api/types";

const RESOURCE_LABELS: Record<ResourceType, string> = {
  iron_ingot: "Iron Ingots",
  nickel_ingot: "Nickel Ingots",
  silicon_wafer: "Silicon Wafers",
  cobalt_ingot: "Cobalt Ingots",
};

function costSummary(cost: Partial<Record<ResourceType, number>>): string {
  const parts = (Object.keys(RESOURCE_LABELS) as ResourceType[])
    .filter((r) => (cost[r] ?? 0) > 0)
    .map((r) => `${cost[r]!.toLocaleString()} ${RESOURCE_LABELS[r]}`);
  return parts.length ? parts.join(" · ") : "Free";
}

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
  const isCommander = hasRole("commander");
  const map = useQuery({ queryKey: ["hex-map"], queryFn: api.getHexMap });
  const stations = useQuery({ queryKey: ["stations"], queryFn: api.listStations });
  const ships = useQuery({ queryKey: ["ships"], queryFn: api.listShips });
  const builds = useQuery({ queryKey: ["ship-builds"], queryFn: api.listShipBuilds });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [regenOpen, setRegenOpen] = useState(false);
  const [terrainMapsOpen, setTerrainMapsOpen] = useState(false);
  const [buildTile, setBuildTile] = useState<HexTile | null>(null);
  const [buildShipyard, setBuildShipyard] = useState<Station | null>(null);

  const selected = map.data?.tiles.find((t) => t.id === selectedId) ?? null;
  const mapByTerrain = useMemo(() => {
    const m: Partial<Record<HexTerrain, TerrainMap>> = {};
    for (const tm of map.data?.terrain_maps ?? []) m[tm.terrain] = tm;
    return m;
  }, [map.data?.terrain_maps]);
  const stationsByTile = useMemo(() => {
    const m: Record<string, Station[]> = {};
    for (const s of stations.data ?? []) (m[s.hex_tile_id] ??= []).push(s);
    return m;
  }, [stations.data]);
  const shipsByTile = useMemo(() => {
    const m: Record<string, Ship[]> = {};
    for (const s of ships.data ?? []) (m[s.hex_tile_id] ??= []).push(s);
    return m;
  }, [ships.data]);
  const buildsByShipyard = useMemo(() => {
    const m: Record<string, ShipBuildOrder[]> = {};
    for (const b of builds.data ?? []) (m[b.shipyard_id] ??= []).push(b);
    return m;
  }, [builds.data]);

  return (
    <div>
      <PageHeader
        title="Sector Map"
        subtitle="The campaign's hex grid. Sectors will host stations and ship movements."
        action={
          isAdmin && (
            <div className="flex gap-2">
              <button className="btn-ghost" onClick={() => setTerrainMapsOpen(true)}>
                Terrain maps
              </button>
              <button className="btn-primary" onClick={() => setRegenOpen(true)}>
                Regenerate grid
              </button>
            </div>
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
          <HexGrid
            map={map.data}
            selectedId={selectedId}
            onSelect={setSelectedId}
            stationsByTile={stationsByTile}
          />
          <SectorPanel
            tile={selected}
            terrainMap={selected ? mapByTerrain[selected.terrain] ?? null : null}
            stations={selected ? stationsByTile[selected.id] ?? [] : []}
            ships={selected ? shipsByTile[selected.id] ?? [] : []}
            buildsByShipyard={buildsByShipyard}
            isAdmin={isAdmin}
            isCommander={isCommander}
            onBuild={() => selected && setBuildTile(selected)}
            onBuildShip={setBuildShipyard}
            onDeselect={() => setSelectedId(null)}
          />
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
      {terrainMapsOpen && map.data && (
        <TerrainMapsModal
          assignments={mapByTerrain}
          onClose={() => setTerrainMapsOpen(false)}
        />
      )}
      {buildTile && (
        <BuildStationModal
          tile={buildTile}
          onClose={() => setBuildTile(null)}
          onBuilt={() => setBuildTile(null)}
        />
      )}
      {buildShipyard && (
        <BuildShipModal
          shipyard={buildShipyard}
          inProgress={buildsByShipyard[buildShipyard.id]?.length ?? 0}
          onClose={() => setBuildShipyard(null)}
          onQueued={() => setBuildShipyard(null)}
        />
      )}
    </div>
  );
}

function HexGrid({
  map,
  selectedId,
  onSelect,
  stationsByTile,
}: {
  map: HexMap;
  selectedId: string | null;
  onSelect: (id: string) => void;
  stationsByTile: Record<string, Station[]>;
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
              {(stationsByTile[tile.id]?.length ?? 0) > 0 && (
                <>
                  <rect
                    x={x + SIZE * 0.28}
                    y={y - SIZE * 0.62}
                    width={9}
                    height={9}
                    rx={1.5}
                    fill="#0d1020"
                    stroke="#f0b64a"
                    strokeWidth={1.5}
                  />
                  <text
                    x={x + SIZE * 0.28 + 4.5}
                    y={y - SIZE * 0.62 + 7}
                    textAnchor="middle"
                    fontSize="7"
                    fontWeight="bold"
                    fill="#f0b64a"
                  >
                    {stationsByTile[tile.id].length}
                  </text>
                </>
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
  terrainMap,
  stations,
  ships,
  buildsByShipyard,
  isAdmin,
  isCommander,
  onBuild,
  onBuildShip,
  onDeselect,
}: {
  tile: HexTile | null;
  terrainMap: TerrainMap | null;
  stations: Station[];
  ships: Ship[];
  buildsByShipyard: Record<string, ShipBuildOrder[]>;
  isAdmin: boolean;
  isCommander: boolean;
  onBuild: () => void;
  onBuildShip: (shipyard: Station) => void;
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

      <div className="mt-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">Game map</div>
        {terrainMap ? (
          <p className="text-sm mt-0.5">{terrainMap.game_map_name}</p>
        ) : (
          <p className="text-xs text-muted/80 mt-0.5">
            No map assigned to {meta.label.toLowerCase()} sectors.
          </p>
        )}
        {isAdmin && (
          <p className="text-[11px] text-muted/70 mt-1">
            Set per-terrain via “Terrain maps”. Loaded for future battles &amp; construction.
          </p>
        )}
      </div>

      <div className="mt-4 border-t border-border pt-3">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">
            Stations ({stations.length})
          </div>
          {isCommander && (
            <button className="btn-primary text-xs py-1" onClick={onBuild}>
              + Build
            </button>
          )}
        </div>
        {stations.length ? (
          <ul className="mt-2 space-y-1.5">
            {stations.map((s) => (
              <li key={s.id} className="rounded-lg border border-border p-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{s.station_type_name}</span>
                  <span
                    className={`badge ${
                      s.kind === "shipyard" ? "bg-amber/20 text-amber-dark" : "bg-good/15 text-good"
                    }`}
                  >
                    {s.kind}
                  </span>
                </div>
                {s.kind === "resource" && s.produced_resource && (
                  <div className="text-xs text-muted mt-0.5">
                    +{s.production_amount.toLocaleString()} {RESOURCE_LABELS[s.produced_resource]}/turn
                  </div>
                )}
                <div className="text-[11px] text-muted/70 mt-0.5">
                  {s.built_by_name ? `Built by ${s.built_by_name}` : "Campaign start"} · turn {s.built_on_turn}
                </div>
                {s.kind === "shipyard" && (
                  <ShipyardBuilds
                    shipyard={s}
                    orders={buildsByShipyard[s.id] ?? []}
                    isCommander={isCommander}
                    onBuildShip={() => onBuildShip(s)}
                  />
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted/80 mt-1">No stations in this sector yet.</p>
        )}
      </div>

      <div className="mt-4 border-t border-border pt-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">
          Ships ({ships.length})
        </div>
        {ships.length ? (
          <ul className="mt-2 space-y-1">
            {shipCounts(ships).map((g) => (
              <li key={g.name} className="flex items-center justify-between text-sm">
                <span className="truncate">{g.name}</span>
                <span className="text-muted tabular-nums shrink-0">×{g.count}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted/80 mt-1">No ships stationed here.</p>
        )}
        <p className="text-[11px] text-muted/70 mt-1">
          Shared campaign stock. Movement arrives in a future update.
        </p>
      </div>

      {isAdmin && <TileEditor tile={tile} />}
    </Card>
  );
}

// Collapse a sector's ships into per-class counts for a compact list.
function shipCounts(ships: Ship[]): { name: string; count: number }[] {
  const m = new Map<string, number>();
  for (const s of ships) m.set(s.ship_class_name, (m.get(s.ship_class_name) ?? 0) + 1);
  return [...m.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function ShipyardBuilds({
  shipyard,
  orders,
  isCommander,
  onBuildShip,
}: {
  shipyard: Station;
  orders: ShipBuildOrder[];
  isCommander: boolean;
  onBuildShip: () => void;
}) {
  const used = orders.length;
  const slots = shipyard.build_slots;
  const full = used >= slots;
  return (
    <div className="mt-2 rounded-lg bg-black/10 p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Build slots {used}/{slots}
        </span>
        {isCommander && (
          <button
            className="btn-primary text-[11px] py-0.5 px-2 disabled:opacity-50"
            disabled={full}
            title={full ? "All build slots are in use" : undefined}
            onClick={onBuildShip}
          >
            + Build ship
          </button>
        )}
      </div>
      {orders.length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {orders.map((o) => {
            const done = o.build_time - o.turns_remaining;
            const pct = o.build_time > 0 ? (done / o.build_time) * 100 : 0;
            return (
              <li key={o.id}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="truncate">{o.ship_class_name}</span>
                  <span className="text-muted shrink-0 tabular-nums">
                    {o.turns_remaining} {o.turns_remaining === 1 ? "turn" : "turns"}
                  </span>
                </div>
                <div className="h-1 rounded-full bg-border overflow-hidden mt-0.5">
                  <div className="h-full bg-amber" style={{ width: `${pct}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
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

function TerrainMapsModal({
  assignments,
  onClose,
}: {
  assignments: Partial<Record<HexTerrain, TerrainMap>>;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const maps = useQuery({ queryKey: ["maps"], queryFn: api.listMaps });

  const set = useMutation({
    mutationFn: ({ terrain, mapId }: { terrain: HexTerrain; mapId: string | null }) =>
      api.setTerrainMap(terrain, mapId),
    onSuccess: () => {
      toast("Terrain map updated.", "success");
      qc.invalidateQueries({ queryKey: ["hex-map"] });
    },
    onError: (e: any) => toast(e.message ?? "Could not update the terrain map", "error"),
  });

  return (
    <Modal open onClose={onClose} title="Terrain maps">
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Assign a Game Map to each terrain type. Every sector of that terrain loads
          this map for future battles and station construction. One map can back
          several terrains; the map itself isn’t modified by play.
        </p>
        {maps.isLoading ? (
          <Spinner label="Loading game maps…" />
        ) : !maps.data?.length ? (
          <EmptyState
            title="No game maps yet"
            hint="Upload a world save on the Game Maps page first."
          />
        ) : (
          <div className="space-y-2">
            {TERRAIN_ORDER.map((terrain) => {
              const meta = TERRAIN[terrain];
              const current = assignments[terrain]?.game_map_id ?? "";
              return (
                <div key={terrain} className="flex items-center gap-3">
                  <span className="flex items-center gap-2 w-36 shrink-0">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: meta.marker ?? "#39415f" }}
                    />
                    <span className="text-sm">{meta.label}</span>
                  </span>
                  <select
                    className="input"
                    value={current}
                    disabled={set.isPending}
                    onChange={(e) =>
                      set.mutate({ terrain, mapId: e.target.value || null })
                    }
                  >
                    <option value="">— No map —</option>
                    {(maps.data as GameMap[]).map((gm) => (
                      <option key={gm.id} value={gm.id}>
                        {gm.name}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        )}
        <div className="flex justify-end">
          <button className="btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </Modal>
  );
}

function BuildStationModal({
  tile,
  onClose,
  onBuilt,
}: {
  tile: HexTile;
  onClose: () => void;
  onBuilt: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const types = useQuery({ queryKey: ["station-types"], queryFn: api.listStationTypes });
  const resources = useQuery({ queryKey: ["resources"], queryFn: api.getResources });
  const [chosen, setChosen] = useState<StationType | null>(null);

  // The starter shipyard is a one-per-campaign gift, not a buildable type.
  const buildable = (types.data ?? []).filter((t) => !t.is_starter);

  const balances: Partial<Record<ResourceType, number>> = {};
  for (const b of resources.data?.balances ?? []) balances[b.resource] = b.amount;
  const canAfford = (t: StationType) =>
    (Object.keys(RESOURCE_LABELS) as ResourceType[]).every(
      (r) => (balances[r] ?? 0) >= (t.cost[r] ?? 0),
    );

  const build = useMutation({
    mutationFn: () => api.buildStation(tile.id, chosen!.id),
    onSuccess: (s) => {
      toast(`Built ${s.station_type_name} in sector (${tile.q}, ${tile.r}).`, "success");
      qc.invalidateQueries({ queryKey: ["stations"] });
      qc.invalidateQueries({ queryKey: ["resources"] });
      onBuilt();
    },
    onError: (e: any) => toast(e.message ?? "Could not build the station", "error"),
  });

  const title = `Build in sector (${tile.q}, ${tile.r})`;

  // Step 2: confirm the chosen type.
  if (chosen) {
    const affordable = canAfford(chosen);
    return (
      <Modal open onClose={onClose} title={title}>
        <div className="space-y-4">
          <div className="rounded-xl border border-border p-3">
            <div className="flex items-center gap-2">
              <span className="font-bold">{chosen.name}</span>
              <span
                className={`badge ${
                  chosen.kind === "shipyard" ? "bg-amber/20 text-amber-dark" : "bg-good/15 text-good"
                }`}
              >
                {chosen.kind}
              </span>
            </div>
            {chosen.description && (
              <p className="text-sm text-muted mt-1">{chosen.description}</p>
            )}
            <div className="text-sm mt-2">
              <span className="text-muted">Cost:</span> {costSummary(chosen.cost)}
            </div>
            {chosen.kind === "resource" && chosen.produced_resource && (
              <div className="text-sm">
                <span className="text-muted">Generates:</span>{" "}
                {chosen.production_amount.toLocaleString()} {RESOURCE_LABELS[chosen.produced_resource]}/turn
              </div>
            )}
          </div>
          {!affordable && (
            <div className="text-sm text-bad">
              The campaign can’t afford this station right now.
            </div>
          )}
          <div className="flex justify-between gap-2">
            <button className="btn-ghost" onClick={() => setChosen(null)}>
              ← Back
            </button>
            <button
              className="btn-primary"
              disabled={!affordable || build.isPending}
              onClick={() => build.mutate()}
            >
              {build.isPending ? "Building…" : "Confirm & build"}
            </button>
          </div>
        </div>
      </Modal>
    );
  }

  // Step 1: pick a station type.
  return (
    <Modal open onClose={onClose} title={title}>
      <div className="space-y-3">
        <p className="text-sm text-muted">Choose a station type to construct here.</p>
        {types.isLoading ? (
          <Spinner label="Loading station types…" />
        ) : !buildable.length ? (
          <EmptyState
            title="No station types"
            hint="An admin must create station types first."
          />
        ) : (
          <div className="space-y-2">
            {buildable.map((t) => {
              const affordable = canAfford(t);
              return (
                <button
                  key={t.id}
                  onClick={() => setChosen(t)}
                  className="w-full text-left rounded-xl border border-border p-3 hover:border-amber transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{t.name}</span>
                    <span
                      className={`badge ${
                        t.kind === "shipyard" ? "bg-amber/20 text-amber-dark" : "bg-good/15 text-good"
                      }`}
                    >
                      {t.kind}
                    </span>
                    {!affordable && <span className="badge bg-bad/15 text-bad">can’t afford</span>}
                  </div>
                  <div className="text-xs text-muted mt-1">Cost: {costSummary(t.cost)}</div>
                  {t.kind === "resource" && t.produced_resource && (
                    <div className="text-xs text-muted">
                      +{t.production_amount.toLocaleString()} {RESOURCE_LABELS[t.produced_resource]}/turn
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
        <div className="flex justify-end">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}

function BuildShipModal({
  shipyard,
  inProgress,
  onClose,
  onQueued,
}: {
  shipyard: Station;
  inProgress: number;
  onClose: () => void;
  onQueued: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const classes = useQuery({ queryKey: ["ship-classes"], queryFn: api.listShipClasses });
  const resources = useQuery({ queryKey: ["resources"], queryFn: api.getResources });
  const [chosenId, setChosenId] = useState<string | null>(null);

  const balances: Partial<Record<ResourceType, number>> = {};
  for (const b of resources.data?.balances ?? []) balances[b.resource] = b.amount;
  const canAfford = (cost: Partial<Record<ResourceType, number>>) =>
    (Object.keys(RESOURCE_LABELS) as ResourceType[]).every(
      (r) => (balances[r] ?? 0) >= (cost[r] ?? 0),
    );

  const chosen = (classes.data ?? []).find((c) => c.id === chosenId) ?? null;
  const slotsFree = shipyard.build_slots - inProgress;

  const queue = useMutation({
    mutationFn: () => api.queueShipBuild(shipyard.id, chosenId!),
    onSuccess: (o) => {
      toast(`Queued ${o.ship_class_name} — ready in ${o.turns_remaining} turns.`, "success");
      qc.invalidateQueries({ queryKey: ["ship-builds"] });
      qc.invalidateQueries({ queryKey: ["resources"] });
      onQueued();
    },
    onError: (e: any) => toast(e.message ?? "Could not queue the build", "error"),
  });

  const title = `Build at ${shipyard.station_type_name}`;

  // Step 2: confirm the chosen class.
  if (chosen) {
    const affordable = canAfford(chosen.cost);
    return (
      <Modal open onClose={onClose} title={title}>
        <div className="space-y-4">
          <div className="rounded-xl border border-border p-3">
            <div className="font-bold">{chosen.name}</div>
            {chosen.description && (
              <p className="text-sm text-muted mt-1">{chosen.description}</p>
            )}
            <div className="text-sm mt-2">
              <span className="text-muted">Cost:</span> {costSummary(chosen.cost)}
            </div>
            <div className="text-sm">
              <span className="text-muted">Build time:</span> {chosen.build_time}{" "}
              {chosen.build_time === 1 ? "turn" : "turns"}
            </div>
          </div>
          {!affordable && (
            <div className="text-sm text-bad">
              The campaign can’t afford this ship right now.
            </div>
          )}
          {slotsFree <= 0 && (
            <div className="text-sm text-bad">This shipyard has no free build slots.</div>
          )}
          <div className="flex justify-between gap-2">
            <button className="btn-ghost" onClick={() => setChosenId(null)}>
              ← Back
            </button>
            <button
              className="btn-primary"
              disabled={!affordable || slotsFree <= 0 || queue.isPending}
              onClick={() => queue.mutate()}
            >
              {queue.isPending ? "Queuing…" : "Confirm & queue"}
            </button>
          </div>
        </div>
      </Modal>
    );
  }

  // Step 1: pick a ship class.
  return (
    <Modal open onClose={onClose} title={title}>
      <div className="space-y-3">
        <p className="text-sm text-muted">
          {slotsFree} of {shipyard.build_slots} build{" "}
          {shipyard.build_slots === 1 ? "slot" : "slots"} free. Choose a ship class to queue.
        </p>
        {classes.isLoading ? (
          <Spinner label="Loading ship classes…" />
        ) : !classes.data?.length ? (
          <EmptyState
            title="No ship classes"
            hint="An admin must create ship classes first."
          />
        ) : (
          <div className="space-y-2">
            {classes.data.map((c) => {
              const affordable = canAfford(c.cost);
              return (
                <button
                  key={c.id}
                  onClick={() => setChosenId(c.id)}
                  className="w-full text-left rounded-xl border border-border p-3 hover:border-amber transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{c.name}</span>
                    {!affordable && <span className="badge bg-bad/15 text-bad">can’t afford</span>}
                  </div>
                  <div className="text-xs text-muted mt-1">
                    Cost: {costSummary(c.cost)} · {c.build_time}{" "}
                    {c.build_time === 1 ? "turn" : "turns"}
                  </div>
                </button>
              );
            })}
          </div>
        )}
        <div className="flex justify-end">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}
