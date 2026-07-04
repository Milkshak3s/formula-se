import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Badge, Card, EmptyState, Modal, PageHeader, Spinner } from "../components/ui";
import type {
  GameServer,
  PreparedWorld,
  PreparedWorldStatus,
  ServerReportedState,
} from "../api/types";

const STATUS_TONE: Record<PreparedWorldStatus, "neutral" | "good" | "bad" | "amber"> = {
  queued: "amber",
  processing: "amber",
  ready: "good",
  failed: "bad",
  expired: "neutral",
};

const SERVER_TONE: Record<ServerReportedState, "neutral" | "good" | "bad" | "amber"> = {
  offline: "neutral",
  idle: "neutral",
  starting: "amber",
  running: "good",
  error: "bad",
};

function OnlineDot({ online }: { online: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${online ? "bg-good" : "bg-muted/40"}`}
      title={online ? "online" : "offline"}
    />
  );
}

export default function PreparedWorldsPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canControl = hasRole("commander");

  const { data, isLoading } = useQuery({
    queryKey: ["prepared-worlds"],
    queryFn: api.listPreparedWorlds,
    // Poll so queued/processing rows update to ready without a manual refresh.
    refetchInterval: (query) => {
      const rows = (query.state.data as PreparedWorld[]) ?? [];
      return rows.some((w) => w.status === "queued" || w.status === "processing")
        ? 2500
        : false;
    },
  });

  const { data: servers } = useQuery({
    queryKey: ["servers"],
    queryFn: api.listServers,
    // Keep server status/heartbeat live while the page is open.
    refetchInterval: (query) =>
      ((query.state.data as GameServer[]) ?? []).length ? 4000 : false,
  });

  // The prepared world awaiting a server choice (only shown when >1 server).
  const [picking, setPicking] = useState<PreparedWorld | null>(null);

  const start = useMutation({
    mutationFn: ({ serverId, worldId }: { serverId: string; worldId: string }) =>
      api.startServer(serverId, worldId),
    onSuccess: () => {
      toast("Start order sent to the server.", "success");
      qc.invalidateQueries({ queryKey: ["servers"] });
      setPicking(null);
    },
    onError: (e: any) => toast(e.message ?? "Start failed", "error"),
  });

  const stop = useMutation({
    mutationFn: (serverId: string) => api.stopServer(serverId),
    onSuccess: () => {
      toast("Stop order sent.", "success");
      qc.invalidateQueries({ queryKey: ["servers"] });
    },
    onError: (e: any) => toast(e.message ?? "Stop failed", "error"),
  });

  const download = async (id: string) => {
    try {
      const { url } = await api.downloadPreparedWorld(id);
      window.open(url, "_blank");
    } catch (e: any) {
      toast(e.message ?? "Download failed", "error");
    }
  };

  const onStart = (world: PreparedWorld) => {
    const list = servers ?? [];
    if (list.length === 1) start.mutate({ serverId: list[0].id, worldId: world.id });
    else setPicking(world);
  };

  // Servers currently desired-to-run or reporting-running a given world.
  const serversForWorld = (worldId: string) =>
    (servers ?? []).filter(
      (s) =>
        s.desired_prepared_world_id === worldId ||
        s.reported_prepared_world_id === worldId,
    );

  const hasServers = (servers ?? []).length > 0;

  return (
    <div>
      <PageHeader
        title="Prepared Worlds"
        subtitle="Generated saves. Downloads expire 24h after they're ready."
      />

      {hasServers && (
        <ServerStrip
          servers={servers!}
          canControl={canControl}
          onStop={(id) => stop.mutate(id)}
          stopping={stop.isPending}
        />
      )}

      {isLoading ? (
        <Spinner label="Loading…" />
      ) : !data?.length ? (
        <EmptyState title="No prepared worlds yet" hint="Commanders can Start a World." />
      ) : (
        <div className="space-y-3">
          {data.map((w) => {
            const on = serversForWorld(w.id);
            return (
              <Card key={w.id} className="flex items-center justify-between">
                <div>
                  <div className="font-semibold">{w.name}</div>
                  <div className="text-xs text-muted mt-0.5">
                    {new Date(w.created_at).toLocaleString()}
                    {w.error ? ` — ${w.error}` : ""}
                  </div>
                  {on.length > 0 && (
                    <div className="text-xs mt-1 text-muted">
                      {on
                        .map((s) => `▶ ${s.name} (${s.reported_state})`)
                        .join(" · ")}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <Badge tone={STATUS_TONE[w.status]}>{w.status}</Badge>
                  {w.status === "ready" && (
                    <button
                      className="btn-ghost text-xs py-1.5"
                      onClick={() => download(w.id)}
                    >
                      Download
                    </button>
                  )}
                  {w.status === "ready" && canControl && hasServers && (
                    <button
                      className="btn-primary text-xs py-1.5"
                      disabled={start.isPending}
                      onClick={() => onStart(w)}
                    >
                      Start
                    </button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        open={!!picking}
        onClose={() => setPicking(null)}
        title={picking ? `Start “${picking.name}” on…` : "Start on…"}
      >
        <div className="space-y-2">
          {(servers ?? []).map((s) => (
            <button
              key={s.id}
              className="w-full flex items-center justify-between card p-3 hover:border-amber disabled:opacity-50"
              disabled={start.isPending}
              onClick={() =>
                picking && start.mutate({ serverId: s.id, worldId: picking.id })
              }
            >
              <span className="flex items-center gap-2 font-medium text-sm">
                <OnlineDot online={s.online} />
                {s.name}
              </span>
              <Badge tone={SERVER_TONE[s.reported_state]}>{s.reported_state}</Badge>
            </button>
          ))}
        </div>
      </Modal>
    </div>
  );
}

function ServerStrip({
  servers,
  canControl,
  onStop,
  stopping,
}: {
  servers: GameServer[];
  canControl: boolean;
  onStop: (id: string) => void;
  stopping: boolean;
}) {
  return (
    <Card className="mb-4">
      <div className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">
        Servers
      </div>
      <div className="space-y-2">
        {servers.map((s) => {
          const busy =
            !!s.desired_prepared_world_id ||
            s.reported_state === "running" ||
            s.reported_state === "starting";
          return (
            <div key={s.id} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <OnlineDot online={s.online} />
                <span className="font-medium text-sm truncate">{s.name}</span>
                <Badge tone={SERVER_TONE[s.reported_state]}>{s.reported_state}</Badge>
                {s.reported_state === "error" && s.last_error && (
                  <span className="text-xs text-bad truncate">{s.last_error}</span>
                )}
              </div>
              {canControl && busy && (
                <button
                  className="btn-ghost text-xs py-1"
                  disabled={stopping}
                  onClick={() => onStop(s.id)}
                >
                  Stop
                </button>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
