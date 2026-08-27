"use client";

import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatRelativeTime, formatAddress, getRiskColor, getRiskBg, getConfidenceColor } from "@/lib/utils";
import {
  Shield,
  Search,
  Activity,
  FileText,
  AlertTriangle,
  CheckCircle,
  Clock,
  TrendingUp,
  ExternalLink,
  Plus,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";

const mockCase = {
  id: "1",
  case_number: "TRX-20240115-0042",
  title: "DeFi Protocol Exploit",
  crime_type: "fraud",
  description: "Major DeFi protocol exploit involving flash loan attack across multiple protocols. Initial attack vector identified as a vulnerable oracle price feed. Funds traced through Tornado Cash and multiple DEX swaps.",
  status: "in_progress",
  assigned_to: "Analyst A",
  wallets: 15,
  updated: "2024-01-15T10:30:00Z",
  created: "2024-01-15T08:00:00Z",
};

const mockWallets = [
  { id: "1", address: "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", chain: "Ethereum", label: "Attacker", attribution_status: "attributed", risk_score: 95, entity_name: "Unknown", entity_confidence: "PROBABLE" },
  { id: "2", address: "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", chain: "Ethereum", label: "Intermediary 1", attribution_status: "under_review", risk_score: 72, entity_name: "Uniswap V3", entity_confidence: "HIGH_CONFIDENCE" },
  { id: "3", address: "0xA0b86a33E6441b8C4C8C8C8C8C8C8C8C8C8C8C", chain: "Polygon", label: "Intermediary 2", attribution_status: "unverified", risk_score: 45, entity_name: undefined, entity_confidence: undefined },
  { id: "4", address: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", chain: "Ethereum", label: "Exchange Deposit", attribution_status: "confirmed", risk_score: 88, entity_name: "Binance", entity_confidence: "CONFIRMED" },
  { id: "5", address: "0x6B175474E89094C44Da98b954EedeAC495271d0F", chain: "Ethereum", label: "Token Contract", attribution_status: "unverified", risk_score: 12, entity_name: "DAI Stablecoin", entity_confidence: "CONFIRMED" },
];

const mockInvestigations = [
  { id: "1", wallet: "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", chain: "Ethereum", status: "completed", progress: 100, started: "2024-01-15T08:15:00Z", completed: "2024-01-15T09:45:00Z" },
  { id: "2", wallet: "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", chain: "Ethereum", status: "running", progress: 65, started: "2024-01-15T09:00:00Z", completed: undefined },
  { id: "3", wallet: "0xA0b86a33E6441b8C4C8C8C8C8C8C8C8C8C8C8C", chain: "Polygon", status: "pending", progress: 0, started: "2024-01-15T10:00:00Z", completed: undefined },
];

const statusBadges = {
  open: <Badge variant="info">Open</Badge>,
  in_progress: <Badge variant="warning">In Progress</Badge>,
  closed: <Badge variant="success">Closed</Badge>,
  archived: <Badge variant="secondary">Archived</Badge>,
};

const attributionBadges = {
  unverified: <Badge variant="secondary">Unverified</Badge>,
  under_review: <Badge variant="warning">Under Review</Badge>,
  attributed: <Badge variant="info">Attributed</Badge>,
  confirmed: <Badge variant="success">Confirmed</Badge>,
};

const investigationStatusBadges = {
  pending: <Badge variant="secondary">Pending</Badge>,
  running: <Badge variant="warning">Running</Badge>,
  completed: <Badge variant="success">Completed</Badge>,
  failed: <Badge variant="destructive">Failed</Badge>,
};

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.caseId;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="capitalize text-sm">
              {mockCase.crime_type.replace("_", " ")}
            </Badge>
            <h1 className="text-2xl font-bold tracking-tight">{mockCase.title}</h1>
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
            <span>Case: <span className="font-mono text-foreground">{mockCase.case_number}</span></span>
            <span>Status: {statusBadges[mockCase.status as keyof typeof statusBadges]}</span>
            <span>Assigned: {mockCase.assigned_to}</span>
            <span>Created: {formatRelativeTime(mockCase.created)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href={`/analyze?case=${caseId}`}>
              <Plus className="w-4 h-4 mr-2" />
              Add Wallet
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href={`/reports?case=${caseId}`}>
              <FileText className="w-4 h-4 mr-2" />
              Generate Report
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Tracked Wallets</p>
                <p className="text-3xl font-bold tracking-tight">{mockWallets.length}</p>
              </div>
              <div className="p-3 rounded-lg bg-primary/10 text-primary">
                <Shield className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Completed Traces</p>
                <p className="text-3xl font-bold tracking-tight">
                  {mockInvestigations.filter((i) => i.status === "completed").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-green-500/10 text-green-400">
                <CheckCircle className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Running Traces</p>
                <p className="text-3xl font-bold tracking-tight">
                  {mockInvestigations.filter((i) => i.status === "running").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-amber-500/10 text-amber-400">
                <Activity className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">High Risk Wallets</p>
                <p className="text-3xl font-bold tracking-tight text-destructive">
                  {mockWallets.filter((w) => w.risk_score >= 75).length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-destructive/10 text-destructive">
                <AlertTriangle className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="wallets">Wallets ({mockWallets.length})</TabsTrigger>
          <TabsTrigger value="investigations">Investigations ({mockInvestigations.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Case Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground whitespace-pre-wrap">{mockCase.description}</p>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Risk Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Average Risk Score</span>
                      <span className="font-bold text-destructive">
                        {Math.round(mockWallets.reduce((a, b) => a + b.risk_score, 0) / mockWallets.length)}
                      </span>
                    </div>
                    <div className="h-2 bg-tracex-border rounded-full overflow-hidden">
                      <div
                        className="h-full bg-destructive"
                        style={{ width: `${mockWallets.reduce((a, b) => a + b.risk_score, 0) / mockWallets.length}%` }}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Chains Involved</p>
                      <p className="font-bold">2 (Ethereum, Polygon)</p>
                    </div>
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Exchanges Identified</p>
                      <p className="font-bold text-green-400">1 (Binance)</p>
                    </div>
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Mixers Detected</p>
                      <p className="font-bold text-amber-400">1 (Tornado Cash)</p>
                    </div>
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Total Value Traced</p>
                      <p className="font-bold">$2.4M</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-lg">Recent Activity</CardTitle>
                <Button variant="ghost" size="sm">View All</Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                    <div className="w-2 h-2 rounded-full bg-green-400" />
                    <div className="flex-1">
                      <p className="font-medium">Investigation completed for wallet <code className="font-mono text-sm">{formatAddress(mockWallets[1].address)}</code></p>
                      <p className="text-sm text-muted-foreground">Identified Binance deposit with CONFIRMED confidence</p>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatRelativeTime("2024-01-15T09:45:00Z")}</span>
                  </div>
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                    <div className="w-2 h-2 rounded-full bg-amber-400" />
                    <div className="flex-1">
                      <p className="font-medium">Trace running for wallet <code className="font-mono text-sm">{formatAddress(mockWallets[2].address)}</code></p>
                      <p className="text-sm text-muted-foreground">65% complete - tracing through Polygon DEX swaps</p>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatRelativeTime("2024-01-15T10:00:00Z")}</span>
                  </div>
                  <div className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                    <div className="w-2 h-2 rounded-full bg-blue-400" />
                    <div className="flex-1">
                      <p className="font-medium">New wallet added to case</p>
                      <p className="text-sm text-muted-foreground">DAI token contract identified as intermediary</p>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatRelativeTime("2024-01-15T10:30:00Z")}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="wallets">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Tracked Wallets</CardTitle>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/analyze?case=${caseId}`}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Wallet
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Address</TableHead>
                      <TableHead>Chain</TableHead>
                      <TableHead>Label</TableHead>
                      <TableHead>Attribution</TableHead>
                      <TableHead>Risk Score</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockWallets.map((w) => (
                      <TableRow key={w.id}>
                        <TableCell>
                          <code className="font-mono text-sm">{formatAddress(w.address)}</code>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{w.chain}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{w.label}</TableCell>
                        <TableCell>{attributionBadges[w.attribution_status as keyof typeof attributionBadges]}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className={`h-2 w-24 ${getRiskBg(w.risk_score)} rounded-full overflow-hidden`}>
                              <div
                                className={`h-full ${getRiskColor(w.risk_score)} transition-all duration-300`}
                                style={{ width: `${w.risk_score}%` }}
                              />
                            </div>
                            <span className={getRiskColor(w.risk_score)}>{w.risk_score}</span>
                          </div>
                        </TableCell>
                        <TableCell>{w.entity_name || <span className="text-muted-foreground">Unknown</span>}</TableCell>
                        <TableCell>
                          {w.entity_confidence && (
                            <Badge
                              className={getConfidenceColor(w.entity_confidence)}
                            >
                              {w.entity_confidence}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="icon" asChild>
                            <Link href={`/analyze?wallet=${w.id}&case=${caseId}`}>
                              <ChevronRight className="w-4 h-4" />
                            </Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="investigations">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Investigation Runs</CardTitle>
              <Button variant="outline" size="sm">Start New Trace</Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {mockInvestigations.map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between p-4 rounded-lg bg-tracex-surface-hover/50">
                    <div className="flex items-center gap-4">
                      <div className="w-2 h-2 rounded-full bg-primary" />
                      <div>
                        <p className="font-mono text-sm">{formatAddress(inv.wallet)}</p>
                        <p className="text-xs text-muted-foreground">
                          {inv.chain} • Started {formatRelativeTime(inv.started)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="w-40">
                        <div className="h-2 bg-tracex-border rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all duration-300"
                            style={{ width: `${inv.progress}%` }}
                          />
                        </div>
                      </div>
                      <span className="text-sm text-muted-foreground">{inv.progress}%</span>
                      {investigationStatusBadges[inv.status as keyof typeof investigationStatusBadges]}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}