import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Badge, Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type { HexTile, Ship, ShipBuildOrder } from "../api/types";

function sectorLabel(q: number, r: number, tiles: HexTile[]): string {
  const t = tiles.find((t) => t.q === q && t.r === r);
  const name = t?.name?.trim();
  return name ? `${name} (${q}, ${r})` : `Sector (${q}, ${r})`;
}

function BuildProgress({ order }: { order: ShipBuildOrder }) {
  const done = order.build_time - order.turns_remaining;
  const pct = order.build_time > 0 ? (done / order.build_time) * 100 : 0;
  return (
    <div>
      <div className="h-2 rounded-full bg-border overflow-hidden">
        <div className="h-full bg-amber" style={{ width: `${pct}%` }} />
      </div>
      <div className="text-[11px] text-muted mt-1 tabular-nums">
        {order.turns_remaining} {order.turns_remaining === 1 ? "turn" : "turns"} left
        {" · "}
        {done}/{order.build_time}
      </div>
    </div>
  );
}

function BuildQueue({ tiles }: { tiles: HexTile[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { hasRole } = useAuth();
  const canCancel = hasRole("commander");
  const builds = useQuery({ queryKey: ["ship-builds"], queryFn: api.listShipBuilds });

  const cancel = useMutation({
    mutationFn: (id: string) => api.cancelShipBuild(id),
    onSuccess: () => {
      toast("Build cancelled. Spent resources are not refunded.", "success");
      qc.invalidateQueries({ queryKey: ["ship-builds"] });
    },
    onError: (e: any) => toast(e.message ?? "Could not cancel the build", "error"),
  });

  return (
    <Card>
      <h2 className="font-bold mb-1">Under construction</h2>
      <p className="text-xs text-muted mb-3">
        Ships build one turn at a time at their shipyard. Queue new builds from a
        shipyard on the Sector Map.
      </p>
      {builds.isLoading ? (
        <Spinner label="Loading build queue…" />
      ) : !builds.data?.length ? (
        <p className="text-sm text-muted/80">Nothing in construction right now.</p>
      ) : (
        <ul className="space-y-2">
          {builds.data.map((o) => (
            <li key={o.id} className="rounded-xl border border-border p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium truncate">{o.ship_class_name}</div>
                  <div className="text-[11px] text-muted mt-0.5">
                    {sectorLabel(o.q, o.r, tiles)}
                    {o.queued_by_name ? ` · queued by ${o.queued_by_name}` : ""}
                  </div>
                </div>
                {canCancel && (
                  <button
                    className="text-xs text-muted hover:text-bad shrink-0"
                    disabled={cancel.isPending}
                    onClick={() => cancel.mutate(o.id)}
                  >
                    Cancel
                  </button>
                )}
              </div>
              <div className="mt-2">
                <BuildProgress order={o} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ShipStock({ tiles }: { tiles: HexTile[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const ships = useQuery({ queryKey: ["ships"], queryFn: api.listShips });
  const [grantOpen, setGrantOpen] = useState(false);

  const scrap = useMutation({
    mutationFn: (id: string) => api.scrapShip(id),
    onSuccess: () => {
      toast("Ship removed from stock.", "success");
      qc.invalidateQueries({ queryKey: ["ships"] });
    },
    onError: (e: any) => toast(e.message ?? "Could not remove the ship", "error"),
  });

  // Group identical class+sector rows into a count for a compact fleet view.
  const grouped = useMemo(() => {
    const list = ships.data ?? [];
    const m = new Map<string, { name: string; q: number; r: number; ships: Ship[] }>();
    for (const s of list) {
      const key = `${s.ship_class_id}@${s.q},${s.r}`;
      const g = m.get(key) ?? { name: s.ship_class_name, q: s.q, r: s.r, ships: [] };
      g.ships.push(s);
      m.set(key, g);
    }
    return [...m.values()].sort(
      (a, b) => a.name.localeCompare(b.name) || a.q - b.q || a.r - b.r,
    );
  }, [ships.data]);

  return (
    <Card>
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-bold">Fleet stock</h2>
        {isAdmin && (
          <button className="btn-primary text-xs py-1" onClick={() => setGrantOpen(true)}>
            + Add ship
          </button>
        )}
      </div>
      <p className="text-xs text-muted mb-3">
        Completed ships are shared across the campaign, grouped by class and sector.
      </p>
      {ships.isLoading ? (
        <Spinner label="Loading fleet…" />
      ) : !grouped.length ? (
        <EmptyState
          title="No ships yet"
          hint="Queue a build at a shipyard, or have an admin grant one."
        />
      ) : (
        <ul className="space-y-2">
          {grouped.map((g) => (
            <li key={`${g.name}@${g.q},${g.r}`} className="rounded-xl border border-border p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-medium truncate">{g.name}</span>
                  {g.ships.length > 1 && <Badge tone="amber">×{g.ships.length}</Badge>}
                </div>
                <span className="text-xs text-muted shrink-0">
                  {sectorLabel(g.q, g.r, tiles)}
                </span>
              </div>
              {isAdmin && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {g.ships.map((s, i) => (
                    <button
                      key={s.id}
                      className="text-[11px] rounded-md border border-border px-1.5 py-0.5 text-muted hover:text-bad hover:border-bad/50"
                      disabled={scrap.isPending}
                      onClick={() => scrap.mutate(s.id)}
                      title={`Remove this ${g.name} (built turn ${s.built_on_turn})`}
                    >
                      remove #{i + 1}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {grantOpen && <GrantShipModal tiles={tiles} onClose={() => setGrantOpen(false)} />}
    </Card>
  );
}

function GrantShipModal({ tiles, onClose }: { tiles: HexTile[]; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const classes = useQuery({ queryKey: ["ship-classes"], queryFn: api.listShipClasses });
  const [classId, setClassId] = useState("");
  const [tileId, setTileId] = useState("");

  const sortedTiles = useMemo(
    () => [...tiles].sort((a, b) => a.r - b.r || a.q - b.q),
    [tiles],
  );

  const grant = useMutation({
    mutationFn: () => api.grantShip(classId, tileId),
    onSuccess: (s) => {
      toast(`Granted ${s.ship_class_name} to sector (${s.q}, ${s.r}).`, "success");
      qc.invalidateQueries({ queryKey: ["ships"] });
      onClose();
    },
    onError: (e: any) => toast(e.message ?? "Could not add the ship", "error"),
  });

  return (
    <Modal open onClose={onClose} title="Add a ship to stock">
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Place a ship of any class directly into the shared campaign stock, at a
          chosen sector. Free — no build cost.
        </p>
        <div>
          <label className="label">Ship class</label>
          <select className="input" value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">— Select a class —</option>
            {(classes.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Sector</label>
          <select className="input" value={tileId} onChange={(e) => setTileId(e.target.value)}>
            <option value="">— Select a sector —</option>
            {sortedTiles.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name?.trim() ? `${t.name} (${t.q}, ${t.r})` : `Sector (${t.q}, ${t.r})`}
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={!classId || !tileId || grant.isPending}
            onClick={() => grant.mutate()}
          >
            {grant.isPending ? "Adding…" : "Add ship"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function FleetPage() {
  const map = useQuery({ queryKey: ["hex-map"], queryFn: api.getHexMap });
  const tiles = map.data?.tiles ?? [];

  return (
    <div>
      <PageHeader
        title="Fleet"
        subtitle="The campaign's shared ship stock and the shipyard build queue."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <ShipStock tiles={tiles} />
        <BuildQueue tiles={tiles} />
      </div>
    </div>
  );
}
