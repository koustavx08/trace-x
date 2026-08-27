"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatRelativeTime, formatAddress } from "@/lib/utils";
import { Plus, Search, Filter, ChevronDown, MoreHorizontal } from "lucide-react";
import Link from "next/link";

const mockCases = [
  { id: "1", case_number: "TRX-20240115-0042", title: "DeFi Protocol Exploit", crime_type: "fraud", description: "Major DeFi protocol exploit involving flash loan attack", status: "in_progress", assigned_to: "Analyst A", wallets: 15, updated: "2024-01-15T10:30:00Z", created: "2024-01-15T08:00:00Z" },
  { id: "2", case_number: "TRX-20240114-0038", title: "Ransomware Payment Tracing", crime_type: "ransomware", description: "Tracing ransomware payments across multiple chains", status: "open", assigned_to: "Analyst B", wallets: 8, updated: "2024-01-14T16:45:00Z", created: "2024-01-14T10:00:00Z" },
  { id: "3", case_number: "TRX-20240113-0029", title: "Money Laundering Ring", crime_type: "money_laundering", description: "International money laundering operation", status: "closed", assigned_to: "Analyst A", wallets: 42, updated: "2024-01-13T09:15:00Z", created: "2024-01-10T14:00:00Z" },
  { id: "4", case_number: "TRX-20240112-0017", title: "Darknet Market Seizure", crime_type: "darknet_market", description: "Cryptocurrency seizure from darknet marketplace", status: "archived", assigned_to: "Analyst C", wallets: 23, updated: "2024-01-12T14:20:00Z", created: "2024-01-11T09:00:00Z" },
  { id: "5", case_number: "TRX-20240111-0009", title: "Sanctions Evasion", crime_type: "sanctions_evasion", description: "Tracking sanctions evasion through crypto mixers", status: "in_progress", assigned_to: "Analyst B", wallets: 31, updated: "2024-01-11T11:30:00Z", created: "2024-01-09T16:00:00Z" },
];

const statusOptions = ["open", "in_progress", "closed", "archived"];
const crimeTypeOptions = ["fraud", "money_laundering", "ransomware", "darknet_market", "sanctions_evasion", "other"];

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

export default function CasesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [crimeTypeFilter, setCrimeTypeFilter] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<typeof mockCases[0] | null>(null);

  const filteredCases = mockCases.filter((c) => {
    const matchesSearch = c.case_number.toLowerCase().includes(search.toLowerCase()) ||
      c.title.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || c.status === statusFilter;
    const matchesCrimeType = !crimeTypeFilter || c.crime_type === crimeTypeFilter;
    return matchesSearch && matchesStatus && matchesCrimeType;
  });

  const handleCreateCase = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    console.log("Create case:", Object.fromEntries(formData));
    setDialogOpen(false);
    e.currentTarget.reset();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cases</h1>
          <p className="text-muted-foreground">Manage investigation cases</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              New Case
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Case</DialogTitle>
              <DialogDescription>Enter the details for the new investigation case</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateCase}>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="case_number">Case Number</Label>
                  <Input id="case_number" name="case_number" placeholder="TRX-20240115-0042" required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="title">Title</Label>
                  <Input id="title" name="title" placeholder="Case title" required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="crime_type">Crime Type</Label>
                  <Select name="crime_type" required>
                    <SelectTrigger>
                      <SelectValue placeholder="Select crime type" />
                    </SelectTrigger>
                    <SelectContent>
                      {crimeTypeOptions.map((type) => (
                        <SelectItem key={type} value={type}>
                          {type.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea id="description" name="description" placeholder="Case description" rows={4} required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="status">Status</Label>
                  <Select name="status" defaultValue="open">
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                      {statusOptions.map((status) => (
                        <SelectItem key={status} value={status}>
                          {statusLabels[status]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">Create Case</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg">All Cases ({filteredCases.length})</CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search cases..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 w-64"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Statuses</SelectItem>
                {statusOptions.map((s) => (
                  <SelectItem key={s} value={s}>
                    {statusLabels[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={crimeTypeFilter} onValueChange={setCrimeTypeFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Types</SelectItem>
                {crimeTypeOptions.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Case Number</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Crime Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Assigned To</TableHead>
                  <TableHead>Wallets</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono text-sm">{c.case_number}</TableCell>
                    <TableCell>
                      <Link href={`/cases/${c.id}`} className="font-medium hover:text-primary transition-colors">
                        {c.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {c.crime_type.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={c.status === "in_progress" ? "warning" : c.status === "open" ? "info" : c.status === "closed" ? "success" : "secondary"}>
                        {statusLabels[c.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>{c.assigned_to}</TableCell>
                    <TableCell>{c.wallets}</TableCell>
                    <TableCell className="text-muted-foreground">{formatRelativeTime(c.created)}</TableCell>
                    <TableCell className="text-muted-foreground">{formatRelativeTime(c.updated)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="ghost" size="icon" asChild>
                          <Link href={`/cases/${c.id}`}>
                            <MoreHorizontal className="w-4 h-4" />
                          </Link>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}