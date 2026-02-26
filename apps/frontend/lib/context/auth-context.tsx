'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { API_BASE } from '@/lib/api/client';

const ACCESS_TOKEN_KEY = 'resume_matcher_access_token';
const REFRESH_TOKEN_KEY = 'resume_matcher_refresh_token';

export interface UserProfile {
  user_id: string;
  email: string;
  llm_provider: string;
  llm_model: string;
  llm_api_key: string;
  llm_api_base: string | null;
  telegram_bot_token: string;
  telegram_webhook_url: string;
  enable_cover_letter: boolean;
  enable_outreach_message: boolean;
  ui_language: string;
  content_language: string;
  default_prompt_id: string;
  created_at: string;
}

interface AuthContextValue {
  user: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function storeTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export async function tryRefreshTokens(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    storeTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    router.push('/auth/login');
  }, [router]);

  const fetchCurrentUser = useCallback(
    async (token: string): Promise<UserProfile | null> => {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.status === 401) {
        const newToken = await tryRefreshTokens();
        if (!newToken) return null;

        const retryRes = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${newToken}` },
        });
        if (!retryRes.ok) return null;
        return retryRes.json();
      }

      if (!res.ok) return null;
      return res.json();
    },
    []
  );

  const refreshUser = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      return;
    }
    const profile = await fetchCurrentUser(token);
    if (profile) {
      setUser(profile);
    } else {
      logout();
    }
  }, [fetchCurrentUser, logout]);

  // On mount: check existing token and load user
  useEffect(() => {
    const init = async () => {
      const token = getAccessToken();
      if (!token) {
        setIsLoading(false);
        return;
      }
      const profile = await fetchCurrentUser(token);
      if (profile) {
        setUser(profile);
      } else {
        clearTokens();
      }
      setIsLoading(false);
    };
    init();
  }, [fetchCurrentUser]);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Login failed');
      }

      const data = await res.json();
      storeTokens(data.access_token, data.refresh_token);

      const profile = await fetchCurrentUser(data.access_token);
      if (profile) {
        setUser(profile);
      }
    },
    [fetchCurrentUser]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
