import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Badge, Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type { ResourceType, StationKind, StationType } from "../api/types";

export const RESOURCE_LABELS: Record<ResourceType, string> = {
  iron_ingot: "Iron Ingots",
  nickel_ingot: "Nickel Ingots",
  silicon_wafer: "Silicon Wafers",
  cobalt_ingot: "Cobalt Ingots",
};
const RESOURCES = Object.keys(RESOURCE_LABELS) as ResourceType[];

export function costSummary(cost: Partial<Record<ResourceType, number>>): string {
  const parts = RESOURCES.filter((r) => (cost[r] ?? 0) > 0).map(
    (r) => `${cost[r]!.toLocaleString()} ${RESOURCE_LABELS[r]}`,
  );
  return parts.length ? parts.join(" · ") : "Free";
}

export default function StationTypesPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const isAdmin = hasRole("admin");
  const { data, isLoading } = useQuery({ queryKey: ["station-types"], queryFn: api.listStationTypes });

  const [editing, setEditing] = useState<StationType | null>(null);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState<StationType | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["station-types"] });
  const toast = useToast();
  const del = useMutation({
    mutationFn: api.deleteStationType,
    onSuccess: invalidate,
    onError: (e: any) => toast(e.message ?? "Could not delete", "error"),
  });

  return (
    <div>
      <PageHeader
        title="Station Types"
        subtitle="Templates Commanders build from — cost, per-turn output, and a station blueprint."
        action={
          isAdmin && (
            <button className="btn-primary" onClick={() => setCreating(true)}>
              + New type
            </button>
          )
        }
      />

      {isLoading ? (
        <Spinner label="Loading station types…" />
      ) : !data?.length ? (
        <EmptyState title="No station types yet" hint={isAdmin ? "Create one to let Commanders build." : ""} />
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {data.map((t) => (
            <Card key={t.id}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex gap-3 min-w-0">
                  {t.has_blueprint && (
                    <img
                      src={api.stationThumbnailUrl(t.id)}
                      alt=""
                      className="h-14 w-14 rounded-lg border border-border object-cover bg-cream shrink-0"
                    />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold truncate">{t.name}</h3>
                      <Badge tone={t.kind === "shipyard" ? "amber" : "good"}>{t.kind}</Badge>
                      {t.is_starter && <Badge>starter</Badge>}
                    </div>
                    {t.description && <p className="text-muted text-sm mt-0.5">{t.description}</p>}
                  </div>
                </div>
              </div>
              <div className="mt-3 text-sm space-y-1">
                <div>
                  <span className="text-muted">Cost:</span> {costSummary(t.cost)}
                </div>
                {t.kind === "resource" && t.produced_resource && (
                  <div>
                    <span className="text-muted">Generates:</span>{" "}
                    {t.production_amount.toLocaleString()} {RESOURCE_LABELS[t.produced_resource]}/turn
                  </div>
                )}
                <div className="text-xs text-muted">
                  {t.has_blueprint ? `Blueprint: ${t.stats?.block_count ?? "?"} blocks` : "No blueprint"}
                </div>
              </div>
              {isAdmin && (
                <div className="flex gap-2 mt-4">
                  <button className="btn-primary text-xs py-1.5" onClick={() => setUploading(t)}>
                    {t.has_blueprint ? "Replace blueprint" : "Upload blueprint"}
                  </button>
                  <button className="btn-ghost text-xs py-1.5" onClick={() => setEditing(t)}>
                    Edit
                  </button>
                  {!t.is_starter && (
                    <button
                      className="text-xs text-muted hover:text-bad ml-auto self-center"
                      onClick={() => confirm(`Delete ${t.name}?`) && del.mutate(t.id)}
                    >
                      Delete
                    </button>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {(creating || editing) && (
        <TypeModal
          type={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            invalidate();
            setCreating(false);
            setEditing(null);
          }}
        />
      )}
      {uploading && (
        <BlueprintModal
          type={uploading}
          onClose={() => setUploading(null)}
          onSaved={() => {
            invalidate();
            setUploading(null);
          }}
        />
      )}
    </div>
  );
}

function TypeModal({
  type,
  onClose,
  onSaved,
}: {
  type: StationType | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(type?.name ?? "");
  const [kind, setKind] = useState<StationKind>(type?.kind ?? "resource");
  const [description, setDescription] = useState(type?.description ?? "");
  const [cost, setCost] = useState<Partial<Record<ResourceType, number>>>(type?.cost ?? {});
  const [producedResource, setProducedResource] = useState<ResourceType>(
    type?.produced_resource ?? "iron_ingot",
  );
  const [productionAmount, setProductionAmount] = useState<number>(type?.production_amount ?? 100);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const cleanCost: Record<string, number> = {};
      for (const r of RESOURCES) if ((cost[r] ?? 0) > 0) cleanCost[r] = cost[r]!;
      const payload = {
        name,
        kind,
        description,
        cost: cleanCost,
        produced_resource: kind === "resource" ? producedResource : null,
        production_amount: kind === "resource" ? productionAmount : 0,
      };
      return type ? api.updateStationType(type.id, payload) : api.createStationType(payload);
    },
    onSuccess: onSaved,
    onError: (e: any) => setError(e.message),
  });

  return (
    <Modal open onClose={onClose} title={type ? "Edit station type" : "New station type"}>
      <div className="space-y-4">
        <div>
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Kind</label>
          <select
            className="input"
            value={kind}
            disabled={!!type}
            onChange={(e) => setKind(e.target.value as StationKind)}
          >
            <option value="resource">Resource station</option>
            <option value="shipyard">Shipyard</option>
          </select>
          {type && <p className="text-xs text-muted mt-1">Kind can't be changed after creation.</p>}
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
          <label className="label">Build cost</label>
          <div className="grid grid-cols-2 gap-2">
            {RESOURCES.map((r) => (
              <div key={r}>
                <label className="text-xs text-muted">{RESOURCE_LABELS[r]}</label>
                <input
                  className="input"
                  type="number"
                  min={0}
                  value={cost[r] ?? 0}
                  onChange={(e) => setCost({ ...cost, [r]: Number(e.target.value) })}
                />
              </div>
            ))}
          </div>
        </div>
        {kind === "resource" && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="label">Generates</label>
              <select
                className="input"
                value={producedResource}
                onChange={(e) => setProducedResource(e.target.value as ResourceType)}
              >
                {RESOURCES.map((r) => (
                  <option key={r} value={r}>
                    {RESOURCE_LABELS[r]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Amount / turn</label>
              <input
                className="input"
                type="number"
                min={1}
                value={productionAmount}
                onChange={(e) => setProductionAmount(Number(e.target.value))}
              />
            </div>
          </div>
        )}
        {error && <div className="text-sm text-bad">{error}</div>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" disabled={!name || save.isPending} onClick={() => save.mutate()}>
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
}

function BlueprintModal({
  type,
  onClose,
  onSaved,
}: {
  type: StationType;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const upload = useMutation({
    mutationFn: () => api.uploadStationBlueprint(type.id, file!),
    onSuccess: () => {
      toast(`Blueprint attached to ${type.name}.`, "success");
      onSaved();
    },
    onError: (e: any) => setError(e.message),
  });

  return (
    <Modal open onClose={onClose} title={`Station blueprint — ${type.name}`}>
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Upload a <code>.zip</code> of the station blueprint folder (keeps the thumbnail)
          or a bare <code>bp.sbc</code>. This grid is injected into map station slots when
          the sector loads.
        </p>
        <input
          type="file"
          accept=".zip,.sbc"
          className="input"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setError(null);
          }}
        />
        {error && <div className="text-sm text-bad">{error}</div>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" disabled={!file || upload.isPending} onClick={() => upload.mutate()}>
            {upload.isPending ? "Uploading…" : "Upload"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
