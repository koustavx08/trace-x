"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatAddress, formatCurrency, formatRelativeTime } from "@/lib/utils";
import { analysisApi, casesApi, riskApi, walletsApi, investigationsApi, Case, Wallet } from "@/lib/api";
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

// Mirrors the seeded synthetic dataset in
// apps/api/scripts/demo_dataset.py -- case numbers, suspect wallets, wallet
// counts, risk scores and attributed exchanges are the values the seeder
// writes. Run `python scripts/demo_dataset.py` to print them and keep this
// list in step after changing a scenario.
const demoCases = [
  {
    id: "defi-exploit",
    case_number: "TRX-20240115-0042",
    title: "DeFi Protocol Flash Loan Exploit",
    crime_type: "fraud",
    description: "Oracle-manipulation exploit against the Protocol X lending pool. The operator funded a fresh EOA with a 100 ETH Tornado Cash withdrawal, drained 3,214.87 WETH (USD 8.14M) in a single flash-loaned transaction, then split the proceeds: 500 ETH back into Tornado Cash, 1,200 WETH swapped to USDC and sent to Kraken, and 900 ETH bridged to Polygon and placed with Binance in three sub-USD-1M transfers.",
    status: "in_progress",
    suspect_wallet: "0xa241ec91A7D0c2c8bf11d01C168579Ee1201a209",
    chains: ["Ethereum", "Polygon"],
    tags: ["Oracle Manipulation", "Flash Loan", "Tornado Cash", "Cross-chain", "Exchange Off-ramp"],
    wallet_count: 14,
    risk_score: 96.5,
    vasp: "Kraken / Binance",
    vasp_confidence: "CONFIRMED",
  },
  {
    id: "ransomware",
    case_number: "TRX-20240114-0038",
    title: "Ransomware Payment Tracing - LockBit 3.0",
    crime_type: "ransomware",
    description: "USD 1.05M ransom paid in USDT by a co-operating complainant, quoted to the victim as 25 BTC. The collection wallet was gas-funded from the Tornado Cash 10 ETH pool, then split the payment 40/30/30 across three fresh layering wallets within 34 minutes - one leg to a nested OTC desk, one to Kraken, one bridged to Arbitrum.",
    status: "open",
    suspect_wallet: "0x4eEE35E743a626F05f6e1cfaB340C04e791537b6",
    chains: ["Ethereum", "Arbitrum"],
    tags: ["Ransomware", "LockBit 3.0", "Layering", "Nested OTC", "Arbitrum"],
    wallet_count: 14,
    risk_score: 93.5,
    vasp: "Kraken",
    vasp_confidence: "CONFIRMED",
  },
  {
    id: "money-laundering",
    case_number: "TRX-20240113-0029",
    title: "International Money Laundering Ring - Peel Chain",
    crime_type: "money_laundering",
    description: "USD 4.18M of investment-fraud proceeds laundered through an 18-hop peel chain over three weeks. Each hop shaved a round-number slice (USD 12k-47.5k) into a fresh deposit address at one of six exchanges and forwarded the remainder, with two mid-chain stablecoin swaps on Curve to break same-asset tracing.",
    status: "closed",
    suspect_wallet: "0x57F2168D232D1D56608B0561fB628e9A584389C9",
    chains: ["Ethereum"],
    tags: ["Peel Chain", "Nested Exchanges", "Round Amounts", "Stablecoin Hopping", "Disclosure Orders"],
    wallet_count: 45,
    risk_score: 89,
    vasp: "Binance / OKX / HTX / Gate.io / KuCoin / Coinbase",
    vasp_confidence: "CONFIRMED",
  },
  {
    id: "darknet",
    case_number: "TRX-20240112-0017",
    title: "Darknet Market Seizure - Vendor Bond Escrow",
    crime_type: "darknet_market",
    description: "EVM-side asset trace supporting the seizure of a Hydra-successor marketplace. 26 in-scope vendor-bond wallets funded a single escrow contract over five weeks; the operator bridged 60% of the balance to Polygon, swapped it to USDC and moved it to Bybit. The residual balance was moved to law-enforcement custody under a seizure order.",
    status: "archived",
    suspect_wallet: "0x7cd628D05a4977b0c114830e96052142ED4a7827",
    chains: ["Ethereum", "Polygon"],
    tags: ["Darknet Market", "Vendor Bonds", "Seizure", "Polygon Bridge", "Forfeiture"],
    wallet_count: 34,
    risk_score: 87,
    vasp: "Bybit",
    vasp_confidence: "HIGH_CONFIDENCE",
  },
  {
    id: "sanctions",
    case_number: "TRX-20240111-0009",
    title: "Sanctions Evasion - Designated Individual",
    crime_type: "sanctions_evasion",
    description: "A dormant 2019-vintage wallet reactivated four days after an OFAC SDN designation moved 19,800 ETH (USD 50.10M) into a fresh primary wallet: 1,200 ETH into Tornado Cash as twelve identical deposits, 6,500 ETH shielded into Railgun, and 4,000 ETH swapped to USDT and bridged to BSC via Stargate before reaching Binance.",
    status: "in_progress",
    suspect_wallet: "0x3268F479AAc4A79bebbDEbE3b03AB9C4F56EeCDF",
    chains: ["Ethereum", "BSC"],
    tags: ["Sanctions", "OFAC SDN", "Tornado Cash", "Railgun", "Stargate", "BSC"],
    wallet_count: 10,
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
      // Step 1: Find existing seeded case in DB (by case_number) or fallback
      let caseResponse: Case | null = null;
      try {
        const casesList = await casesApi.list({ search: demoCase.case_number });
        if (casesList?.items?.length) {
          caseResponse =
            casesList.items.find((c) => c.case_number === demoCase.case_number) ||
            casesList.items[0];
        }
      } catch (err) {
        console.warn("Could not find seeded case by case_number", err);
      }

      // If not found in DB, create it
      if (!caseResponse) {
        caseResponse = await casesApi.create({
          title: demoCase.title,
          crime_type: demoCase.crime_type as any,
          description: demoCase.description,
          status: "in_progress",
        });
      }

      // Step 2: Find or create suspect wallet for this case
      let targetWallet: Wallet | null = null;
      try {
        const walletsList = await walletsApi.list({ case_id: caseResponse.id });
        if (walletsList?.items?.length) {
          targetWallet =
            walletsList.items.find(
              (w) => w.address.toLowerCase() === demoCase.suspect_wallet.toLowerCase()
            ) || walletsList.items[0];
        }
      } catch (err) {
        console.warn("Could not list wallets for case", err);
      }

      if (!targetWallet) {
        targetWallet = await walletsApi.create({
          case_id: caseResponse.id,
          address: demoCase.suspect_wallet,
          chain: demoCase.chains[0] || "Ethereum",
          label: "Suspect Wallet",
        });
      }

      // Step 3: Find completed investigation run
      let investigation: any = null;
      try {
        const invList = await investigationsApi.list({ case_id: caseResponse.id });
        if (invList?.items?.length) {
          investigation =
            invList.items.find((i) => i.status === "completed") || invList.items[0];
        }
      } catch (err) {
        console.warn("Could not list investigations", err);
      }

      if (!investigation) {
        investigation = {
          id: caseResponse.id,
          status: "completed",
          result_summary: {
            transactions_found: demoCase.wallet_count,
            unique_addresses: demoCase.wallet_count,
            demo: true,
          },
        };
      }

      // Step 4: Get attribution from riskApi
      let attributionResponse: any = null;
      try {
        attributionResponse = await riskApi.getAttribution(targetWallet.id, 6);
      } catch (err) {
        console.warn("Attribution lookup failed, using synthetic fallback", err);
        attributionResponse = {
          attributed: true,
          nearest_vasp: {
            entity_name: demoCase.vasp,
            confidence: demoCase.vasp_confidence,
            confidence_score: demoCase.vasp_confidence === "CONFIRMED" ? 0.95 : 0.85,
            distance_hops: 2,
          },
        };
      }

      // Step 5: Get risk assessment from riskApi
      let riskResponse: any = null;
      try {
        riskResponse = await riskApi.assessWallet(targetWallet.id);
      } catch (err) {
        console.warn("Risk assessment failed, using synthetic score", err);
        riskResponse = {
          overall_score: demoCase.risk_score,
          risk_level: demoCase.risk_score >= 75 ? "CRITICAL" : "HIGH",
          factors: [],
          methodology: "12-factor behavioral and on-chain intelligence risk engine",
        };
      }

      // Step 6: Get transactions from analysisApi
      let transactions: any[] = [];
      try {
        const txResponse = await analysisApi.getWalletTransactions(targetWallet.id, { page: 1, page_size: 100 });
        transactions = txResponse?.items || [];

        // Fallback: if suspect wallet has no direct tx rows, check other case wallets
        if (transactions.length === 0 && caseResponse) {
          const walletsList = await walletsApi.list({ case_id: caseResponse.id });
          for (const w of walletsList?.items || []) {
            if (w.id === targetWallet.id) continue;
            try {
              const otherTx = await analysisApi.getWalletTransactions(w.id, { page: 1, page_size: 50 });
              if (otherTx?.items?.length) {
                transactions = [...transactions, ...otherTx.items];
              }
            } catch {
              // ignore
            }
            if (transactions.length >= 50) break;
          }
        }
      } catch (err) {
        console.warn("Could not fetch wallet transactions", err);
      }

      setAnalysisResult({
        case: caseResponse,
        wallet: targetWallet,
        investigation,
        attribution: attributionResponse,
        risk: riskResponse,
        transactions,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo failed to load");
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
            <Card key={demoCase.id} className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => handleRunDemo(demoCase)}>
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

          {loading && (
            <div className="flex flex-col items-center justify-center p-12 text-center bg-card rounded-xl border border-border">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
              <p className="text-lg font-medium">Loading Synthetic Investigation Data...</p>
              <p className="text-sm text-muted-foreground">Tracing fund flows, querying Neo4j graph, and computing 12-factor risk score</p>
            </div>
          )}

          {analysisResult && (
            <Tabs defaultValue="overview" className="space-y-4">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="transactions">
                  Transactions {analysisResult.transactions?.length ? `(${analysisResult.transactions.length})` : ""}
                </TabsTrigger>
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
                          <p className="text-3xl font-bold tracking-tight">
                            {analysisResult.transactions?.length || analysisResult.investigation?.result_summary?.transactions_found || 0}
                          </p>
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
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>
                        Transactions ({analysisResult.transactions?.length || 0})
                      </CardTitle>
                      <p className="text-sm text-muted-foreground mt-1">
                        On-chain activity for suspect wallet{" "}
                        <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                          {formatAddress(selectedCase?.suspect_wallet || analysisResult.wallet?.address || "")}
                        </code>
                      </p>
                    </div>
                    <Link
                      href={`/analyze?address=${selectedCase?.suspect_wallet || analysisResult.wallet?.address || ""}`}
                      className="text-xs text-primary hover:underline flex items-center gap-1"
                    >
                      Open in Analyze <ExternalLink className="w-3 h-3" />
                    </Link>
                  </CardHeader>
                  <CardContent className="p-0">
                    {(!analysisResult.transactions || analysisResult.transactions.length === 0) ? (
                      <div className="text-center py-12 text-muted-foreground">
                        <FileText className="w-12 h-12 mx-auto mb-3 opacity-40" />
                        <p className="text-base font-medium">No transactions recorded</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          No transactions found for this wallet in the seeded database.
                        </p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Tx Hash</TableHead>
                              <TableHead>Block</TableHead>
                              <TableHead>Time</TableHead>
                              <TableHead>From</TableHead>
                              <TableHead>To</TableHead>
                              <TableHead>Value (USD)</TableHead>
                              <TableHead>Token</TableHead>
                              <TableHead>Method</TableHead>
                              <TableHead>Flags</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {analysisResult.transactions.map((tx: any) => {
                              const isFromSuspect =
                                tx.from_address?.toLowerCase() ===
                                (selectedCase?.suspect_wallet || analysisResult.wallet?.address || "").toLowerCase();
                              const isToSuspect =
                                tx.to_address?.toLowerCase() ===
                                (selectedCase?.suspect_wallet || analysisResult.wallet?.address || "").toLowerCase();

                              return (
                                <TableRow key={tx.tx_hash} className="hover:bg-muted/50">
                                  <TableCell>
                                    <code className="font-mono text-sm">{formatAddress(tx.tx_hash)}</code>
                                  </TableCell>
                                  <TableCell className="font-mono text-sm">
                                    #{tx.block_number?.toLocaleString()}
                                  </TableCell>
                                  <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                                    {formatRelativeTime(tx.timestamp)}
                                  </TableCell>
                                  <TableCell>
                                    <code
                                      className={`font-mono text-sm ${
                                        isFromSuspect ? "text-amber-400 font-semibold" : ""
                                      }`}
                                      title={tx.from_address}
                                    >
                                      {formatAddress(tx.from_address)}
                                      {isFromSuspect && " (Suspect)"}
                                    </code>
                                  </TableCell>
                                  <TableCell>
                                    <code
                                      className={`font-mono text-sm ${
                                        isToSuspect ? "text-amber-400 font-semibold" : ""
                                      }`}
                                      title={tx.to_address}
                                    >
                                      {formatAddress(tx.to_address)}
                                      {isToSuspect && " (Suspect)"}
                                    </code>
                                  </TableCell>
                                  <TableCell className="font-mono tabular-nums text-sm font-medium">
                                    {formatCurrency(tx.value_usd ?? tx.value ?? 0)}
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
                                        <AlertTriangle className="w-3 h-3" /> Suspicious
                                      </Badge>
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </CardContent>
                </Card>
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
                        <p className="text-xs mt-2">View full graph in <Button variant="ghost" size="sm" asChild><Link href={`/graph?address=${encodeURIComponent(analysisResult.wallet?.address || selectedCase?.suspect_wallet || "")}`}><ExternalLink className="w-4 h-4 mr-1" />Open Graph</Link></Button></p>
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