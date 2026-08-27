"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useSearchParams } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatRelativeTime, formatAddress } from "@/lib/utils";
import { riskApi, aiApi } from "@/lib/api";
import {
  Bot,
  User,
  Send,
  Sparkles,
  Brain,
  AlertTriangle,
  CheckCircle,
  Info,
  ChevronDown,
  ChevronUp,
  Copy,
  Clipboard,
  Trash2,
  Plus,
  History,
  X,
} from "lucide-react";

interface Evidence {
  source: string;
  evidence_type: string;
  description: string;
  confidence: string;
  data: Record<string, any>;
  timestamp: string;
}

interface AIResponse {
  answer: string;
  query_type: string;
  confidence: string;
  evidence: Evidence[];
  follow_up_questions: string[];
  metadata: Record<string, any>;
}

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

interface ChatSession {
  session_id: string;
  case_id?: string;
  messages: ChatMessage[];
}

interface Capability {
  name: string;
  description: string;
  example_queries: string[];
}

const queryTypes = [
  { id: "risk", label: "Risk Analysis", icon: AlertTriangle, color: "text-destructive" },
  { id: "attribution", label: "VASP Attribution", icon: CheckCircle, color: "text-green-400" },
  { id: "patterns", label: "Pattern Detection", icon: Brain, color: "text-amber-400" },
  { id: "flow", label: "Fund Flow", icon: Info, color: "text-blue-400" },
  { id: "entity", label: "Entity Lookup", icon: Sparkles, color: "text-purple-400" },
  { id: "case", label: "Case Overview", icon: History, color: "text-cyan-400" },
];

export default function AIAssistantPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showCapabilities, setShowCapabilities] = useState(false);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const [selectedQuickQuery, setSelectedQuickQuery] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const searchParams = useSearchParams();
  const [autoQuerySent, setAutoQuerySent] = useState(false);

  useEffect(() => {
    loadCapabilities();
    const savedSession = localStorage.getItem("ai_chat_session");
    if (savedSession) {
      setSessionId(savedSession);
      loadHistory(savedSession);
    } else {
      newSession();
    }
  }, []);

  useEffect(() => {
    const address = searchParams.get("address");
    const caseId = searchParams.get("case");
    if (address && !autoQuerySent) {
      const query = caseId
        ? `Analyze wallet ${address} in case ${caseId}. Show me the risk assessment, attribution, and any suspicious patterns.`
        : `Analyze wallet ${address}. Show me the risk assessment, attribution, and any suspicious patterns.`;
      setInput(query);
      setAutoQuerySent(true);
    }
  }, [searchParams, autoQuerySent]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadCapabilities = async () => {
    try {
      const data = await aiApi.getCapabilities();
      setCapabilities(data.capabilities);
    } catch (err) {
      console.error("Failed to load capabilities:", err);
    }
  };

  const newSession = () => {
    const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newId);
    localStorage.setItem("ai_chat_session", newId);
    setMessages([
      {
        role: "assistant",
        content: "Hello! I'm your TRACE-X Investigation Assistant. I can help you with risk analysis, VASP attribution, pattern detection, fund flow tracing, entity lookups, case overviews, and timeline analysis. What would you like to investigate today?",
        timestamp: new Date().toISOString(),
      },
    ]);
    setSuggestedActions([
      "What's the risk score for a specific wallet?",
      "Trace funds from a suspect address",
      "Show me case summary",
      "Any suspicious patterns on Ethereum?",
    ]);
  };

  const loadHistory = async (id: string) => {
    try {
      const data = await aiApi.getChatHistory(id);
      setMessages(data.messages);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input;
    setInput("");
    setIsLoading(true);
    setSuggestedActions([]);

    try {
      const response = await aiApi.chat({
        message: currentInput,
        session_id: sessionId || undefined,
        case_id: new URLSearchParams(window.location.search).get("case") || undefined,
      });

      setSessionId(response.session_id);
      localStorage.setItem("ai_chat_session", response.session_id);

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.message.content,
        timestamp: response.message.timestamp,
        metadata: response.message.metadata,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setSuggestedActions(response.suggested_actions || []);
    } catch (err) {
      console.error("Chat error:", err);
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickQuery = (query: string) => {
    setInput(query);
    handleSend();
  };

  const handleSuggestedAction = (action: string) => {
    handleQuickQuery(action);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const clearHistory = () => {
    if (sessionId) {
      aiApi.deleteChatHistory(sessionId);
      localStorage.removeItem("ai_chat_session");
    }
    newSession();
  };

  const formatConfidence = (confidence: string) => {
    const colors: Record<string, string> = {
      CONFIRMED: "bg-green-500/20 text-green-400",
      HIGH_CONFIDENCE: "bg-blue-500/20 text-blue-400",
      PROBABLE: "bg-amber-500/20 text-amber-400",
      UNKNOWN: "bg-muted text-muted-foreground",
    };
    return colors[confidence] || "bg-muted text-muted-foreground";
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-tracex-border p-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Brain className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Investigation Assistant</h1>
            <p className="text-sm text-muted-foreground">AI-powered analysis with evidence-grounded responses</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => setShowCapabilities(!showCapabilities)}>
            <Sparkles className="w-5 h-5" />
          </Button>
          <Button variant="outline" size="sm" onClick={clearHistory}>
            <Trash2 className="w-4 h-4 mr-2" />
            New Chat
          </Button>
        </div>
      </div>

      {showCapabilities && (
        <div className="border-b border-tracex-border p-4 bg-tracex-surface-hover/30">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Capabilities</h3>
            <Button variant="ghost" size="sm" onClick={() => setShowCapabilities(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((cap) => (
              <Card key={cap.name} className="bg-tracex-surface-hover/50">
                <CardContent className="p-4">
                  <h4 className="font-medium mb-2">{cap.name}</h4>
                  <p className="text-sm text-muted-foreground mb-3">{cap.description}</p>
                  <div className="space-y-1">
                    {cap.example_queries.slice(0, 2).map((q, i) => (
                      <Button
                        key={i}
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-xs h-auto py-1 px-2 text-left"
                        onClick={() => handleQuickQuery(q)}
                      >
                        {q}
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-hidden flex flex-col">
        <ScrollArea className="flex-1 pr-2">
          <div className="space-y-4 p-4">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    msg.role === "user"
                      ? "bg-primary/20 text-primary"
                      : msg.role === "assistant"
                      ? "bg-purple-500/20 text-purple-400"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {msg.role === "user" ? (
                    <User className="w-4 h-4" />
                  ) : msg.role === "assistant" ? (
                    <Bot className="w-4 h-4" />
                  ) : (
                    <Info className="w-4 h-4" />
                  )}
                </div>
                <div
                  className={`max-w-[80%] ${
                    msg.role === "user" ? "text-right" : ""
                  }`}
                >
                  <div
                    className={`rounded-2xl p-4 ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground rounded-tr-sm"
                        : "bg-tracex-surface border border-tracex-border rounded-tl-sm"
                    }`}
                  >
                    <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
                    {msg.metadata && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        <Badge
                          variant="secondary"
                          className={`text-xs ${formatConfidence(msg.metadata.confidence)}`}
                        >
                          {msg.metadata.confidence}
                        </Badge>
                        <Badge variant="outline" className="text-xs capitalize">
                          {msg.metadata.query_type?.replace("_", " ")}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {msg.metadata.evidence_count} evidence
                        </Badge>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 mt-1 opacity-50 text-xs">
                    <span>{formatRelativeTime(msg.timestamp)}</span>
                    <Button variant="ghost" size="icon" className="h-6 w-6 p-0" onClick={() => copyToClipboard(msg.content)}>
                      <Copy className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-purple-400 animate-pulse" />
                </div>
                <div className="bg-tracex-surface border border-tracex-border rounded-2xl p-4 rounded-tl-sm animate-pulse">
                  <div className="h-4 bg-tracex-border rounded w-3/4 mb-2"></div>
                  <div className="h-4 bg-tracex-border rounded w-1/2"></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {suggestedActions.length > 0 && (
          <div className="border-t border-tracex-border p-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
              <Sparkles className="w-3 h-3" />
              Suggested follow-ups:
            </div>
            <div className="flex flex-wrap gap-2">
              {suggestedActions.map((action, idx) => (
                <Button
                  key={idx}
                  variant="outline"
                  size="sm"
                  className="h-auto py-1.5"
                  onClick={() => handleSuggestedAction(action)}
                >
                  {action}
                </Button>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-tracex-border p-4">
          <div className="flex gap-2">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about risk, attribution, patterns, fund flow, entities, cases, or timelines..."
              className="flex-1 min-h-[50px] max-h-32"
              disabled={isLoading}
              rows={1}
            />
            <Button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="h-[50px] flex-shrink-0"
              size="lg"
            >
              <Send className="w-5 h-5" />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2 text-center">
            Press Enter to send, Shift+Enter for new line. Try: "Risk for wallet 0x...", "Trace funds from 0x...", "Case TRX-20240115-0042 summary"
          </p>
        </div>
      </div>
    </div>
  );
}