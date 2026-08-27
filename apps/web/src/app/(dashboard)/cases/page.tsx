"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatRelativeTime } from "@/lib/utils";
import { casesApi } from "@/lib/api";
import { Plus, Search, Filter, ChevronDown, MoreHorizontal } from "lucide-react";
import Link from "next/link";

const statusOptions = ["open", "in_progress", "closed", "archived"];
const crimeTypeOptions = ["fraud", "money_laundering", "ransomware", "darknet_market", "sanctions_evasion", "other"];

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

export default function CasesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [crimeTypeFilter, setCrimeTypeFilter] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const { data: casesData, isLoading, error } = useQuery({
    queryKey: ["cases", { page, pageSize, status: statusFilter, crime_type: crimeTypeFilter, search }],
    queryFn: () => casesApi.list({ page, page_size: pageSize, status: statusFilter || undefined, crime_type: crimeTypeFilter || undefined, search: search || undefined }),
  });

  const createCaseMutation = useMutation({
    mutationFn: (data: any) => casesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      setDialogOpen(false);
    },
  });

  const handleCreateCase = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const data = Object.fromEntries(formData);
    createCaseMutation.mutate(data);
    e.currentTarget.reset();
  };

  const filteredCases = casesData?.items || [];
  const totalCases = casesData?.total || 0;
  const totalPages = casesData?.total_pages || 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cases</h1>
          <p className="text-muted-foreground">Manage investigation cases</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button disabled={createCaseMutation.isPending}>
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
                <Button type="submit" disabled={createCaseMutation.isPending}>
                  {createCaseMutation.isPending ? "Creating..." : "Create Case"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-lg">All Cases ({totalCases})</CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search cases..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="pl-10 w-64"
              />
            </div>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
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
            <Select value={crimeTypeFilter} onValueChange={(v) => { setCrimeTypeFilter(v); setPage(1); }}>
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
          {isLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-destructive">
              Failed to load cases: {error instanceof Error ? error.message : "Unknown error"}
            </div>
          ) : (
            <>
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
                    {filteredCases.map((c: any) => (
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
                        <TableCell>{c.assigned_to || "Unassigned"}</TableCell>
                        <TableCell>{c.wallets_count || 0}</TableCell>
                        <TableCell className="text-muted-foreground">{formatRelativeTime(c.created_at)}</TableCell>
                        <TableCell className="text-muted-foreground">{formatRelativeTime(c.updated_at)}</TableCell>
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
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages} • {totalCases} total
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                      Previous
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}