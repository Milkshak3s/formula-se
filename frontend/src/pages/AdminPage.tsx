import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import type { Role } from "../api/types";

const ROLES: Role[] = ["member", "engineer", "commander", "admin"];

export default function AdminPage() {
  return (
    <div className="space-y-8">
      <PageHeader title="Admin" subtitle="Users, invite code, block data, and server settings." />
      <UsersSection />
      <SettingsSection />
      <ServersSection />
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

function ServersSection() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data, isLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: api.listServers,
  });
  const [name, setName] = useState("");
  // Plaintext token from the most recent register/rotate — shown once.
  const [newToken, setNewToken] = useState<{ name: string; token: string } | null>(
    null,
  );

  const showToken = (s: { name: string; token: string }) => {
    setNewToken({ name: s.name, token: s.token });
    qc.invalidateQueries({ queryKey: ["servers"] });
  };

  const create = useMutation({
    mutationFn: () => api.createServer(name.trim()),
    onSuccess: (s) => {
      setName("");
      showToken(s);
    },
    onError: (e: any) => toast(e.message ?? "Failed to register", "error"),
  });
  const rotate = useMutation({
    mutationFn: (id: string) => api.rotateServerToken(id),
    onSuccess: showToken,
    onError: (e: any) => toast(e.message ?? "Failed to rotate", "error"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteServer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
    onError: (e: any) => toast(e.message ?? "Failed to delete", "error"),
  });

  return (
    <Card>
      <h2 className="font-bold mb-3">Dedicated servers</h2>
      <p className="text-sm text-muted mb-3">
        Register each Space Engineers host running the agent. The token is shown
        once — copy it into the agent's config. Enable “dedicated-server push”
        above to allow Start/Stop from Prepared Worlds.
      </p>

      <div className="flex gap-2 max-w-md mb-4">
        <input
          className="input"
          placeholder="Server name (e.g. Main Arena)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button
          className="btn-primary"
          disabled={!name.trim() || create.isPending}
          onClick={() => create.mutate()}
        >
          Register
        </button>
      </div>

      {newToken && (
        <div className="card p-3 mb-4 bg-cream">
          <div className="text-sm font-medium mb-1">
            Token for “{newToken.name}” — copy it now, it won't be shown again:
          </div>
          <div className="flex gap-2">
            <input
              className="input font-mono text-xs"
              readOnly
              value={newToken.token}
              onFocus={(e) => e.currentTarget.select()}
            />
            <button
              className="btn-ghost text-xs"
              onClick={() => {
                navigator.clipboard?.writeText(newToken.token);
                toast("Copied", "success");
              }}
            >
              Copy
            </button>
            <button
              className="btn-ghost text-xs"
              onClick={() => setNewToken(null)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <Spinner />
      ) : !data?.length ? (
        <div className="text-sm text-muted">No servers registered.</div>
      ) : (
        <div className="divide-y divide-border">
          {data.map((s) => (
            <div key={s.id} className="flex items-center justify-between py-2 gap-3">
              <div className="min-w-0">
                <div className="font-medium text-sm flex items-center gap-2">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      s.online ? "bg-good" : "bg-muted/40"
                    }`}
                  />
                  <span className="truncate">{s.name}</span>
                  <Badge
                    tone={
                      s.reported_state === "running"
                        ? "good"
                        : s.reported_state === "error"
                          ? "bad"
                          : "neutral"
                    }
                  >
                    {s.reported_state}
                  </Badge>
                </div>
                <div className="text-xs text-muted font-mono">
                  {s.token_prefix}… · last seen{" "}
                  {s.last_seen_at
                    ? new Date(s.last_seen_at).toLocaleString()
                    : "never"}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  className="btn-ghost text-xs"
                  disabled={rotate.isPending}
                  onClick={() => rotate.mutate(s.id)}
                >
                  Rotate token
                </button>
                <button
                  className="btn-ghost text-xs text-bad"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (confirm(`Delete server “${s.name}”?`)) remove.mutate(s.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
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
