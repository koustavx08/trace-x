"use client";

import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { formatAddress, formatRelativeTime, getRiskColor, getRiskBg, getConfidenceColor } from "@/lib/utils";
import { riskApi, graphApi } from "@/lib/api";
import {
  AlertTriangle,
  CheckCircle,
  Shield,
  Target,
  BarChart3,
  FileText,
  Download,
  ChevronRight,
  ExternalLink,
  Search,
  Filter,
  Layers,
} from "lucide-react";
import Link from "next/link";

interface RiskFactor {
  type: string;
  severity: string;
  score: number;
  weight: number;
  weighted_score: number;
  description: string;
  evidence: Record<string, any>;
  confidence: string;
}

interface RiskAssessment {
  overall_score: number;
  risk_level: string;
  factors: RiskFactor[];
  summary: string;
  methodology: string;
  assessed_at: string;
}

interface Attribution {
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

interface AttributionResponse {
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

interface CaseRiskSummary {
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

export default function RiskPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const caseId = params.caseId as string;
  const walletId = searchParams.get("wallet");
  const [activeTab, setActiveTab] = useState("overview");

  const { data: caseRisk, isLoading: caseRiskLoading } = useQuery({
    queryKey: ["caseRiskSummary", caseId],
    queryFn: () => riskApi.getCaseRiskSummary(caseId),
    enabled: !!caseId,
  });

  const { data: walletRisk, isLoading: walletRiskLoading } = useQuery({
    queryKey: ["walletRisk", walletId],
    queryFn: () => riskApi.assessWallet(walletId!),
    enabled: !!walletId,
  });

  const { data: walletAttribution, isLoading: attributionLoading } = useQuery({
    queryKey: ["walletAttribution", walletId],
    queryFn: () => riskApi.getAttribution(walletId!),
    enabled: !!walletId,
  });

  if (!walletId && !caseId) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Shield className="w-12 h-12 mx-auto mb-4 opacity-30" />
        <p className="text-lg font-medium">Select a case or wallet to view risk analysis</p>
        <p className="text-sm mt-1">Navigate from Cases or Analyze pages</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Risk Analysis</h1>
          <p className="text-muted-foreground">
            {walletId ? `Wallet: ${formatAddress(walletId)}` : `Case: ${caseId}`}
          </p>
        </div>
        {walletId && (
          <Button variant="outline" asChild>
            <Link href={`/graph?wallet=${walletId}`}>
              <ExternalLink className="w-4 h-4 mr-2" />
              View Graph
            </Link>
          </Button>
        )}
      </div>

      {walletId && walletRisk && (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="factors">Risk Factors ({walletRisk.factors.length})</TabsTrigger>
            <TabsTrigger value="attribution">Attribution ({walletAttribution?.all_attributions.length || 0})</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Overall Risk Score</p>
                      <p className="text-4xl font-bold tracking-tight {getRiskColor(walletRisk.overall_score)}">
                        {walletRisk.overall_score.toFixed(1)}
                      </p>
                    </div>
                    <div className={`p-4 rounded-lg ${getRiskBg(walletRisk.overall_score)}`}>
                      <Badge 
                        variant={
                          walletRisk.risk_level === "critical" ? "destructive" :
                          walletRisk.risk_level === "high" ? "destructive" :
                          walletRisk.risk_level === "medium" ? "warning" :
                          walletRisk.risk_level === "low" ? "success" : "info"
                        }
                        className="text-lg"
                      >
                        {walletRisk.risk_level.toUpperCase()}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Risk Factors</p>
                  <p className="text-3xl font-bold tracking-tight">{walletRisk.factors.length}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Attributions</p>
                  <p className="text-3xl font-bold tracking-tight">{walletAttribution?.all_attributions.length || 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Nearest VASP</p>
                  <p className="text-3xl font-bold tracking-tight">
                    {walletAttribution?.nearest_vasp ? "Found" : "None"}
                  </p>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Risk Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground whitespace-pre-wrap">{walletRisk.summary}</p>
              </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Top Risk Factors</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {walletRisk.factors
                      .sort((a, b) => b.weighted_score - a.weighted_score)
                      .slice(0, 5)
                      .map((factor) => (
                        <div key={factor.type} className="p-3 rounded-lg border border-tracex-border bg-tracex-surface-hover/50">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium">{factor.type.replace("_", " ")}</span>
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
                          <div className="flex items-center gap-2">
                            <div className={`h-2 flex-1 ${getRiskBg(factor.score)} rounded-full overflow-hidden`}>
                              <div className={`h-full ${getRiskColor(factor.score)}`} style={{ width: `${factor.score}%` }} />
                            </div>
                            <span className="text-sm font-mono tabular-nums">{factor.score}/100</span>
                            <Badge variant="outline" className="text-xs">{factor.weighted_score.toFixed(1)} weighted</Badge>
                          </div>
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Attribution Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  {walletAttribution?.nearest_vasp ? (
                    <div className="space-y-3">
                      <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{walletAttribution.nearest_vasp.entity_name}</p>
                            <p className="text-sm text-muted-foreground">
                              {walletAttribution.nearest_vasp.entity_type} • {walletAttribution.nearest_vasp.distance_hops} hops • {walletAttribution.nearest_vasp.total_value_eth.toFixed(4)} ETH
                            </p>
                          </div>
                          <Badge 
                            className={getConfidenceColor(walletAttribution.nearest_vasp.confidence)}
                          >
                            {walletAttribution.nearest_vasp.confidence}
                          </Badge>
                        </div>
                        <div className="mt-2 h-2 bg-tracex-border rounded-full overflow-hidden">
                          <div className="h-full bg-primary" style={{ width: `${walletAttribution.nearest_vasp.confidence_score * 100}%` }} />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Confidence: {(walletAttribution.nearest_vasp.confidence_score * 100).toFixed(1)}%</p>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div className="p-2 rounded bg-tracex-surface-hover/50">
                          <p className="text-muted-foreground">Exchanges</p>
                          <p className="font-bold">{walletAttribution.summary.exchanges_found}</p>
                        </div>
                        <div className="p-2 rounded bg-tracex-surface-hover/50">
                          <p className="text-muted-foreground">Mixers</p>
                          <p className="font-bold text-amber-400">{walletAttribution.summary.mixers_found}</p>
                        </div>
                        <div className="p-2 rounded bg-tracex-surface-hover/50">
                          <p className="text-muted-foreground">Bridges</p>
                          <p className="font-bold">{walletAttribution.summary.bridges_found}</p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Target className="w-12 h-12 mx-auto mb-4 opacity-30" />
                      <p className="text-lg font-medium">No VASP Attribution Found</p>
                      <p className="text-sm mt-1">Fund flow did not reach a known exchange within trace depth</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="factors" className="space-y-4">
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Factor</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Score</TableHead>
                      <TableHead>Weight</TableHead>
                      <TableHead>Weighted</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Description</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {walletRisk.factors
                      .sort((a, b) => b.weighted_score - a.weighted_score)
                      .map((factor) => (
                        <TableRow key={factor.type}>
                          <TableCell className="font-medium">{factor.type.replace("_", " ")}</TableCell>
                          <TableCell>
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
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <div className={`h-2 w-24 ${getRiskBg(factor.score)} rounded-full overflow-hidden`}>
                                <div className={`h-full ${getRiskColor(factor.score)}`} style={{ width: `${factor.score}%` }} />
                              </div>
                              <span>{factor.score}</span>
                            </div>
                          </TableCell>
                          <TableCell>{factor.weight}</TableCell>
                          <TableCell className="font-mono tabular-nums">{factor.weighted_score.toFixed(1)}</TableCell>
                          <TableCell>
                            <Badge className={getConfidenceColor(factor.confidence)}>
                              {factor.confidence}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground max-w-xs truncate">{factor.description}</TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="attribution" className="space-y-4">
            {walletAttribution && walletAttribution.all_attributions.length > 0 ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">All Attributions ({walletAttribution.all_attributions.length})</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Entity</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Address</TableHead>
                            <TableHead>Confidence</TableHead>
                            <TableHead>Score</TableHead>
                            <TableHead>Hops</TableHead>
                            <TableHead>Value (ETH)</TableHead>
                            <TableHead>Path Type</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {walletAttribution.all_attributions.map((attr) => (
                            <TableRow key={attr.entity_name + attr.address}>
                              <TableCell className="font-medium">{attr.entity_name}</TableCell>
                              <TableCell>
                                <Badge variant="outline" className="capitalize">{attr.entity_type}</Badge>
                              </TableCell>
                              <TableCell className="font-mono text-sm">{formatAddress(attr.address)}</TableCell>
                              <TableCell>
                                <Badge className={getConfidenceColor(attr.confidence)}>
                                  {attr.confidence}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-mono tabular-nums">{(attr.confidence_score * 100).toFixed(1)}%</TableCell>
                              <TableCell>{attr.distance_hops}</TableCell>
                              <TableCell className="font-mono tabular-nums">{attr.total_value_eth.toFixed(4)}</TableCell>
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

                {walletAttribution.nearest_vasp && walletAttribution.nearest_vasp.path && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">Path to Nearest VASP</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {walletAttribution.nearest_vasp.path.nodes.map((nodeId: string, i: number) => (
                          <div key={nodeId} className="flex items-center gap-3 p-2 rounded bg-tracex-surface-hover/50">
                            <span className="w-8 text-center text-muted-foreground">{i}</span>
                            <div className="flex-1">
                              <p className="font-mono text-sm">{nodeId}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <Target className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p className="text-lg font-medium">No Attributions Found</p>
                  <p className="text-sm text-muted-foreground mt-1">No VASP or entity attribution within trace depth</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      )}

      {!walletId && caseRisk && (
        <Card>
          <CardHeader>
            <CardTitle>Case Risk Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-4 mb-6">
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Total Wallets</p>
                  <p className="text-3xl font-bold tracking-tight">{caseRisk?.total_wallets ?? 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Avg Risk Score</p>
                  <p className="text-3xl font-bold tracking-tight text-destructive">{caseRisk?.average_risk_score ?? 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Confirmed Attributions</p>
                  <p className="text-3xl font-bold tracking-tight text-green-400">{caseRisk?.attribution?.confirmed ?? 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm font-medium text-muted-foreground">Chains</p>
                  <p className="text-3xl font-bold tracking-tight">{caseRisk?.chains?.length ?? 0}</p>
                </CardContent>
              </Card>
            </div>

            {(!caseRisk?.total_wallets || caseRisk.total_wallets === 0) && (
              <div className="p-4 mb-6 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-700 dark:text-blue-300 text-sm">
                No suspect wallets added to this case yet. Add suspect addresses in the Case detail view to generate live risk scoring.
              </div>
            )}

            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Risk Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(caseRisk?.risk_distribution || {}).map(([level, count]) => (
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
                          <div className={`h-full ${level === "critical" ? "bg-destructive" : level === "high" ? "bg-destructive" : level === "medium" ? "bg-amber-400" : level === "low" ? "bg-green-400" : "bg-blue-400"}`} style={{ width: `${(caseRisk?.total_wallets || 0) > 0 ? (count / (caseRisk?.total_wallets || 1)) * 100 : 0}%` }} />
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
                  {caseRisk?.top_risk_wallets && caseRisk.top_risk_wallets.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Wallet</TableHead>
                          <TableHead>Label</TableHead>
                          <TableHead>Risk Score</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {caseRisk.top_risk_wallets.map((w) => (
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
                    <p className="text-muted-foreground">No suspect wallets added yet</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}