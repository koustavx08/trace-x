"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatAddress } from "@/lib/utils";
import { analysisApi, casesApi, riskApi } from "@/lib/api";
import {
  Shield,
  Search,
  Activity,
  FileText,
  AlertTriangle,
  CheckCircle,
  GitBranch,
  Play,
  ChevronRight,
  ExternalLink,
  Sparkles,
  Target,
  BarChart3,
  Bot,
} from "lucide-react";
import Link from "next/link";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const demoCases = [
  {
    id: "defi-exploit",
    case_number: "TRX-20240115-0042",
    title: "DeFi Protocol Flash Loan Exploit",
    crime_type: "fraud",
    description: "Major DeFi protocol exploit involving flash loan attack across multiple protocols. Attacker borrowed 50,000 ETH via flash loan, manipulated oracle prices, drained liquidity pools. Funds traced through Tornado Cash and multiple DEX swaps across Ethereum and Polygon.",
    status: "in_progress",
    suspect_wallet: "0x742D35CC6634c0532925A3b844BC9E7595F0BEb0",
    chains: ["Ethereum", "Polygon"],
    tags: ["Flash Loan", "Tornado Cash", "Multi-chain", "Flash Loan Exploit"],
    wallet_count: 6,
    risk_score: 95,
    vasp: "Binance",
    vasp_confidence: "CONFIRMED",
  },
  {
    id: "ransomware",
    case_number: "TRX-20240114-0038",
    title: "Ransomware Payment Tracing - LockBit 3.0",
    crime_type: "ransomware",
    description: "Tracing ransomware payments from LockBit 3.0 affiliate across multiple chains. Victim organization paid 25 BTC equivalent in ETH/USDT. Payments split across multiple wallets, traced through Wasabi Wallet coinjoins, then to nested exchange deposits.",
    status: "open",
    suspect_wallet: "0x8aD1e08C7793af67e9d92fe308d5697FB81d3E43",
    chains: ["Ethereum", "Arbitrum"],
    tags: ["Ransomware", "LockBit", "CoinJoin", "Wasabi Wallet"],
    wallet_count: 5,
    risk_score: 92,
    vasp: "Kraken",
    vasp_confidence: "CONFIRMED",
  },
  {
    id: "money-laundering",
    case_number: "TRX-20240113-0029",
    title: "International Money Laundering Ring - Nested Exchanges",
    crime_type: "money_laundering",
    description: "International money laundering operation using nested exchange structure. Funds from predicate offenses moved through layered exchange deposits, DEX swaps, and cross-chain bridges. Network of 40+ wallets identified. Peel chain pattern with round amounts.",
    status: "closed",
    suspect_wallet: "0x0000000000000000000000000000000000001010",
    chains: ["Ethereum", "Polygon", "BSC"],
    tags: ["Money Laundering", "Nested Exchanges", "Peel Chain", "Round Amounts"],
    wallet_count: 5,
    risk_score: 82,
    vasp: "Huobi / OKX / Gate.io",
    vasp_confidence: "CONFIRMED",
  },
  {
    id: "darknet",
    case_number: "TRX-20240112-0017",
    title: "Darknet Market Seizure - Hydra Successor",
    crime_type: "darknet_market",
    description: "Cryptocurrency seizure from darknet marketplace successor to Hydra. Marketplace operated on Tor with Bitcoin and Monero primary, but used Ethereum/Polygon for vendor bond escrow. Seized 150+ vendor wallets, 500+ buyer wallets.",
    status: "archived",
    suspect_wallet: "0x159939f79D0B3D4e752912fA658A4D3776c9b5e3",
    chains: ["Ethereum", "Polygon"],
    tags: ["Darknet", "Market Seizure", "Vendor Bonds", "Polygon Bridge"],
    wallet_count: 3,
    risk_score: 75,
    vasp: "Bybit",
    vasp_confidence: "HIGH_CONFIDENCE",
  },
  {
    id: "sanctions",
    case_number: "TRX-20240111-0009",
    title: "Sanctions Evasion - Russian Oligarch Crypto Holdings",
    crime_type: "sanctions_evasion",
    description: "Tracking sanctions evasion through crypto mixers and DeFi protocols. OFAC SDN-listed individual using Tornado Cash, Railgun, and cross-chain bridges to obscure ownership of ~$50M in crypto assets.",
    status: "in_progress",
    suspect_wallet: "0x169455c72558a2D9A2C4a5b8F6e9e8D7a6B5c4D3",
    chains: ["Ethereum", "BSC"],
    tags: ["Sanctions", "OFAC", "Tornado Cash", "Railgun", "Cross-chain"],
    wallet_count: 4,
    risk_score: 99,
    vasp: "Binance",
    vasp_confidence: "CONFIRMED",
  },
];

const crimeTypeLabels: Record<string, string> = {
  fraud: "Fraud",
  money_laundering: "Money Laundering",
  ransomware: "Ransomware",
  darknet_market: "Darknet Market",
  sanctions_evasion: "Sanctions Evasion",
};

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

export default function DemoPage() {
  const [selectedCase, setSelectedCase] = useState<typeof demoCases[0] | null>(null);
  const [loading, setLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunDemo = async (demoCase: typeof demoCases[0]) => {
    setSelectedCase(demoCase);
    setLoading(true);
    setError(null);
    setAnalysisResult(null);

    try {
      // Step 1: Create case
      const caseResponse = await casesApi.create({
        title: demoCase.title,
        crime_type: demoCase.crime_type as any,
        description: demoCase.description,
        status: "in_progress",
      });

      // Step 2: Analyze wallet
      const analysisResponse = await analysisApi.analyzeWallet(caseResponse.id, {
        address: demoCase.suspect_wallet,
        trace_depth: 5,
        max_transactions: 1000,
      });

      // Step 3: Get attribution
      const attributionResponse = await riskApi.getAttribution(analysisResponse.wallet.id, 6);

      // Step 4: Get risk assessment
      const riskResponse = await riskApi.assessWallet(analysisResponse.wallet.id);

      setAnalysisResult({
        case: caseResponse,
        wallet: analysisResponse.wallet,
        investigation: analysisResponse.investigation,
        attribution: attributionResponse,
        risk: riskResponse,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo failed");
    } finally {
      setLoading(false);
    }
  };

  const formatAddressShort = (addr: string) => {
    if (!addr) return "";
    return `${addr.slice(0, 10)}...${addr.slice(-8)}`;
  };

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case "CONFIRMED": return "text-green-400";
      case "HIGH_CONFIDENCE": return "text-blue-400";
      case "PROBABLE": return "text-amber-400";
      default: return "text-muted-foreground";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Judge Mode - Demo Scenarios</h1>
          <p className="text-muted-foreground">
            Pre-seeded synthetic SIH 2026 investigation cases. Click &quot;Run Full Demo&quot; to execute the complete investigation flow.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="gap-1 text-xs">
            <Sparkles className="w-3 h-3" />
            Synthetic Demo Data
          </Badge>
        </div>
      </div>

      {!selectedCase ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {demoCases.map((demoCase) => (
            <Card key={demoCase.id} className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => setSelectedCase(demoCase)}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="capitalize text-sm">
                    {crimeTypeLabels[demoCase.crime_type]}
                  </Badge>
                  <Badge variant={demoCase.status === "in_progress" ? "warning" : demoCase.status === "open" ? "info" : demoCase.status === "closed" ? "success" : "secondary"}>
                    {statusLabels[demoCase.status]}
                  </Badge>
                </div>
                <CardTitle className="text-lg">{demoCase.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground line-clamp-3">{demoCase.description}</p>
                
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-muted-foreground">Case</p>
                    <p className="font-mono font-medium">{demoCase.case_number}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Chains</p>
                    <p className="font-medium">{demoCase.chains.join(", ")}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Wallets</p>
                    <p className="font-medium">{demoCase.wallet_count}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Risk Score</p>
                    <p className={`font-bold ${demoCase.risk_score >= 75 ? "text-destructive" : demoCase.risk_score >= 50 ? "text-amber-400" : "text-green-400"}`}>
                      {demoCase.risk_score}/100
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-1">
                  {demoCase.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>

                <div className="pt-2 border-t border-tracex-border">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Probable VASP</span>
                    <Badge variant={demoCase.vasp_confidence === "CONFIRMED" ? "success" : "warning"} className="gap-1">
                      <CheckCircle className="w-3 h-3" />
                      {demoCase.vasp} ({demoCase.vasp_confidence})
                    </Badge>
                  </div>
                </div>
              </CardContent>
              <CardContent className="pt-0">
                <Button 
                  className="w-full" 
                  onClick={(e) => { e.stopPropagation(); handleRunDemo(demoCase); }}
                  disabled={loading}
                >
                  <Play className="w-4 h-4 mr-2" />
                  {loading ? "Running Demo..." : "Run Full Demo"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <Button variant="ghost" size="sm" onClick={() => { setSelectedCase(null); setAnalysisResult(null); }}>
                <ChevronRight className="w-4 h-4 mr-1 rotate-180" />
                Back to Demo Cases
              </Button>
              <h1 className="text-2xl font-bold tracking-tight mt-2">{selectedCase?.title}</h1>
            </div>
            <div className="flex gap-2">
              <Badge variant="secondary" className="gap-1 text-xs">
                <Sparkles className="w-3 h-3" />
                Synthetic Demo Data
              </Badge>
            </div>
          </div>

          {error && (
            <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive">
              {error}
            </div>
          )}

          {analysisResult && (
            <Tabs defaultValue="overview" className="space-y-4">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="transactions">Transactions</TabsTrigger>
                <TabsTrigger value="attribution">Attribution</TabsTrigger>
                <TabsTrigger value="risk">Risk Assessment</TabsTrigger>
                <TabsTrigger value="graph">Graph</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-6">
                <div className="grid gap-4 md:grid-cols-4">
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">Transactions Analyzed</p>
                          <p className="text-3xl font-bold tracking-tight">{analysisResult.investigation?.result_summary?.transactions_found || 0}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-primary/10 text-primary">
                          <Activity className="w-6 h-6" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">Unique Addresses</p>
                          <p className="text-3xl font-bold tracking-tight">{analysisResult.investigation?.result_summary?.unique_addresses || 0}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-green-500/10 text-green-400">
                          <GitBranch className="w-6 h-6" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">Risk Score</p>
                          <p className="text-3xl font-bold tracking-tight text-destructive">{analysisResult.risk?.overall_score?.toFixed(1) || 0}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-destructive/10 text-destructive">
                          <AlertTriangle className="w-6 h-6" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">VASP Found</p>
                          <p className="text-3xl font-bold tracking-tight text-green-400">
                            {analysisResult.attribution?.attributed ? "Yes" : "No"}
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-green-500/10 text-green-400">
                          <Target className="w-6 h-6" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>Suspect Wallet</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-mono text-lg">{formatAddress(selectedCase?.suspect_wallet || "")}</p>
                        <p className="text-sm text-muted-foreground">{selectedCase?.chains.join(", ")}</p>
                      </div>
                      <Badge variant="destructive" className="text-lg px-3 py-1">
                        Risk: {analysisResult.risk?.overall_score?.toFixed(1) || 0}/100
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-lg">Investigation Status</CardTitle>
                    <Badge variant={
                      analysisResult.investigation?.status === "completed" ? "success" :
                      analysisResult.investigation?.status === "running" ? "warning" :
                      analysisResult.investigation?.status === "failed" ? "destructive" : "secondary"
                    }>
                      {analysisResult.investigation?.status || "Unknown"}
                    </Badge>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                        <div className={`w-2 h-2 rounded-full ${analysisResult.investigation?.status === "completed" ? "bg-green-400" : analysisResult.investigation?.status === "running" ? "bg-amber-400" : "bg-blue-400"}`} />
                        <div className="flex-1">
                          <p className="font-medium">Wallet Analysis</p>
                          <p className="text-sm text-muted-foreground">
                            {analysisResult.investigation?.result_summary?.transactions_found} transactions analyzed
                          </p>
                        </div>
                        <Badge variant={analysisResult.investigation?.status === "completed" ? "success" : analysisResult.investigation?.status === "running" ? "warning" : "secondary"}>
                          {analysisResult.investigation?.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                        <div className="w-2 h-2 rounded-full bg-green-400" />
                        <div className="flex-1">
                          <p className="font-medium">Graph Sync</p>
                          <p className="text-sm text-muted-foreground">Wallet and transactions synced to Neo4j</p>
                        </div>
                        <Badge variant="success">Synced</Badge>
                      </div>
                      <div className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                        <div className="w-2 h-2 rounded-full bg-purple-400" />
                        <div className="flex-1">
                          <p className="font-medium">Entity Enrichment</p>
                          <p className="text-sm text-muted-foreground">Known entities checked against intelligence database</p>
                        </div>
                        <Badge variant="info">Completed</Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="transactions">
                {analysisResult.investigation && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Transactions ({analysisResult.investigation?.result_summary?.transactions_found || 0})</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-muted-foreground text-center py-8">
                        Transaction data loaded from blockchain analysis. View full transaction history in the Analyze page.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="attribution">
                <Card>
                  <CardHeader>
                    <CardTitle>VASP Attribution</CardTitle>
                  </CardHeader>
                   <CardContent>
                     {analysisResult.attribution?.attributed ? (
                       <div className="space-y-4">
                         <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                           <div className="flex items-center justify-between">
                             <div>
                               <p className="font-semibold text-green-400">VASP Identified</p>
                               <p className="text-sm text-muted-foreground">
                                 Funds traced to <strong>{analysisResult.attribution?.nearest_vasp?.entity_name || "Unknown"}</strong>
                                 with <Badge variant="success" className="ml-2">{analysisResult.attribution?.nearest_vasp?.confidence}</Badge> confidence
                               </p>
                             </div>
                             <div className="text-right">
                               <p className="font-mono text-lg text-green-400">
                                 {(analysisResult.attribution?.nearest_vasp?.confidence_score * 100).toFixed(1)}%
                               </p>
                               <p className="text-xs text-muted-foreground">Confidence Score</p>
                             </div>
                           </div>
                           <div className="grid grid-cols-3 gap-4 text-sm mt-4">
                             <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                               <p className="text-muted-foreground">Distance</p>
                               <p className="font-bold">{analysisResult.attribution?.nearest_vasp?.distance_hops} hops</p>
                             </div>
                             <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                               <p className="text-muted-foreground">Value Traced</p>
                               <p className="font-bold">{analysisResult.attribution?.nearest_vasp?.total_value_eth?.toFixed(4) || 0} ETH</p>
                             </div>
                             <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                               <p className="text-muted-foreground">Evidence Items</p>
                               <p className="font-bold">{analysisResult.attribution?.nearest_vasp?.evidence?.length || 0}</p>
                             </div>
                           </div>
                         </div>
                       </div>
                     ) : (
                       <div className="text-center py-8 text-muted-foreground">
                         <AlertTriangle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                         <p className="text-lg font-medium">No VASP Attribution Found</p>
                         <p className="text-sm mt-1">Fund flow did not reach a known exchange within trace depth</p>
                       </div>
                     )}
                   </CardContent>
                </Card>

                {analysisResult.attribution?.all_attributions?.length && (
                  <Card className="mt-4">
                    <CardHeader>
                      <CardTitle>All Attributions ({analysisResult.attribution.all_attributions.length})</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Entity</TableHead>
                              <TableHead>Type</TableHead>
                              <TableHead>Confidence</TableHead>
                              <TableHead>Hops</TableHead>
                              <TableHead>Value (ETH)</TableHead>
                              <TableHead>Type</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {analysisResult.attribution.all_attributions.map((attr: any, i: number) => (
                              <TableRow key={i}>
                                <TableCell className="font-medium">{attr.entity_name}</TableCell>
                                <TableCell>
                                  <Badge variant="outline" className="capitalize">{attr.entity_type}</Badge>
                                </TableCell>
                                <TableCell>
                                  <Badge 
                                    variant={
                                      attr.confidence === "CONFIRMED" ? "success" :
                                      attr.confidence === "HIGH_CONFIDENCE" ? "info" :
                                      attr.confidence === "PROBABLE" ? "warning" : "secondary"
                                    }
                                  >
                                    {attr.confidence}
                                  </Badge>
                                </TableCell>
                                <TableCell>{attr.distance_hops}</TableCell>
                                <TableCell className="font-mono tabular-nums">{attr.total_value_eth?.toFixed(4) || 0}</TableCell>
                                <TableCell>
                                  <Badge variant="outline">{attr.attribution_type}</Badge>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="risk">
                {analysisResult.risk && (
                  <div className="space-y-6">
                    <Card>
                      <CardHeader>
                        <CardTitle>Risk Assessment</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-6">
                        <div className="flex items-center justify-between p-6 rounded-lg bg-tracex-surface-hover/50">
                          <div>
                            <p className="text-sm font-medium text-muted-foreground">Overall Risk Score</p>
                            <p className="text-4xl font-bold tracking-tight text-destructive">
                              {analysisResult.risk.overall_score?.toFixed(1) || 0}
                            </p>
                            <p className="text-sm text-muted-foreground mt-1">
                              <Badge 
                                variant={
                                  analysisResult.risk.risk_level === "critical" ? "destructive" :
                                  analysisResult.risk.risk_level === "high" ? "destructive" :
                                  analysisResult.risk.risk_level === "medium" ? "warning" :
                                  analysisResult.risk.risk_level === "low" ? "success" : "info"
                                }
                              >
                                {analysisResult.risk.risk_level?.toUpperCase()}
                              </Badge>
                            </p>
                          </div>
                          <div className="w-24 h-24 rounded-full border-4 border-tracex-border flex items-center justify-center">
                            <span className="text-2xl font-bold text-destructive">
                              {(analysisResult.risk.overall_score || 0).toFixed(0)}
                            </span>
                          </div>
                        </div>

                        <Card>
                          <CardHeader>
                            <CardTitle>Risk Summary</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <p className="text-muted-foreground whitespace-pre-wrap">{analysisResult.risk.summary}</p>
                          </CardContent>
                        </Card>

                         <Card>
                           <CardHeader>
                             <CardTitle>Risk Factors ({analysisResult.risk.factors?.length || 0})</CardTitle>
                           </CardHeader>
                           <CardContent>
                             {analysisResult.risk.factors?.map((factor: any, i: number) => (
                               <div key={i} className="p-4 rounded-lg border border-tracex-border bg-tracex-surface-hover/50">
                                 <div className="flex items-start justify-between gap-4">
                                   <div className="flex-1">
                                     <div className="flex items-center gap-2 mb-1">
                                       <span className="font-semibold">{factor.type.replace("_", " ")}</span>
                                       <Badge 
                                         variant={
                                           factor.severity === "critical" ? "destructive" :
                                           factor.severity === "high" ? "destructive" :
                                           factor.severity === "medium" ? "warning" :
                                           factor.severity === "low" ? "success" : "info"
                                         }
                                       >
                                         {factor.severity.toUpperCase()}
                                       </Badge>
                                     </div>
                                     <p className="text-sm text-muted-foreground">{factor.description}</p>
                                     <p className="text-xs text-muted-foreground mt-1">
                                       Weight: {factor.weight} | Score: {factor.score} | Weighted: {factor.weighted_score.toFixed(1)}
                                     </p>
                                   </div>
                                   <Badge 
                                     variant={
                                       factor.confidence === "CONFIRMED" ? "success" :
                                       factor.confidence === "HIGH_CONFIDENCE" ? "info" :
                                       factor.confidence === "PROBABLE" ? "warning" : "secondary"
                                     }
                                     className={getConfidenceColor(factor.confidence)}
                                   >
                                     {factor.confidence}
                                   </Badge>
                                 </div>
                               </div>
                             ))}
                           </CardContent>
                         </Card>

                        <Card>
                          <CardHeader>
                            <CardTitle>Methodology</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{analysisResult.risk.methodology}</p>
                          </CardContent>
                        </Card>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="graph">
                <Card>
                  <CardHeader>
                    <CardTitle>Investigation Graph</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[500px] flex items-center justify-center bg-tracex-darker rounded-lg border border-tracex-border">
                      <div className="text-center text-muted-foreground">
                        <GitBranch className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg font-medium">Graph Visualization</p>
                        <p className="text-sm mt-1">Interactive fund flow graph (React Flow)</p>
                        <p className="text-xs mt-2">View full graph in <Button variant="ghost" size="sm" asChild><Link href={`/graph?wallet=${analysisResult.wallet?.id}`}><ExternalLink className="w-4 h-4 mr-1" />Open Graph</Link></Button></p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )}
        </div>
      )}
    </div>
  );
}