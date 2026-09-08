"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { casesApi } from "@/lib/api";
import { ArrowLeft, Shield, FolderPlus, AlertCircle } from "lucide-react";
import Link from "next/link";

const crimeTypes = [
  { value: "fraud", label: "Financial Fraud / DeFi Exploit" },
  { value: "money_laundering", label: "Money Laundering & Smurfing" },
  { value: "ransomware", label: "Ransomware Extortion" },
  { value: "darknet_market", label: "Darknet Market Activity" },
  { value: "sanctions_evasion", label: "Sanctions Evasion (OFAC/SDN)" },
  { value: "other", label: "Other Cybercrime" },
];

export default function NewCasePage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [crimeType, setCrimeType] = useState("fraud");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("open");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (payload: {
      title: string;
      crime_type: string;
      description: string;
      status: string;
    }) => casesApi.create(payload),
    onSuccess: (newCase) => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      // Redirect directly to the newly created case detail dossier
      router.push(`/cases/${newCase.id}`);
    },
    onError: (err: any) => {
      setErrorMsg(
        err?.response?.data?.detail || "Failed to create investigation case. Please check your inputs."
      );
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!title.trim() || !description.trim()) {
      setErrorMsg("Please fill in both the case title and description.");
      return;
    }
    createMutation.mutate({
      title: title.trim(),
      crime_type: crimeType,
      description: description.trim(),
      status,
    });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Navigation Header */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" asChild className="text-[#73798D] hover:text-[#151B2B]">
          <Link href="/cases">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Cases Registry
          </Link>
        </Button>
      </div>

      {/* Main Creation Card */}
      <Card className="rounded-2xl border border-[#E5E7EB] bg-white shadow-xs">
        <CardHeader className="p-8 border-b border-[#E5E7EB]/80">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-xl bg-[#EEF0FF] text-[#3430D9] flex items-center justify-center">
              <FolderPlus className="w-5 h-5" />
            </div>
            <div>
              <CardTitle className="text-xl font-bold text-[#151B2B]">
                Initiate Criminal Investigation
              </CardTitle>
              <CardDescription className="text-xs text-[#73798D] mt-0.5">
                Register a new forensic investigation dossier with chain-of-custody tracking.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-8">
          {errorMsg && (
            <div className="mb-6 p-4 rounded-xl bg-[#FFF0F3] border border-[#D94F72]/20 flex items-center gap-3 text-sm text-[#D94F72]">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Case Title */}
            <div className="space-y-2">
              <Label htmlFor="title" className="text-xs font-semibold text-[#151B2B]">
                Investigation Title <span className="text-[#D94F72]">*</span>
              </Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Orbit Protocol $4.2M Flash Loan Exploit"
                className="h-11 rounded-xl bg-[#F8F9FC] border-[#E5E7EB] text-sm focus:bg-white"
                required
              />
            </div>

            {/* Crime Type & Status */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-[#151B2B]">
                  Crime Classification <span className="text-[#D94F72]">*</span>
                </Label>
                <Select value={crimeType} onValueChange={setCrimeType}>
                  <SelectTrigger className="h-11 rounded-xl bg-[#F8F9FC] border-[#E5E7EB] text-sm">
                    <SelectValue placeholder="Select Crime Type" />
                  </SelectTrigger>
                  <SelectContent>
                    {crimeTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value} className="text-sm">
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-semibold text-[#151B2B]">
                  Initial Status
                </Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="h-11 rounded-xl bg-[#F8F9FC] border-[#E5E7EB] text-sm">
                    <SelectValue placeholder="Select Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">Open</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="closed">Closed</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description" className="text-xs font-semibold text-[#151B2B]">
                Forensic Incident Description <span className="text-[#D94F72]">*</span>
              </Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Provide initial background on victim complaints, known illicit transactions, stolen amounts, and target blockchains..."
                rows={5}
                className="rounded-xl bg-[#F8F9FC] border-[#E5E7EB] text-sm focus:bg-white resize-none"
                required
              />
            </div>

            {/* Form Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#E5E7EB]/80">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/cases")}
                className="h-11 px-5 rounded-xl border-[#E5E7EB] text-[#73798D] hover:text-[#151B2B]"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                loading={createMutation.isPending}
                className="h-11 px-6 rounded-xl bg-[#3430D9] hover:bg-[#2723B8] text-white font-semibold text-sm shadow-sm"
              >
                <Shield className="w-4 h-4 mr-2" />
                Create Investigation Dossier
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
