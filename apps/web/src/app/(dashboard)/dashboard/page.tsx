"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { formatRelativeTime, formatAddress, getRiskColor, getRiskBg, getConfidenceColor } from "@/lib/utils";
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
} from "lucide-react";

const stats = [
  { name: "Active Cases", value: "12", change: "+2", icon: FolderOpen, color: "text-blue-400" },
  { name: "Wallets Tracked", value: "347", change: "+23", icon: Search, color: "text-green-400" },
  { name: "Investigations Running", value: "3", change: "0", icon: Activity, color: "text-amber-400" },
  { name: "Reports Generated", value: "28", change: "+5", icon: FileText, color: "text-purple-400" },
];

const recentCases = [
  { id: "1", case_number: "TRX-20240115-0042", title: "DeFi Protocol Exploit", crime_type: "fraud", status: "in_progress", wallets: 15, updated: "2024-01-15T10:30:00Z" },
  { id: "2", case_number: "TRX-20240114-0038", title: "Ransomware Payment Tracing", crime_type: "ransomware", status: "open", wallets: 8, updated: "2024-01-14T16:45:00Z" },
  { id: "3", case_number: "TRX-20240113-0029", title: "Money Laundering Ring", crime_type: "money_laundering", status: "closed", wallets: 42, updated: "2024-01-13T09:15:00Z" },
  { id: "4", case_number: "TRX-20240112-0017", title: "Darknet Market Seizure", crime_type: "darknet_market", status: "archived", wallets: 23, updated: "2024-01-12T14:20:00Z" },
];

const recentInvestigations = [
  { id: "1", case_id: "TRX-20240115-0042", wallet: "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", chain: "Ethereum", status: "running", progress: 65 },
  { id: "2", case_id: "TRX-20240114-0038", wallet: "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", chain: "Ethereum", status: "completed", progress: 100 },
  { id: "3", case_id: "TRX-20240115-0042", wallet: "0xA0b86a33E6441b8C4C8C8C8C8C8C8C8C8C8C8C8C", chain: "Polygon", status: "pending", progress: 0 },
];

const statusBadges: Record<string, React.ReactNode> = {
  open: <Badge variant="info">Open</Badge>,
  in_progress: <Badge variant="warning">In Progress</Badge>,
  closed: <Badge variant="success">Closed</Badge>,
  archived: <Badge variant="secondary">Archived</Badge>,
};

const investigationStatusBadges: Record<string, React.ReactNode> = {
  pending: <Badge variant="secondary">Pending</Badge>,
  running: <Badge variant="warning">Running</Badge>,
  completed: <Badge variant="success">Completed</Badge>,
  failed: <Badge variant="destructive">Failed</Badge>,
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Overview of active investigations and platform status</p>
        </div>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          New Case
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
            <Button variant="ghost" size="sm">View All</Button>
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
                  {recentCases.map((caseItem) => (
                    <TableRow key={caseItem.id}>
                      <TableCell className="font-mono text-sm">{caseItem.case_number}</TableCell>
                      <TableCell className="font-medium">{caseItem.title}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">{caseItem.crime_type.replace("_", " ")}</Badge>
                      </TableCell>
                      <TableCell>{statusBadges[caseItem.status]}</TableCell>
                      <TableCell>{caseItem.wallets}</TableCell>
                      <TableCell className="text-muted-foreground">{formatRelativeTime(caseItem.updated)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-lg">Active Investigations</CardTitle>
            <Button variant="ghost" size="sm">View All</Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentInvestigations.map((inv) => (
                <div key={inv.id} className="flex items-center justify-between p-4 rounded-lg bg-tracex-surface-hover/50">
                  <div className="flex items-center gap-4">
                    <div className="w-2 h-2 rounded-full bg-primary" />
                    <div>
                      <p className="font-mono text-sm">{formatAddress(inv.wallet)}</p>
                      <p className="text-xs text-muted-foreground">{inv.chain} • {inv.case_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="w-32">
                      <div className="h-2 bg-tracex-border rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-300"
                          style={{ width: `${inv.progress}%` }}
                        />
                      </div>
                    </div>
                    {investigationStatusBadges[inv.status]}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg">Platform Health</CardTitle>
          <Badge variant="success" className="gap-1">
            <CheckCircle className="w-3 h-3" />
            All Systems Operational
          </Badge>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-4 rounded-lg bg-tracex-surface-hover/50">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-green-400" />
                <span className="font-medium">Database</span>
              </div>
              <p className="text-sm text-muted-foreground">PostgreSQL connected • 12ms latency</p>
            </div>
            <div className="p-4 rounded-lg bg-tracex-surface-hover/50">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-green-400" />
                <span className="font-medium">Graph Database</span>
              </div>
              <p className="text-sm text-muted-foreground">Neo4j connected • 8ms latency</p>
            </div>
            <div className="p-4 rounded-lg bg-tracex-surface-hover/50">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-green-400" />
                <span className="font-medium">Blockchain RPC</span>
              </div>
              <p className="text-sm text-muted-foreground">Ethereum & Polygon healthy</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}