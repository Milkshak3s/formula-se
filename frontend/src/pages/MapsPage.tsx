import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { Badge, Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type { GameMap, ShipClass, StartSlot } from "../api/types";

interface DraftSlot {
  name: string;
  gps_string: string;
  gps_x: number;
  gps_y: number;
  gps_z: number;
  ship_class_ids: string[];
}

function toDraft(s: StartSlot): DraftSlot {
  return {
    name: s.name,
    gps_string: "",
    gps_x: s.gps_x,
    gps_y: s.gps_y,
    gps_z: s.gps_z,
    ship_class_ids: s.ship_class_ids,
  };
}

export default function MapsPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const isAdmin = hasRole("admin");
  const maps = useQuery({ queryKey: ["maps"], queryFn: api.listMaps });
  const classes = useQuery({ queryKey: ["ship-classes"], queryFn: api.listShipClasses });
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState<GameMap | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["maps"] });
  const del = useMutation({ mutationFn: api.deleteMap, onSuccess: invalidate });

  const classById = (id: string) => classes.data?.find((c) => c.id === id)?.name ?? "?";

  return (
    <div>
      <PageHeader
        title="Game Maps"
        subtitle="World saves with designated start positions per ship class."
        action={
          isAdmin && (
            <button className="btn-primary" onClick={() => setUploading(true)}>
              + Upload map
            </button>
          )
        }
      />

      {maps.isLoading ? (
        <Spinner label="Loading maps…" />
      ) : !maps.data?.length ? (
        <EmptyState title="No maps yet" hint={isAdmin ? "Upload a world save .zip." : ""} />
      ) : (
        <div className="space-y-4">
          {maps.data.map((m) => (
            <Card key={m.id}>
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold">{m.name}</h3>
                  {m.description && <p className="text-muted text-sm mt-0.5">{m.description}</p>}
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <button className="text-xs text-muted hover:text-ink" onClick={() => setEditing(m)}>
                      Edit start slots
                    </button>
                    <button
                      className="text-xs text-bad"
                      onClick={() => confirm(`Delete ${m.name}?`) && del.mutate(m.id)}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
              <div className="mt-3">
                <div className="text-sm font-medium mb-2">
                  {m.start_slots.length} start slot{m.start_slots.length === 1 ? "" : "s"}
                </div>
                <div className="grid sm:grid-cols-2 gap-2">
                  {m.start_slots.map((s) => (
                    <div key={s.id} className="rounded-xl border border-border p-3">
                      <div className="font-medium text-sm">{s.name}</div>
                      <div className="text-xs text-muted mt-0.5">
                        ({s.gps_x.toFixed(0)}, {s.gps_y.toFixed(0)}, {s.gps_z.toFixed(0)})
                      </div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {s.ship_class_ids.map((id) => (
                          <Badge key={id} tone="amber">
                            {classById(id)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {uploading && (
        <UploadMapModal
          onClose={() => setUploading(false)}
          onSaved={() => {
            invalidate();
            setUploading(false);
          }}
        />
      )}
      {editing && (
        <StartSlotEditor
          map={editing}
          classes={classes.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            invalidate();
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function UploadMapModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.createMap(name, description, file!),
    onSuccess: onSaved,
    onError: (e: any) => setError(e.message),
  });

  return (
    <Modal open onClose={onClose} title="Upload game map">
      <div className="space-y-4">
        <div>
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea
            className="input"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <label className="label">World save (.zip)</label>
          <input
            className="input"
            type="file"
            accept=".zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        {error && <div className="text-sm text-bad">{error}</div>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={!name || !file || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Uploading…" : "Upload"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function StartSlotEditor({
  map,
  classes,
  onClose,
  onSaved,
}: {
  map: GameMap;
  classes: ShipClass[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [slots, setSlots] = useState<DraftSlot[]>(map.start_slots.map(toDraft));
  const [error, setError] = useState<string | null>(null);

  const addSlot = () =>
    setSlots([
      ...slots,
      { name: `Start ${slots.length + 1}`, gps_string: "", gps_x: 0, gps_y: 0, gps_z: 0, ship_class_ids: [] },
    ]);
  const update = (i: number, patch: Partial<DraftSlot>) =>
    setSlots(slots.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const remove = (i: number) => setSlots(slots.filter((_, idx) => idx !== i));
  const toggleClass = (i: number, id: string) => {
    const s = slots[i];
    const has = s.ship_class_ids.includes(id);
    update(i, {
      ship_class_ids: has ? s.ship_class_ids.filter((x) => x !== id) : [...s.ship_class_ids, id],
    });
  };

  const save = useMutation({
    mutationFn: () =>
      api.updateMap(map.id, {
        start_slots: slots.map((s, i) => ({
          name: s.name,
          position_index: i,
          gps_string: s.gps_string || null,
          gps_x: s.gps_string ? null : s.gps_x,
          gps_y: s.gps_string ? null : s.gps_y,
          gps_z: s.gps_string ? null : s.gps_z,
          ship_class_ids: s.ship_class_ids,
        })),
      }),
    onSuccess: onSaved,
    onError: (e: any) => setError(e.message),
  });

  return (
    <Modal open onClose={onClose} title={`Start slots — ${map.name}`}>
      <div className="space-y-4">
        {slots.map((s, i) => (
          <div key={i} className="rounded-xl border border-border p-3 space-y-3">
            <div className="flex items-center justify-between">
              <input
                className="input max-w-[60%]"
                value={s.name}
                onChange={(e) => update(i, { name: e.target.value })}
              />
              <button className="text-xs text-bad" onClick={() => remove(i)}>
                Remove
              </button>
            </div>
            <div>
              <label className="label">Paste GPS (optional — overrides X/Y/Z)</label>
              <input
                className="input"
                placeholder="GPS:Start:1024:0:2048:#FF7500:"
                value={s.gps_string}
                onChange={(e) => update(i, { gps_string: e.target.value })}
              />
            </div>
            {!s.gps_string && (
              <div className="grid grid-cols-3 gap-2">
                {(["gps_x", "gps_y", "gps_z"] as const).map((axis) => (
                  <div key={axis}>
                    <label className="label">{axis.slice(-1).toUpperCase()}</label>
                    <input
                      className="input"
                      type="number"
                      value={s[axis]}
                      onChange={(e) => update(i, { [axis]: Number(e.target.value) } as any)}
                    />
                  </div>
                ))}
              </div>
            )}
            <div>
              <label className="label">Supported classes</label>
              <div className="flex flex-wrap gap-2">
                {classes.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => toggleClass(i, c.id)}
                    className={`badge ${
                      s.ship_class_ids.includes(c.id)
                        ? "bg-amber/25 text-amber-dark"
                        : "bg-cream text-muted"
                    }`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ))}
        <button className="btn-ghost w-full" onClick={addSlot}>
          + Add start slot
        </button>
        {error && <div className="text-sm text-bad">{error}</div>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>
            Save start slots
          </button>
        </div>
      </div>
    </Modal>
  );
}
