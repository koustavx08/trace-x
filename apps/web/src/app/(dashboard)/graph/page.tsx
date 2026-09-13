"use client";

import { useCallback, useEffect, useState, useMemo, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { formatAddress, formatCurrency } from "@/lib/utils";
import {
  graphApi,
  walletsApi,
  reportsApi,
  GraphNode,
  GraphEdge,
  SubgraphResponse,
} from "@/lib/api";
import { GraphAICoPilot } from "@/components/graph/GraphAICoPilot";
import {
  Search,
  Target,
  GitBranch,
  Layers,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Copy,
  Check,
  X,
  ShieldAlert,
  Sparkles,
  ArrowRight,
  FileText,
  Scale,
  Loader2,
} from "lucide-react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  EdgeProps,
  NodeProps,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  Connection,
  NodeTypes,
  EdgeTypes,
  NodeChange,
  EdgeChange,
  getBezierPath,
  MarkerType,
  Position,
  ReactFlowInstance,
  Handle,
} from "reactflow";
import "reactflow/dist/style.css";
import dagre from "dagre";

// Pre-seeded Demo Scenarios for Instant 1-Click Evaluation
const DEMO_PRESETS = [
  {
    id: "defi",
    title: "DeFi Flash Loan Exploit",
    subtitle: "3,214.87 WETH · Uniswap V3 & Tornado Cash",
    address: "0xa241ec91A7D0c2c8bf11d01C168579Ee1201a209",
    badge: "96.5 Risk",
    badgeColor: "bg-red-500/10 text-red-600 border-red-200 dark:border-red-900/50",
    chain: "Ethereum",
  },
  {
    id: "lockbit",
    title: "LockBit 3.0 Ransomware",
    subtitle: "USD 1.05M in USDT · Layering & Arbitrum",
    address: "0x4eEE35E743a626F05f6e1cfaB340C04e791537b6",
    badge: "93.5 Risk",
    badgeColor: "bg-red-500/10 text-red-600 border-red-200 dark:border-red-900/50",
    chain: "Ethereum",
  },
  {
    id: "hydra",
    title: "Hydra Market Seizure",
    subtitle: "Vendor-Bond Escrow · Polygon Bridge",
    address: "0x7cd628D05a4977b0c114830e96052142ED4a7827",
    badge: "87 Risk",
    badgeColor: "bg-amber-500/10 text-amber-600 border-amber-200 dark:border-amber-900/50",
    chain: "Ethereum",
  },
  {
    id: "sanctions",
    title: "OFAC Sanctions Evasion",
    subtitle: "OFAC SDN Holdings · Railgun & Stargate",
    address: "0x3268F479AAc4A79bebbDEbE3b03AB9C4F56EeCDF",
    badge: "99 Risk",
    badgeColor: "bg-red-500/10 text-red-600 border-red-200 dark:border-red-900/50",
    chain: "Ethereum",
  },
];

function WalletNode({ data }: NodeProps<GraphNode>) {
  const riskScore = data.risk_score || 0;
  const riskBorder =
    riskScore >= 75
      ? "border-destructive bg-red-50/70 dark:bg-destructive/10"
      : riskScore >= 50
      ? "border-amber-400 bg-amber-50/70 dark:bg-amber-400/10"
      : riskScore >= 25
      ? "border-yellow-400 bg-yellow-50/70 dark:bg-yellow-400/10"
      : "border-green-400 bg-green-50/70 dark:bg-green-400/10";

  return (
    <div
      className={`p-3 rounded-2xl border-2 ${riskBorder} min-w-[200px] text-center cursor-pointer transition-all hover:scale-105 hover:shadow-lg bg-white dark:bg-[#1E2024] shadow-sm`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-primary !border-2 !border-white dark:!border-[#1E2024]"
      />
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
          <GitBranch className="w-3.5 h-3.5 text-primary" />
        </div>
        <Badge variant="outline" className="text-[10px] font-mono uppercase">
          {data.chain || "ETH"}
        </Badge>
      </div>
      <p className="font-mono text-xs font-semibold text-[#151B2B] dark:text-white mb-0.5">
        {formatAddress(data.address || "")}
      </p>
      {data.label && (
        <p className="font-medium text-xs text-primary truncate max-w-[180px] mx-auto">
          {data.label}
        </p>
      )}
      <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-gray-100 dark:border-gray-800 text-[11px]">
        <span className="text-muted-foreground">Risk Score</span>
        <span
          className={`font-bold ${
            riskScore >= 75
              ? "text-destructive"
              : riskScore >= 50
              ? "text-amber-500"
              : "text-green-600"
          }`}
        >
          {riskScore}/100
        </span>
      </div>
      {data.entity_name && (
        <Badge
          variant="secondary"
          className="mt-1.5 text-[10px] w-full justify-center truncate"
        >
          {data.entity_name}
        </Badge>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-primary !border-2 !border-white dark:!border-[#1E2024]"
      />
    </div>
  );
}

function EntityNode({ data }: NodeProps<GraphNode>) {
  const confidenceColors: Record<string, string> = {
    CONFIRMED: "border-green-500 bg-green-50/70 dark:bg-green-500/10",
    HIGH_CONFIDENCE: "border-blue-500 bg-blue-50/70 dark:bg-blue-500/10",
    PROBABLE: "border-amber-500 bg-amber-50/70 dark:bg-amber-500/10",
    UNKNOWN: "border-gray-300 bg-gray-50/70 dark:bg-muted",
  };
  const color =
    confidenceColors[data.confidence || "UNKNOWN"] ||
    "border-gray-300 bg-gray-50/70 dark:bg-muted";

  return (
    <div
      className={`p-3 rounded-2xl border-2 ${color} min-w-[200px] text-center cursor-pointer transition-all hover:scale-105 hover:shadow-lg bg-white dark:bg-[#1E2024] shadow-sm`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-purple-600 !border-2 !border-white dark:!border-[#1E2024]"
      />
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="w-7 h-7 rounded-lg bg-purple-500/10 flex items-center justify-center">
          <Layers className="w-3.5 h-3.5 text-purple-600" />
        </div>
        <Badge variant="outline" className="text-[10px] capitalize">
          {data.entity_type || "VASP"}
        </Badge>
      </div>
      <p className="font-bold text-xs text-[#151B2B] dark:text-white truncate max-w-[180px] mx-auto">
        {data.name}
      </p>
      <p className="font-mono text-[11px] text-muted-foreground mb-1.5">
        {formatAddress(data.address || "")}
      </p>
      <Badge
        variant={
          data.confidence === "CONFIRMED"
            ? "success"
            : data.confidence === "HIGH_CONFIDENCE"
            ? "info"
            : data.confidence === "PROBABLE"
            ? "warning"
            : "secondary"
        }
        className="text-[10px] w-full justify-center"
      >
        {data.confidence || "ATTRIBUTED"}
      </Badge>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-purple-600 !border-2 !border-white dark:!border-[#1E2024]"
      />
    </div>
  );
}

function TransactionNode({ data }: NodeProps<GraphNode>) {
  return (
    <div className="p-2.5 rounded-2xl border border-amber-300 dark:border-amber-500/30 bg-amber-50/50 dark:bg-[#1E2024] min-w-[170px] text-center cursor-pointer transition-all hover:scale-105 hover:shadow-lg shadow-sm">
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-amber-500 !border-2 !border-white dark:!border-[#1E2024]"
      />
      <div className="flex items-center justify-center gap-1.5 mb-1">
        <div className="w-5 h-5 rounded bg-amber-500/20 flex items-center justify-center">
          <GitBranch className="w-3 h-3 text-amber-600" />
        </div>
        <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400">
          {data.value_usd
            ? formatCurrency(data.value_usd)
            : data.value
            ? `${(parseFloat(data.value) / 1e18).toFixed(2)} ETH`
            : "TX"}
        </span>
      </div>
      <p className="font-mono text-[10px] text-muted-foreground truncate max-w-[150px] mx-auto">
        {formatAddress(data.tx_hash || "")}
      </p>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-amber-500 !border-2 !border-white dark:!border-[#1E2024]"
      />
    </div>
  );
}

function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition = Position.Bottom,
  targetPosition = Position.Top,
  style,
  markerEnd,
  data,
}: EdgeProps<GraphEdge>) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <path
      id={id}
      className="react-flow__edge-path"
      strokeWidth={2}
      stroke="currentColor"
      fill="none"
      d={edgePath}
      style={{ ...style, strokeDasharray: data?.dashed ? "5,5" : undefined }}
      markerEnd={markerEnd}
    />
  );
}

// Stable node and edge types defined outside component with window caching to eliminate ReactFlow Warning #002 during renders & Fast Refresh
const nodeTypes: NodeTypes =
  typeof window !== "undefined" && (window as unknown as { __TRACE_X_NODE_TYPES__?: NodeTypes }).__TRACE_X_NODE_TYPES__
    ? (window as unknown as { __TRACE_X_NODE_TYPES__: NodeTypes }).__TRACE_X_NODE_TYPES__
    : {
        wallet: WalletNode,
        entity: EntityNode,
        transaction: TransactionNode,
      };

if (typeof window !== "undefined") {
  (window as unknown as { __TRACE_X_NODE_TYPES__: NodeTypes }).__TRACE_X_NODE_TYPES__ = nodeTypes;
}

const edgeTypes: EdgeTypes =
  typeof window !== "undefined" && (window as unknown as { __TRACE_X_EDGE_TYPES__?: EdgeTypes }).__TRACE_X_EDGE_TYPES__
    ? (window as unknown as { __TRACE_X_EDGE_TYPES__: EdgeTypes }).__TRACE_X_EDGE_TYPES__
    : {
        default: CustomEdge,
      };

if (typeof window !== "undefined") {
  (window as unknown as { __TRACE_X_EDGE_TYPES__: EdgeTypes }).__TRACE_X_EDGE_TYPES__ = edgeTypes;
}

function layoutGraph(nodes: Node<GraphNode>[], edges: Edge[]): Node<GraphNode>[] {
  const NODE_WIDTH = 220;
  const NODE_HEIGHT = 110;

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 70, ranksep: 110 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  return nodes.map((node) => {
    const { x, y } = g.node(node.id) ?? { x: 0, y: 0 };
    return {
      ...node,
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
    };
  });
}

function GraphView() {
  const searchParams = useSearchParams();
  const initialWallet =
    searchParams.get("wallet") || searchParams.get("address") || "";
  const caseId = searchParams.get("case_id") || searchParams.get("caseId") || "";

  const [walletId, setWalletId] = useState(initialWallet);
  const [depth, setDepth] = useState(2);
  const [loading, setLoading] = useState(false);
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance<GraphNode, GraphEdge> | null>(null);
  const [, setViewport] = useState({ x: 0, y: 0, zoom: 1 });

  const [nodes, setNodes] = useState<Node<GraphNode>[]>([]);
  const [edges, setEdges] = useState<Edge<GraphEdge>[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [copied, setCopied] = useState(false);
  const [isAICoPilotOpen, setIsAICoPilotOpen] = useState(false);
  const router = useRouter();
  const [draftingReport, setDraftingReport] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  const handleFocusNode = useCallback(
    (identifier: string) => {
      if (!reactFlowInstance) return;
      const targetClean = identifier.trim().toLowerCase();
      const target = nodes.find(
        (n) =>
          n.id.toLowerCase() === targetClean ||
          (n.data.address && n.data.address.toLowerCase() === targetClean) ||
          (n.data.tx_hash && n.data.tx_hash.toLowerCase() === targetClean)
      );
      if (target) {
        reactFlowInstance.setCenter(
          target.position.x + 100,
          target.position.y + 50,
          { zoom: 1.3, duration: 800 }
        );
        setSelectedNode(target.data);
      }
    },
    [nodes, reactFlowInstance]
  );

  const handleDraftReport = async () => {
    if (!selectedNode) return;
    const targetAddress = selectedNode.address || selectedNode.tx_hash;
    if (!targetAddress) return;

    setDraftingReport(true);
    setDraftError(null);

    try {
      const entityName =
        selectedNode.name ||
        selectedNode.label ||
        selectedNode.entity_name ||
        (selectedNode.entity_type === "exchange" ? "Centralized Exchange (VASP)" : "Custodial VASP");

      await reportsApi.draftStatutoryNotice({
        wallet_address: targetAddress,
        entity_name: entityName,
        notice_type: "section_91_crpc",
        format: "pdf",
      });

      router.push("/reports");
    } catch (err) {
      console.error("Failed to draft statutory notice:", err);
      setDraftError(err instanceof Error ? err.message : "Failed to draft statutory notice");
    } finally {
      setDraftingReport(false);
    }
  };

  const fetchGraphWithAddress = useCallback(
    async (rawInput: string) => {
      let targetAddress = rawInput.trim();
      if (!targetAddress) {
        setError("Please enter a wallet address or select a demo scenario.");
        return;
      }

      setLoading(true);
      setError(null);
      setSelectedNode(null);

      try {
        // If input is a UUID, resolve it to an Ethereum address via walletsApi
        if (!targetAddress.startsWith("0x") && targetAddress.includes("-")) {
          try {
            const w = await walletsApi.get(targetAddress);
            if (w?.address) {
              targetAddress = w.address;
            }
          } catch {
            // fallback to original input
          }
        }

        const response = await graphApi.getSubgraph({
          addresses: [targetAddress],
          chain: "Ethereum",
          depth,
        });

        if (!response.nodes || response.nodes.length === 0) {
          setError(
            `No graph nodes found for ${targetAddress}. Try one of the pre-seeded demo cases above.`
          );
          setSubgraph(null);
        } else {
          setSubgraph(response);
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to connect to Neo4j graph repository"
        );
      } finally {
        setLoading(false);
      }
    },
    [depth]
  );

  const fetchGraph = () => {
    fetchGraphWithAddress(walletId);
  };

  const handleSelectPreset = (address: string) => {
    setWalletId(address);
    fetchGraphWithAddress(address);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Auto-load on mount if query param exists
  useEffect(() => {
    if (initialWallet) {
      setWalletId(initialWallet);
      fetchGraphWithAddress(initialWallet);
    }
  }, [initialWallet, fetchGraphWithAddress]);

  // Rebuild the ReactFlow node/edge state whenever a new subgraph is loaded
  useEffect(() => {
    if (!subgraph) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const rawNodes: Node<GraphNode>[] = subgraph.nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: { x: 0, y: 0 },
      data: n,
    }));

    const rawEdges: Edge<GraphEdge>[] = subgraph.edges.map((e, i) => ({
      id: `edge-${i}`,
      source: e.from,
      target: e.to,
      type: "default",
      animated: !e.dashed,
      style: { strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed },
      label: e.value
        ? formatCurrency((parseFloat(e.value) / 1e18) * 2500)
        : undefined,
      labelBgStyle: { fill: "rgba(255,255,255,0.9)", fillOpacity: 0.9 },
      data: e,
    }));

    setNodes(layoutGraph(rawNodes, rawEdges));
    setEdges(rawEdges);
  }, [subgraph]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) =>
      addEdge(
        {
          ...connection,
          type: "default",
          animated: false,
          style: { strokeWidth: 2 },
          data: {
            from: connection.source ?? "",
            to: connection.target ?? "",
            dashed: true,
          },
        },
        eds
      )
    );
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#151B2B] dark:text-white">
            Investigation Graph
          </h1>
          <p className="text-muted-foreground text-sm">
            Interactive multi-hop Neo4j fund flow & VASP attribution network
          </p>
        </div>
      </div>

      {/* Preset Showcase Bar */}
      <div className="p-3.5 rounded-2xl bg-white dark:bg-[#1E2024] border border-gray-100 dark:border-gray-800 shadow-sm space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          <Sparkles className="w-3.5 h-3.5 text-primary" />
          <span>Evaluation Showcase Presets (1-Click Load):</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {DEMO_PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => handleSelectPreset(preset.address)}
              className={`px-3 py-2 rounded-xl border text-xs font-medium transition-all flex items-center gap-2.5 hover:scale-[1.02] ${
                walletId.toLowerCase() === preset.address.toLowerCase()
                  ? "bg-primary text-white border-primary shadow-sm"
                  : "bg-gray-50/80 dark:bg-gray-900/50 border-gray-200 dark:border-gray-800 hover:border-primary/50 text-[#151B2B] dark:text-gray-200"
              }`}
            >
              <span className="font-semibold">{preset.title}</span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${preset.badgeColor}`}
              >
                {preset.badge}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Controls Card */}
      <Card className="rounded-2xl border-gray-100 dark:border-gray-800 shadow-sm bg-white dark:bg-[#1E2024]">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-semibold">
            Traversal Controls
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[240px]">
              <Label htmlFor="wallet-id" className="text-xs text-muted-foreground">
                Suspect Wallet Address / ID
              </Label>
              <div className="flex gap-2 mt-1.5">
                <Input
                  id="wallet-id"
                  placeholder="0xa241ec91A7D0c2c8bf11d01C168579Ee1201a209"
                  value={walletId}
                  onChange={(e) => setWalletId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && fetchGraph()}
                  className="font-mono text-sm rounded-xl"
                />
                <Button
                  onClick={fetchGraph}
                  disabled={loading || !walletId}
                  className="rounded-xl px-5"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Tracing...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4 mr-2" />
                      Trace Graph
                    </>
                  )}
                </Button>
              </div>
            </div>

            <div>
              <Label htmlFor="depth" className="text-xs text-muted-foreground">
                Trace Depth: <span className="font-semibold text-primary">{depth} hops</span>
              </Label>
              <div className="flex items-center gap-3 mt-2">
                <Slider
                  id="depth"
                  value={[depth]}
                  max={4}
                  min={1}
                  step={1}
                  onValueChange={([v]: number[]) => setDepth(v)}
                  className="w-36"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => reactFlowInstance?.fitView()}
                disabled={!reactFlowInstance}
                className="rounded-xl"
              >
                <Target className="w-4 h-4 mr-1.5" />
                Fit View
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  reactFlowInstance?.setViewport({ x: 0, y: 0, zoom: 1 })
                }
                disabled={!reactFlowInstance}
                className="rounded-xl"
              >
                <RefreshCw className="w-4 h-4 mr-1.5" />
                Reset
              </Button>
            </div>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {subgraph && (
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-1 border-t border-gray-100 dark:border-gray-800">
              <span className="flex items-center gap-1 font-medium text-green-600 dark:text-green-400">
                <CheckCircle className="w-3.5 h-3.5" /> {subgraph.nodes.length} Nodes Loaded
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <GitBranch className="w-3.5 h-3.5 text-primary" /> {subgraph.edges.length} Transaction Flows
              </span>
              <span>•</span>
              <span>
                Suspect Wallets: {subgraph.nodes.filter((n) => n.type === "wallet").length} |
                Attributed VASPs: {subgraph.nodes.filter((n) => n.type === "entity").length} |
                Transactions: {subgraph.nodes.filter((n) => n.type === "transaction").length}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Main Canvas Container with Inspector Panel */}
      <Card className="h-[72vh] rounded-2xl border-gray-100 dark:border-gray-800 shadow-sm relative overflow-hidden bg-white dark:bg-[#151B2B]">
        <CardContent className="p-0 h-full relative">
          {subgraph && subgraph.nodes.length > 0 ? (
            <>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onInit={setReactFlowInstance}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView={true}
                onMove={(_, vp) => setViewport(vp)}
                onNodeClick={(_, node) => setSelectedNode(node.data)}
                onPaneClick={() => setSelectedNode(null)}
              >
                <Background color="#94A3B8" gap={20} size={1} />
                <Controls className="!bg-white dark:!bg-[#1E2024] !border-gray-200 dark:!border-gray-800 !rounded-xl !shadow-sm" />
                <MiniMap
                  nodeColor={(node) => {
                    if (node.type === "entity") return "#9333ea";
                    if (node.type === "wallet") return "#3430D9";
                    return "#f59e0b";
                  }}
                  maskColor="rgba(245, 247, 250, 0.7)"
                  className="!rounded-xl !border !border-gray-200 dark:!border-gray-800 !bg-white dark:!bg-[#1E2024]"
                />
              </ReactFlow>

              {/* Slide-out Node Inspector Panel */}
              {selectedNode && (
                <div className="absolute top-4 right-4 z-30 w-84 max-w-[90vw] rounded-2xl bg-white/95 dark:bg-[#1A1D24]/95 backdrop-blur-md border border-gray-200/80 dark:border-gray-800 shadow-2xl p-5 space-y-4 animate-in fade-in slide-in-from-right-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          selectedNode.type === "wallet"
                            ? "default"
                            : selectedNode.type === "entity"
                            ? "secondary"
                            : "warning"
                        }
                        className="uppercase text-[10px]"
                      >
                        {selectedNode.type}
                      </Badge>
                      {selectedNode.chain && (
                        <span className="text-xs font-mono text-muted-foreground">
                          {selectedNode.chain}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      aria-label="Close inspector"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div>
                    <h3 className="font-bold text-base text-[#151B2B] dark:text-white truncate">
                      {selectedNode.label ||
                        selectedNode.name ||
                        (selectedNode.type === "transaction"
                          ? "On-Chain Transaction"
                          : "Suspect Address")}
                    </h3>
                    <p className="text-xs font-mono text-muted-foreground break-all mt-1">
                      {selectedNode.address || selectedNode.tx_hash}
                    </p>
                  </div>

                  {selectedNode.risk_score !== undefined && (
                    <div className="p-3 rounded-xl bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-gray-800">
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="font-medium text-muted-foreground">
                          ML Forensic Risk
                        </span>
                        <span
                          className={`font-bold ${
                            selectedNode.risk_score >= 75
                              ? "text-destructive"
                              : selectedNode.risk_score >= 50
                              ? "text-amber-500"
                              : "text-green-600"
                          }`}
                        >
                          {selectedNode.risk_score}/100
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden">
                        <div
                          className={`h-full ${
                            selectedNode.risk_score >= 75
                              ? "bg-destructive"
                              : selectedNode.risk_score >= 50
                              ? "bg-amber-400"
                              : "bg-green-500"
                          }`}
                          style={{ width: `${selectedNode.risk_score}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {selectedNode.confidence && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        Attribution Confidence
                      </span>
                      <Badge
                        variant={
                          selectedNode.confidence === "CONFIRMED"
                            ? "success"
                            : "info"
                        }
                      >
                        {selectedNode.confidence}
                      </Badge>
                    </div>
                  )}

                  {selectedNode.value_usd && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        Transaction Value
                      </span>
                      <span className="font-bold">
                        {formatCurrency(selectedNode.value_usd)}
                      </span>
                    </div>
                  )}

                  {/* Compute custodial status */}
                  {(() => {
                    const isCustodial =
                      selectedNode.type === "entity" ||
                      selectedNode.entity_type === "exchange" ||
                      Boolean(selectedNode.entity_name) ||
                      Boolean(selectedNode.name && /binance|kraken|coinbase|bybit|okx|exchange|vasp/i.test(selectedNode.name)) ||
                      Boolean(selectedNode.label && /binance|kraken|coinbase|bybit|okx|exchange|vasp/i.test(selectedNode.label));

                    return (
                      <div className="pt-2 flex flex-col gap-2">
                        {isCustodial ? (
                          <Button
                            size="sm"
                            onClick={handleDraftReport}
                            disabled={draftingReport}
                            className="w-full rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-semibold shadow-sm transition-all"
                          >
                            {draftingReport ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                                Drafting Section 91 Notice...
                              </>
                            ) : (
                              <>
                                <Scale className="w-3.5 h-3.5 mr-2" />
                                Draft Section 91 / Freeze Notice
                              </>
                            )}
                          </Button>
                        ) : (
                          selectedNode.address && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleDraftReport}
                              disabled={draftingReport}
                              className="w-full rounded-xl"
                            >
                              {draftingReport ? (
                                <>
                                  <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" />
                                  Drafting Notice...
                                </>
                              ) : (
                                <>
                                  <FileText className="w-3.5 h-3.5 mr-2" />
                                  Draft Statutory Notice
                                </>
                              )}
                            </Button>
                          )
                        )}

                        {draftError && (
                          <p className="text-xs text-destructive text-center">{draftError}</p>
                        )}

                        {selectedNode.address && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setIsAICoPilotOpen(true)}
                              className="w-full rounded-xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60"
                            >
                              <Sparkles className="w-3.5 h-3.5 mr-2 text-purple-500" />
                              Ask AI About This Node
                            </Button>

                            <Button size="sm" asChild variant={isCustodial ? "outline" : "default"} className="w-full rounded-xl">
                              <Link href={`/risk?wallet=${selectedNode.address}`}>
                                <ShieldAlert className="w-3.5 h-3.5 mr-2" />
                                Assess in Risk Engine
                              </Link>
                            </Button>
                          </>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            copyToClipboard(
                              selectedNode.address || selectedNode.tx_hash || ""
                            )
                          }
                          className="w-full rounded-xl"
                        >
                          {copied ? (
                            <>
                              <Check className="w-3.5 h-3.5 mr-2 text-green-500" />
                              Copied!
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5 mr-2" />
                              Copy Identifier
                            </>
                          )}
                        </Button>
                      </div>
                    );
                  })()}

                </div>
              )}
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <GitBranch className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-lg font-bold text-[#151B2B] dark:text-white">
                Multi-Hop Forensic Fund Flow Canvas
              </h2>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Select a high-profile demo scenario below to load the live Neo4j
                graph traversal, mixer detection, and VASP cashout attribution.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6 max-w-xl w-full text-left">
                {DEMO_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handleSelectPreset(preset.address)}
                    className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/30 hover:border-primary hover:bg-white dark:hover:bg-[#1E2024] transition-all group flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-semibold text-sm text-[#151B2B] dark:text-white group-hover:text-primary transition-colors">
                          {preset.title}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${preset.badgeColor}`}
                        >
                          {preset.badge}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {preset.subtitle}
                      </p>
                    </div>
                    <div className="flex items-center text-xs font-semibold text-primary mt-3">
                      <span>Visualize Trace</span>
                      <ArrowRight className="w-3.5 h-3.5 ml-1 transition-transform group-hover:translate-x-1" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {subgraph && subgraph.nodes.length > 0 && (
            <GraphAICoPilot
              caseId={caseId || undefined}
              seedWallet={walletId}
              nodes={nodes}
              edges={edges}
              selectedNode={selectedNode}
              onFocusNode={handleFocusNode}
              isOpen={isAICoPilotOpen}
              onToggleOpen={() => setIsAICoPilotOpen((prev) => !prev)}
            />
          )}
        </CardContent>
      </Card>

      {/* Tabular Inspector for Nodes, Edges, and Entities */}
      {subgraph && (
        <Tabs defaultValue="nodes" className="space-y-4">
          <TabsList className="rounded-xl">
            <TabsTrigger value="nodes">Nodes ({subgraph.nodes.length})</TabsTrigger>
            <TabsTrigger value="edges">Edges ({subgraph.edges.length})</TabsTrigger>
            <TabsTrigger value="entities">
              Entities ({subgraph.nodes.filter((n) => n.type === "entity").length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="nodes">
            <Card className="rounded-2xl border-gray-100 dark:border-gray-800">
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-800 text-muted-foreground text-xs">
                      <th className="text-left p-3 font-semibold">ID</th>
                      <th className="text-left p-3 font-semibold">Type</th>
                      <th className="text-left p-3 font-semibold">Address / Hash</th>
                      <th className="text-left p-3 font-semibold">Label</th>
                      <th className="text-left p-3 font-semibold">Risk</th>
                      <th className="text-left p-3 font-semibold">Entity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subgraph.nodes.map((n) => (
                      <tr
                        key={n.id}
                        onClick={() => setSelectedNode(n)}
                        className="border-b border-gray-100 dark:border-gray-800/50 hover:bg-gray-50/50 dark:hover:bg-gray-900/30 cursor-pointer"
                      >
                        <td className="p-3 font-mono text-xs text-muted-foreground">
                          {n.id.split(":").pop()?.slice(0, 16)}...
                        </td>
                        <td className="p-3">
                          <Badge variant="outline" className="capitalize text-xs">
                            {n.type}
                          </Badge>
                        </td>
                        <td className="p-3 font-mono text-xs">
                          {formatAddress(n.address || n.tx_hash || "")}
                        </td>
                        <td className="p-3 text-xs font-medium">
                          {n.label || n.name || "-"}
                        </td>
                        <td className="p-3">
                          {n.risk_score !== undefined && (
                            <span
                              className={`font-bold text-xs ${
                                n.risk_score >= 75
                                  ? "text-destructive"
                                  : n.risk_score >= 50
                                  ? "text-amber-500"
                                  : "text-green-600"
                              }`}
                            >
                              {n.risk_score}
                            </span>
                          )}
                        </td>
                        <td className="p-3">
                          {n.entity_name && (
                            <Badge variant="secondary" className="text-xs">
                              {n.entity_name}
                            </Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="edges">
            <Card className="rounded-2xl border-gray-100 dark:border-gray-800">
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-800 text-muted-foreground text-xs">
                      <th className="text-left p-3 font-semibold">From Node</th>
                      <th className="text-left p-3 font-semibold">Relationship</th>
                      <th className="text-left p-3 font-semibold">To Node</th>
                      <th className="text-left p-3 font-semibold">Value (ETH)</th>
                      <th className="text-left p-3 font-semibold">Tx Hash</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subgraph.edges.map((e, i) => (
                      <tr
                        key={i}
                        className="border-b border-gray-100 dark:border-gray-800/50"
                      >
                        <td className="p-3 font-mono text-xs">
                          {formatAddress(e.from.split(":").pop() || "")}
                        </td>
                        <td className="p-3">
                          <Badge
                            variant={
                              e.type === "SENT" || e.type === "RECEIVED"
                                ? "default"
                                : "outline"
                            }
                            className="text-[10px]"
                          >
                            {e.type || "FLOW"}
                          </Badge>
                        </td>
                        <td className="p-3 font-mono text-xs">
                          {formatAddress(e.to.split(":").pop() || "")}
                        </td>
                        <td className="p-3 font-mono text-xs font-semibold">
                          {e.value
                            ? (parseFloat(e.value) / 1e18).toFixed(4)
                            : "-"}
                        </td>
                        <td className="p-3 font-mono text-xs text-muted-foreground">
                          {formatAddress(e.tx_hash || "")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="entities">
            <Card className="rounded-2xl border-gray-100 dark:border-gray-800">
              {subgraph.nodes.filter((n) => n.type === "entity").length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Layers className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p className="text-base font-medium">No Entities Found</p>
                  <p className="text-sm mt-1">
                    Run entity enrichment to identify VASPs and mixers
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto max-h-96">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 dark:border-gray-800 text-muted-foreground text-xs">
                        <th className="text-left p-3 font-semibold">Entity Name</th>
                        <th className="text-left p-3 font-semibold">Entity Type</th>
                        <th className="text-left p-3 font-semibold">Address</th>
                        <th className="text-left p-3 font-semibold">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subgraph.nodes
                        .filter((n) => n.type === "entity")
                        .map((n) => (
                          <tr
                            key={n.id}
                            onClick={() => setSelectedNode(n)}
                            className="border-b border-gray-100 dark:border-gray-800/50 hover:bg-gray-50/50 dark:hover:bg-gray-900/30 cursor-pointer"
                          >
                            <td className="p-3 font-semibold text-xs text-[#151B2B] dark:text-white">
                              {n.name}
                            </td>
                            <td className="p-3">
                              <Badge variant="outline" className="capitalize text-xs">
                                {n.entity_type}
                              </Badge>
                            </td>
                            <td className="p-3 font-mono text-xs">
                              {formatAddress(n.address || "")}
                            </td>
                            <td className="p-3">
                              <Badge
                                variant={
                                  n.confidence === "CONFIRMED"
                                    ? "success"
                                    : n.confidence === "HIGH_CONFIDENCE"
                                    ? "info"
                                    : n.confidence === "PROBABLE"
                                    ? "warning"
                                    : "secondary"
                                }
                                className="text-xs"
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
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

export default function GraphPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="flex items-center gap-3 text-muted-foreground text-sm">
            <RefreshCw className="w-5 h-5 animate-spin text-primary" />
            <span>Loading forensic graph canvas...</span>
          </div>
        </div>
      }
    >
      <GraphView />
    </Suspense>
  );
}