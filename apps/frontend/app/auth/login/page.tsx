'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/context/auth-context';

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await login(email, password);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md px-4">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-bold text-black tracking-tight">Resume Matcher</h1>
        <p className="font-mono text-xs text-black/50 mt-1 uppercase tracking-widest">
          Sign in to your account
        </p>
      </div>

      {/* Card */}
      <div className="border border-black bg-white shadow-[4px_4px_0px_0px_#000]">
        <form onSubmit={handleSubmit} className="p-8 space-y-6">
          {error && (
            <div className="border border-[#DC2626] bg-[#DC2626]/5 px-4 py-3">
              <p className="font-mono text-xs text-[#DC2626]">{error}</p>
            </div>
          )}

          <div className="space-y-1">
            <label htmlFor="email" className="font-mono text-xs uppercase tracking-widest text-black">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
              placeholder="you@example.com"
            />
          </div>

          <div className="space-y-1">
            <label
              htmlFor="password"
              className="font-mono text-xs uppercase tracking-widest text-black"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full border border-black bg-black py-2.5 font-mono text-sm uppercase tracking-widest text-white shadow-[2px_2px_0px_0px_#666] hover:bg-black/90 active:shadow-none active:translate-x-[2px] active:translate-y-[2px] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isLoading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="border-t border-black px-8 py-4">
          <p className="font-mono text-xs text-black/60 text-center">
            No account?{' '}
            <Link href="/auth/signup" className="text-[#1D4ED8] underline hover:no-underline">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
