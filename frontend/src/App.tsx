import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ShipClassesPage from "./pages/ShipClassesPage";
import SlotsPage from "./pages/SlotsPage";
import MapsPage from "./pages/MapsPage";
import HexMapPage from "./pages/HexMapPage";
import FleetPage from "./pages/FleetPage";
import StationTypesPage from "./pages/StationTypesPage";
import StartWorldPage from "./pages/StartWorldPage";
import PreparedWorldsPage from "./pages/PreparedWorldsPage";
import AdminPage from "./pages/AdminPage";
import type { Role } from "./api/types";

function Protected({ children, role }: { children: JSX.Element; role?: Role }) {
  const { user, isLoading, hasRole } = useAuth();
  if (isLoading)
    return (
      <div className="min-h-screen grid place-items-center">
        <Spinner label="Loading…" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  if (role && !hasRole(role))
    return (
      <Layout>
        <div className="card p-8 text-center">
          <p className="font-semibold">Not authorized</p>
          <p className="text-muted text-sm mt-1">
            This area requires the {role} role.
          </p>
        </div>
      </Layout>
    );
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><DashboardPage /></Protected>} />
      <Route path="/ship-classes" element={<Protected><ShipClassesPage /></Protected>} />
      <Route path="/slots" element={<Protected><SlotsPage /></Protected>} />
      <Route path="/maps" element={<Protected><MapsPage /></Protected>} />
      <Route path="/sector-map" element={<Protected><HexMapPage /></Protected>} />
      <Route path="/fleet" element={<Protected><FleetPage /></Protected>} />
      <Route path="/station-types" element={<Protected><StationTypesPage /></Protected>} />
      <Route
        path="/start-world"
        element={<Protected role="commander"><StartWorldPage /></Protected>}
      />
      <Route
        path="/prepared-worlds"
        element={<Protected><PreparedWorldsPage /></Protected>}
      />
      <Route path="/admin" element={<Protected role="admin"><AdminPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
