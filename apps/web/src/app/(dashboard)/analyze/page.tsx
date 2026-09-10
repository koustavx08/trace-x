"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { formatAddress, formatCurrency, formatRelativeTime, getRiskColor, getRiskBg } from "@/lib/utils";
import { analysisApi } from "@/lib/api";
import {
  Search,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Activity,
  Link2,
  Filter,
  Download,
  Share2,
  XCircle,
  CheckCircle2,
  GitBranch,
  ExternalLink,
  Bot,
} from "lucide-react";

interface ChainInfo {
  chain_id: number;
  name: string;
  symbol: string;
  explorer: string;
  rpc_env: string;
}

interface Transaction {
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
}

interface Pattern {
  type: string;
  severity: "High" | "Medium" | "Low";
  description: string;
  wallets: number;
}

export default function AnalyzePage() {
  const [address, setAddress] = useState("");
  const [chainId, setChainId] = useState<number | undefined>(undefined);
  const [depth, setDepth] = useState(5);
  const [analyzing, setAnalyzing] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; error?: string } | null>(null);
  const [results, setResults] = useState<Transaction[] | null>(null);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [traceResult, setTraceResult] = useState<any>(null);
  const [chains, setChains] = useState<ChainInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("transactions");

  useEffect(() => {
    loadChains();
  }, []);

  const loadChains = async () => {
    try {
      const response = await analysisApi.listChains();
      setChains(response.chains);
    } catch (err) {
      console.error("Failed to load chains:", err);
    }
  };

  const validateAddress = async () => {
    if (!address || address.length < 42) {
      setValidationResult({ valid: false, error: "Address too short" });
      return;
    }

    setValidating(true);
    setError(null);
    try {
      const result = await analysisApi.validateAddress(address, chainId);
      setValidationResult(result);
      if (result.valid && result.chain_id && !chainId) {
        setChainId(result.chain_id);
      }
    } catch (err) {
      setValidationResult({ valid: false, error: "Validation failed" });
    } finally {
      setValidating(false);
    }
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!address || !validationResult?.valid) return;

    setAnalyzing(true);
    setError(null);
    setResults(null);
    setPatterns([]);
    setTraceResult(null);

    try {
      const caseId = new URLSearchParams(window.location.search).get("case");
      if (!caseId) {
        throw new Error("No case selected. Please select a case first.");
      }

      const response = await analysisApi.analyzeWallet(caseId, {
        address,
        chain_id: chainId,
        trace_depth: depth,
        max_transactions: 1000,
      });

      if (response.investigation.status === "completed" && response.investigation.result_summary) {
        const txResponse = await analysisApi.getWalletTransactions(response.wallet.id);
        setResults(txResponse.items);

        const detectedPatterns = detectPatterns(txResponse.items);
        setPatterns(detectedPatterns);
      } else if (response.investigation.status === "failed") {
        throw new Error(response.investigation.error_message || "Analysis failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleTrace = async () => {
    if (!results || results.length === 0) return;

    try {
      const walletId = new URLSearchParams(window.location.search).get("wallet");
      if (!walletId) return;

      const result = await analysisApi.traceFundFlow(walletId, {
        max_hops: depth,
        min_value_eth: 0.001,
      });
      setTraceResult(result);
      setActiveTab("graph");
    } catch (err) {
      setError("Failed to trace fund flow");
    }
  };

  const detectPatterns = (txs: Transaction[]): Pattern[] => {
    const patterns: Pattern[] = [];
    const addresses = new Map<string, number>();

    txs.forEach(tx => {
      addresses.set(tx.from_address, (addresses.get(tx.from_address) || 0) + 1);
      addresses.set(tx.to_address, (addresses.get(tx.to_address) || 0) + 1);
    });

    const multiHop = Array.from(addresses.entries()).filter(([, count]) => count > 2).length;
    if (multiHop > 0) {
      patterns.push({
        type: "Peel Chain",
        severity: "High",
        description: `${multiHop} addresses with 3+ transactions - potential peel chain`,
        wallets: multiHop,
      });
    }

    const roundAmounts = txs.filter(tx => {
      const val = parseFloat(tx.value);
      return val > 0 && val === Math.floor(val) && val % 1 === 0;
    }).length;
    if (roundAmounts > 2) {
      patterns.push({
        type: "Round Amounts",
        severity: "Medium",
        description: `${roundAmounts} transactions with round ETH amounts`,
        wallets: roundAmounts,
      });
    }

    const rapidTxs = txs.filter((tx, i) => {
      if (i === 0) return false;
      const prev = new Date(txs[i - 1].timestamp).getTime();
      const curr = new Date(tx.timestamp).getTime();
      return (curr - prev) < 60000;
    }).length;
    if (rapidTxs > 2) {
      patterns.push({
        type: "Rapid Movement",
        severity: "Medium",
        description: `${rapidTxs} transactions within 1 minute of previous`,
        wallets: rapidTxs,
      });
    }

    return patterns;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analyze Wallet</h1>
          <p className="text-muted-foreground">Trace fund flows and detect suspicious patterns</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Wallet Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAnalyze} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="md:col-span-2">
                <Label htmlFor="address">Wallet Address</Label>
                <div className="flex gap-2">
                  <Input
                    id="address"
                    placeholder="0xa241ec91A7D0c2c8bf11d01C168579Ee1201a209"
                    value={address}
                    onChange={(e) => {
                      setAddress(e.target.value);
                      setValidationResult(null);
                    }}
                    onBlur={validateAddress}
                    required
                    disabled={analyzing}
                  />
                  <Select value={chainId?.toString() || ""} onValueChange={(v) => setChainId(v ? parseInt(v) : undefined)}>
                    <SelectTrigger className="w-[160px]">
                      <SelectValue placeholder="Auto-detect" />
                    </SelectTrigger>
                    <SelectContent>
                      {chains.map((c) => (
                        <SelectItem key={c.chain_id} value={c.chain_id.toString()}>
                          {c.name} ({c.symbol})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {validating && <Activity className="w-5 h-5 mt-10 animate-spin text-muted-foreground" />}
                  {validationResult?.valid && !validating && <CheckCircle2 className="w-5 h-5 mt-10 text-green-400" />}
                  {validationResult?.error && !validating && <XCircle className="w-5 h-5 mt-10 text-destructive" />}
                </div>
                {validationResult?.error && !validating && (
                  <p className="text-sm text-destructive mt-1">{validationResult.error}</p>
                )}
              </div>
              <div>
                <Label htmlFor="depth">Trace Depth</Label>
                <Select value={depth.toString()} onValueChange={(v) => setDepth(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((d) => (
                      <SelectItem key={d} value={d.toString()}>
                        {d} hops
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
                {error}
              </div>
            )}

            <div className="flex items-center gap-4">
              <Button type="submit" disabled={analyzing || !address || !validationResult?.valid} className="w-full sm:w-auto">
                {analyzing ? (
                  <>
                    <Activity className="w-4 h-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    Start Analysis
                  </>
                )}
              </Button>
              <Button type="button" variant="outline" onClick={handleTrace} disabled={!results || results.length === 0}>
                <Activity className="w-4 h-4 mr-2" />
                Trace Fund Flow
              </Button>
              <Button type="button" variant="outline" disabled={!results}>
                <Download className="w-4 h-4 mr-2" />
                Export Results
              </Button>
              {results && results.length > 0 && (
                <Button type="button" variant="outline" asChild>
                  <a href={`/graph?wallet=${new URLSearchParams(window.location.search).get("wallet") || ""}&address=${address}`} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Open in Graph
                  </a>
                </Button>
              )}
              {address && validationResult?.valid && (
                <Button type="button" variant="outline" asChild>
                  <a href={`/ai?address=${address}&case=${new URLSearchParams(window.location.search).get("case") || ""}`} target="_blank" rel="noopener noreferrer">
                    <Bot className="w-4 h-4 mr-2" />
                    Ask AI Assistant
                  </a>
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {results && (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="transactions">Transactions ({results.length})</TabsTrigger>
            <TabsTrigger value="patterns">Patterns ({patterns.length})</TabsTrigger>
            <TabsTrigger value="graph">Graph View</TabsTrigger>
          </TabsList>

          <TabsContent value="transactions">
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tx Hash</TableHead>
                        <TableHead>Block</TableHead>
                        <TableHead>Time</TableHead>
                        <TableHead>From</TableHead>
                        <TableHead>To</TableHead>
                        <TableHead>Value</TableHead>
                        <TableHead>Token</TableHead>
                        <TableHead>Method</TableHead>
                        <TableHead>Flags</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {results.map((tx) => (
                        <TableRow key={tx.tx_hash}>
                          <TableCell>
                            <code className="font-mono text-sm">{formatAddress(tx.tx_hash)}</code>
                          </TableCell>
                          <TableCell className="font-mono text-sm">#{tx.block_number.toLocaleString()}</TableCell>
                          <TableCell className="text-muted-foreground">{formatRelativeTime(tx.timestamp)}</TableCell>
                          <TableCell>
                            <code className="font-mono text-sm">{formatAddress(tx.from_address)}</code>
                          </TableCell>
                          <TableCell>
                            <code className="font-mono text-sm">{formatAddress(tx.to_address)}</code>
                          </TableCell>
                          <TableCell className="font-mono tabular-nums">
                            {formatCurrency(tx.value_usd || 0)}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{tx.token_symbol || "ETH"}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{tx.method || "transfer"}</Badge>
                          </TableCell>
                          <TableCell>
                            {tx.is_suspicious && (
                              <Badge variant="destructive" className="gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                Suspicious
                              </Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="patterns">
            <Card>
              <CardHeader>
                <CardTitle>Detected Patterns</CardTitle>
              </CardHeader>
              <CardContent>
                {patterns.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <CheckCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p className="text-lg font-medium">No suspicious patterns detected</p>
                    <p className="text-sm mt-1">Analysis found no obvious red flags in transaction history</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {patterns.map((pattern) => (
                      <div
                        key={pattern.type}
                        className="p-4 rounded-lg border border-tracex-border bg-tracex-surface-hover/50"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-semibold">{pattern.type}</span>
                              <Badge variant={pattern.severity === "High" ? "destructive" : pattern.severity === "Medium" ? "warning" : "success"}>
                                {pattern.severity}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground">{pattern.description}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              Affected wallets: {pattern.wallets}
                            </p>
                          </div>
                          <Button variant="ghost" size="icon">
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="graph">
            <Card>
              <CardHeader>
                <CardTitle>Fund Flow Trace</CardTitle>
              </CardHeader>
              <CardContent>
                {traceResult ? (
                  <div className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-4">
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm text-muted-foreground">Wallets Traced</p>
                          <p className="text-2xl font-bold">{traceResult.wallets_traced}</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm text-muted-foreground">Edges Found</p>
                          <p className="text-2xl font-bold">{traceResult.edges.length}</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm text-muted-foreground">Paths Found</p>
                          <p className="text-2xl font-bold">{traceResult.paths.length}</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-4">
                          <p className="text-sm text-muted-foreground">Max Hops</p>
                          <p className="text-2xl font-bold">{traceResult.max_hops_reached}</p>
                        </CardContent>
                      </Card>
                    </div>
                    <div className="h-[400px] flex items-center justify-center bg-tracex-darker rounded-lg border border-tracex-border">
                      <div className="text-center text-muted-foreground">
                        <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg font-medium">Graph Visualization</p>
                        <p className="text-sm mt-1">Interactive fund flow graph (React Flow)</p>
                        <p className="text-xs mt-2">Coming in Phase 10</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-[500px] flex items-center justify-center bg-tracex-darker rounded-lg border border-tracex-border">
                    <div className="text-center text-muted-foreground">
                      <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p className="text-lg font-medium">Graph Visualization</p>
                      <p className="text-sm mt-1">Click &quot;Trace Fund Flow&quot; to build the graph</p>
                      <p className="text-xs mt-2">Full interactive graph coming in Phase 10</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}