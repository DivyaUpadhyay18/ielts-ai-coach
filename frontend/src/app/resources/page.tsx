"use client";

import React, { useState } from "react";
import { 
  Search, 
  BookOpen, 
  Video, 
  FileText, 
  Clock, 
  Filter,
  GraduationCap,
  ChevronRight
} from "lucide-react";
import { DashboardLayout } from "@/components/layouts/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function ResourcesPage() {
  const [activeCategory, setActiveCategory] = useState("All");

  const categories = ["All", "Writing", "Speaking", "Vocabulary", "Grammar", "Exam Tips"];

  const resources = [
    {
      id: 1,
      title: "Mastering Writing Task 2: The 4-Paragraph Structure",
      skill: "Writing",
      difficulty: "Intermediate",
      duration: "12 min read",
      provider: "AI Coach Team",
      type: "Article"
    },
    {
      id: 2,
      title: "Speaking Part 1: Common Topics & Model Answers",
      skill: "Speaking",
      difficulty: "Beginner",
      duration: "20 min video",
      provider: "British Council",
      type: "Video"
    },
    {
      id: 3,
      title: "Academic Vocabulary for Data Description",
      skill: "Vocabulary",
      difficulty: "Advanced",
      duration: "15 min study",
      provider: "Official IELTS",
      type: "Guide"
    },
    {
      id: 4,
      title: "How to Avoid Common Punctuation Mistakes",
      skill: "Grammar",
      difficulty: "Intermediate",
      duration: "8 min read",
      provider: "AI Coach Team",
      type: "Article"
    },
    {
      id: 5,
      title: "Time Management Strategies for the Computer Exam",
      skill: "Exam Tips",
      difficulty: "All Levels",
      duration: "10 min read",
      provider: "IDP Education",
      type: "Article"
    },
    {
      id: 6,
      title: "Complex Sentences for Band 7.0+",
      skill: "Grammar",
      difficulty: "Advanced",
      duration: "25 min study",
      provider: "AI Coach Team",
      type: "Guide"
    }
  ];

  const filteredResources = activeCategory === "All" 
    ? resources 
    : resources.filter(r => r.skill === activeCategory);

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header & Search */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Study Resources</h1>
            <p className="text-muted-foreground">Handpicked guides and videos to boost your band score.</p>
          </div>
          <div className="relative w-full md:w-80">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search resources..." className="pl-10" />
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground mr-2" />
            {categories.map((cat) => (
              <Button
                key={cat}
                variant={activeCategory === cat ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveCategory(cat)}
                className="whitespace-nowrap"
              >
                {cat}
              </Button>
            ))}
          </div>
        </div>

        {/* Resource Grid */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredResources.map((resource) => (
            <Card key={resource.id} className="flex flex-col group hover:shadow-md transition-shadow">
              <CardHeader className="space-y-2">
                <div className="flex justify-between items-start">
                  <Badge 
                    variant={resource.skill === 'Writing' ? 'default' : resource.skill === 'Speaking' ? 'accent' : 'secondary'}
                  >
                    {resource.skill}
                  </Badge>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center gap-1">
                    {resource.type === 'Video' ? <Video className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
                    {resource.type}
                  </span>
                </div>
                <CardTitle className="text-lg leading-snug group-hover:text-primary transition-colors">
                  {resource.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1">
                <div className="flex flex-col gap-2">
                  <div className="flex items-center text-sm text-muted-foreground">
                    <GraduationCap className="mr-2 h-4 w-4" />
                    <span>{resource.provider}</span>
                  </div>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <Clock className="mr-2 h-4 w-4" />
                    <span>{resource.duration}</span>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="border-t border-border pt-4 flex justify-between items-center">
                <Badge variant="outline" className="text-[10px]">
                  {resource.difficulty}
                </Badge>
                <Button variant="ghost" size="sm" className="text-primary hover:text-primary hover:bg-primary/5">
                  View Resource <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>

        {/* Empty State */}
        {filteredResources.length === 0 && (
          <div className="text-center py-20">
            <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-medium">No resources found</h3>
            <p className="text-muted-foreground">Try adjusting your filters or search terms.</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}