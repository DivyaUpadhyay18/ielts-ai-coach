"use client";

import { useState, useEffect, useCallback } from "react";
import {
  SessionStartResponse,
  SessionNote,
  SessionBookmark,
  SessionCompleteResponse,
  ResourceItem,
  PreviousMistake,
} from "@/types";
import { learningSessionsService } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  PlayCircle,
  CheckCircle2,
  Bookmark,
  BookmarkCheck,
  Clock,
  Award,
  FileText,
  ExternalLink,
  AlertCircle,
  Plus,
  X,
} from "lucide-react";

const LearningSessionPage = () => {
  const [session, setSession] = useState<SessionStartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [noteInput, setNoteInput] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [progressInput, setProgressInput] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [completeResult, setCompleteResult] = useState<SessionCompleteResponse | null>(null);

  const loadSession = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const skill = params.get("skill") || undefined;
    const missionId = params.get("mission_id") || undefined;

    setLoading(true);
    setError(null);
    try {
      const data = await learningSessionsService.startSession({
        mission_id: missionId,
        skill,
      });
      setSession(data);
      if (data.progress_percent) {
        setProgressInput(data.progress_percent);
      }
    } catch (err: any) {
      setError(err?.message || "Could not load session data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const handleComplete = async () => {
    if (!session?.mission?.id) return;

    const currentProgress =
      typeof progressInput === "number" ? progressInput : session.progress_percent;

    if (currentProgress < 50) {
      setError("Set progress to at least 50% before marking complete");
      return;
    }

    setCompleting(true);
    setError(null);
    try {
      await learningSessionsService.updateProgress(session.mission.id, {
        progress_percent: 100,
      });

      const result = await learningSessionsService.completeSession(session.mission.id, {
        progress: 100,
        actual_duration_minutes: session.estimated_time,
      });

      setCompleteResult(result);
      setSession((prev) =>
        prev
          ? {
              ...prev,
              progress_percent: 100,
            }
          : prev
      );
    } catch (err: any) {
      setError(err?.message || "Could not complete session");
    } finally {
      setCompleting(false);
    }
  };

  const handleAddNote = async () => {
    if (!session?.mission?.id || !noteInput.trim()) return;

    setAddingNote(true);
    setError(null);
    try {
      const note = await learningSessionsService.addNote(session.mission.id, {
        content: noteInput,
      });
      setSession((prev) =>
        prev
          ? {
              ...prev,
              notes: [...(prev.notes || []), note],
            }
          : prev
      );
      setNoteInput("");
    } catch (err: any) {
      setError(err?.message || "Could not save your note");
    } finally {
      setAddingNote(false);
    }
  };

  const handleToggleBookmark = async (resource: ResourceItem) => {
    if (!session?.mission?.id) return;

    const isBookmarked = session.bookmarks?.some(
      (b: SessionBookmark) => b.resource_id === resource.id
    );

    if (isBookmarked) return;

    setError(null);
    try {
      const bookmark = await learningSessionsService.addBookmark(
        session.mission.id,
        { resource_id: resource.id }
      );
      setSession((prev) =>
        prev
          ? {
              ...prev,
              bookmarks: [...(prev.bookmarks || []), bookmark],
            }
          : prev
      );
      setError("Resource bookmarked! Saved to your session bookmarks");
    } catch (err: any) {
      setError(err?.message || "Could not bookmark resource");
    }
  };

  const handleProgressUpdate = async () => {
    if (!session?.mission?.id) return;

    const progress = typeof progressInput === "number" ? progressInput : 0;
    if (progress < 0 || progress > 100) return;

    try {
      await learningSessionsService.updateProgress(session.mission.id, {
        progress_percent: progress,
      });
      setSession((prev) =>
        prev
          ? { ...prev, progress_percent: progress }
          : prev
      );
    } catch (err: any) {
      setError(err?.message || "Could not update progress");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">No session data available</p>
      </div>
    );
  }

  const {
    mission,
    recommended_resource,
    related_resources,
    previous_mistakes,
    notes,
    bookmarks,
    progress_percent,
    estimated_time,
    xp_reward,
    current_band,
    target_band,
    remaining_days,
  } = session;

  if (!mission) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">No mission found for today</p>
      </div>
    );
  }

  const isBookmarked = (resourceId: string) =>
    bookmarks?.some((b: SessionBookmark) => b.resource_id === resourceId);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {error && (
          <div
            className={`p-4 rounded-lg flex items-center gap-3 text-sm ${
              error.includes("bookmarked") || error.includes("saved")
                ? "bg-green-50 text-green-800 border border-green-200"
                : "bg-red-50 text-red-800 border border-red-200"
            }`}
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Completion Success Display */}
        {completeResult && (
          <Card className="border-green-200 bg-green-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-700">
                <Award className="w-6 h-6" />
                Mission Completed!
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="text-lg">
                  <strong>+{completeResult.xp_earned} XP</strong> earned
                </p>
                <p className="text-sm text-gray-600">
                  {completeResult.message}
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold">{completeResult.level}</p>
                    <p className="text-xs text-gray-500">Level</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold">{completeResult.total_xp}</p>
                    <p className="text-xs text-gray-500">Total XP</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold">{completeResult.streak_current}</p>
                    <p className="text-xs text-gray-500">Day Streak</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold">{completeResult.achievements_unlocked.length}</p>
                    <p className="text-xs text-gray-500">Achievements</p>
                  </div>
                </div>
                {completeResult.achievements_unlocked.length > 0 && (
                  <p className="text-sm mt-2">
                    Unlocked: {completeResult.achievements_unlocked.join(", ")}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{mission.title}</h1>
            <p className="text-gray-600 mt-1">
              Skill: <Badge variant="secondary">{mission.skill}</Badge>
              <Badge variant="outline" className="ml-2">
                {mission.status}
              </Badge>
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">
              Band: {current_band} → {target_band}
            </p>
            <p className="text-sm text-gray-500">
              Exam in: {remaining_days} days
            </p>
          </div>
        </div>

        {/* Mission Details Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlayCircle className="w-5 h-5 text-blue-500" />
              Today&apos;s Mission
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-lg">Task Description</h3>
                <p className="text-gray-700 mt-1">
                  {mission.skill.charAt(0).toUpperCase() + mission.skill.slice(1)} practice
                  mission for today. Complete the recommended resource and related
                  materials to earn XP.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                  <Clock className="w-4 h-4 text-gray-500" />
                  <div>
                    <span className="text-xs text-gray-500">Estimated Time</span>
                    <span className="font-semibold block">
                      {estimated_time} minutes
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                  <Award className="w-4 h-4 text-yellow-400" />
                  <div>
                    <span className="text-xs text-gray-500">XP Reward</span>
                    <span className="font-semibold block">+{xp_reward} XP</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                  <div>
                    <span className="text-xs text-gray-500">Current Progress</span>
                    <span className="font-semibold block">
                      {progress_percent}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Progress Bar */}
        <Card>
          <CardHeader>
            <CardTitle>Progress Tracker</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Progress value={progress_percent} className="h-4" />

              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  max="100"
                  value={progressInput}
                  onChange={(e) =>
                    setProgressInput(
                      e.target.value === "" ? "" : parseInt(e.target.value)
                    )
                  }
                  className="w-20"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleProgressUpdate}
                >
                  Update
                </Button>
                <span className="text-sm text-gray-500">
                  Set to 100% to mark complete
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recommended Resource */}
        {recommended_resource && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Recommended Resource</span>
                <Button
                  variant={isBookmarked(recommended_resource.id) ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleToggleBookmark(recommended_resource)}
                >
                  {isBookmarked(recommended_resource.id) ? (
                    <BookmarkCheck className="w-4 h-4" />
                  ) : (
                    <Bookmark className="w-4 h-4" />
                  )}
                  {isBookmarked(recommended_resource.id) ? "Bookmarked" : "Bookmark"}
                </Button>
              </CardTitle>
              <CardDescription>
                Hand-picked for your <strong>{mission.skill}</strong> mission
              </CardDescription>
            </CardHeader>
            <CardContent>
              <a
                href={
                  recommended_resource.url ||
                  `https://study.raenna.ai/resource/${recommended_resource.id}`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="group"
              >
                <div className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex gap-4">
                    {recommended_resource.thumbnail && (
                      <img
                        src={recommended_resource.thumbnail}
                        alt={recommended_resource.title}
                        className="w-24 h-16 object-cover rounded"
                      />
                    )}
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg group-hover:text-blue-600 transition-colors">
                        {recommended_resource.title}
                      </h3>
                      <p className="text-gray-600 text-sm mt-1 line-clamp-2">
                        {recommended_resource.description}
                      </p>
                      <div className="flex items-center gap-1 mt-2">
                        <Badge
                          variant={
                            recommended_resource.type === "Video" ? "default" : "secondary"
                          }
                        >
                          {recommended_resource.type}
                        </Badge>
                        {recommended_resource.is_free && (
                          <Badge variant="outline">Free</Badge>
                        )}
                        {recommended_resource.official && (
                          <Badge
                            variant="outline"
                            className="bg-blue-50 text-blue-700"
                          >
                            Official
                          </Badge>
                        )}
                        {recommended_resource.estimated_time && (
                          <Badge variant="outline">
                            {recommended_resource.estimated_time} min
                          </Badge>
                        )}
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-blue-600" />
                  </div>
                </div>
              </a>
            </CardContent>
          </Card>
        )}

        {/* Previous Mistakes */}
        {previous_mistakes.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-orange-500" />
                Previous Mistakes
              </CardTitle>
              <CardDescription>
                Review these errors before starting your session
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {previous_mistakes.map((mistake: PreviousMistake, idx: number) => (
                  <div
                    key={mistake.task_id || idx}
                    className="border-l-4 border-orange-400 pl-4 py-2 bg-orange-50"
                  >
                    <p className="font-medium text-sm">
                      {mistake.mistake_type}
                    </p>
                    <p className="text-gray-700 text-sm mt-1">
                      {mistake.description}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      From: {mistake.task_title} ({mistake.skill})
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Related Resources */}
        {related_resources.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Related Resources</CardTitle>
              <CardDescription>
                Additional materials to supplement your mission
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {related_resources.map((resource: ResourceItem) => (
                  <div
                    key={resource.id}
                    className="border rounded-lg p-3 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-medium text-sm">
                          {resource.title}
                        </h3>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                          {resource.description}
                        </p>
                        <div className="flex items-center gap-1 mt-2">
                          <Badge variant="outline" className="text-xs">
                            {resource.type}
                          </Badge>
                          {resource.is_free && (
                            <Badge variant="outline" className="text-xs">
                              Free
                            </Badge>
                          )}
                          {resource.official && (
                            <Badge
                              variant="outline"
                              className="text-xs bg-blue-50 text-blue-700"
                            >
                              Official
                            </Badge>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggleBookmark(resource)}
                      >
                        {isBookmarked(resource.id) ? (
                          <BookmarkCheck className="w-4 h-4 text-blue-500" />
                        ) : (
                          <Bookmark className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Notes Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-gray-600" />
              Notes
            </CardTitle>
            <CardDescription>
              Save notes during your learning session
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex gap-2">
                <Textarea
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Write a note about this session..."
                  className="flex-1"
                  rows={3}
                />
                <Button
                  onClick={handleAddNote}
                  disabled={addingNote || !noteInput.trim()}
                  size="sm"
                >
                  {addingNote ? "..." : <Plus className="w-4 h-4" />}
                </Button>
              </div>

              {notes && notes.length > 0 ? (
                <div className="space-y-3">
                  {notes.map((note: SessionNote, idx: number) => (
                    <div
                      key={note.id || idx}
                      className="p-3 bg-gray-50 rounded-lg border"
                    >
                      <p className="text-gray-700 text-sm">{note.content}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {note.created_at
                          ? new Date(note.created_at).toLocaleString()
                          : ""}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-sm">
                  No notes yet. Start taking notes during your session!
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Mark Complete */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Award className="w-6 h-6 text-yellow-400" />
                <div>
                  <p className="font-semibold">
                    Earn {xp_reward} XP upon completion
                  </p>
                  <p className="text-sm text-gray-500">
                    This will mark your mission as completed, log study time,
                    update your streak, and update your dashboard.
                  </p>
                </div>
              </div>
              <Button
                variant="default"
                size="lg"
                onClick={handleComplete}
                disabled={completing || progress_percent >= 100 || !!completeResult}
                className="bg-green-600 hover:bg-green-700"
              >
                {completing ? (
                  "..."
                ) : progress_percent >= 100 || completeResult ? (
                  "Completed"
                ) : (
                  <>
                    <CheckCircle2 className="w-5 h-5 mr-2" />
                    Mark Complete
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LearningSessionPage;