"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  StickyNote,
  Highlighter,
  Bell,
  Search,
  Plus,
  X,
  Trash2,
  CheckCircle2,
  Clock,
  Bookmark,
  BookmarkCheck,
  ChevronDown,
  ChevronUp,
  Calendar,
  Loader2,
  Pencil,
  Save,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { resourceNotesService } from "@/services/api";
import type {
  ResourceNote,
  ResourceHighlight,
  RevisionReminder,
  NoteColor,
} from "@/types/resource-notes";
import type { ResourceItem } from "@/types";

interface ResourceNotesProps {
  resource: ResourceItem;
  onClose?: () => void;
}

const COLOR_META: Record<NoteColor, { bg: string; border: string; text: string; label: string }> = {
  yellow: { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-700", label: "Yellow" },
  green: { bg: "bg-green-50", border: "border-green-200", text: "text-green-700", label: "Green" },
  blue: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", label: "Blue" },
  purple: { bg: "bg-purple-50", border: "border-purple-200", text: "text-purple-700", label: "Purple" },
  pink: { bg: "bg-pink-50", border: "border-pink-200", text: "text-pink-700", label: "Pink" },
  red: { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", label: "Red" },
};

const ALL_COLORS: NoteColor[] = ["yellow", "green", "blue", "purple", "pink", "red"];

export function ResourceNotes({ resource, onClose }: ResourceNotesProps) {
  const [notes, setNotes] = useState<ResourceNote[]>([]);
  const [highlights, setHighlights] = useState<ResourceHighlight[]>([]);
  const [reminders, setReminders] = useState<RevisionReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Note form state
  const [noteContent, setNoteContent] = useState("");
  const [noteColor, setNoteColor] = useState<NoteColor>("yellow");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");

  // Highlight form state
  const [highlightText, setHighlightText] = useState("");
  const [highlightColor, setHighlightColor] = useState<NoteColor>("yellow");
  const [highlightNote, setHighlightNote] = useState("");

  // Reminder form state
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderDate, setReminderDate] = useState("");
  const [reminderTime, setReminderTime] = useState("");

  // Search
  const [searchQuery, setSearchQuery] = useState("");

  // Active tab
  const [activeTab, setActiveTab] = useState<"notes" | "highlights" | "reminders">("notes");

  // ─── Load data ───
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [notesRes, highlightsRes, remindersRes] = await Promise.all([
        resourceNotesService.listNotes({ resource_id: resource.id }),
        resourceNotesService.listHighlights({ resource_id: resource.id }),
        resourceNotesService.listReminders(),
      ]);
      setNotes(notesRes.notes || []);
      setHighlights(highlightsRes.highlights || []);
      setReminders(remindersRes.reminders || []);
    } catch (err: any) {
      setError(err?.message || "Failed to load notes");
    } finally {
      setLoading(false);
    }
  }, [resource.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ─── Filtered notes by search ───
  const filteredNotes = useMemo(() => {
    if (!searchQuery) return notes;
    const q = searchQuery.toLowerCase();
    return notes.filter((n) => n.content.toLowerCase().includes(q));
  }, [notes, searchQuery]);

  // ─── Note handlers ───
  const handleAddNote = async () => {
    if (!noteContent.trim()) return;
    try {
      const note = await resourceNotesService.createNote({
        resource_id: resource.id,
        content: noteContent.trim(),
        color: noteColor,
      });
      setNotes((prev) => [note, ...prev]);
      setNoteContent("");
    } catch (err: any) {
      setError(err?.message || "Failed to add note");
    }
  };

  const handleUpdateNote = async (noteId: string) => {
    if (!editingContent.trim()) return;
    try {
      const updated = await resourceNotesService.updateNote(noteId, {
        content: editingContent.trim(),
      });
      setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)));
      setEditingNoteId(null);
      setEditingContent("");
    } catch (err: any) {
      setError(err?.message || "Failed to update note");
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await resourceNotesService.deleteNote(noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch (err: any) {
      setError(err?.message || "Failed to delete note");
    }
  };

  const handleToggleHighlight = async (noteId: string, isHighlighted: boolean) => {
    try {
      const updated = await resourceNotesService.updateNote(noteId, {
        is_highlighted: !isHighlighted,
      });
      setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)));
    } catch (err: any) {
      setError(err?.message || "Failed to update highlight");
    }
  };

  // ─── Highlight handlers ───
  const handleAddHighlight = async () => {
    if (!highlightText.trim()) return;
    try {
      const highlight = await resourceNotesService.createHighlight({
        resource_id: resource.id,
        selected_text: highlightText.trim(),
        color: highlightColor,
        note: highlightNote.trim() || undefined,
      });
      setHighlights((prev) => [highlight, ...prev]);
      setHighlightText("");
      setHighlightNote("");
    } catch (err: any) {
      setError(err?.message || "Failed to add highlight");
    }
  };

  const handleDeleteHighlight = async (highlightId: string) => {
    try {
      await resourceNotesService.deleteHighlight(highlightId);
      setHighlights((prev) => prev.filter((h) => h.id !== highlightId));
    } catch (err: any) {
      setError(err?.message || "Failed to delete highlight");
    }
  };

  // ─── Reminder handlers ───
  const handleAddReminder = async () => {
    if (!reminderTitle.trim() || !reminderDate) return;
    try {
      const reminder = await resourceNotesService.createReminder({
        resource_id: resource.id,
        title: reminderTitle.trim(),
        reminder_date: reminderDate,
        reminder_time: reminderTime || undefined,
      });
      setReminders((prev) => [reminder, ...prev]);
      setReminderTitle("");
      setReminderDate("");
      setReminderTime("");
    } catch (err: any) {
      setError(err?.message || "Failed to add reminder");
    }
  };

  const handleToggleReminder = async (reminderId: string, isCompleted: boolean) => {
    try {
      const updated = await resourceNotesService.updateReminder(reminderId, {
        is_completed: !isCompleted,
      });
      setReminders((prev) => prev.map((r) => (r.id === reminderId ? updated : r)));
    } catch (err: any) {
      setError(err?.message || "Failed to update reminder");
    }
  };

  const handleDeleteReminder = async (reminderId: string) => {
    try {
      await resourceNotesService.deleteReminder(reminderId);
      setReminders((prev) => prev.filter((r) => r.id !== reminderId));
    } catch (err: any) {
      setError(err?.message || "Failed to delete reminder");
    }
  };

  // ─── Format date ───
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StickyNote className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">Notes & Highlights</h3>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search notes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9 h-10 text-sm"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {[
          { key: "notes" as const, label: `Notes (${notes.length})`, icon: StickyNote },
          { key: "highlights" as const, label: `Highlights (${highlights.length})`, icon: Highlighter },
          { key: "reminders" as const, label: `Reminders (${reminders.length})`, icon: Bell },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* ─── Notes Tab ─── */}
      {!loading && activeTab === "notes" && (
        <div className="space-y-3">
          {/* Add note form */}
          <div className="space-y-2 rounded-lg border border-border p-3">
            <Textarea
              placeholder="Write a note about this resource..."
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              className="min-h-20 text-sm"
            />
            <div className="flex items-center justify-between">
              <div className="flex gap-1">
                {ALL_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setNoteColor(color)}
                    className={`h-5 w-5 rounded-full border-2 transition-all ${
                      COLOR_META[color].bg
                    } ${noteColor === color ? "border-primary scale-110" : "border-transparent"}`}
                    title={COLOR_META[color].label}
                  />
                ))}
              </div>
              <Button size="sm" onClick={handleAddNote} disabled={!noteContent.trim()}>
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Note
              </Button>
            </div>
          </div>

          {/* Notes list */}
          {filteredNotes.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              {searchQuery ? "No notes match your search" : "No notes yet. Add your first note above!"}
            </p>
          ) : (
            <div className="space-y-2">
              {filteredNotes.map((note) => {
                const colorMeta = COLOR_META[note.color] || COLOR_META.yellow;
                return (
                  <div key={note.id} className={`rounded-lg border ${colorMeta.border} ${colorMeta.bg} p-3`}>
                    {editingNoteId === note.id ? (
                      <div className="space-y-2">
                        <Textarea
                          value={editingContent}
                          onChange={(e) => setEditingContent(e.target.value)}
                          className="min-h-16 text-sm"
                        />
                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => handleUpdateNote(note.id)} disabled={!editingContent.trim()}>
                            <Save className="h-3.5 w-3.5 mr-1" />
                            Save
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => { setEditingNoteId(null); setEditingContent(""); }}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                        <div className="flex items-center justify-between mt-2">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleToggleHighlight(note.id, note.is_highlighted)}
                              className={`flex items-center gap-1 text-xs transition-colors ${
                                note.is_highlighted ? "text-amber-600" : "text-muted-foreground hover:text-amber-600"
                              }`}
                            >
                              <Highlighter className="h-3.5 w-3.5" />
                              {note.is_highlighted ? "Highlighted" : "Highlight"}
                            </button>
                            <span className="text-xs text-muted-foreground">
                              {note.created_at ? formatDate(note.created_at) : ""}
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => { setEditingNoteId(note.id); setEditingContent(note.content); }}
                              className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteNote(note.id)}
                              className="p-1 text-muted-foreground hover:text-red-600 transition-colors"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─── Highlights Tab ─── */}
      {!loading && activeTab === "highlights" && (
        <div className="space-y-3">
          {/* Add highlight form */}
          <div className="space-y-2 rounded-lg border border-border p-3">
            <Textarea
              placeholder="Paste or type the text you want to highlight..."
              value={highlightText}
              onChange={(e) => setHighlightText(e.target.value)}
              className="min-h-16 text-sm"
            />
            <Input
              placeholder="Optional note about this highlight..."
              value={highlightNote}
              onChange={(e) => setHighlightNote(e.target.value)}
              className="text-sm"
            />
            <div className="flex items-center justify-between">
              <div className="flex gap-1">
                {ALL_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setHighlightColor(color)}
                    className={`h-5 w-5 rounded-full border-2 transition-all ${
                      COLOR_META[color].bg
                    } ${highlightColor === color ? "border-primary scale-110" : "border-transparent"}`}
                    title={COLOR_META[color].label}
                  />
                ))}
              </div>
              <Button size="sm" onClick={handleAddHighlight} disabled={!highlightText.trim()}>
                <Highlighter className="h-3.5 w-3.5 mr-1" />
                Add Highlight
              </Button>
            </div>
          </div>

          {/* Highlights list */}
          {highlights.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No highlights yet. Highlight important concepts from this resource!
            </p>
          ) : (
            <div className="space-y-2">
              {highlights.map((highlight) => {
                const colorMeta = COLOR_META[highlight.color] || COLOR_META.yellow;
                return (
                  <div key={highlight.id} className={`rounded-lg border ${colorMeta.border} ${colorMeta.bg} p-3`}>
                    <p className="text-sm font-medium">&quot;{highlight.selected_text}&quot;</p>
                    {highlight.note && (
                      <p className="text-xs text-muted-foreground mt-1">{highlight.note}</p>
                    )}
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-muted-foreground">
                        {highlight.created_at ? formatDate(highlight.created_at) : ""}
                      </span>
                      <button
                        onClick={() => handleDeleteHighlight(highlight.id)}
                        className="p-1 text-muted-foreground hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─── Reminders Tab ─── */}
      {!loading && activeTab === "reminders" && (
        <div className="space-y-3">
          {/* Add reminder form */}
          <div className="space-y-2 rounded-lg border border-border p-3">
            <Input
              placeholder="Reminder title (e.g. 'Review vocabulary list')"
              value={reminderTitle}
              onChange={(e) => setReminderTitle(e.target.value)}
              className="text-sm"
            />
            <div className="flex gap-2">
              <Input
                type="date"
                value={reminderDate}
                onChange={(e) => setReminderDate(e.target.value)}
                className="text-sm flex-1"
              />
              <Input
                type="time"
                value={reminderTime}
                onChange={(e) => setReminderTime(e.target.value)}
                className="text-sm w-32"
              />
            </div>
            <Button size="sm" onClick={handleAddReminder} disabled={!reminderTitle.trim() || !reminderDate} className="w-full">
              <Bell className="h-3.5 w-3.5 mr-1" />
              Add Reminder
            </Button>
          </div>

          {/* Reminders list */}
          {reminders.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No revision reminders yet. Set a reminder to review this resource!
            </p>
          ) : (
            <div className="space-y-2">
              {reminders.map((reminder) => (
                <div
                  key={reminder.id}
                  className={`flex items-center gap-3 rounded-lg border border-border p-3 ${
                    reminder.is_completed ? "opacity-60" : ""
                  }`}
                >
                  <button
                    onClick={() => handleToggleReminder(reminder.id, reminder.is_completed)}
                    className={`flex-shrink-0 h-5 w-5 rounded-full border-2 transition-colors ${
                      reminder.is_completed
                        ? "bg-green-500 border-green-500 text-white"
                        : "border-muted-foreground hover:border-primary"
                    }`}
                  >
                    {reminder.is_completed && <CheckCircle2 className="h-4 w-4" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium ${reminder.is_completed ? "line-through" : ""}`}>
                      {reminder.title}
                    </p>
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {formatDate(reminder.reminder_date)}
                      {reminder.reminder_time && (
                        <>
                          <Clock className="h-3 w-3 ml-1" />
                          {reminder.reminder_time}
                        </>
                      )}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteReminder(reminder.id)}
                    className="p-1 text-muted-foreground hover:text-red-600 transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}