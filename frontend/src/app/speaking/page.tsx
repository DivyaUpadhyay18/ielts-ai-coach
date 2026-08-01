"use client";

import React, { useState } from "react";
import { 
  Mic, 
  Square, 
  Volume2, 
  MessageSquare, 
  ChevronRight, 
  Sparkles,
  RefreshCcw,
  Headphones,
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";

export default function SpeakingPracticePage() {
  const [isRecording, setIsRecording] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [transcript, setTranscript] = useState("");
  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        // Stop all tracks to release the microphone
        stream.getTracks().forEach(track => track.stop());
        setTranscript("Well, I live in a coastal city in the south of the country... it's a very vibrant and energetic place...");
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone access denied:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto h-[calc(100vh-140px)] flex flex-col gap-6">
        
        {/* Header with Progress */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <MessageSquare className="h-6 w-6 text-primary" /> Speaking Simulator
            </h1>
            <p className="text-sm text-muted-foreground">Part 1: Introduction and Interview</p>
          </div>
          <div className="flex items-center gap-2">
            {[1, 2, 3].map((step) => (
              <div 
                key={step}
                className={`h-2 w-12 rounded-full transition-colors ${
                  step === currentStep ? 'bg-primary' : step < currentStep ? 'bg-success' : 'bg-secondary'
                }`}
              />
            ))}
            <span className="ml-2 text-xs font-bold text-muted-foreground uppercase">Part {currentStep} of 3</span>
          </div>
        </div>

        {/* Main Simulator Area */}
        <div className="flex-1 grid lg:grid-cols-3 gap-6 overflow-hidden">
          
          {/* Left/Center: Examiner & Interaction */}
          <div className="lg:col-span-2 flex flex-col gap-6 overflow-hidden">
            <Card className="flex-1 flex flex-col items-center justify-center p-8 bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-950 border-2 border-primary/10">
              <div className="relative mb-8">
                <Avatar 
                  size="xl" 
                  className="h-32 w-32 ring-4 ring-white shadow-2xl" 
                  fallback="AI" 
                />
                <div className="absolute -bottom-2 -right-2 bg-success h-6 w-6 rounded-full border-4 border-white flex items-center justify-center">
                  <div className="h-2 w-2 rounded-full bg-white animate-pulse" />
                </div>
              </div>

              <div className="text-center max-w-md space-y-4">
                <Badge variant="outline" className="bg-white/50 dark:bg-black/50">Examiner is speaking...</Badge>
                <h2 className="text-2xl font-bold leading-tight">
                  &ldquo;Could you tell me about the town or city where you live?&rdquo;
                </h2>
                <div className="flex justify-center gap-2">
                   <Button variant="ghost" size="sm" className="h-8 text-xs">
                     <Volume2 className="mr-1 h-4 w-4" /> Replay Question
                   </Button>
                </div>
              </div>

              {/* Waveform Visualization (Mock) */}
              <div className="mt-12 w-full max-w-xs h-16 flex items-center justify-center gap-1">
                {[...Array(20)].map((_, i) => (
                  <div 
                    key={i} 
                    className={`w-1 rounded-full bg-primary/40 transition-all duration-300 ${
                      isRecording ? 'animate-bounce' : 'h-2'
                    }`}
                    style={{ 
                      height: isRecording ? `${Math.random() * 100}%` : '8px',
                      animationDelay: `${i * 0.05}s`
                    }}
                  />
                ))}
              </div>
            </Card>

            {/* Controls */}
            <div className="flex items-center justify-center gap-6 pb-4">
              <Button 
                variant="outline" 
                size="icon" 
                className="h-12 w-12 rounded-full"
                onClick={() => {}}
              >
                <RefreshCcw className="h-5 w-5" />
              </Button>

              <button 
                onClick={toggleRecording}
                className={`group relative flex h-20 w-20 items-center justify-center rounded-full transition-all duration-300 shadow-xl ${
                  isRecording 
                  ? 'bg-error scale-110' 
                  : 'bg-primary hover:scale-105'
                }`}
              >
                {isRecording ? (
                  <Square className="h-8 w-8 text-white fill-current" />
                ) : (
                  <Mic className="h-10 w-10 text-white" />
                )}
                {isRecording && (
                  <span className="absolute -inset-2 rounded-full border-2 border-error animate-ping opacity-25" />
                )}
              </button>

              <Button 
                variant="default" 
                size="icon" 
                className="h-12 w-12 rounded-full bg-accent hover:bg-accent/90"
                onClick={() => setCurrentStep(currentStep + 1)}
              >
                <ChevronRight className="h-6 w-6" />
              </Button>
            </div>
          </div>

          {/* Right: Live Insights / Transcript */}
          <div className="flex flex-col gap-6 overflow-hidden">
            <Card className="flex-1 overflow-hidden flex flex-col">
              <div className="p-4 border-b border-border bg-slate-50 dark:bg-slate-900 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                  <Headphones className="h-3 w-3" /> Live Transcript
                </span>
                {isRecording && <Badge variant="destructive" className="animate-pulse">Listening</Badge>}
              </div>
              <CardContent className="flex-1 overflow-y-auto p-4 italic text-sm leading-relaxed text-muted-foreground">
                {transcript ? (
                  <p className="animate-in fade-in slide-in-from-bottom-2">
                    {transcript}
                    <span className="inline-block w-1 h-4 bg-primary ml-1 animate-pulse" />
                  </p>
                ) : isRecording ? (
                  <p className="text-center mt-20 opacity-50">Recording in progress...</p>
                ) : (
                  <p className="text-center mt-20 opacity-30">Your response will appear here as you speak.</p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-primary/5 border-primary/20">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="text-xs font-bold">AI Coach Focus</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  The examiner is looking for **fluency**. Try to keep talking without long pauses, even if you make small mistakes.
                </p>
              </CardContent>
            </Card>
          </div>

        </div>
      </div>
    </DashboardLayout>
  );
}