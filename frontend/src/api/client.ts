import type {
  AppSettings,
  BlockDataStats,
  Blueprint,
  BlueprintHistory,
  GameMap,
  GameServer,
  HexMap,
  HexTerrain,
  HexTile,
  PreparedWorld,
  Requirement,
  ServerCreated,
  ShipClass,
  Slot,
  TurnState,
  User,
} from "./types";

export class ApiError extends Error {
  status: number;
  body: any;
  constructor(status: number, message: string, body: any) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers:
      options.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    const message =
      body?.detail || body?.message || `Request failed (${res.status})`;
    throw new ApiError(res.status, message, body);
  }
  return body as T;
}

const json = (data: unknown): RequestInit => ({ body: JSON.stringify(data) });

export const api = {
  // --- auth ---
  me: () => request<User>("/api/auth/me"),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", ...json({ email, password }) }),
  register: (data: {
    email: string;
    display_name: string;
    password: string;
    invite_code: string;
  }) => request<User>("/api/auth/register", { method: "POST", ...json(data) }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  // --- users ---
  listUsers: () => request<User[]>("/api/users"),
  setRole: (id: string, role: string) =>
    request<User>(`/api/users/${id}`, { method: "PATCH", ...json({ role }) }),

  // --- ship classes ---
  listShipClasses: () => request<ShipClass[]>("/api/ship-classes"),
  createShipClass: (data: {
    name: string;
    description: string;
    requirements: Requirement[];
  }) => request<ShipClass>("/api/ship-classes", { method: "POST", ...json(data) }),
  updateShipClass: (id: string, data: Partial<ShipClass>) =>
    request<ShipClass>(`/api/ship-classes/${id}`, { method: "PATCH", ...json(data) }),
  deleteShipClass: (id: string) =>
    request<void>(`/api/ship-classes/${id}`, { method: "DELETE" }),

  // --- slots ---
  listSlots: () => request<Slot[]>("/api/slots"),
  createSlot: (ship_class_id: string, name: string) =>
    request<Slot>("/api/slots", { method: "POST", ...json({ ship_class_id, name }) }),
  deleteSlot: (id: string) => request<void>(`/api/slots/${id}`, { method: "DELETE" }),
  clearSlot: (id: string) =>
    request<void>(`/api/slots/${id}/blueprint`, { method: "DELETE" }),
  uploadBlueprint: (slotId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<any>(`/api/slots/${slotId}/blueprint`, {
      method: "POST",
      body: form,
    });
  },
  slotHistory: (slotId: string) =>
    request<BlueprintHistory[]>(`/api/slots/${slotId}/blueprints`),
  downloadBlueprint: (id: string) =>
    request<{ url: string }>(`/api/blueprints/${id}/download`),
  thumbnailUrl: (id: string) => `/api/blueprints/${id}/thumbnail`,

  // --- maps ---
  listMaps: () => request<GameMap[]>("/api/maps"),
  createMap: (name: string, description: string, file: File) => {
    const form = new FormData();
    form.append("name", name);
    form.append("description", description);
    form.append("file", file);
    return request<GameMap>("/api/maps", { method: "POST", body: form });
  },
  updateMap: (id: string, data: any) =>
    request<GameMap>(`/api/maps/${id}`, { method: "PATCH", ...json(data) }),
  deleteMap: (id: string) => request<void>(`/api/maps/${id}`, { method: "DELETE" }),

  // --- prepared worlds ---
  listPreparedWorlds: () => request<PreparedWorld[]>("/api/prepared-worlds"),
  getPreparedWorld: (id: string) =>
    request<PreparedWorld>(`/api/prepared-worlds/${id}`),
  createPreparedWorld: (data: {
    map_id: string;
    name: string;
    assignments: { start_slot_id: string; slot_id: string | null }[];
  }) => request<PreparedWorld>("/api/prepared-worlds", { method: "POST", ...json(data) }),
  downloadPreparedWorld: (id: string) =>
    request<{ url: string }>(`/api/prepared-worlds/${id}/download`),

  // --- servers ---
  listServers: () => request<GameServer[]>("/api/servers"),
  createServer: (name: string) =>
    request<ServerCreated>("/api/servers", { method: "POST", ...json({ name }) }),
  rotateServerToken: (id: string) =>
    request<ServerCreated>(`/api/servers/${id}/rotate-token`, { method: "POST" }),
  deleteServer: (id: string) =>
    request<void>(`/api/servers/${id}`, { method: "DELETE" }),
  startServer: (id: string, prepared_world_id: string) =>
    request<GameServer>(`/api/servers/${id}/start`, {
      method: "POST",
      ...json({ prepared_world_id }),
    }),
  stopServer: (id: string) =>
    request<GameServer>(`/api/servers/${id}/stop`, { method: "POST" }),

  // --- block data ---
  blockDataStats: () => request<BlockDataStats>("/api/block-definitions"),
  refreshBlockData: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<any>("/api/block-definitions", { method: "POST", body: form });
  },

  // --- turns ---
  getTurnState: () => request<TurnState>("/api/turns"),
  advanceTurn: () => request<TurnState>("/api/turns/advance", { method: "POST" }),

  // --- sector (hex) map ---
  getHexMap: () => request<HexMap>("/api/hex-map"),
  regenerateHexMap: (radius: number, name?: string) =>
    request<HexMap>("/api/hex-map/regenerate", {
      method: "POST",
      ...json({ radius, name }),
    }),
  updateHexTile: (id: string, data: { terrain?: HexTerrain; name?: string }) =>
    request<HexTile>(`/api/hex-map/tiles/${id}`, { method: "PATCH", ...json(data) }),

  // --- settings ---
  getSettings: () => request<AppSettings>("/api/settings"),
  updateSettings: (data: Partial<AppSettings>) =>
    request<AppSettings>("/api/settings", { method: "PATCH", ...json(data) }),
};

export type { Blueprint };
