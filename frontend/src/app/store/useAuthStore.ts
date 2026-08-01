import { create } from 'zustand';
import { supabase } from '@/app/lib/supabase';

// Define what the User data looks like
export interface UserProfile {
  id: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
}

// Define the "Store" shape
interface AuthState {
  user: UserProfile | null;
  isLoading: boolean;
  // Action to update the user
  setUser: (user: UserProfile | null) => void;
  // Action to set loading state
  setLoading: (loading: boolean) => void;
  // Action to clear everything (Logout)
  logout: () => void;
  // Initialize auth session from Supabase
  initialize: () => Promise<void>;
  // Login with email/password
  login: (email: string, password: string) => Promise<{ error?: string }>;
  // Signup with email/password
  signup: (email: string, password: string, fullName: string) => Promise<{ error?: string }>;
  // Reset password
  resetPassword: (email: string) => Promise<{ error?: string }>;
  // Sign in with Google
  loginWithGoogle: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,

  setUser: (user) => set({ user, isLoading: false }),
  
  setLoading: (loading) => set({ isLoading: loading }),

  logout: async () => {
    await supabase.auth.signOut();
    set({ user: null, isLoading: false });
  },

  initialize: async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user) {
        const profile: UserProfile = {
          id: session.user.id,
          email: session.user.email,
          full_name: session.user.user_metadata?.full_name,
          avatar_url: session.user.user_metadata?.avatar_url,
        };
        set({ user: profile, isLoading: false });
      } else {
        set({ user: null, isLoading: false });
      }
    } catch {
      set({ user: null, isLoading: false });
    }
  },

  login: async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) return { error: error.message };
    if (data.user) {
      const profile: UserProfile = {
        id: data.user.id,
        email: data.user.email,
        full_name: data.user.user_metadata?.full_name,
      };
      set({ user: profile, isLoading: false });
    }
    return {};
  },

  signup: async (email: string, password: string, fullName: string) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    });
    if (error) return { error: error.message };
    if (data.user) {
      const profile: UserProfile = {
        id: data.user.id,
        email: data.user.email,
        full_name: fullName,
      };
      set({ user: profile, isLoading: false });
    }
    return {};
  },

  resetPassword: async (email: string) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/login`,
    });
    if (error) return { error: error.message };
    return {};
  },

  loginWithGoogle: async () => {
    await supabase.auth.signInWithOAuth({ provider: 'google' });
  },
}));
