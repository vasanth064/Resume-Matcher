'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ResumePreviewProvider } from '@/components/common/resume_previewer_context';
import { StatusCacheProvider } from '@/lib/context/status-cache';
import { LanguageProvider } from '@/lib/context/language-context';
import { LocalizedErrorBoundary } from '@/components/common/error-boundary';
import { useAuth } from '@/lib/context/auth-context';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F0F0E8]">
        <p className="font-mono text-xs text-black/50 uppercase tracking-widest">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return <>{children}</>;
}

export default function DefaultLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <StatusCacheProvider>
        <LanguageProvider>
          <ResumePreviewProvider>
            <LocalizedErrorBoundary>
              <main className="min-h-screen flex flex-col">{children}</main>
            </LocalizedErrorBoundary>
          </ResumePreviewProvider>
        </LanguageProvider>
      </StatusCacheProvider>
    </AuthGuard>
  );
}
