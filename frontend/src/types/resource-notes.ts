// Resource Notes, Highlights, and Revision Reminders types

export type NoteColor = "yellow" | "green" | "blue" | "purple" | "pink" | "red";

export interface ResourceNote {
  id: string;
  user_id: string;
  resource_id: string;
  content: string;
  color: NoteColor;
  is_highlighted: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ResourceNoteCreate {
  resource_id: string;
  content: string;
  color?: NoteColor;
  is_highlighted?: boolean;
}

export interface ResourceNoteUpdate {
  content?: string;
  color?: NoteColor;
  is_highlighted?: boolean;
}

export interface ResourceNoteListResponse {
  notes: ResourceNote[];
  total: number;
}

export interface ResourceHighlight {
  id: string;
  user_id: string;
  resource_id: string;
  selected_text: string;
  color: NoteColor;
  note: string | null;
  created_at: string | null;
}

export interface ResourceHighlightCreate {
  resource_id: string;
  selected_text: string;
  color?: NoteColor;
  note?: string;
}

export interface ResourceHighlightListResponse {
  highlights: ResourceHighlight[];
  total: number;
}

export interface RevisionReminder {
  id: string;
  user_id: string;
  resource_id: string;
  note_id: string | null;
  reminder_date: string;
  reminder_time: string | null;
  title: string;
  is_completed: boolean;
  created_at: string | null;
}

export interface RevisionReminderCreate {
  resource_id: string;
  note_id?: string;
  reminder_date: string;
  reminder_time?: string;
  title: string;
}

export interface RevisionReminderUpdate {
  reminder_date?: string;
  reminder_time?: string;
  title?: string;
  is_completed?: boolean;
}

export interface RevisionReminderListResponse {
  reminders: RevisionReminder[];
  total: number;
}

export interface ResourceNoteStats {
  notes_count: number;
  highlights_count: number;
  reminders_count: number;
}