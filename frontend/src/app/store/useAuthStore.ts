import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authService, tokenManager } from '@/services/api';

// Define what the User data looks like
export interface UserProfile {
  id: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  is_active?: boolean;
  created_at?: string;
  // Onboarding / profile fields
  country?: string;
  timezone?: string;
  module?: string;
  current_band?: number;
  target_band?: number;
  exam_date?: string;
  daily_minutes_budget?: number;
  preferred_study_time?: string;
  weakest_skill?: string[];
  strongest_skill?: string[];
  previous_ielts_attempt?: boolean;
  is_onboarding_complete?: boolean;
  onboarded_at?: string;
}

// Define the "Store" shape
interface AuthState {
  user: UserProfile | null;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;
  
  // Actions
  setUser: (user: UserProfile | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
  
  // Auth operations
  initialize: () => Promise<void>;
  login: (email: string, password: string) => Promise<{ error?: string }>;
  signup: (email: string, password: string, fullName: string) => Promise<{ error?: string }>;
  logout: () => Promise<void>;
  resetPassword: (email: string) => Promise<{ error?: string }>;
  refreshProfile: () => Promise<void>;
  loginWithGoogle: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isLoading: true,
      isInitialized: false,
      error: null,

      setUser: (user) => set({ user, isLoading: false, isInitialized: true }),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),

      initialize: async () => {
        try {
          const token = tokenManager.getAccessToken();
          if (!token) {
            set({ user: null, isLoading: false, isInitialized: true });
            return;
          }

          // Try to fetch user profile from backend
          try {
            const profile = await authService.getMe();
            set({ 
              user: {
                id: profile.id,
                email: profile.email,
                full_name: profile.full_name,
                avatar_url: profile.avatar_url,
                is_active: profile.is_active,
                created_at: profile.created_at,
              }, 
              isLoading: false, 
              isInitialized: true 
            });
          } catch {
            // Token might be expired, try to refresh
            const refreshToken = tokenManager.getRefreshToken();
            if (refreshToken) {
              try {
                const tokens = await authService.refreshToken(refreshToken);
                tokenManager.setTokens(tokens.access_token, tokens.refresh_token);
                
                // Retry fetching profile
                const profile = await authService.getMe();
                set({ 
                  user: {
                    id: profile.id,
                    email: profile.email,
                    full_name: profile.full_name,
                    avatar_url: profile.avatar_url,
                  }, 
                  isLoading: false, 
                  isInitialized: true 
                });
              } catch {
                tokenManager.clearTokens();
                set({ user: null, isLoading: false, isInitialized: true });
              }
            } else {
              tokenManager.clearTokens();
              set({ user: null, isLoading: false, isInitialized: true });
            }
          }
        } catch {
          set({ user: null, isLoading: false, isInitialized: true });
        }
      },

      login: async (email: string, password: string) => {
        try {
          set({ isLoading: true, error: null });
          const response = await authService.login(email, password);
          
          // Store tokens
          tokenManager.setTokens(response.access_token, response.refresh_token);
          
          // Fetch user profile
          const profile = await authService.getMe();
          set({
            user: {
              id: profile.id,
              email: profile.email,
              full_name: profile.full_name,
              avatar_url: profile.avatar_url,
            },
            isLoading: false,
            error: null,
          });
          
          return {};
        } catch (error: any) {
          const message = error.response?.data?.detail || error.message || 'Login failed';
          set({ isLoading: false, error: message });
          return { error: message };
        }
      },

      signup: async (email: string, password: string, fullName: string) => {
        try {
          set({ isLoading: true, error: null });
          const response = await authService.register(email, password, fullName);
          
          // Store tokens
          tokenManager.setTokens(response.access_token, response.refresh_token);
          
          // Fetch user profile
          const profile = await authService.getMe();
          set({
            user: {
              id: profile.id,
              email: profile.email,
              full_name: profile.full_name,
              avatar_url: profile.avatar_url,
            },
            isLoading: false,
            error: null,
          });
          
          return {};
        } catch (error: any) {
          const message = error.response?.data?.detail || error.message || 'Registration failed';
          set({ isLoading: false, error: message });
          return { error: message };
        }
      },

      logout: async () => {
        try {
          set({ isLoading: true });
          await authService.logout();
        } catch {
          // Even if logout API fails, clear local state
          tokenManager.clearTokens();
        } finally {
          set({ user: null, isLoading: false, error: null });
        }
      },

      resetPassword: async (email: string) => {
        try {
          set({ isLoading: true, error: null });
          const response = await authService.forgotPassword(email);
          set({ isLoading: false });
          return {};
        } catch (error: any) {
          const message = error.response?.data?.detail || error.message || 'Failed to send reset email';
          set({ isLoading: false, error: message });
          return { error: message };
        }
      },

      refreshProfile: async () => {
        try {
          const profile = await authService.getMe();
          set({
            user: {
              id: profile.id,
              email: profile.email,
              full_name: profile.full_name,
              avatar_url: profile.avatar_url,
            },
          });
        } catch {
          // Silently fail
        }
      },

      loginWithGoogle: async () => {
        // Google OAuth is handled by Supabase
        const { supabase } = await import('@/app/lib/supabase');
        await supabase.auth.signInWithOAuth({ provider: 'google' });
      },
    }),
    {
      name: 'ielts-auth-storage',
      partialize: (state) => ({
        user: state.user,
      }),
    }
  )
);
