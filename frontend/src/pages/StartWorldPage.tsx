import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../components/toast";
import { Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import type { GameMap, Slot } from "../api/types";

export default function StartWorldPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const maps = useQuery({ queryKey: ["maps"], queryFn: api.listMaps });
  const slots = useQuery({ queryKey: ["slots"], queryFn: api.listSlots });

  const [step, setStep] = useState(1);
  const [mapId, setMapId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [assignments, setAssignments] = useState<Record<string, string>>({}); // startSlotId -> slotId

  const selectedMap: GameMap | undefined = maps.data?.find((m) => m.id === mapId);

  const filledSlots = useMemo(
    () => (slots.data ?? []).filter((s) => s.active_blueprint),
    [slots.data],
  );

  const create = useMutation({
    mutationFn: () =>
      api.createPreparedWorld({
        map_id: mapId!,
        name,
        assignments: Object.entries(assignments)
          .filter(([, slotId]) => slotId)
          .map(([start_slot_id, slot_id]) => ({ start_slot_id, slot_id })),
      }),
    onSuccess: () => {
      toast("World queued — preparing your save.", "success");
      navigate("/prepared-worlds");
    },
  });

  if (maps.isLoading || slots.isLoading) return <Spinner label="Loading…" />;
  if (!maps.data?.length)
    return (
      <div>
        <PageHeader title="Start a World" />
        <EmptyState title="No maps available" hint="An admin needs to upload a game map first." />
      </div>
    );

  return (
    <div>
      <PageHeader title="Start a World" subtitle="Assemble a match and generate a ready-to-run save." />

      <div className="flex gap-2 mb-6 text-sm">
        {["Map & name", "Assign ships", "Confirm"].map((s, i) => (
          <div
            key={s}
            className={`flex items-center gap-2 rounded-full px-3 py-1 ${
              step === i + 1 ? "bg-amber/20 text-amber-dark font-semibold" : "text-muted"
            }`}
          >
            <span className="h-5 w-5 grid place-items-center rounded-full bg-surface border border-border text-xs">
              {i + 1}
            </span>
            {s}
          </div>
        ))}
      </div>

      {step === 1 && (
        <Card className="space-y-4 max-w-xl">
          <div>
            <label className="label">Run name</label>
            <input
              className="input"
              placeholder="Match 1 — Finals"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Game map</label>
            <select
              className="input"
              value={mapId ?? ""}
              onChange={(e) => setMapId(e.target.value || null)}
            >
              <option value="">Select a map…</option>
              {maps.data.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.start_slots.length} start slots)
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end">
            <button
              className="btn-primary"
              disabled={!mapId || !name}
              onClick={() => setStep(2)}
            >
              Next
            </button>
          </div>
        </Card>
      )}

      {step === 2 && selectedMap && (
        <Card className="space-y-4 max-w-2xl">
          {selectedMap.start_slots.length === 0 && (
            <p className="text-muted text-sm">This map has no start slots defined.</p>
          )}
          {selectedMap.start_slots.map((ss) => {
            const compatible = filledSlots.filter((s: Slot) =>
              ss.ship_class_ids.includes(s.ship_class_id),
            );
            return (
              <div key={ss.id} className="rounded-xl border border-border p-3">
                <div className="font-medium">{ss.name}</div>
                <div className="text-xs text-muted mb-2">
                  ({ss.gps_x.toFixed(0)}, {ss.gps_y.toFixed(0)}, {ss.gps_z.toFixed(0)})
                </div>
                <select
                  className="input"
                  value={assignments[ss.id] ?? ""}
                  onChange={(e) =>
                    setAssignments((a) => ({ ...a, [ss.id]: e.target.value }))
                  }
                >
                  <option value="">— Leave empty —</option>
                  {compatible.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.ship_class_name}: {s.name} ({s.active_blueprint?.name})
                    </option>
                  ))}
                </select>
                {compatible.length === 0 && (
                  <p className="text-xs text-muted mt-1">
                    No filled slots match this start slot's classes.
                  </p>
                )}
              </div>
            );
          })}
          <div className="flex justify-between">
            <button className="btn-ghost" onClick={() => setStep(1)}>
              Back
            </button>
            <button className="btn-primary" onClick={() => setStep(3)}>
              Next
            </button>
          </div>
        </Card>
      )}

      {step === 3 && selectedMap && (
        <Card className="space-y-4 max-w-2xl">
          <div>
            <div className="text-sm text-muted">Run name</div>
            <div className="font-semibold">{name}</div>
          </div>
          <div>
            <div className="text-sm text-muted">Map</div>
            <div className="font-semibold">{selectedMap.name}</div>
          </div>
          <div>
            <div className="text-sm text-muted mb-1">Assignments</div>
            <ul className="space-y-1 text-sm">
              {selectedMap.start_slots.map((ss) => {
                const slot = filledSlots.find((s) => s.id === assignments[ss.id]);
                return (
                  <li key={ss.id} className="flex justify-between border-b border-border py-1">
                    <span>{ss.name}</span>
                    <span className="text-muted">
                      {slot ? `${slot.name} — ${slot.active_blueprint?.name}` : "empty"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
          {create.isError && (
            <div className="text-sm text-bad">{(create.error as any).message}</div>
          )}
          <div className="flex justify-between">
            <button className="btn-ghost" onClick={() => setStep(2)}>
              Back
            </button>
            <button className="btn-primary" disabled={create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Queuing…" : "Generate prepared world"}
            </button>
          </div>
        </Card>
      )}
    </div>
  );
}
