"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { formatAddress, formatCurrency } from "@/lib/utils";
import { analysisApi, graphApi } from "@/lib/api";
import {
  Search,
  Target,
  GitBranch,
  Layers,
  Settings,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Download,
  AlertTriangle,
  CheckCircle,
  Info,
} from "lucide-react";
import ReactFlow, { Background, Controls, MiniMap, Node, Edge, addEdge, Connection, NodeTypes, EdgeTypes } from "reactflow";
import "reactflow/dist/style.css";

interface GraphNode {
  id: string;
  type: "wallet" | "entity" | "transaction";
  address?: string;
  chain?: string;
  label?: string;
  name?: string;
  entity_type?: string;
  confidence?: string;
  risk_score?: number;
  tx_hash?: string;
  value?: string;
  value_usd?: number;
}

interface GraphEdge {
  from: string;
  to: string;
  value?: string;
  tx_hash?: string;
}

interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const nodeTypes: NodeTypes = {
  wallet: WalletNode,
  entity: EntityNode,
  transaction: TransactionNode,
};

const edgeTypes: EdgeTypes = {
  default: CustomEdge,
};

function WalletNode({ data }: Node<GraphNode>) {
  const riskColor = data.risk_score
    ? data.risk_score >= 75 ? "border-destructive bg-destructive/10" 
      : data.risk_score >= 50 ? "border-amber-400 bg-amber-400/10"
      : data.risk_score >= 25 ? "border-yellow-400 bg-yellow-400/10"
      : "border-green-400 bg-green-400/10"
    : "border-primary bg-primary/10";

  return (
    <div className={`p-3 rounded-lg border-2 ${riskColor} min-w-[180px] text-center`}>
      <div className="flex items-center justify-center gap-2 mb-1">
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
          <GitBranch className="w-4 h-4 text-primary" />
        </div>
        <Badge variant="outline" className="text-xs">{data.chain}</Badge>
      </div>
      <p className="font-mono text-xs break-all mb-1">{formatAddress(data.address || "")}</p>
      {data.label && <p className="font-medium text-sm text-primary">{data.label}</p>}
      <p className="text-xs text-muted-foreground">Risk: {data.risk_score || 0}</p>
      {data.entity_name && (
        <Badge variant="secondary" className="mt-1 text-xs">{data.entity_name}</Badge>
      )}
    </div>
  );
}

function EntityNode({ data }: Node<GraphNode>) {
  const confidenceColors: Record<string, string> = {
    CONFIRMED: "border-green-400 bg-green-400/10",
    HIGH_CONFIDENCE: "border-blue-400 bg-blue-400/10",
    PROBABLE: "border-amber-400 bg-amber-400/10",
    UNKNOWN: "border-muted-foreground bg-muted",
  };
  const color = confidenceColors[data.confidence || "UNKNOWN"] || "border-muted-foreground bg-muted";

  return (
    <div className={`p-3 rounded-lg border-2 ${color} min-w-[180px] text-center`}>
      <div className="flex items-center justify-center gap-2 mb-1">
        <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
          <Layers className="w-4 h-4 text-purple-400" />
        </div>
        <Badge variant="outline" className="text-xs capitalize">{data.entity_type}</Badge>
      </div>
      <p className="font-semibold text-sm">{data.name}</p>
      <p className="font-mono text-xs break-all mb-1 text-muted-foreground">{formatAddress(data.address || "")}</p>
      <Badge 
        variant={data.confidence === "CONFIRMED" ? "success" : data.confidence === "HIGH_CONFIDENCE" ? "info" : data.confidence === "PROBABLE" ? "warning" : "secondary"}
        className="text-xs"
      >
        {data.confidence}
      </Badge>
    </div>
  );
}

function TransactionNode({ data }: Node<GraphNode>) {
  return (
    <div className="p-2 rounded-lg border border-tracex-border bg-tracex-surface min-w-[140px] text-center">
      <div className="flex items-center justify-center gap-1 mb-1">
        <div className="w-6 h-6 rounded bg-amber-500/20 flex items-center justify-center">
          <GitBranch className="w-3 h-3 text-amber-400" />
        </div>
        <Badge variant="outline" className="text-xs">{data.token_symbol || "TX"}</Badge>
      </div>
      <p className="font-mono text-xs break-all mb-1">{formatAddress(data.tx_hash || "")}</p>
      <p className="text-xs text-muted-foreground">{data.value_usd ? formatCurrency(data.value_usd) : data.value}</p>
    </div>
  );
}

function CustomEdge({ id, source, target, data }: Edge) {
  return (
    <>
      <path
        strokeWidth={2}
        stroke="currentColor"
        fill="none"
        d={data.path}
        style={{ strokeDasharray: data.dashed ? "5,5" : undefined }}
      />
      <marker
        id={`arrow-${id}`}
        markerWidth={10}
        markerHeight={10}
        refX={8}
        refY={3}
        orient="auto"
        markerUnits="strokeWidth"
      >
        <path d="M0,0 L0,6 L9,3 z" fill="currentColor" />
      </marker>
    </>
  );
}

export default function GraphPage() {
  const [walletId, setWalletId] = useState("");
  const [caseId, setCaseId] = useState("");
  const [depth, setDepth] = useState(2);
  const [loading, setLoading] = useState(false);
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });

  const rfRef = useRef<ReactFlow<GraphNode, GraphEdge>>(null);

  const fetchGraph = async () => {
    if (!walletId) {
      setError("Wallet ID is required");
      return;
    }

    setLoading(true);
    setError(null);
    setSubgraph(null);

    try {
      const response = await graphApi.getSubgraph({ addresses: [walletId], chain: "Ethereum", depth });
      setSubgraph(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch graph");
    } finally {
      setLoading(false);
    }
  };

  const onNodesChange = (changes: any) => {
    // Handle node changes if needed
  };

  const onEdgesChange = (changes: any) => {
    // Handle edge changes if needed
  };

  const onConnect = (connection: Connection) => {
    // Handle new connections
  };

  const nodes = subgraph?.nodes.map(n => ({
    id: n.id,
    type: n.type,
    position: { x: Math.random() * 500, y: Math.random() * 500 },
    data: n,
  })) || [];

  const edges = subgraph?.edges.map((e, i) => ({
    id: `edge-${i}`,
    source: e.from,
    target: e.to,
    type: "default",
    animated: true,
    style: { strokeWidth: 2 },
    label: e.value ? formatCurrency(parseFloat(e.value) / 1e18 * 2000) : undefined,
    labelBgStyle: { fill: "rgba(0,0,0,0.8)", fillOpacity: 0.8 },
  })) || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Investigation Graph</h1>
          <p className="text-muted-foreground">Interactive fund flow visualization</p>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg">Graph Controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <Label htmlFor="wallet-id">Wallet Address / ID</Label>
              <div className="flex gap-2">
                <Input
                  id="wallet-id"
                  placeholder="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
                  value={walletId}
                  onChange={(e) => setWalletId(e.target.value)}
                />
                <Button onClick={fetchGraph} disabled={loading || !walletId}>
                  {loading ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4 mr-2" />
                      Load Graph
                    </>
                  )}
                </Button>
              </div>
            </div>
            <div>
              <Label htmlFor="depth">Depth</Label>
              <Slider
                id="depth"
                value={[depth]}
                max={4}
                min={1}
                step={1}
                onValueChange={([v]) => setDepth(v)}
                className="w-40"
              />
              <span className="text-sm text-muted-foreground">{depth} hops</span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => rfRef.current?.fitView()} disabled={!reactFlowInstance}>
                <Target className="w-4 h-4 mr-2" />
                Fit View
              </Button>
              <Button variant="outline" onClick={() => rfRef.current?.setViewport({ x: 0, y: 0, zoom: 1 })} disabled={!reactFlowInstance}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Reset
              </Button>
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </div>
          )}

          {subgraph && (
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span><CheckCircle className="w-4 h-4 inline mr-1 text-green-400" /> {subgraph.nodes.length} nodes</span>
              <span><GitBranch className="w-4 h-4 inline mr-1" /> {subgraph.edges.length} edges</span>
              <span>
                Wallets: {subgraph.nodes.filter(n => n.type === "wallet").length} | 
                Entities: {subgraph.nodes.filter(n => n.type === "entity").length} | 
                Transactions: {subgraph.nodes.filter(n => n.type === "transaction").length}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="h-[70vh]">
        <CardContent className="p-0 h-full">
          {subgraph && subgraph.nodes.length > 0 ? (
            <ReactFlow<GraphNode, GraphEdge>
              ref={rfRef}
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView={true}
              onViewportChange={setViewport}
            >
              <Background color="#1f2937" gap={16} />
              <Controls />
              <MiniMap
                nodeColor={(node) => {
                  if (node.type === "entity") return "#a855f7";
                  if (node.type === "wallet") return "#3b82f6";
                  return "#f59e0b";
                }}
                maskColor="rgba(0,0,0,0.8)"
              />
            </ReactFlow>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
              <GitBranch className="w-16 h-16 mb-4 opacity-30" />
              <p className="text-lg font-medium">No Graph Loaded</p>
              <p className="text-sm mt-1">Enter a wallet address and click "Load Graph" to visualize the fund flow</p>
              <div className="mt-6 p-4 rounded-lg bg-tracex-surface border border-tracex-border max-w-md text-left">
                <p className="font-medium mb-2">Quick Start:</p>
                <ol className="space-y-1 text-sm list-decimal list-inside">
                  <li>Go to <a href="/cases" className="text-primary underline">Cases</a> and select a case</li>
                  <li>Click on a wallet to view details</li>
                  <li>Copy the wallet ID or address</li>
                  <li>Paste it here and click Load Graph</li>
                </ol>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {subgraph && (
        <Tabs defaultValue="nodes" className="space-y-4">
          <TabsList>
            <TabsTrigger value="nodes">Nodes ({subgraph.nodes.length})</TabsTrigger>
            <TabsTrigger value="edges">Edges ({subgraph.edges.length})</TabsTrigger>
            <TabsTrigger value="entities">Entities ({subgraph.nodes.filter(n => n.type === "entity").length})</TabsTrigger>
          </TabsList>

          <TabsContent value="nodes">
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-tracex-border">
                    <th className="text-left p-2 font-medium">ID</th>
                    <th className="text-left p-2 font-medium">Type</th>
                    <th className="text-left p-2 font-medium">Address</th>
                    <th className="text-left p-2 font-medium">Label</th>
                    <th className="text-left p-2 font-medium">Risk</th>
                    <th className="text-left p-2 font-medium">Entity</th>
                  </tr>
                </thead>
                <tbody>
                  {subgraph.nodes.map((n) => (
                    <tr key={n.id} className="border-b border-tracex-border/50">
                      <td className="p-2 font-mono text-xs">{n.id.split(":").pop()?.slice(0, 20)}...</td>
                      <td className="p-2">
                        <Badge variant="outline" className="capitalize">{n.type}</Badge>
                      </td>
                      <td className="p-2 font-mono text-xs">{formatAddress(n.address || "")}</td>
                      <td className="p-2">{n.label || n.name || "-"}</td>
                      <td className="p-2">
                        {n.risk_score !== undefined && (
                          <span className={n.risk_score >= 75 ? "text-destructive" : n.risk_score >= 50 ? "text-amber-400" : "text-green-400"}>
                            {n.risk_score}
                          </span>
                        )}
                      </td>
                      <td className="p-2">
                        {n.entity_name && (
                          <Badge variant="secondary" className="text-xs">{n.entity_name}</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          <TabsContent value="edges">
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-tracex-border">
                    <th className="text-left p-2 font-medium">From</th>
                    <th className="text-left p-2 font-medium">To</th>
                    <th className="text-left p-2 font-medium">Value (ETH)</th>
                    <th className="text-left p-2 font-medium">Tx Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {subgraph.edges.map((e, i) => (
                    <tr key={i} className="border-b border-tracex-border/50">
                      <td className="p-2 font-mono text-xs">{formatAddress(e.from.split(":").pop() || "")}</td>
                      <td className="p-2 font-mono text-xs">{formatAddress(e.to.split(":").pop() || "")}</td>
                      <td className="p-2">{e.value ? (parseFloat(e.value) / 1e18).toFixed(4) : "-"}</td>
                      <td className="p-2 font-mono text-xs">{formatAddress(e.tx_hash || "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          <TabsContent value="entities">
            {subgraph.nodes.filter(n => n.type === "entity").length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Layers className="w-12 h-12 mx-auto mb-4 opacity-30" />
                <p className="text-lg font-medium">No Entities Found</p>
                <p className="text-sm mt-1">Run entity enrichment to identify VASPs and mixers</p>
              </div>
            ) : (
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-tracex-border">
                      <th className="text-left p-2 font-medium">Name</th>
                      <th className="text-left p-2 font-medium">Type</th>
                      <th className="text-left p-2 font-medium">Address</th>
                      <th className="text-left p-2 font-medium">Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subgraph.nodes.filter(n => n.type === "entity").map((n) => (
                      <tr key={n.id} className="border-b border-tracex-border/50">
                        <td className="p-2 font-medium">{n.name}</td>
                        <td className="p-2">
                          <Badge variant="outline" className="capitalize">{n.entity_type}</Badge>
                        </td>
                        <td className="p-2 font-mono text-xs">{formatAddress(n.address || "")}</td>
                        <td className="p-2">
                          <Badge 
                            variant={n.confidence === "CONFIRMED" ? "success" : n.confidence === "HIGH_CONFIDENCE" ? "info" : n.confidence === "PROBABLE" ? "warning" : "secondary"}
                          >
                            {n.confidence}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}