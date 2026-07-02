import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Badge, Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import type { PreparedWorld, PreparedWorldStatus } from "../api/types";

const STATUS_TONE: Record<PreparedWorldStatus, "neutral" | "good" | "bad" | "amber"> = {
  queued: "amber",
  processing: "amber",
  ready: "good",
  failed: "bad",
  expired: "neutral",
};

export default function PreparedWorldsPage() {
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

  const download = async (id: string) => {
    const { url } = await api.downloadPreparedWorld(id);
    window.open(url, "_blank");
  };

  return (
    <div>
      <PageHeader title="Prepared Worlds" subtitle="Generated saves. Downloads expire 24h after they're ready." />
      {isLoading ? (
        <Spinner label="Loading…" />
      ) : !data?.length ? (
        <EmptyState title="No prepared worlds yet" hint="Commanders can Start a World." />
      ) : (
        <div className="space-y-3">
          {data.map((w) => (
            <Card key={w.id} className="flex items-center justify-between">
              <div>
                <div className="font-semibold">{w.name}</div>
                <div className="text-xs text-muted mt-0.5">
                  {new Date(w.created_at).toLocaleString()}
                  {w.error ? ` — ${w.error}` : ""}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge tone={STATUS_TONE[w.status]}>{w.status}</Badge>
                {w.status === "ready" && (
                  <button className="btn-primary text-xs py-1.5" onClick={() => download(w.id)}>
                    Download
                  </button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
