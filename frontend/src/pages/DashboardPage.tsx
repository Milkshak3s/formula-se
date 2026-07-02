import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { Card, PageHeader } from "../components/ui";

function Stat({ label, value, to }: { label: string; value: number | string; to: string }) {
  return (
    <Link to={to} className="card p-5 hover:border-amber transition-colors block">
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-muted text-sm mt-1">{label}</div>
    </Link>
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
