import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import type { Role } from "../api/types";

const ROLES: Role[] = ["member", "engineer", "commander", "admin"];

export default function AdminPage() {
  return (
    <div className="space-y-8">
      <PageHeader title="Admin" subtitle="Users, invite code, block data, and server settings." />
      <UsersSection />
      <SettingsSection />
      <BlockDataSection />
    </div>
  );
}

function UsersSection() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: api.listUsers });
  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => api.setRole(id, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <Card>
      <h2 className="font-bold mb-3">Users & roles</h2>
      {isLoading ? (
        <Spinner />
      ) : (
        <div className="divide-y divide-border">
          {data?.map((u) => (
            <div key={u.id} className="flex items-center justify-between py-2">
              <div>
                <div className="font-medium text-sm">{u.display_name}</div>
                <div className="text-xs text-muted">{u.email}</div>
              </div>
              {u.id === user?.id ? (
                <Badge tone="amber">{u.role} (you)</Badge>
              ) : (
                <select
                  className="input max-w-[10rem]"
                  value={u.role}
                  onChange={(e) => setRole.mutate({ id: u.id, role: e.target.value })}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function SettingsSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const [invite, setInvite] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (payload: any) => api.updateSettings(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const inviteValue = invite ?? data?.invite_code ?? "";

  return (
    <Card>
      <h2 className="font-bold mb-3">Registration & server</h2>
      <div className="space-y-4 max-w-md">
        <div>
          <label className="label">Invite code (required to register)</label>
          <div className="flex gap-2">
            <input className="input" value={inviteValue} onChange={(e) => setInvite(e.target.value)} />
            <button
              className="btn-primary"
              onClick={() => save.mutate({ invite_code: inviteValue })}
              disabled={save.isPending}
            >
              Save
            </button>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={data?.server_push_enabled ?? false}
            onChange={(e) => save.mutate({ server_push_enabled: e.target.checked })}
          />
          Enable dedicated-server push (feature flag)
        </label>
      </div>
    </Card>
  );
}

function BlockDataSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["block-data"], queryFn: api.blockDataStats });
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const refresh = useMutation({
    mutationFn: () => api.refreshBlockData(file!),
    onSuccess: (res: any) => {
      setMsg(`Parsed ${res.parsed}, upserted ${res.upserted}.`);
      qc.invalidateQueries({ queryKey: ["block-data"] });
    },
    onError: (e: any) => setMsg(e.message),
  });

  return (
    <Card>
      <h2 className="font-bold mb-3">Block data (PCU / weapons)</h2>
      <div className="text-sm text-muted mb-3">
        {data ? (
          <>
            {data.count} block definitions · last updated{" "}
            {data.updated_at ? new Date(data.updated_at).toLocaleString() : "—"}
          </>
        ) : (
          <Spinner />
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 max-w-lg">
        <input
          type="file"
          accept=".sbc,.zip"
          className="input flex-1"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          className="btn-primary"
          disabled={!file || refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          {refresh.isPending ? "Uploading…" : "Refresh from CubeBlocks*.sbc"}
        </button>
      </div>
      {msg && <div className="text-sm mt-2">{msg}</div>}
    </Card>
  );
}
