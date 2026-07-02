import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { Badge, Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type { Requirement, RequirementType, ShipClass } from "../api/types";

const RULE_LABELS: Record<RequirementType, string> = {
  block_count: "Block count",
  grid_size: "Grid size",
  pcu_limit: "PCU limit",
  weapon_count: "Weapon count",
  block_whitelist: "Block whitelist",
  block_blacklist: "Block blacklist",
};

function describeRule(r: Requirement): string {
  const p = r.params || {};
  switch (r.rule_type) {
    case "block_count":
      return `${p.min ?? "0"}–${p.max ?? "∞"} blocks`;
    case "grid_size":
      return `${p.size ?? "?"} grid only`;
    case "pcu_limit":
      return `≤ ${p.max ?? "?"} PCU`;
    case "weapon_count":
      return `≤ ${p.max ?? "?"} weapons`;
    case "block_whitelist":
      return `whitelist (${(p.type_ids || []).length} types)`;
    case "block_blacklist":
      return `blacklist (${(p.rules || []).length} caps)`;
    default:
      return r.rule_type;
  }
}

function RuleEditor({
  rules,
  onChange,
}: {
  rules: Requirement[];
  onChange: (r: Requirement[]) => void;
}) {
  const add = (rule_type: RequirementType) => {
    const defaults: Record<string, any> = {
      block_count: { min: 1, max: 1000 },
      grid_size: { size: "Large" },
      pcu_limit: { max: 30000 },
      weapon_count: { max: 20 },
      block_whitelist: { type_ids: [], subtype_ids: [] },
      block_blacklist: { rules: [] },
    };
    onChange([...rules, { rule_type, params: defaults[rule_type] }]);
  };
  const update = (i: number, params: any) =>
    onChange(rules.map((r, idx) => (idx === i ? { ...r, params } : r)));
  const remove = (i: number) => onChange(rules.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-3">
      {rules.map((r, i) => (
        <div key={i} className="rounded-xl border border-border p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium text-sm">{RULE_LABELS[r.rule_type]}</span>
            <button className="text-bad text-xs" onClick={() => remove(i)}>
              Remove
            </button>
          </div>
          <RuleParams rule={r} onChange={(p) => update(i, p)} />
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        {(Object.keys(RULE_LABELS) as RequirementType[]).map((rt) => (
          <button key={rt} className="btn-ghost text-xs py-1" onClick={() => add(rt)}>
            + {RULE_LABELS[rt]}
          </button>
        ))}
      </div>
    </div>
  );
}

function NumField({ label, value, onChange }: { label: string; value: any; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        className="input"
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function RuleParams({ rule, onChange }: { rule: Requirement; onChange: (p: any) => void }) {
  const p = rule.params || {};
  switch (rule.rule_type) {
    case "block_count":
      return (
        <div className="grid grid-cols-2 gap-3">
          <NumField label="Min" value={p.min} onChange={(v) => onChange({ ...p, min: v })} />
          <NumField label="Max" value={p.max} onChange={(v) => onChange({ ...p, max: v })} />
        </div>
      );
    case "pcu_limit":
      return <NumField label="Max PCU" value={p.max} onChange={(v) => onChange({ ...p, max: v })} />;
    case "weapon_count":
      return <NumField label="Max weapons" value={p.max} onChange={(v) => onChange({ ...p, max: v })} />;
    case "grid_size":
      return (
        <select
          className="input"
          value={p.size ?? "Large"}
          onChange={(e) => onChange({ ...p, size: e.target.value })}
        >
          <option value="Large">Large grid</option>
          <option value="Small">Small grid</option>
        </select>
      );
    case "block_whitelist":
      return (
        <div>
          <label className="label">Allowed TypeIds (comma-separated)</label>
          <input
            className="input"
            defaultValue={(p.type_ids || []).join(", ")}
            onBlur={(e) =>
              onChange({
                ...p,
                type_ids: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
          />
        </div>
      );
    case "block_blacklist":
      return (
        <div>
          <label className="label">
            Caps as <code>SubtypeId:max</code>, comma-separated
          </label>
          <input
            className="input"
            defaultValue={(p.rules || [])
              .map((r: any) => `${r.subtype_id || r.type_id}:${r.max}`)
              .join(", ")}
            onBlur={(e) =>
              onChange({
                ...p,
                rules: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean)
                  .map((pair) => {
                    const [id, max] = pair.split(":");
                    return { subtype_id: id.trim(), max: Number(max) || 0 };
                  }),
              })
            }
          />
        </div>
      );
    default:
      return null;
  }
}

export default function ShipClassesPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const isAdmin = hasRole("admin");
  const { data, isLoading } = useQuery({ queryKey: ["ship-classes"], queryFn: api.listShipClasses });

  const [editing, setEditing] = useState<ShipClass | null>(null);
  const [creating, setCreating] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["ship-classes"] });
  const del = useMutation({ mutationFn: api.deleteShipClass, onSuccess: invalidate });

  return (
    <div>
      <PageHeader
        title="Ship Classes"
        subtitle="Requirement sets that every blueprint of a class must satisfy."
        action={
          isAdmin && (
            <button className="btn-primary" onClick={() => setCreating(true)}>
              + New class
            </button>
          )
        }
      />

      {isLoading ? (
        <Spinner label="Loading classes…" />
      ) : !data?.length ? (
        <EmptyState title="No ship classes yet" hint={isAdmin ? "Create one to get started." : ""} />
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {data.map((c) => (
            <Card key={c.id}>
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold">{c.name}</h3>
                  {c.description && <p className="text-muted text-sm mt-0.5">{c.description}</p>}
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <button className="text-xs text-muted hover:text-ink" onClick={() => setEditing(c)}>
                      Edit
                    </button>
                    <button
                      className="text-xs text-bad"
                      onClick={() => confirm(`Delete ${c.name}?`) && del.mutate(c.id)}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                {c.requirements.length ? (
                  c.requirements.map((r, i) => (
                    <Badge key={i}>{describeRule(r)}</Badge>
                  ))
                ) : (
                  <span className="text-muted text-sm">No requirements</span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {(creating || editing) && (
        <ClassModal
          klass={editing}
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
    </div>
  );
}

function ClassModal({
  klass,
  onClose,
  onSaved,
}: {
  klass: ShipClass | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(klass?.name ?? "");
  const [description, setDescription] = useState(klass?.description ?? "");
  const [rules, setRules] = useState<Requirement[]>(klass?.requirements ?? []);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async () => {
      const payload = { name, description, requirements: rules };
      if (klass) return api.updateShipClass(klass.id, payload);
      return api.createShipClass(payload);
    },
    onSuccess: onSaved,
    onError: (e: any) => setError(e.message),
  });

  return (
    <Modal open onClose={onClose} title={klass ? "Edit ship class" : "New ship class"}>
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
          <label className="label">Requirements</label>
          <RuleEditor rules={rules} onChange={setRules} />
        </div>
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
