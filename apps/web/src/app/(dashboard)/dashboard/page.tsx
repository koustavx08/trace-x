"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { formatRelativeTime, formatAddress } from "@/lib/utils";
import { casesApi, walletsApi, investigationsApi, healthApi } from "@/lib/api";
import {
  Activity,
  FolderOpen,
  Search,
  FileText,
  AlertTriangle,
  CheckCircle,
  Clock,
  TrendingUp,
  Plus,
  Shield,
} from "lucide-react";
import Link from "next/link";

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

const investigationStatusLabels: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export default function DashboardPage() {
  const { data: casesData } = useQuery({
    queryKey: ["cases", { page: 1, page_size: 5, status: "open,in_progress" }],
    queryFn: () => casesApi.list({ page: 1, page_size: 5, status: "open,in_progress" }),
  });

  const { data: walletsData } = useQuery({
    queryKey: ["wallets", { page: 1, page_size: 1 }],
    queryFn: () => walletsApi.list({ page: 1, page_size: 1 }),
  });

  const { data: investigationsData } = useQuery({
    queryKey: ["investigations", { page: 1, page_size: 5, status: "running,pending" }],
    queryFn: () => investigationsApi.list({ page: 1, page_size: 5, status: "running,pending" }),
  });

  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: () => healthApi.check(),
    refetchInterval: 30000,
  });

  const activeCasesCount = casesData?.items.filter((c: any) => c.status !== "closed" && c.status !== "archived").length || 0;
  const totalWallets = walletsData?.total || 0;
  const runningInvestigations = investigationsData?.items.filter((i: any) => i.status === "running").length || 0;
  const completedInvestigations = investigationsData?.items.filter((i: any) => i.status === "completed").length || 0;

  const stats = [
    { name: "Active Cases", value: activeCasesCount.toString(), change: "+0", icon: FolderOpen, color: "text-blue-400" },
    { name: "Wallets Tracked", value: totalWallets.toString(), change: "+0", icon: Search, color: "text-green-400" },
    { name: "Investigations Running", value: runningInvestigations.toString(), change: "0", icon: Activity, color: "text-amber-400" },
    { name: "Completed Traces", value: completedInvestigations.toString(), change: "+0", icon: FileText, color: "text-purple-400" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Overview of active investigations and platform status</p>
        </div>
        <Button asChild>
          <Link href="/cases/new">
            <Plus className="w-4 h-4 mr-2" />
            New Case
          </Link>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.name}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{stat.name}</p>
                  <p className="text-3xl font-bold tracking-tight">{stat.value}</p>
                  <p className="text-xs text-green-400 mt-1">{stat.change} this week</p>
                </div>
                <div className={`p-3 rounded-lg bg-primary/10 ${stat.color}`}>
                  <stat.icon className="w-6 h-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Recent Cases</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/cases">View All</Link>
            </Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case Number</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Wallets</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(casesData?.items || []).map((caseItem: any) => (
                    <TableRow key={caseItem.id}>
                      <TableCell className="font-mono text-sm">{caseItem.case_number}</TableCell>
                      <TableCell className="font-medium">{caseItem.title}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">{caseItem.crime_type.replace("_", " ")}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={caseItem.status === "in_progress" ? "warning" : caseItem.status === "open" ? "info" : caseItem.status === "closed" ? "success" : "secondary"}>
                          {statusLabels[caseItem.status]}
                        </Badge>
                      </TableCell>
                      <TableCell>{caseItem.wallets_count || 0}</TableCell>
                      <TableCell className="text-muted-foreground">{formatRelativeTime(caseItem.updated_at)}</TableCell>
                    </TableRow>
                  ))}
                  {(casesData?.items?.length || 0) === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        No active cases. <Link href="/cases/new" className="text-primary underline">Create your first case</Link>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Active Investigations</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/cases">View All</Link>
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {(investigationsData?.items || []).map((inv: any) => (
                <div key={inv.id} className="flex items-center justify-between p-4 rounded-lg bg-tracex-surface-hover/50">
                  <div className="flex items-center gap-4">
                    <div className={`w-2 h-2 rounded-full ${inv.status === "completed" ? "bg-green-400" : inv.status === "running" ? "bg-amber-400" : "bg-blue-400"}`} />
                    <div>
                      <p className="font-mono text-sm">{formatAddress(inv.wallet_id || "unknown")}</p>
                      <p className="text-xs text-muted-foreground">{inv.case_id} • Started {formatRelativeTime(inv.started_at)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="w-32">
                      <div className="h-2 bg-tracex-border rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${inv.status === "completed" ? "bg-green-400" : inv.status === "running" ? "bg-amber-400" : "bg-blue-400"}`}
                          style={{ width: `${inv.result_summary?.progress || (inv.status === "completed" ? 100 : inv.status === "running" ? 50 : 0)}%` }}
                        />
                      </div>
                    </div>
                    <Badge variant={inv.status === "completed" ? "success" : inv.status === "running" ? "warning" : "secondary"}>
                      {investigationStatusLabels[inv.status]}
                    </Badge>
                  </div>
                </div>
              ))}
              {(investigationsData?.items?.length || 0) === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">No active investigations</p>
                  <p className="text-sm mt-1">Start a wallet trace to see investigations here</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg">Platform Health</CardTitle>
          <Badge variant={healthData?.status === "healthy" ? "success" : healthData?.status === "degraded" ? "warning" : "destructive"} className="gap-1">
            <CheckCircle className="w-3 h-3" />
            {healthData?.status === "healthy" ? "All Systems Operational" : healthData?.status === "degraded" ? "Degraded Performance" : "System Issues"}
          </Badge>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-4 rounded-lg bg-tracex-surface-hover/50">
              <div className="flex items-center gap-2 mb-2">
                <Activity className={`w-4 h-4 ${healthData?.services?.database === "connected" ? "text-green-400" : "text-destructive"}`} />
                <span className="font-medium">Database</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {healthData?.services?.database === "connected" ? "PostgreSQL connected" : "PostgreSQL disconnected"}
              </p>
            </div>
            <div className="p-4 rounded-lg bg-tracex-surface-hover/50">
              <div className="flex items-center gap-2 mb-2">
                <Activity className={`w-4 h-4 ${healthData?.services?.neo4j === "connected" ? "text-green-400" : "text-destructive"}`} />
                <span className="font-medium">Graph Database</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {healthData?.services?.neo4j === "connected" ? "Neo4j connected" : "Neo4j disconnected"}
              </p>
            </div>
            <div className="p-4 rounded-lg bg-tracex-surface-hover/50">
              <div className="flex items-center gap-2 mb-2">
                <Activity className={`w-4 h-4 ${healthData?.services?.redis === "connected" ? "text-green-400" : "text-destructive"}`} />
                <span className="font-medium">Cache</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {healthData?.services?.redis === "connected" ? "Redis connected" : "Redis disconnected"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}