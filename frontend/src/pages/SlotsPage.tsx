import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth";
import { Badge, Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import { ValidationReportView } from "../components/ValidationReport";
import { useToast } from "../components/toast";
import type { Slot, ValidationReport } from "../api/types";

export default function SlotsPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const slots = useQuery({ queryKey: ["slots"], queryFn: api.listSlots });
  const classes = useQuery({ queryKey: ["ship-classes"], queryFn: api.listShipClasses });
  const [uploadSlot, setUploadSlot] = useState<Slot | null>(null);
  const [historySlot, setHistorySlot] = useState<Slot | null>(null);
  const [creating, setCreating] = useState(false);

  const isAdmin = hasRole("admin");
  const canUpload = hasRole("engineer");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["slots"] });

  const grouped = useMemo(() => {
    const map = new Map<string, Slot[]>();
    for (const s of slots.data ?? []) {
      const key = s.ship_class_name ?? "Unassigned";
      (map.get(key) ?? map.set(key, []).get(key)!).push(s);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [slots.data]);

  const del = useMutation({ mutationFn: api.deleteSlot, onSuccess: invalidate });
  const clear = useMutation({ mutationFn: api.clearSlot, onSuccess: invalidate });

  return (
    <div>
      <PageHeader
        title="Blueprint Slots"
        subtitle="Each slot holds at most one accepted blueprint, capping the ship pool."
        action={
          isAdmin && (
            <button className="btn-primary" onClick={() => setCreating(true)}>
              + New slot
            </button>
          )
        }
      />

      {slots.isLoading ? (
        <Spinner label="Loading slots…" />
      ) : !slots.data?.length ? (
        <EmptyState title="No slots yet" hint={isAdmin ? "Create slots per ship class." : ""} />
      ) : (
        <div className="space-y-8">
          {grouped.map(([className, group]) => (
            <div key={className}>
              <h2 className="font-bold text-lg mb-3">{className}</h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {group.map((s) => {
                  const bp = s.active_blueprint;
                  return (
                    <Card key={s.id}>
                      <div className="flex items-start justify-between">
                        <h3 className="font-semibold">{s.name}</h3>
                        {bp ? <Badge tone="good">Filled</Badge> : <Badge>Empty</Badge>}
                      </div>
                      {bp ? (
                        <div className="mt-3 flex gap-3">
                          {bp.has_thumbnail && (
                            <img
                              src={api.thumbnailUrl(bp.id)}
                              alt=""
                              className="h-16 w-16 rounded-lg border border-border object-cover bg-cream shrink-0"
                            />
                          )}
                          <div className="text-sm text-muted space-y-1 min-w-0">
                            <div className="font-medium text-ink truncate">{bp.name}</div>
                            <div className="flex gap-3 flex-wrap text-xs">
                              <span>{bp.stats?.block_count ?? "?"} blocks</span>
                              <span>{bp.stats?.pcu ?? "?"} PCU</span>
                              <span>{bp.stats?.weapon_count ?? 0} weapons</span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <p className="text-muted text-sm mt-3">No blueprint yet.</p>
                      )}
                      <div className="flex gap-2 mt-4">
                        {canUpload && (
                          <button className="btn-primary text-xs py-1.5" onClick={() => setUploadSlot(s)}>
                            {bp ? "Replace" : "Upload"}
                          </button>
                        )}
                        {bp && (
                          <button
                            className="btn-ghost text-xs py-1.5"
                            onClick={async () => {
                              const { url } = await api.downloadBlueprint(bp.id);
                              window.open(url, "_blank");
                            }}
                          >
                            Download
                          </button>
                        )}
                        <button
                          className="btn-ghost text-xs py-1.5"
                          onClick={() => setHistorySlot(s)}
                        >
                          History
                        </button>
                        {isAdmin && bp && (
                          <button
                            className="text-xs text-muted hover:text-bad ml-auto self-center"
                            onClick={() => clear.mutate(s.id)}
                          >
                            Clear
                          </button>
                        )}
                        {isAdmin && !bp && (
                          <button
                            className="text-xs text-muted hover:text-bad ml-auto self-center"
                            onClick={() => confirm(`Delete slot ${s.name}?`) && del.mutate(s.id)}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {uploadSlot && (
        <UploadModal
          slot={uploadSlot}
          onClose={() => setUploadSlot(null)}
          onDone={() => {
            invalidate();
          }}
        />
      )}
      {historySlot && (
        <HistoryModal slot={historySlot} onClose={() => setHistorySlot(null)} />
      )}
      {creating && (
        <CreateSlotModal
          classes={(classes.data ?? []).map((c) => ({ id: c.id, name: c.name }))}
          onClose={() => setCreating(false)}
          onSaved={() => {
            invalidate();
            setCreating(false);
          }}
        />
      )}
    </div>
  );
}

function UploadModal({
  slot,
  onClose,
  onDone,
}: {
  slot: Slot;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: () => api.uploadBlueprint(slot.id, file!),
    onSuccess: (res) => {
      setReport(res.report ?? res);
      toast(`Blueprint accepted for ${slot.name}.`, "success");
      onDone();
    },
    onError: (e: any) => {
      if (e instanceof ApiError && e.status === 422) {
        setReport(e.body as ValidationReport);
        toast("Validation failed — see the checklist.", "error");
      } else {
        setError(e.message);
      }
    },
  });

  return (
    <Modal open onClose={onClose} title={`Upload to ${slot.name}`}>
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Upload a <code>.zip</code> of the blueprint folder (keeps the thumbnail) or a
          bare <code>bp.sbc</code>. It must pass every requirement for{" "}
          <b>{slot.ship_class_name}</b>.
        </p>
        <input
          type="file"
          accept=".zip,.sbc"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setReport(null);
            setError(null);
          }}
          className="input"
        />
        {error && <div className="text-sm text-bad">{error}</div>}
        {report && <ValidationReportView report={report} />}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            {report?.passed ? "Done" : "Cancel"}
          </button>
          <button
            className="btn-primary"
            disabled={!file || upload.isPending}
            onClick={() => upload.mutate()}
          >
            {upload.isPending ? "Validating…" : "Upload & validate"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function HistoryModal({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["slot-history", slot.id],
    queryFn: () => api.slotHistory(slot.id),
  });

  const statusTone = (s: string) =>
    s === "active" ? "good" : s === "replaced" ? "amber" : "neutral";

  return (
    <Modal open onClose={onClose} title={`Upload history — ${slot.name}`}>
      {isLoading ? (
        <Spinner label="Loading history…" />
      ) : !data?.length ? (
        <p className="text-muted text-sm">No uploads yet.</p>
      ) : (
        <ul className="space-y-2">
          {data.map((h) => (
            <li key={h.id} className="flex items-center gap-3 rounded-xl border border-border p-3">
              {h.has_thumbnail ? (
                <img
                  src={api.thumbnailUrl(h.id)}
                  alt=""
                  className="h-12 w-12 rounded-lg border border-border object-cover bg-cream shrink-0"
                />
              ) : (
                <div className="h-12 w-12 rounded-lg bg-cream shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm truncate">{h.name}</span>
                  <Badge tone={statusTone(h.status) as any}>{h.status}</Badge>
                </div>
                <div className="text-xs text-muted mt-0.5">
                  {h.stats?.pcu ?? "?"} PCU · {h.stats?.block_count ?? "?"} blocks ·{" "}
                  {h.uploader_name ?? "unknown"} · {new Date(h.created_at).toLocaleString()}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="flex justify-end mt-4">
        <button className="btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}

function CreateSlotModal({
  classes,
  onClose,
  onSaved,
}: {
  classes: { id: string; name: string }[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [classId, setClassId] = useState(classes[0]?.id ?? "");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.createSlot(classId, name),
    onSuccess: onSaved,
    onError: (e: any) => setError(e.message),
  });

  return (
    <Modal open onClose={onClose} title="New blueprint slot">
      <div className="space-y-4">
        <div>
          <label className="label">Ship class</label>
          <select className="input" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Slot name</label>
          <input
            className="input"
            placeholder="e.g. Battleship #1"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        {error && <div className="text-sm text-bad">{error}</div>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={!classId || !name || save.isPending}
            onClick={() => save.mutate()}
          >
            Create
          </button>
        </div>
      </div>
    </Modal>
  );
}
