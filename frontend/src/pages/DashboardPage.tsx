import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Card, PageHeader } from "../components/ui";

function Stat({ label, value, to }: { label: string; value: number | string; to: string }) {
  return (
    <Link to={to} className="card p-5 hover:border-amber transition-colors block">
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-muted text-sm mt-1">{label}</div>
    </Link>
  );
}

function TurnBanner() {
  const toast = useToast();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canAdvance = hasRole("commander");

  const { data } = useQuery({ queryKey: ["turn"], queryFn: api.getTurnState });

  const advance = useMutation({
    mutationFn: api.advanceTurn,
    onSuccess: (state) => {
      toast(`Advanced to turn ${state.current_turn}.`, "success");
      // Turn changes may drive other game systems — refresh everything.
      qc.invalidateQueries();
    },
    onError: (e: any) => toast(e.message ?? "Could not advance the turn", "error"),
  });

  const by = data?.last_advanced_by_name;
  const at = data?.last_advanced_at;

  return (
    <Card className="mb-6 flex items-center justify-between gap-4 border-amber/40">
      <div>
        <div className="text-xs font-semibold text-muted uppercase tracking-wide">
          Campaign turn
        </div>
        <div className="text-4xl font-bold mt-1 tabular-nums">
          {data?.current_turn ?? "—"}
        </div>
        <div className="text-xs text-muted mt-1">
          {at
            ? `Last advanced ${new Date(at).toLocaleString()}${by ? ` by ${by}` : ""}`
            : "Not advanced yet."}
        </div>
      </div>
      {canAdvance && (
        <button
          className="btn-primary shrink-0"
          disabled={advance.isPending}
          onClick={() => advance.mutate()}
        >
          {advance.isPending ? "Advancing…" : "Next turn →"}
        </button>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const slots = useQuery({ queryKey: ["slots"], queryFn: api.listSlots });
  const classes = useQuery({ queryKey: ["ship-classes"], queryFn: api.listShipClasses });
  const maps = useQuery({ queryKey: ["maps"], queryFn: api.listMaps });
  const worlds = useQuery({ queryKey: ["prepared-worlds"], queryFn: api.listPreparedWorlds });

  const filled = (slots.data ?? []).filter((s) => s.active_blueprint).length;

  return (
    <div>
      <PageHeader
        title={`Welcome, ${user?.display_name ?? ""}`}
        subtitle="Your league at a glance."
      />

      <TurnBanner />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Ship classes" value={classes.data?.length ?? 0} to="/ship-classes" />
        <Stat
          label="Slots filled"
          value={`${filled}/${slots.data?.length ?? 0}`}
          to="/slots"
        />
        <Stat label="Game maps" value={maps.data?.length ?? 0} to="/maps" />
        <Stat
          label="Prepared worlds"
          value={worlds.data?.length ?? 0}
          to="/prepared-worlds"
        />
      </div>

      <Card className="mt-6">
        <h2 className="font-bold mb-2">How Formula SE works</h2>
        <ol className="list-decimal list-inside text-muted text-sm space-y-1">
          <li>Admins define <b>Ship Classes</b> with validation requirements.</li>
          <li>Admins create <b>Blueprint Slots</b> to cap the ship pool per class.</li>
          <li>Engineers upload blueprints — validated against class rules on upload.</li>
          <li>Admins upload <b>Game Maps</b> and mark start positions per class.</li>
          <li>Commanders <b>Start a World</b>: pick a map, assign ships, download the save.</li>
        </ol>
      </Card>
    </div>
  );
}
