export type Role = "member" | "engineer" | "commander" | "admin";

export const ROLE_LEVEL: Record<Role, number> = {
  member: 0,
  engineer: 1,
  commander: 2,
  admin: 3,
};

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  created_at: string;
}

export type RequirementType =
  | "block_count"
  | "grid_size"
  | "pcu_limit"
  | "weapon_count"
  | "block_whitelist"
  | "block_blacklist";

export interface Requirement {
  id?: string;
  rule_type: RequirementType;
  params: Record<string, any>;
}

export interface ShipClass {
  id: string;
  name: string;
  description: string;
  created_at: string;
  requirements: Requirement[];
}

export interface Blueprint {
  id: string;
  slot_id: string;
  uploader_id: string | null;
  name: string;
  stats: Record<string, any>;
  status: string;
  created_at: string;
  has_thumbnail: boolean;
}

export interface BlueprintHistory {
  id: string;
  name: string;
  status: string;
  stats: Record<string, any>;
  uploader_name: string | null;
  has_thumbnail: boolean;
  created_at: string;
}

export interface Slot {
  id: string;
  ship_class_id: string;
  name: string;
  created_at: string;
  ship_class_name: string | null;
  active_blueprint: Blueprint | null;
}

export interface StartSlot {
  id: string;
  map_id: string;
  name: string;
  position_index: number;
  gps_x: number;
  gps_y: number;
  gps_z: number;
  ship_class_ids: string[];
}

export interface GameMap {
  id: string;
  name: string;
  description: string;
  created_at: string;
  start_slots: StartSlot[];
}

export type PreparedWorldStatus =
  | "queued"
  | "processing"
  | "ready"
  | "failed"
  | "expired";

export interface PreparedWorld {
  id: string;
  map_id: string;
  name: string;
  status: PreparedWorldStatus;
  error: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface RuleResult {
  rule: string;
  param: Record<string, any>;
  measured: any;
  allowed: any;
  passed: boolean;
  detail: string;
}

export interface ValidationReport {
  passed: boolean;
  results: RuleResult[];
  stats: Record<string, any>;
}

export interface BlockDataStats {
  count: number;
  updated_at: string | null;
  sources: Record<string, number>;
}

export interface AppSettings {
  invite_code: string;
  server_push_enabled: boolean;
}

export interface TurnEvent {
  id: string;
  turn_number: number;
  advanced_by: string | null;
  advanced_by_name: string | null;
  created_at: string;
}

export interface TurnState {
  current_turn: number;
  last_advanced_at: string | null;
  last_advanced_by: string | null;
  last_advanced_by_name: string | null;
  history: TurnEvent[];
}

export type ResourceType =
  | "iron_ingot"
  | "nickel_ingot"
  | "silicon_wafer"
  | "cobalt_ingot";

export interface ResourceBalance {
  resource: ResourceType;
  amount: number;
}

export interface ResourceState {
  balances: ResourceBalance[];
}

export type HexTerrain =
  | "deep_space"
  | "asteroid_field"
  | "nebula"
  | "ice_field"
  | "planet"
  | "star_system";

export interface HexTile {
  id: string;
  q: number;
  r: number;
  terrain: HexTerrain;
  name: string;
}

export interface TerrainMap {
  terrain: HexTerrain;
  game_map_id: string;
  game_map_name: string;
}

export interface HexMap {
  id: number;
  name: string;
  radius: number;
  tiles: HexTile[];
  terrain_maps: TerrainMap[];
}

export type ServerReportedState =
  | "offline"
  | "idle"
  | "starting"
  | "running"
  | "error";

export interface GameServer {
  id: string;
  name: string;
  token_prefix: string;
  reported_state: ServerReportedState;
  online: boolean;
  desired_prepared_world_id: string | null;
  reported_prepared_world_id: string | null;
  last_error: string | null;
  last_seen_at: string | null;
  created_at: string;
}

// Returned only on register / rotate — carries the one-time plaintext token.
export interface ServerCreated extends GameServer {
  token: string;
}
