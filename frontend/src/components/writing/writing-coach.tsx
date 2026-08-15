"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  MessageCircle,
  Send,
  Bot,
  User,
  Loader2,
  BookOpen,
  Lightbulb,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal, ModalHeader, ModalTitle, ModalFooter } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { writingCoachService } from "@/services/api";
import type {
  WritingCoachAnswer,
  WritingCoachConversation,
  WritingCoachMessage,
  WritingEvaluation,
} from "@/types/writing-workspace";

interface WritingCoachProps {
  submissionId: string;
  evaluation: WritingEvaluation;
  onClose: () => void;
}

// Quick-question presets grounded in the evaluation.
const PRESET_QUESTIONS = [
  "Why is this sentence wrong?",
  "How can I improve my introduction?",
  "Why is my Task Response low?",
  "Give me a better way to express this idea.",
  "How can I improve my grammar?",
] as const;

const FOCUS_COLORS: Record<string, string> = {
  task_response: "bg-blue-500/20 text-blue-700",
  coherence: "bg-green-500/20 text-green-700",
  vocabulary: "bg-purple-500/20 text-purple-700",
  grammar: "bg-orange-500/20 text-orange-700",
  introduction: "bg-pink-500/20 text-pink-700",
  overall: "bg-indigo-500/20 text-indigo-700",
  other: "bg-gray-500/20 text-gray-700",
};

export function WritingCoach({
  submissionId,
  evaluation,
  onClose,
}: WritingCoachProps) {
  const [conversation, setConversation] =
    useState<WritingCoachConversation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [conversation, scrollToBottom]);

  const handleAsk = useCallback(async (q: string) => {
    if (!q.trim()) return;
    const qTrimmed = q.trim();
    setQuestion("");
    setError(null);
    setLoading(true);

    // Optimistically add the user message to the UI.
    const userMessage: WritingCoachMessage = {
      id: `local-${Date.now()}`,
      conversation_id: conversation?.id || "",
      role: "user",
      content: qTrimmed,
      structured: {},
      created_at: new Date().toISOString(),
    };
    setConversation((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        messages: [...prev.messages, userMessage],
      };
    });

    try {
      const result: WritingCoachAnswer = await writingCoachService.ask(
        submissionId,
        qTrimmed
      );

      // Add the coach's answer.
      const coachMessage: WritingCoachMessage = {
        id: `coach-${Date.now()}`,
        conversation_id: result.conversation_id || "",
        role: "coach",
        content: result.answer,
        structured: {
          focus: result.focus,
          referenced_text: result.referenced_text,
          referenced_feedback: result.referenced_feedback,
        },
        created_at: new Date().toISOString(),
      };
      setConversation((prev) => {
        if (!prev) {
          return {
            id: result.conversation_id || "",
            user_id: "",
            evaluation_id: evaluation.id || "",
            submission_id: submissionId,
            title: "Writing coaching session",
            status: "active",
            messages: [userMessage, coachMessage],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
        }
        return {
          ...prev,
          messages: [...prev.messages, coachMessage],
        };
      });
    } catch (err: any) {
      setError(err?.message || "Failed to get coach's answer");
      setConversation((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          messages: prev.messages.slice(0, -1),
        };
      });
    } finally {
      setLoading(false);
    }
  }, [submissionId, evaluation.id, conversation?.id]);

  // Load existing conversation messages on mount if a conversation exists.
  const loadConversation = useCallback(async () => {
    try {
      const data = await writingCoachService.listConversations(1, 0);
      if (data.items.length > 0) {
        const conv = await writingCoachService.getConversation(data.items[0].id);
        setConversation(conv as WritingCoachConversation);
      }
    } catch {
      // No existing conversation — that's fine.
    }
  }, []);

  useEffect(() => {
    void loadConversation();
  }, [loadConversation]);

  const renderReferencedText = (texts: string[]) => {
    if (!texts.length) return null;
    return (
      <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-950/30 rounded border-l-2 border-blue-500">
        <p className="text-xs font-medium text-blue-700 dark:text-blue-300 mb-1">
          Quoted from your essay:
        </p>
        {texts.map((t, i) => (
          <blockquote
            key={i}
            className="text-sm italic text-blue-800 dark:text-blue-200"
          >
            &ldquo;{t}&rdquo;
          </blockquote>
        ))}
      </div>
    );
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      className="max-w-3xl h-[80vh] flex flex-col"
    >
      <ModalHeader>
        <ModalTitle className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5 text-blue-600" />
          Writing Coach
        </ModalTitle>
        <p className="text-sm text-muted-foreground">
          Ask questions about your essay — grounded in your actual writing and evaluation.
        </p>
      </ModalHeader>

      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {/* Evaluation summary card (shown at top of conversation) */}
        {!conversation?.messages.length && (
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <BookOpen className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium text-sm">
                    Previous evaluation: Band {evaluation.overall_band?.toFixed(1)}
                  </p>
                  {evaluation.criteria_bands && (
                    <div className="flex gap-2 flex-wrap">
                      {Object.entries(evaluation.criteria_bands).map(([k, v]) => (
                        <Badge key={k} variant="secondary" className="text-xs">
                          {k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}: {v}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {evaluation.weaknesses && evaluation.weaknesses.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Weakness: {evaluation.weaknesses[0]}
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Quick-question presets (only shown when no conversation yet) */}
        {!conversation?.messages.length && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Or try one of these questions:
            </p>
            <div className="grid gap-2">
              {PRESET_QUESTIONS.map((preset) => (
                <Button
                  key={preset}
                  variant="ghost"
                  size="sm"
                  className="justify-start text-left h-auto py-2"
                  onClick={() => void handleAsk(preset)}
                  disabled={loading}
                >
                  <Lightbulb className="h-4 w-4 mr-2 flex-shrink-0" />
                  <span className="text-sm">{preset}</span>
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Conversation messages */}
        {conversation?.messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {msg.role === "coach" && (
              <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-950/30 flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-blue-600" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-secondary text-secondary-foreground"
              }`}
            >
              <div className="prose prose-sm max-w-none">
                {msg.content.split("\n").map((line, i) => (
                  <p key={i} className="mb-2 last:mb-0">
                    {line}
                  </p>
                ))}
              </div>
              {msg.role === "coach" && msg.structured.focus && (
                <Badge
                  className={`mt-2 text-xs ${
                    FOCUS_COLORS[msg.structured.focus as string] ||
                    FOCUS_COLORS.other
                  }`}
                >
                  Focus: {msg.structured.focus}
                </Badge>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <User className="h-4 w-4 text-white" />
              </div>
            )}
          </div>
        ))}

        {/* Referenced text (from current answer) */}
        {conversation?.messages
          .filter((m) => m.role === "coach")
          .slice(-1)[0]?.structured?.referenced_text &&
          renderReferencedText(
            (conversation.messages.filter((m) => m.role === "coach").slice(-1)[0]
              .structured.referenced_text as string[]) || []
          )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border pt-3 space-y-2">
        {error && (
          <div className="flex items-center gap-2 p-2 text-sm text-red-600 bg-red-50 dark:bg-red-950/20 rounded">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}
        <div className="flex gap-2">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about your essay... e.g. 'Why is my Task Response low?'"
            className="flex-1 min-h-[40px] max-h-32"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!loading && question.trim()) {
                  void handleAsk(question);
                }
              }
            }}
          />
          <Button
            size="sm"
            onClick={() => question.trim() && !loading && void handleAsk(question)}
            disabled={loading || !question.trim()}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      <ModalFooter>
        <Button size="sm" variant="outline" onClick={onClose}>
          Close
        </Button>
      </ModalFooter>
    </Modal>
  );
}
