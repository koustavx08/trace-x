"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { formatRelativeTime } from "@/lib/utils";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import {
  Shield,
  Database,
  Server,
  Key,
  User,
  Bell,
  Palette,
  Save,
  AlertCircle,
  CheckCircle,
  Plus,
  ChevronRight,
  Info,
} from "lucide-react";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("general");
  const [addUserOpen, setAddUserOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: usersData, isLoading: usersLoading, error: usersError } = useQuery({
    queryKey: ["users"],
    queryFn: () => authApi.listUsers({ page: 1, page_size: 100 }),
    enabled: activeTab === "users",
  });

  const currentUserId = useAuthStore((s) => s.user?.id);

  const createUserMutation = useMutation({
    mutationFn: (data: { email: string; password: string; full_name: string; role: string }) =>
      authApi.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setAddUserOpen(false);
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ userId, is_active }: { userId: string; is_active: boolean }) =>
      authApi.updateUser(userId, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const handleCreateUser = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const data = Object.fromEntries(formData) as {
      email: string;
      password: string;
      full_name: string;
      role: string;
    };
    createUserMutation.mutate(data);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Configure platform settings and preferences</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="general">
            <Palette className="w-4 h-4 mr-2" />
            General
          </TabsTrigger>
          <TabsTrigger value="blockchain">
            <Server className="w-4 h-4 mr-2" />
            Blockchain
          </TabsTrigger>
          <TabsTrigger value="database">
            <Database className="w-4 h-4 mr-2" />
            Database
          </TabsTrigger>
          <TabsTrigger value="users">
            <User className="w-4 h-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger value="security">
            <Shield className="w-4 h-4 mr-2" />
            Security
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Application Settings</CardTitle>
              <CardDescription>General application configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="app_name">Application Name</Label>
                  <Input id="app_name" defaultValue="TRACE-X" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select defaultValue="UTC">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UTC">UTC</SelectItem>
                      <SelectItem value="EST">EST</SelectItem>
                      <SelectItem value="PST">PST</SelectItem>
                      <SelectItem value="CET">CET</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="date_format">Date Format</Label>
                  <Select defaultValue="ISO">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ISO">ISO 8601 (YYYY-MM-DD)</SelectItem>
                      <SelectItem value="US">US (MM/DD/YYYY)</SelectItem>
                      <SelectItem value="EU">EU (DD/MM/YYYY)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="language">Language</Label>
                  <Select defaultValue="en">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center justify-between p-4 rounded-lg bg-tracex-surface-hover/50">
                <div>
                  <p className="font-medium">Dark Mode</p>
                  <p className="text-sm text-muted-foreground">Use dark theme throughout the application</p>
                </div>
                <Switch defaultChecked />
              </div>
              <div className="flex items-center justify-between p-4 rounded-lg bg-tracex-surface-hover/50">
                <div>
                  <p className="font-medium">Compact Mode</p>
                  <p className="text-sm text-muted-foreground">Reduce spacing for dense information display</p>
                </div>
                <Switch />
              </div>
              <Button><Save className="w-4 h-4 mr-2" />Save Changes</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="blockchain" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Blockchain Providers</CardTitle>
              <CardDescription>Configure RPC endpoints and API keys for blockchain networks</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-4 p-4 rounded-lg border border-tracex-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
                      <Server className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold">Ethereum Mainnet</h3>
                      <p className="text-sm text-muted-foreground">Chain ID: 1</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label htmlFor="eth_rpc">Primary RPC URL</Label>
                      <Input id="eth_rpc" placeholder="https://eth-mainnet.g.alchemy.com/v2/..." />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="eth_alchemy">Alchemy API Key</Label>
                      <Input id="eth_alchemy" type="password" placeholder="Enter Alchemy API key" />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="eth_infura">Infura API Key</Label>
                      <Input id="eth_infura" type="password" placeholder="Enter Infura API key" />
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <span className="text-sm font-medium text-green-400">Status: Connected</span>
                      <Badge variant="success">Healthy</Badge>
                    </div>
                  </div>
                </div>
                <div className="space-y-4 p-4 rounded-lg border border-tracex-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-purple-500/20 text-purple-400">
                      <Server className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold">Polygon Mainnet</h3>
                      <p className="text-sm text-muted-foreground">Chain ID: 137</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label htmlFor="polygon_rpc">Primary RPC URL</Label>
                      <Input id="polygon_rpc" placeholder="https://polygon-mainnet.g.alchemy.com/v2/..." />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="polygon_alchemy">Alchemy API Key</Label>
                      <Input id="polygon_alchemy" type="password" placeholder="Enter Alchemy API key" />
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <span className="text-sm font-medium text-green-400">Status: Connected</span>
                      <Badge variant="success">Healthy</Badge>
                    </div>
                  </div>
                </div>
              </div>
              <Button><Save className="w-4 h-4 mr-2" />Save Provider Settings</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="database" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Database Configuration</CardTitle>
              <CardDescription>PostgreSQL and Neo4j connection settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-4 p-4 rounded-lg border border-tracex-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-green-500/20 text-green-400">
                      <Database className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold">PostgreSQL</h3>
                      <p className="text-sm text-muted-foreground">Primary application database</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label htmlFor="pg_url">Connection URL</Label>
                      <Input id="pg_url" placeholder="postgresql+asyncpg://user:pass@host:5432/db" />
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="pg_pool">Pool Size</Label>
                        <Input id="pg_pool" type="number" defaultValue="10" />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="pg_overflow">Max Overflow</Label>
                        <Input id="pg_overflow" type="number" defaultValue="20" />
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <span className="text-sm font-medium text-green-400">Status: Connected</span>
                      <Badge variant="success">Healthy</Badge>
                    </div>
                  </div>
                </div>
                <div className="space-y-4 p-4 rounded-lg border border-tracex-border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-purple-500/20 text-purple-400">
                      <Database className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold">Neo4j</h3>
                      <p className="text-sm text-muted-foreground">Graph database for transaction relationships</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <Label htmlFor="neo4j_uri">URI</Label>
                      <Input id="neo4j_uri" placeholder="bolt://localhost:7687" />
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="neo4j_user">Username</Label>
                        <Input id="neo4j_user" defaultValue="neo4j" />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="neo4j_pass">Password</Label>
                        <Input id="neo4j_pass" type="password" />
                      </div>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                      <span className="text-sm font-medium text-green-400">Status: Connected</span>
                      <Badge variant="success">Healthy</Badge>
                    </div>
                  </div>
                </div>
              </div>
              <Button><Save className="w-4 h-4 mr-2" />Save Database Settings</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle>User Management</CardTitle>
              <Dialog open={addUserOpen} onOpenChange={setAddUserOpen}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />Add User
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add User</DialogTitle>
                    <DialogDescription>Create a new account for the platform.</DialogDescription>
                  </DialogHeader>
                  <form onSubmit={handleCreateUser}>
                    <div className="grid gap-4 py-4">
                      <div className="grid gap-2">
                        <Label htmlFor="full_name">Full Name</Label>
                        <Input id="full_name" name="full_name" placeholder="Jane Doe" required />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="email">Email</Label>
                        <Input id="email" name="email" type="email" placeholder="jane@example.com" required />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="password">Password</Label>
                        <Input id="password" name="password" type="password" minLength={8} required />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="role">Role</Label>
                        <Select name="role" defaultValue="analyst">
                          <SelectTrigger>
                            <SelectValue placeholder="Select role" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="analyst">Analyst</SelectItem>
                            <SelectItem value="supervisor">Supervisor</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {createUserMutation.isError && (
                        <p className="text-sm text-destructive">
                          {(createUserMutation.error as { response?: { data?: { error?: { message?: string } } } })
                            ?.response?.data?.error?.message || "Failed to create user."}
                        </p>
                      )}
                    </div>
                    <DialogFooter>
                      <Button type="button" variant="outline" onClick={() => setAddUserOpen(false)}>
                        Cancel
                      </Button>
                      <Button type="submit" disabled={createUserMutation.isPending}>
                        {createUserMutation.isPending ? "Creating..." : "Create User"}
                      </Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              {usersError ? (
                <div className="flex items-start gap-3 p-4 rounded-lg bg-tracex-surface-hover/50 border border-tracex-border">
                  <Info className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium">Couldn&apos;t load users</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {(usersError as { response?: { status?: number } })?.response?.status === 403
                        ? "Only admins can view the user list."
                        : "The user list failed to load. Try again shortly."}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto mt-4">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Last Login</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {usersLoading ? (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                            Loading…
                          </TableCell>
                        </TableRow>
                      ) : usersData?.items.length ? (
                        usersData.items.map((u) => (
                          <TableRow key={u.id}>
                            <TableCell>{u.full_name}</TableCell>
                            <TableCell>{u.email}</TableCell>
                            <TableCell className="capitalize">{u.role}</TableCell>
                            <TableCell>
                              <button
                                type="button"
                                disabled={u.id === currentUserId || toggleActiveMutation.isPending}
                                title={
                                  u.id === currentUserId
                                    ? "You can't deactivate your own account"
                                    : u.is_active
                                      ? "Click to deactivate"
                                      : "Click to reactivate"
                                }
                                onClick={() =>
                                  toggleActiveMutation.mutate({
                                    userId: u.id,
                                    is_active: !u.is_active,
                                  })
                                }
                                className="disabled:opacity-60 disabled:cursor-not-allowed"
                              >
                                <Badge variant={u.is_active ? "default" : "secondary"}>
                                  {u.is_active ? "Active" : "Inactive"}
                                </Badge>
                              </button>
                            </TableCell>
                            <TableCell>
                              {u.last_login_at ? formatRelativeTime(u.last_login_at) : "Never"}
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                            No users found
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Security Settings</CardTitle>
              <CardDescription>Authentication and access control configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg border border-tracex-border">
                  <div>
                    <p className="font-medium">Two-Factor Authentication</p>
                    <p className="text-sm text-muted-foreground">Require 2FA for all user accounts</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-tracex-border">
                  <div>
                    <p className="font-medium">Session Timeout</p>
                    <p className="text-sm text-muted-foreground">Auto-logout after inactivity</p>
                  </div>
                  <Select defaultValue="30">
                    <SelectTrigger className="w-[200px]"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="15">15 minutes</SelectItem>
                      <SelectItem value="30">30 minutes</SelectItem>
                      <SelectItem value="60">1 hour</SelectItem>
                      <SelectItem value="120">2 hours</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-tracex-border">
                  <div>
                    <p className="font-medium">API Rate Limiting</p>
                    <p className="text-sm text-muted-foreground">Limit requests per minute per IP</p>
                  </div>
                  <Input type="number" defaultValue="100" className="w-[120px]" />
                </div>
              </div>
              <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-5 h-5 text-destructive" />
                  <div>
                    <p className="font-medium text-destructive">Danger Zone</p>
                    <p className="text-sm text-muted-foreground">These actions are irreversible</p>
                  </div>
                </div>
              </div>
              <Button variant="destructive"><Save className="w-4 h-4 mr-2" />Reset All Settings</Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}