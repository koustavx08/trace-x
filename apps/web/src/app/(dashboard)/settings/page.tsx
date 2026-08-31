"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table";
import { formatRelativeTime } from "@/lib/utils";
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
          {/*
            TODO(backend gap): there is no user-listing endpoint yet.
            apps/api/src/api/v1/auth.py only exposes POST /auth/users (create)
            and GET /auth/me (current user) - there is no GET /auth/users (or
            similar) to list/manage accounts, so this tab cannot be wired to
            real data without a new backend route. That route is out of this
            page's write-set to invent, so the previous hardcoded sample-user
            table has been removed rather than left showing fake data. See
            docs/KNOWN_LIMITATIONS.md for the tracked gap.
          */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle>User Management</CardTitle>
              <Button disabled title="User creation UI pending a user-listing API">
                <Plus className="w-4 h-4 mr-2" />Add User
              </Button>
            </CardHeader>
            <CardContent>
              <div className="flex items-start gap-3 p-4 rounded-lg bg-tracex-surface-hover/50 border border-tracex-border">
                <Info className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">User management is not available yet</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    The backend does not currently expose an endpoint to list or manage user
                    accounts (only account creation and fetching the current user exist).
                    This table will be wired up once a user-listing endpoint ships.
                  </p>
                </div>
              </div>
              <div className="overflow-x-auto mt-4 opacity-40 pointer-events-none select-none">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Login</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground py-6">
                        No data source connected
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
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