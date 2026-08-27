"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatRelativeTime, formatAddress, getRiskColor, getRiskBg, getConfidenceColor } from "@/lib/utils";
import { casesApi, walletsApi, investigationsApi, riskApi } from "@/lib/api";
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
  GitBranch,
  BarChart3,
} from "lucide-react";
import Link from "next/link";

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

const attributionLabels: Record<string, string> = {
  unverified: "Unverified",
  under_review: "Under Review",
  attributed: "Attributed",
  confirmed: "Confirmed",
};

const investigationStatusLabels: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.caseId as string;

  const { data: caseData, isLoading: caseLoading, error: caseError } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.get(caseId),
    enabled: !!caseId,
  });

  const { data: walletsData, isLoading: walletsLoading } = useQuery({
    queryKey: ["wallets", { case_id: caseId }],
    queryFn: () => walletsApi.list({ case_id: caseId, page_size: 100 }),
    enabled: !!caseId,
  });

  const { data: investigationsData, isLoading: investigationsLoading } = useQuery({
    queryKey: ["investigations", { case_id: caseId }],
    queryFn: () => investigationsApi.list({ case_id: caseId, page_size: 100 }),
    enabled: !!caseId,
  });

  const { data: caseRiskSummary } = useQuery({
    queryKey: ["caseRiskSummary", caseId],
    queryFn: () => riskApi.getCaseRiskSummary(caseId),
    enabled: !!caseId,
  });

  if (caseLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (caseError || !caseData) {
    return (
      <div className="text-center py-12 text-destructive">
        Failed to load case: {caseError instanceof Error ? caseError.message : "Case not found"}
      </div>
    );
  }

  const c = caseData;
  const wallets = walletsData?.items || [];
  const investigations = investigationsData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="capitalize text-sm">
              {c.crime_type.replace("_", " ")}
            </Badge>
            <h1 className="text-2xl font-bold tracking-tight">{c.title}</h1>
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
            <span>Case: <span className="font-mono text-foreground">{c.case_number}</span></span>
            <span>Status: <Badge variant={c.status === "in_progress" ? "warning" : c.status === "open" ? "info" : c.status === "closed" ? "success" : "secondary"}>{statusLabels[c.status]}</Badge></span>
            <span>Assigned: {c.assigned_to || "Unassigned"}</span>
            <span>Created: {formatRelativeTime(c.created_at)}</span>
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
                <p className="text-3xl font-bold tracking-tight">{wallets.length}</p>
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
                  {investigations.filter((i: any) => i.status === "completed").length}
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
                  {investigations.filter((i: any) => i.status === "running").length}
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
                  {wallets.filter((w: any) => w.risk_score >= 75).length}
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
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="wallets">Wallets ({wallets.length})</TabsTrigger>
          <TabsTrigger value="investigations">Investigations ({investigations.length})</TabsTrigger>
          <TabsTrigger value="risk">Risk Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Case Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground whitespace-pre-wrap">{c.description}</p>
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
                        {wallets.length > 0 ? Math.round(wallets.reduce((a: number, b: any) => a + b.risk_score, 0) / wallets.length) : 0}
                      </span>
                    </div>
                    <div className="h-2 bg-tracex-border rounded-full overflow-hidden">
                      <div
                        className="h-full bg-destructive"
                        style={{ width: `${wallets.length > 0 ? wallets.reduce((a: number, b: any) => a + b.risk_score, 0) / wallets.length : 0}%` }}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Chains Involved</p>
                      <p className="font-bold">
                        {Array.from(new Set(wallets.map((w: any) => w.chain))).length} ({Array.from(new Set(wallets.map((w: any) => w.chain))).join(", ")})
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Exchanges Identified</p>
                      <p className="font-bold text-green-400">
                        {wallets.filter((w: any) => w.entity_name && w.entity_confidence === "CONFIRMED").length}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Mixers Detected</p>
                      <p className="font-bold text-amber-400">
                        {wallets.filter((w: any) => w.entity_name?.toLowerCase().includes("tornado") || w.entity_name?.toLowerCase().includes("mixer")).length}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-tracex-surface-hover/50">
                      <p className="text-sm text-muted-foreground">Total Value Traced</p>
                      <p className="font-bold">${"0"}</p>
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
                  {investigations.slice(0, 3).map((inv: any) => (
                    <div key={inv.id} className="flex items-center gap-4 p-3 rounded-lg bg-tracex-surface-hover/50">
                      <div className={`w-2 h-2 rounded-full ${inv.status === "completed" ? "bg-green-400" : inv.status === "running" ? "bg-amber-400" : "bg-blue-400"}`} />
                      <div className="flex-1">
                        <p className="font-medium">
                          {inv.status === "completed" ? "Investigation completed" : inv.status === "running" ? "Trace running" : "Investigation pending"}
                          {inv.wallet_id && <code className="font-mono text-sm ml-2">{formatAddress(inv.wallet_id)}</code>}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {inv.result_summary?.transactions_found ? `${inv.result_summary.transactions_found} transactions found` : "Waiting to start..."}
                        </p>
                      </div>
                      <span className="text-xs text-muted-foreground">{formatRelativeTime(inv.updated_at || inv.started_at)}</span>
                    </div>
                  ))}
                  {investigations.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground">
                      <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p className="text-lg font-medium">No investigations yet</p>
                      <p className="text-sm mt-1">Add wallets and start traces to see activity here</p>
                    </div>
                  )}
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
              {walletsLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                </div>
              ) : wallets.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">No wallets tracked</p>
                  <p className="text-sm mt-1">Click "Add Wallet" to start tracking addresses</p>
                </div>
              ) : (
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
                      {wallets.map((w: any) => (
                        <TableRow key={w.id}>
                          <TableCell>
                            <code className="font-mono text-sm">{formatAddress(w.address)}</code>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{w.chain}</Badge>
                          </TableCell>
                          <TableCell className="font-medium">{w.label}</TableCell>
                          <TableCell>
                            <Badge variant={w.attribution_status === "confirmed" ? "success" : w.attribution_status === "attributed" ? "info" : w.attribution_status === "under_review" ? "warning" : "secondary"}>
                              {attributionLabels[w.attribution_status]}
                            </Badge>
                          </TableCell>
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
                              <Badge className={getConfidenceColor(w.entity_confidence)}>
                                {w.entity_confidence}
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button variant="ghost" size="icon" asChild>
                                <Link href={`/analyze?wallet=${w.id}&case=${caseId}`}>
                                  <ChevronRight className="w-4 h-4" />
                                </Link>
                              </Button>
                              <Button variant="ghost" size="icon" asChild>
                                <Link href={`/graph?wallet=${w.id}`}>
                                  <GitBranch className="w-4 h-4" />
                                </Link>
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risk">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold">Risk Analysis</h2>
                <p className="text-muted-foreground">Case-level risk assessment and attribution summary</p>
              </div>
              <Button variant="outline" asChild>
                <Link href={`/risk?case=${caseId}`}>
                  <BarChart3 className="w-4 h-4 mr-2" />
                  Open Full Risk Dashboard
                </Link>
              </Button>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Case Risk Summary</CardTitle>
              </CardHeader>
              <CardContent>
                {caseRiskSummary && (
                  <>
                    <div className="grid gap-4 md:grid-cols-4 mb-6">
                      <Card>
                        <CardContent className="p-6">
                          <p className="text-sm font-medium text-muted-foreground">Total Wallets</p>
                          <p className="text-3xl font-bold tracking-tight">{caseRiskSummary.total_wallets}</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-6">
                          <p className="text-sm font-medium text-muted-foreground">Avg Risk Score</p>
                          <p className="text-3xl font-bold tracking-tight text-destructive">{caseRiskSummary.average_risk_score}</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-6">
                          <p className="text-sm font-medium text-muted-foreground">Confirmed Attributions</p>
                          <p className="text-3xl font-bold tracking-tight text-green-400">{caseRiskSummary.attribution.confirmed}</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-6">
                          <p className="text-sm font-medium text-muted-foreground">Chains</p>
                          <p className="text-3xl font-bold tracking-tight">{caseRiskSummary.chains.length}</p>
                        </CardContent>
                      </Card>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2">
                      <Card>
                        <CardHeader>
                          <CardTitle>Risk Distribution</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {Object.entries(caseRiskSummary.risk_distribution).map(([level, count]) => (
                              <div key={level} className="flex items-center gap-4">
                                <Badge 
                                  variant={
                                    level === "critical" ? "destructive" :
                                    level === "high" ? "destructive" :
                                    level === "medium" ? "warning" :
                                    level === "low" ? "success" : "info"
                                  }
                                  className="w-24"
                                >
                                  {level.toUpperCase()}
                                </Badge>
                                <div className="flex-1 h-2 bg-tracex-border rounded-full overflow-hidden">
                                  <div className={`h-full ${level === "critical" ? "bg-destructive" : level === "high" ? "bg-destructive" : level === "medium" ? "bg-amber-400" : level === "low" ? "bg-green-400" : "bg-blue-400"}`} style={{ width: `${caseRiskSummary.total_wallets > 0 ? (count / caseRiskSummary.total_wallets) * 100 : 0}%` }} />
                                </div>
                                <span className="font-mono w-10 text-right">{count}</span>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle>Top Risk Wallets</CardTitle>
                        </CardHeader>
                        <CardContent>
                          {caseRiskSummary.top_risk_wallets.length > 0 ? (
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>Wallet</TableHead>
                                  <TableHead>Label</TableHead>
                                  <TableHead>Risk Score</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {caseRiskSummary.top_risk_wallets.map((w: any) => (
                                  <TableRow key={w.address}>
                                    <TableCell className="font-mono text-sm">{formatAddress(w.address)}</TableCell>
                                    <TableCell>{w.label || "-"}</TableCell>
                                    <TableCell>
                                      <div className="flex items-center gap-2">
                                        <div className={`h-2 w-24 ${getRiskBg(w.risk_score)} rounded-full overflow-hidden`}>
                                          <div className={`h-full ${getRiskColor(w.risk_score)}`} style={{ width: `${w.risk_score}%` }} />
                                        </div>
                                        <span className={getRiskColor(w.risk_score)}>{w.risk_score}</span>
                                      </div>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          ) : (
                            <p className="text-muted-foreground">No wallets in case</p>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="investigations">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Investigation Runs</CardTitle>
              <Button variant="outline" size="sm">Start New Trace</Button>
            </CardHeader>
            <CardContent>
              {investigationsLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                </div>
              ) : investigations.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">No investigations yet</p>
                  <p className="text-sm mt-1">Add wallets and start traces to see investigation runs</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {investigations.map((inv: any) => (
                    <div key={inv.id} className="flex items-center justify-between p-4 rounded-lg bg-tracex-surface-hover/50">
                      <div className="flex items-center gap-4">
                        <div className={`w-2 h-2 rounded-full ${inv.status === "completed" ? "bg-green-400" : inv.status === "running" ? "bg-amber-400" : inv.status === "failed" ? "bg-destructive" : "bg-blue-400"}`} />
                        <div>
                          <p className="font-mono text-sm">{formatAddress(inv.wallet_id || "unknown")}</p>
                          <p className="text-xs text-muted-foreground">
                            Started {formatRelativeTime(inv.started_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="w-40">
                          <div className="h-2 bg-tracex-border rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all duration-300 ${
                                inv.status === "completed" ? "bg-green-400" :
                                inv.status === "running" ? "bg-amber-400" :
                                inv.status === "failed" ? "bg-destructive" : "bg-blue-400"
                              }`}
                              style={{ width: `${inv.result_summary?.progress || (inv.status === "completed" ? 100 : inv.status === "running" ? 50 : 0)}%` }}
                            />
                          </div>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {inv.result_summary?.progress || (inv.status === "completed" ? 100 : inv.status === "running" ? 50 : 0)}%
                        </span>
                        <Badge variant={
                          inv.status === "completed" ? "success" :
                          inv.status === "running" ? "warning" :
                          inv.status === "failed" ? "destructive" : "secondary"
                        }>
                          {investigationStatusLabels[inv.status]}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}