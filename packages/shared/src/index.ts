export type UUID = string & { readonly __brand: unique symbol };

export function uuid(v: string): UUID {
  return v as UUID;
}

export interface BaseEntity {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export type CaseStatus = 'open' | 'in_progress' | 'closed' | 'archived';
export type CrimeType = 'fraud' | 'money_laundering' | 'ransomware' | 'darknet_market' | 'sanctions_evasion' | 'other';
export type AttributionStatus = 'unverified' | 'under_review' | 'attributed' | 'confirmed';
export type InvestigationStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface User extends BaseEntity {
  email: string;
  full_name: string;
  role: 'analyst' | 'supervisor' | 'admin';
  is_active: boolean;
  last_login_at?: string;
}

export interface Case extends BaseEntity {
  case_number: string;
  title: string;
  crime_type: CrimeType;
  description: string;
  status: CaseStatus;
  assigned_to?: UUID;
  metadata?: Record<string, unknown>;
}

export interface Wallet extends BaseEntity {
  address: string;
  chain: string;
  label?: string;
  attribution_status: AttributionStatus;
  risk_score: number;
  entity_name?: string;
  entity_confidence?: 'CONFIRMED' | 'HIGH_CONFIDENCE' | 'PROBABLE' | 'UNKNOWN';
  first_seen_tx_hash?: string;
  metadata?: Record<string, unknown>;
}

export interface Transaction extends BaseEntity {
  wallet_id: UUID;
  tx_hash: string;
  block_number: number;
  timestamp: string;
  from_address: string;
  to_address: string;
  value: string;
  value_usd?: number;
  token_address?: string;
  token_symbol?: string;
  method?: string;
  is_suspicious: boolean;
  metadata?: Record<string, unknown>;
}

export interface InvestigationRun extends BaseEntity {
  case_id: UUID;
  wallet_id: UUID;
  status: InvestigationStatus;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  config?: Record<string, unknown>;
  result_summary?: Record<string, unknown>;
}

export interface Report extends BaseEntity {
  case_id: UUID;
  investigation_run_id?: UUID;
  title: string;
  summary: string;
  findings: Record<string, unknown>;
  risk_assessment: Record<string, unknown>;
  graph_snapshot?: Record<string, unknown>;
  generated_by: UUID;
  format: 'pdf' | 'json' | 'html';
  file_path?: string;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: string;
  services: {
    database: 'connected' | 'disconnected';
    neo4j: 'connected' | 'disconnected';
    redis: 'connected' | 'disconnected';
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export const CHAINS = {
  ethereum: { id: 1, name: 'Ethereum', symbol: 'ETH', explorer: 'https://etherscan.io' },
  polygon: { id: 137, name: 'Polygon', symbol: 'MATIC', explorer: 'https://polygonscan.com' },
} as const;

export type ChainId = keyof typeof CHAINS;
export type ChainConfig = typeof CHAINS[ChainId];