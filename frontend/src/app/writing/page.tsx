"use client";

import React, { useState } from "react";
import { 
  PenTool, 
  Timer, 
  Type, 
  Send, 
  Info, 
  CheckCircle, 
  AlertCircle,
  FileText,
  Sparkles
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function WritingEvaluationPage() {
  const [text, setText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(40 * 60); // 40 minutes in seconds
  const timerRef = React.useRef<NodeJS.Timeout | null>(null);

  const wordCount = text.trim() === "" ? 0 : text.trim().split(/\s+/).length;

  // Start/restart timer on mount
  React.useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setTimerSeconds((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const formatTime = (totalSeconds: number) => {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
  };

  const simulateSubmit = () => {
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setShowFeedback(true);
    }, 2000);
  };

  return (
    <DashboardLayout>
      <div className="flex flex-col h-[calc(100vh-140px)] gap-6">
        
        {/* Top Control Bar */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <PenTool className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Writing Task 2</h1>
              <p className="text-sm text-muted-foreground">Opinion Essay Practice</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 px-4 py-2 bg-secondary rounded-full font-mono text-lg font-bold ${timerSeconds < 300 ? 'text-error' : ''}`}>
              <Timer className="h-5 w-5 text-primary" /> {formatTime(timerSeconds)}
            </div>
            <Button 
              disabled={wordCount < 50 || isSubmitting} 
              onClick={simulateSubmit}
              className="px-6"
            >
              {isSubmitting ? "Analyzing..." : "Submit for AI Review"} 
              <Send className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-6 flex-1 overflow-hidden">
          
          {/* Left: Prompt Area */}
          <Card className="flex flex-col overflow-hidden">
            <CardHeader className="border-b border-border bg-slate-50/50">
              <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">Prompt</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pt-6 space-y-6">
              <div className="prose prose-slate dark:prose-invert">
                <p className="text-lg font-medium leading-relaxed">
                  &ldquo;Some people believe that it is best to accept a bad situation, such as an unsatisfactory job or shortage of money. Others argue that it is better to try and improve such situations.&rdquo;
                </p>
                <p className="font-bold">
                  Discuss both these views and give your own opinion.
                </p>
              </div>

              <div className="space-y-4 pt-6 border-t border-border">
                <h4 className="text-sm font-bold flex items-center gap-2">
                  <Info className="h-4 w-4 text-primary" /> Instructions
                </h4>
                <ul className="text-sm text-muted-foreground space-y-2">
                  <li>• Write at least 250 words.</li>
                  <li>• Use a formal academic style.</li>
                  <li>• Support your arguments with examples.</li>
                  <li>• Spend approximately 40 minutes on this task.</li>
                </ul>
              </div>
            </CardContent>
          </Card>

          {/* Right: Editor Area */}
          <Card className="flex flex-col overflow-hidden border-2 border-primary/20">
            <CardHeader className="border-b border-border flex flex-row items-center justify-between py-3">
              <Tabs defaultValue="standard">
                <TabsList className="h-8">
                  <TabsTrigger value="standard" className="text-xs">Standard Editor</TabsTrigger>
                  <TabsTrigger value="focus" className="text-xs">Focus Mode</TabsTrigger>
                </TabsList>
                <TabsContent value="standard">
                  <div className="p-2 text-xs text-muted-foreground">Standard editor mode</div>
                </TabsContent>
                <TabsContent value="focus">
                  <div className="p-2 text-xs text-muted-foreground">Focus mode — minimize distractions</div>
                </TabsContent>
              </Tabs>
              <div className="flex items-center gap-2 text-sm font-medium">
                <Type className="h-4 w-4 text-muted-foreground" />
                <span className={wordCount < 250 ? "text-warning" : "text-success"}>
                  {wordCount} / 250 words
                </span>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-1 relative">
              <Textarea 
                className="h-full w-full border-none rounded-none p-6 text-lg leading-relaxed focus-visible:ring-0 resize-none bg-transparent"
                placeholder="Type your essay here..."
                value={text}
                onChange={handleTextChange}
              />
              
              {/* AI Feedback Overlay (UI ONLY) */}
              {showFeedback && (
                <div className="absolute inset-0 bg-white/95 dark:bg-slate-950/95 z-50 overflow-y-auto p-8 animate-in fade-in zoom-in-95 duration-300">
                  <div className="flex justify-between items-start mb-8">
                    <div>
                      <Badge variant="accent" className="mb-2 flex items-center gap-1">
                        <Sparkles className="h-3 w-3" /> AI Evaluation Ready
                      </Badge>
                      <h2 className="text-3xl font-bold">Feedback Summary</h2>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setShowFeedback(false)}>Edit Essay</Button>
                  </div>

                  <div className="grid gap-6 md:grid-cols-2">
                    <Card className="bg-primary text-primary-foreground">
                      <CardContent className="pt-6 text-center">
                        <p className="text-sm uppercase tracking-widest opacity-80">Estimated Band</p>
                        <div className="text-6xl font-black my-2">7.0</div>
                        <p className="text-xs">Good work! You met the length requirement.</p>
                      </CardContent>
                    </Card>

                    <div className="space-y-4">
                      <FeedbackMetric label="Task Response" score={7.5} />
                      <FeedbackMetric label="Coherence & Cohesion" score={6.5} />
                      <FeedbackMetric label="Lexical Resource" score={7.0} />
                      <FeedbackMetric label="Grammar Accuracy" score={6.5} />
                    </div>
                  </div>

                  <div className="mt-8 space-y-6">
                    <h3 className="font-bold flex items-center gap-2">
                      <CheckCircle className="h-5 w-5 text-success" /> Major Strengths
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      You provided a very clear personal opinion in the introduction and maintained it throughout the essay.
                    </p>

                    <h3 className="font-bold flex items-center gap-2">
                      <AlertCircle className="h-5 w-5 text-warning" /> Key Improvement
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Try using more cohesive devices (e.g., &ldquo;In contrast&rdquo;, &ldquo;Nevertheless&rdquo;) to link your body paragraphs.
                    </p>
                    
                    <Button className="w-full">View Detailed Annotations</Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}

// Helper for results
const FeedbackMetric = ({ label, score }: { label: string, score: number }) => (
  <div className="space-y-1">
    <div className="flex justify-between text-xs font-bold">
      <span>{label}</span>
      <span>{score}</span>
    </div>
    <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
      <div 
        className="h-full bg-primary transition-all" 
        style={{ width: `${(score / 9) * 100}%` }}
      />
    </div>
  </div>
);