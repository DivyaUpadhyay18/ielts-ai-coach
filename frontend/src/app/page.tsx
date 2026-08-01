import React from "react";
import Link from "next/link";
import { 
  Zap, 
  CheckCircle2, 
  ArrowRight, 
  PenTool, 
  Mic, 
  BarChart3, 
  MessageSquare, 
  Star 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LandingLayout } from "@/components/layouts/landing-layout";

export default function LandingPage() {
  return (
    <LandingLayout>
      {/* 1. HERO SECTION */}
      <section className="relative overflow-hidden bg-background py-20 lg:py-32">
        <div className="container mx-auto px-4 relative z-10">
          <div className="flex flex-col items-center text-center">
            <Badge variant="accent" className="mb-4 px-4 py-1 text-sm">
              ✨ New: Real-time Speaking Feedback
            </Badge>
            <h1 className="max-w-4xl text-5xl font-extrabold tracking-tight sm:text-7xl">
              Master the IELTS with your <span className="text-primary">Personal AI Coach</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
              Get instant band scores, detailed writing corrections, and speaking practice 
              powered by advanced AI. Achieve your target score in half the time.
            </p>
            <div className="mt-10 flex flex-col space-y-4 sm:flex-row sm:space-x-4 sm:space-y-0">
              <Link href="/signup">
                <Button size="lg" className="h-12 px-8 text-base">
                  Start Free Practice <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href="/resources">
                <Button variant="outline" size="lg" className="h-12 px-8 text-base">
                  View Sample Feedback
                </Button>
              </Link>
            </div>
            
            {/* Social Proof */}
            <div className="mt-12 flex flex-col items-center space-y-4">
              <p className="text-sm font-medium text-muted-foreground">Trusted by 10,000+ students worldwide</p>
              <div className="flex space-x-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star key={s} className="h-5 w-5 fill-warning text-warning" />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Decorative background blur */}
        <div className="absolute top-1/2 left-1/2 -z-10 h-[400px] w-[600px] -translate-x-1/2 -translate-y-1/2 bg-primary/10 blur-[120px] rounded-full" />
      </section>

      {/* 2. FEATURES GRID */}
      <section className="bg-slate-50 py-24 dark:bg-slate-950">
        <div className="container mx-auto px-4">
          <div className="mb-16 text-center">
            <h2 className="text-3xl font-bold sm:text-4xl">Everything you need to succeed</h2>
            <p className="mt-4 text-muted-foreground">Advanced tools designed by IELTS examiners and AI engineers.</p>
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            <FeatureCard 
              icon={PenTool}
              title="Writing Evaluation"
              description="Upload your Task 1 & 2 essays and get instant band scores with grammar and vocabulary suggestions."
            />
            <FeatureCard 
              icon={Mic}
              title="Speaking Simulator"
              description="Practice speaking in a real-time exam environment with our AI examiner. Get feedback on pronunciation."
            />
            <FeatureCard 
              icon={BarChart3}
              title="Progress Analytics"
              description="Track your performance across different skills and see your estimated band score improve over time."
            />
            <FeatureCard 
              icon={MessageSquare}
              title="Natural Conversations"
              description="Chat with the AI coach to learn new idioms, complex grammar, and IELTS-specific vocabulary."
            />
            <FeatureCard 
              icon={Zap}
              title="Instant Feedback"
              description="No more waiting days for a tutor. Get your results in seconds and learn from your mistakes immediately."
            />
            <FeatureCard 
              icon={CheckCircle2}
              title="Band 9.0 Strategy"
              description="Access specialized roadmaps designed to help you reach the highest possible scores."
            />
          </div>
        </div>
      </section>

      {/* 3. HOW IT WORKS */}
      <section className="py-24">
        <div className="container mx-auto px-4">
          <h2 className="mb-16 text-center text-3xl font-bold sm:text-4xl">How it works</h2>
          <div className="grid gap-12 lg:grid-cols-3">
            <Step 
              number="01" 
              title="Choose a Task" 
              desc="Select from our library of hundreds of actual IELTS Writing and Speaking prompts." 
            />
            <Step 
              number="02" 
              title="Complete Practice" 
              desc="Type your essay or record your voice. Our interface mimics the real computer-delivered IELTS." 
            />
            <Step 
              number="03" 
              title="Get AI Analysis" 
              desc="Receive a detailed breakdown of your score based on official IELTS marking criteria." 
            />
          </div>
        </div>
      </section>

      {/* 4. TESTIMONIALS */}
      <section className="bg-primary py-24 text-primary-foreground">
        <div className="container mx-auto px-4">
          <h2 className="mb-16 text-center text-3xl font-bold sm:text-4xl">Student Success Stories</h2>
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            <Testimonial 
              name="Sarah L." 
              score="Band 8.5" 
              text="The writing feedback is incredibly accurate. It caught errors that my human tutor missed!" 
            />
            <Testimonial 
              name="Ahmed K." 
              score="Band 7.5" 
              text="I was stuck at 6.0 in Speaking. After two weeks with the AI Coach, I finally hit my target." 
            />
            <Testimonial 
              name="Wei Z." 
              score="Band 8.0" 
              text="The most affordable way to practice. The daily study roadmap kept me on track every day." 
            />
          </div>
        </div>
      </section>

      {/* 5. FAQ SECTION */}
      <section className="py-24">
        <div className="container mx-auto px-4 max-w-3xl">
          <h2 className="mb-12 text-center text-3xl font-bold sm:text-4xl">Frequently Asked Questions</h2>
          <div className="space-y-4">
            <FAQItem 
              question="Is the AI grading accurate?" 
              answer="Yes! Our AI is trained on thousands of officially graded IELTS essays and follows the exact public band descriptors." 
            />
            <FAQItem 
              question="Can I use this for both General and Academic?" 
              answer="Absolutely. We have specific modules and prompts for both Academic and General Training modules." 
            />
            <FAQItem 
              question="How much does it cost?" 
              answer="You can start for free. Premium plans with unlimited AI analysis start at just $15/month." 
            />
          </div>
        </div>
      </section>

      {/* 6. FINAL CTA */}
      <section className="py-24 bg-slate-900 text-white">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold sm:text-5xl mb-6">Ready to hit your target score?</h2>
          <p className="text-slate-400 mb-10 text-lg">Join thousands of students who are already using IELTS AI Coach.</p>
          <Link href="/signup">
            <Button size="lg" variant="accent" className="h-14 px-10 text-lg">
              Get Started for Free
            </Button>
          </Link>
        </div>
      </section>
    </LandingLayout>
  );
}

// Helper Components for this page only
const FeatureCard = ({ icon: Icon, title, description }: any) => (
  <Card className="border-none shadow-none bg-transparent hover:bg-white dark:hover:bg-slate-900 transition-colors">
    <CardContent className="pt-6">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-xl font-bold mb-2">{title}</h3>
      <p className="text-muted-foreground">{description}</p>
    </CardContent>
  </Card>
);

const Step = ({ number, title, desc }: any) => (
  <div className="relative flex flex-col items-center text-center">
    <div className="text-6xl font-black text-slate-100 dark:text-slate-900 absolute -top-10 -z-10">{number}</div>
    <h3 className="text-xl font-bold mb-3 mt-4">{title}</h3>
    <p className="text-muted-foreground">{desc}</p>
  </div>
);

const Testimonial = ({ name, score, text }: any) => (
  <Card className="bg-primary-foreground/10 border-none text-white">
    <CardContent className="pt-6">
      <div className="flex mb-4">
        {[1,2,3,4,5].map(s => <Star key={s} className="h-4 w-4 fill-accent text-accent" />)}
      </div>
      <p className="italic mb-4">&ldquo;{text}&rdquo;</p>
      <div className="flex items-center justify-between">
        <span className="font-bold">{name}</span>
        <Badge variant="accent">{score}</Badge>
      </div>
    </CardContent>
  </Card>
);

const FAQItem = ({ question, answer }: any) => (
  <div className="border-b border-border pb-4">
    <h3 className="text-lg font-medium mb-2">{question}</h3>
    <p className="text-muted-foreground text-sm">{answer}</p>
  </div>
);