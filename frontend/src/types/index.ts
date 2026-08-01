export type IELTSBandScore = 0 | 1 | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 | 5 | 5.5 | 6 | 6.5 | 7 | 7.5 | 8 | 8.5 | 9;

export interface Assessment {
  id: string;
  user_id: string;
  task_type: 'Writing Task 1' | 'Writing Task 2' | 'Speaking';
  user_input: string;
  band_score: number;
  feedback: string;
  corrections: string[];
  created_at: string;
}

export interface UserProfile {
  id: string;
  full_name?: string;
  email?: string;
  avatar_url?: string;
  target_band?: number;
  joined_at: string;
}

export interface AIResponse {
  score: number;
  analysis: string;
  suggestions: string[];
}