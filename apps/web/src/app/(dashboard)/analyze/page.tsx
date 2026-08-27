"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { formatAddress, formatCurrency, formatRelativeTime, getRiskColor, getRiskBg } from "@/lib/utils";
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
} from "lucide-react";

const chains = [
  { id: "ethereum", name: "Ethereum", symbol: "ETH" },
  { id: "polygon", name: "Polygon", symbol: "MATIC" },
];

const mockTransactions = [
  { hash: "0xabc123...def456", block: 19234567, timestamp: "2024-01-15T10:30:00Z", from: "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", to: "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", value: "150.5", valueUsd: 450000, token: "ETH", method: "transfer", suspicious: true },
  { hash: "0xdef456...ghi789", block: 19234580, timestamp: "2024-01-15T10:32:00Z", from: "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", to: "0xA0b86a33E6441b8C4C8C8C8C8C8C8C8C8C8C8C", value: "149.8", valueUsd: 448000, token: "ETH", method: "swap", suspicious: true },
  { hash: "0xghi789...jkl012", block: 19234595, timestamp: "2024-01-15T10:35:00Z", from: "0xA0b86a33E6441b8C4C8C8C8C8C8C8C8C8C8C8C", to: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", value: "148.2", valueUsd: 443000, token: "ETH", method: "transfer", suspicious: false },
  { hash: "0xjkl012...mno345", block: 45678901, timestamp: "2024-01-15T10:38:00Z", from: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", to: "0x6B175474E89094C44Da98b954EedeAC495271d0F", value: "148.0", valueUsd: 442500, token: "ETH", method: "deposit", suspicious: false },
];

const mockPatterns = [
  { type: "Peel Chain", severity: "High", description: "Funds split across multiple addresses in rapid succession", wallets: 5 },
  { type: "Round Amounts", severity: "Medium", description: "Multiple transactions with round ETH amounts detected", wallets: 3 },
  { type: "Mixer Interaction", severity: "High", description: "Funds traced through Tornado Cash deposit", wallets: 1 },
  { type: "Rapid Movement", severity: "Medium", description: "Funds moved through 4 hops in under 10 minutes", wallets: 4 },
];

export default function AnalyzePage() {
  const [address, setAddress] = useState("");
  const [chain, setChain] = useState("ethereum");
  const [depth, setDepth] = useState(5);
  const [analyzing, setAnalyzing] = useState(false);
  const [results, setResults] = useState<typeof mockTransactions | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setAnalyzing(true);
    await new Promise((r) => setTimeout(r, 2000));
    setResults(mockTransactions);
    setAnalyzing(false);
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
                    placeholder="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    required
                  />
                  <Select value={chain} onValueChange={setChain} className="w-[160px]">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {chains.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name} ({c.symbol})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
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

            <div className="flex items-center gap-4">
              <Button type="submit" disabled={analyzing || !address} className="w-full sm:w-auto">
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
              <Button type="button" variant="outline">
                <Download className="w-4 h-4 mr-2" />
                Export Results
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {results && (
        <Tabs defaultValue="transactions" className="space-y-4">
          <TabsList>
            <TabsTrigger value="transactions">Transactions ({results.length})</TabsTrigger>
            <TabsTrigger value="patterns">Patterns ({mockPatterns.length})</TabsTrigger>
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
                        <TableRow key={tx.hash}>
                          <TableCell>
                            <code className="font-mono text-sm">{tx.hash}</code>
                          </TableCell>
                          <TableCell className="font-mono text-sm">#{tx.block.toLocaleString()}</TableCell>
                          <TableCell className="text-muted-foreground">{formatRelativeTime(tx.timestamp)}</TableCell>
                          <TableCell>
                            <code className="font-mono text-sm">{formatAddress(tx.from)}</code>
                          </TableCell>
                          <TableCell>
                            <code className="font-mono text-sm">{formatAddress(tx.to)}</code>
                          </TableCell>
                          <TableCell className="font-mono tabular-nums">
                            {formatCurrency(tx.valueUsd || 0)}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{tx.token}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{tx.method}</Badge>
                          </TableCell>
                          <TableCell>
                            {tx.suspicious && (
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
                <div className="space-y-4">
                  {mockPatterns.map((pattern) => (
                    <div
                      key={pattern.type}
                      className="p-4 rounded-lg border border-tracex-border bg-tracex-surface-hover/50"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold">{pattern.type}</span>
                            <Badge variant={pattern.severity === "High" ? "destructive" : "warning"}>
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
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="graph">
            <Card>
              <CardHeader>
                <CardTitle>Transaction Graph</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[500px] flex items-center justify-center bg-tracex-darker rounded-lg border border-tracex-border">
                  <div className="text-center text-muted-foreground">
                    <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p className="text-lg font-medium">Graph Visualization</p>
                    <p className="text-sm mt-1">Interactive fund flow graph (React Flow)</p>
                    <p className="text-xs mt-2">Coming in Phase 10</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}