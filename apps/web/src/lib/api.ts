import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/auth-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        "Content-Type": "application/json",
      },
      timeout: 30000,
    });

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const { accessToken } = useAuthStore.getState();
        if (accessToken) {
          config.headers = config.headers ?? {};
          config.headers.Authorization = `Bearer ${accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          useAuthStore.getState().logout();
          if (typeof window !== "undefined" && window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
        }
        return Promise.reject(error);
      }
    );
  }

  async get<T>(url: string, params?: Record<string, unknown>) {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: unknown, params?: Record<string, unknown>) {
    const response = await this.client.post<T>(url, data, { params });
    return response.data;
  }

  async patch<T>(url: string, data?: unknown) {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string) {
    const response = await this.client.delete<T>(url);
    return response.data;
  }
}

export const api = new ApiClient();

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Case {
  id: string;
  case_number: string;
  title: string;
  crime_type: string;
  description: string;
  status: string;
  assigned_to?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Wallet {
  id: string;
  case_id: string;
  address: string;
  chain: string;
  label?: string;
  attribution_status: string;
  risk_score: number;
  entity_name?: string;
  entity_confidence?: string;
  first_seen_tx_hash?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface InvestigationRun {
  id: string;
  case_id: string;
  wallet_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  config?: Record<string, unknown>;
  result_summary?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Report {
  id: string;
  case_id: string;
  investigation_run_id?: string;
  title: string;
  summary: string;
  findings: Record<string, unknown>;
  risk_assessment: Record<string, unknown>;
  graph_snapshot?: Record<string, unknown>;
  generated_by: string;
  format: string;
  file_path?: string;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  services: Record<string, string>;
}

export interface ChainInfo {
  chain_id: number;
  name: string;
  symbol: string;
  explorer: string;
  rpc_env: string;
}

export interface ValidateAddressResponse {
  valid: boolean;
  address?: string;
  original_address?: string;
  chain_id?: number;
  chain_name?: string;
  chain_symbol?: string;
  explorer_url?: string;
  detected_chain?: number;
  error?: string;
}

export interface WalletAnalyzeRequest {
  address: string;
  chain_id?: number;
  label?: string;
  trace_depth?: number;
  max_transactions?: number;
}

export interface WalletAnalyzeResponse {
  wallet: Wallet;
  investigation: InvestigationRun;
}

export interface TraceRequest {
  max_hops?: number;
  min_value_eth?: number;
}

export interface TraceResponse {
  root_address: string;
  wallets_traced: number;
  edges: Array<{
    from: string;
    to: string;
    value: string;
    value_eth: number;
    tx_hash: string;
    block: number;
    timestamp: string;
    hop: number;
  }>;
  paths: Array<{
    path: string[];
    length: number;
    total_value_eth: number;
  }>;
  max_hops_reached: number;
}

export interface WalletTransactionsResponse {
  items: Array<{
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
  }>;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GraphNode {
  id: string;
  type: "wallet" | "entity" | "transaction";
  address?: string;
  chain?: string;
  label?: string;
  name?: string;
  entity_type?: string;
  confidence?: string;
  risk_score?: number;
  entity_name?: string;
  entity_confidence?: string;
  tx_hash?: string;
  value?: string;
  value_usd?: number;
  token_symbol?: string;
}

// Raw shape of an edge as returned by GET/POST /graph/subgraph (see
// apps/api/src/graph/repository.py::get_subgraph). Relationship-specific
// fields (value, tx_hash, ...) are nested under `properties` rather than
// flattened, and there is no `path`/`dashed` field — those are UI-only
// concerns computed client-side (see CustomEdge in graph/page.tsx).
interface RawGraphEdge {
  from: string;
  to: string;
  type?: string;
  value?: string;
  tx_hash?: string;
  properties?: Record<string, unknown>;
}

export interface GraphEdge {
  from: string;
  to: string;
  type?: string;
  value?: string;
  tx_hash?: string;
  /**
   * Not sent by the backend. Synthesized here from the relationship `type`
   * so CustomEdge can render inferred/attribution links (e.g. BELONGS_TO)
   * as dashed and actual fund-flow relationships (SENT/RECEIVED) as solid.
   */
  dashed?: boolean;
}

export interface SubgraphRequest {
  addresses: string[];
  chain: string;
  depth?: number;
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface RawSubgraphResponse {
  nodes: GraphNode[];
  edges: RawGraphEdge[];
}

export interface PathToVASPRequest {
  wallet_id: string;
  max_hops?: number;
  min_confidence?: string;
}

export interface ClusterDetectionRequest {
  chain: string;
  min_cluster_size?: number;
}

export interface PatternDetectionRequest {
  chain: string;
  pattern_type: string;
  time_window_hours?: number;
}

export interface EntityLookupRequest {
  address: string;
  chain: string;
}

export const casesApi = {
  list: (params?: { page?: number; page_size?: number; status?: string; crime_type?: string; search?: string }) =>
    api.get<PaginatedResponse<Case>>("/cases", params),
  get: (id: string) => api.get<Case>(`/cases/${id}`),
  create: (data: Partial<Case>) => api.post<Case>("/cases", data),
  update: (id: string, data: Partial<Case>) => api.patch<Case>(`/cases/${id}`, data),
  delete: (id: string) => api.delete<void>(`/cases/${id}`),
};

export const walletsApi = {
  list: (params?: { case_id?: string; chain?: string; attribution_status?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Wallet>>("/wallets", params),
  get: (id: string) => api.get<Wallet>(`/wallets/${id}`),
  create: (data: Partial<Wallet> & { case_id: string }) => api.post<Wallet>("/wallets", data),
  update: (id: string, data: Partial<Wallet>) => api.patch<Wallet>(`/wallets/${id}`, data),
  delete: (id: string) => api.delete<void>(`/wallets/${id}`),
};

export const investigationsApi = {
  list: (params?: { case_id?: string; wallet_id?: string; status?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<InvestigationRun>>("/investigations", params),
  get: (id: string) => api.get<InvestigationRun>(`/investigations/${id}`),
  create: (data: { case_id: string; wallet_id: string; config?: Record<string, unknown> }) =>
    api.post<InvestigationRun>("/investigations", data),
  update: (id: string, data: Partial<InvestigationRun>) => api.patch<InvestigationRun>(`/investigations/${id}`, data),
};

export const reportsApi = {
  list: (params?: { case_id?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Report>>("/reports", params),
  get: (id: string) => api.get<Report>(`/reports/${id}`),
  create: (data: Partial<Report> & { case_id: string; generated_by: string }) =>
    api.post<Report>("/reports", data),
};

export const healthApi = {
  check: () => api.get<HealthResponse>("/health"),
  ready: () => api.get<{ status: string }>("/health/ready"),
  live: () => api.get<{ status: string }>("/health/live"),
};

export const analysisApi = {
  validateAddress: (address: string, chain_id?: number) =>
    api.get<ValidateAddressResponse>("/analysis/wallets/validate", { address, chain_id }),
  listChains: () => api.get<{ chains: ChainInfo[] }>("/analysis/chains"),
  analyzeWallet: (caseId: string, data: WalletAnalyzeRequest) =>
    api.post<WalletAnalyzeResponse>(`/analysis/cases/${caseId}/wallets/analyze`, data),
  traceFundFlow: (walletId: string, data: TraceRequest) =>
    api.post<TraceResponse>(`/analysis/wallets/${walletId}/trace`, data),
  getWalletTransactions: (walletId: string, params?: { page?: number; page_size?: number }) =>
    api.get<WalletTransactionsResponse>(`/analysis/wallets/${walletId}/transactions`, params),
};

export const graphApi = {
  syncWallet: (walletId: string) =>
    api.post<{ status: string; wallet_id: string; transactions: number }>("/graph/wallets/sync", { wallet_id: walletId }),
  getSubgraph: async (data: SubgraphRequest): Promise<SubgraphResponse> => {
    const raw = await api.post<RawSubgraphResponse>("/graph/subgraph", data);
    return {
      nodes: raw.nodes,
      edges: raw.edges.map((e) => {
        const props = e.properties ?? {};
        return {
          from: e.from,
          to: e.to,
          type: e.type,
          value: e.value ?? (props.value as string | undefined),
          tx_hash: e.tx_hash ?? (props.tx_hash as string | undefined),
          // SENT/RECEIVED are real on-chain fund movements; anything else
          // (e.g. BELONGS_TO, an entity attribution link) is inferred, so
          // render it dashed to visually distinguish it in the graph.
          dashed: !!e.type && e.type !== "SENT" && e.type !== "RECEIVED",
        };
      }),
    };
  },
  findPathsToVASP: (walletId: string, data: PathToVASPRequest) =>
    api.post(`/graph/wallets/${walletId}/paths-to-vasp`, data),
  checkMixer: (walletId: string, max_hops?: number) =>
    api.post(`/graph/wallets/${walletId}/mixer-check`, null, { max_hops }),
  detectPatterns: (data: PatternDetectionRequest) =>
    api.post("/graph/patterns/detect", data),
  detectClusters: (data: ClusterDetectionRequest) =>
    api.post("/graph/clusters/detect", data),
  getWalletStats: (walletId: string) =>
    api.get(`/graph/wallets/${walletId}/stats`),
  getWalletCentrality: (walletId: string, algorithm?: string) =>
    api.get(`/graph/wallets/${walletId}/centrality`, { algorithm }),
  getTemporalFlow: (walletId: string, start_date: string, end_date: string, bucket?: string) =>
    api.get(`/graph/wallets/${walletId}/temporal-flow`, { start_date, end_date, bucket }),
  lookupEntity: (data: EntityLookupRequest) =>
    api.post("/graph/entities/lookup", data),
  enrichWallet: (walletId: string) =>
    api.post(`/graph/entities/enrich`, { wallet_id: walletId }),
  syncEntities: () =>
    api.post("/graph/entities/sync"),
  health: () =>
    api.get("/graph/health"),
};

export interface RiskFactor {
  type: string;
  severity: string;
  score: number;
  weight: number;
  weighted_score: number;
  description: string;
  evidence: Record<string, any>;
  confidence: string;
}

export interface RiskAssessment {
  overall_score: number;
  risk_level: string;
  factors: RiskFactor[];
  summary: string;
  methodology: string;
  assessed_at: string;
}

export interface Attribution {
  entity_name: string;
  entity_type: string;
  address: string;
  chain: string;
  attribution_type: string;
  confidence: string;
  confidence_score: number;
  distance_hops: number;
  total_value_eth: number;
  evidence: Array<{
    source: string;
    evidence_type: string;
    description: string;
    confidence: string;
    data: Record<string, any>;
  }>;
  path: any;
}

export interface AttributionResponse {
  attributed: boolean;
  nearest_vasp: Attribution | null;
  all_attributions: Attribution[];
  summary: {
    exchanges_found: number;
    mixers_found: number;
    bridges_found: number;
    highest_confidence: number;
    average_hops: number;
  };
}

export interface CaseRiskSummary {
  case_id: string;
  case_number: string;
  total_wallets: number;
  chains: string[];
  risk_distribution: Record<string, number>;
  attribution: Record<string, number>;
  average_risk_score: number;
  top_risk_wallets: Array<{
    address: string;
    risk_score: number;
    label: string;
  }>;
}

export const riskApi = {
  assessWallet: (walletId: string) =>
    api.get<RiskAssessment>(`/risk/wallets/${walletId}/assess`),
  getAttribution: (walletId: string, max_hops?: number) =>
    api.get<AttributionResponse>(`/risk/wallets/${walletId}/attribution`, { max_hops }),
  attributeWallet: (walletId: string, max_hops?: number) =>
    api.post<Attribution[]>(`/risk/wallets/${walletId}/attribute`, null, { max_hops }),
  generateReport: (data: {
    case_id: string;
    investigation_run_id?: string;
    title?: string;
    template?: string;
    format?: string;
    generated_by: string;
  }) =>
    api.post<{ report_id: string; title: string; format: string; file_size: number; generated_at: string }>("/risk/reports/generate", data),
  downloadReport: (reportId: string) =>
    api.get(`/risk/reports/${reportId}/download`, { responseType: "blob" }),
  getCaseRiskSummary: (caseId: string) =>
    api.get<CaseRiskSummary>(`/risk/cases/${caseId}/risk-summary`),
};

export interface Capability {
  name: string;
  description: string;
  example_queries: string[];
}

export interface Evidence {
  source: string;
  evidence_type: string;
  description: string;
  confidence: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface AIQueryResponse {
  answer: string;
  query_type: string;
  confidence: string;
  evidence: Evidence[];
  follow_up_questions: string[];
  metadata: Record<string, any>;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface ChatSession {
  session_id: string;
  case_id?: string;
  messages: ChatMessage[];
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  case_id?: string;
  wallet_id?: string;
}

export interface ChatResponse {
  session_id: string;
  message: ChatMessage;
  suggested_actions: string[];
}

export interface CapabilitiesResponse {
  capabilities: Capability[];
  confidence_levels: Array<{ level: string; description: string }>;
}

export const aiApi = {
  query: (data: { query: string; case_id?: string; wallet_id?: string }) =>
    api.post<AIQueryResponse>("/ai/query", data),
  chat: (data: ChatRequest) =>
    api.post<ChatResponse>("/ai/chat", data),
  getChatHistory: (sessionId: string) =>
    api.get<ChatSession>(`/ai/chat/history/${sessionId}`),
  deleteChatHistory: (sessionId: string) =>
    api.delete(`/ai/chat/history/${sessionId}`),
  getCapabilities: () =>
    api.get<CapabilitiesResponse>("/ai/capabilities"),
  generateNarrative: (caseId: string, walletIds?: string[]) =>
    api.post<{ case_id: string; narrative: string; generated_at: string }>(`/ai/generate-narrative`, { case_id: caseId, wallet_ids: walletIds }),
};