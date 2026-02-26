'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { API_BASE } from '@/lib/api/client';

const LLM_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'ollama', label: 'Ollama (local)' },
];

const DEFAULT_MODELS: Record<string, string> = {
  openai: 'gpt-4o-mini',
  anthropic: 'claude-haiku-4-5-20251001',
  gemini: 'gemini/gemini-2.0-flash-lite',
  openrouter: 'openrouter/auto',
  deepseek: 'deepseek-chat',
  ollama: 'llama3.2',
};

type Step = 1 | 2 | 3;

export default function SignupPage() {
  const router = useRouter();

  const [step, setStep] = useState<Step>(1);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Step 1: Account
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Step 2: LLM
  const [llmProvider, setLlmProvider] = useState('openai');
  const [llmModel, setLlmModel] = useState(DEFAULT_MODELS['openai']);
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmApiBase, setLlmApiBase] = useState('');

  // Step 3: Telegram (optional)
  const [telegramBotToken, setTelegramBotToken] = useState('');

  function validateStep1(): string | null {
    if (!email || !password) return 'Email and password are required';
    if (password.length < 8) return 'Password must be at least 8 characters';
    if (password !== confirmPassword) return 'Passwords do not match';
    return null;
  }

  function handleProviderChange(provider: string) {
    setLlmProvider(provider);
    setLlmModel(DEFAULT_MODELS[provider] ?? '');
  }

  function validateStep2(): string | null {
    if (!llmProvider) return 'Please select an LLM provider';
    return null;
  }

  function handleStep1(e: FormEvent) {
    e.preventDefault();
    const err = validateStep1();
    if (err) { setError(err); return; }
    setError('');
    setStep(2);
  }

  function handleStep2(e: FormEvent) {
    e.preventDefault();
    const err = validateStep2();
    if (err) { setError(err); return; }
    setError('');
    setStep(3);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          llm_provider: llmProvider,
          llm_model: llmModel,
          llm_api_key: llmApiKey,
          llm_api_base: llmApiBase || null,
          telegram_bot_token: telegramBotToken,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Signup failed');
      }

      const data = await res.json();
      localStorage.setItem('resume_matcher_access_token', data.access_token);
      localStorage.setItem('resume_matcher_refresh_token', data.refresh_token);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setIsLoading(false);
    }
  }

  const stepLabels: Record<Step, string> = {
    1: 'Account',
    2: 'LLM Setup',
    3: 'Telegram',
  };

  return (
    <div className="w-full max-w-md px-4">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl font-bold text-black tracking-tight">Resume Matcher</h1>
        <p className="font-mono text-xs text-black/50 mt-1 uppercase tracking-widest">
          Create your account
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex mb-6">
        {([1, 2, 3] as Step[]).map((s) => (
          <div key={s} className="flex-1">
            <div
              className={`h-1 ${s <= step ? 'bg-black' : 'bg-black/20'} ${s < 3 ? 'mr-1' : ''}`}
            />
            <p
              className={`font-mono text-xs mt-1 uppercase tracking-widest ${s === step ? 'text-black' : 'text-black/40'}`}
            >
              {stepLabels[s]}
            </p>
          </div>
        ))}
      </div>

      {/* Card */}
      <div className="border border-black bg-white shadow-[4px_4px_0px_0px_#000]">
        {/* Step 1: Account */}
        {step === 1 && (
          <form onSubmit={handleStep1} className="p-8 space-y-6">
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
              <label htmlFor="password" className="font-mono text-xs uppercase tracking-widest text-black">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="Min. 8 characters"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="confirm" className="font-mono text-xs uppercase tracking-widest text-black">
                Confirm Password
              </label>
              <input
                id="confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              className="w-full border border-black bg-black py-2.5 font-mono text-sm uppercase tracking-widest text-white shadow-[2px_2px_0px_0px_#666] hover:bg-black/90 active:shadow-none active:translate-x-[2px] active:translate-y-[2px] transition-all"
            >
              Continue
            </button>
          </form>
        )}

        {/* Step 2: LLM Setup */}
        {step === 2 && (
          <form onSubmit={handleStep2} className="p-8 space-y-6">
            {error && (
              <div className="border border-[#DC2626] bg-[#DC2626]/5 px-4 py-3">
                <p className="font-mono text-xs text-[#DC2626]">{error}</p>
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="llm-provider" className="font-mono text-xs uppercase tracking-widest text-black">
                Provider
              </label>
              <select
                id="llm-provider"
                value={llmProvider}
                onChange={(e) => handleProviderChange(e.target.value)}
                required
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black focus:outline-none focus:ring-2 focus:ring-black"
              >
                {LLM_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label htmlFor="llm-model" className="font-mono text-xs uppercase tracking-widest text-black">
                Model <span className="text-black/40">(optional)</span>
              </label>
              <input
                id="llm-model"
                type="text"
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
                placeholder={DEFAULT_MODELS[llmProvider] ?? 'e.g. gpt-4o-mini'}
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="llm-api-key" className="font-mono text-xs uppercase tracking-widest text-black">
                API Key <span className="text-black/40">(optional)</span>
              </label>
              <input
                id="llm-api-key"
                type="password"
                value={llmApiKey}
                onChange={(e) => setLlmApiKey(e.target.value)}
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="sk-..."
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="llm-api-base" className="font-mono text-xs uppercase tracking-widest text-black">
                API Base URL <span className="text-black/40">(optional)</span>
              </label>
              <input
                id="llm-api-base"
                type="text"
                value={llmApiBase}
                onChange={(e) => setLlmApiBase(e.target.value)}
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="https://api.openai.com/v1"
              />
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="flex-1 border border-black bg-white py-2.5 font-mono text-sm uppercase tracking-widest text-black hover:bg-black/5 active:bg-black/10 transition-all"
              >
                Back
              </button>
              <button
                type="submit"
                className="flex-1 border border-black bg-black py-2.5 font-mono text-sm uppercase tracking-widest text-white shadow-[2px_2px_0px_0px_#666] hover:bg-black/90 active:shadow-none active:translate-x-[2px] active:translate-y-[2px] transition-all"
              >
                Continue
              </button>
            </div>
          </form>
        )}

        {/* Step 3: Telegram (optional) */}
        {step === 3 && (
          <form onSubmit={handleSubmit} className="p-8 space-y-6">
            <p className="font-mono text-xs text-black/50 uppercase tracking-widest">
              Optional — skip if you don&apos;t use Telegram
            </p>

            {error && (
              <div className="border border-[#DC2626] bg-[#DC2626]/5 px-4 py-3">
                <p className="font-mono text-xs text-[#DC2626]">{error}</p>
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="tg-token" className="font-mono text-xs uppercase tracking-widest text-black">
                Bot Token
              </label>
              <input
                id="tg-token"
                type="password"
                value={telegramBotToken}
                onChange={(e) => setTelegramBotToken(e.target.value)}
                className="w-full border border-black bg-white px-3 py-2 font-mono text-sm text-black placeholder-black/30 focus:outline-none focus:ring-2 focus:ring-black"
                placeholder="1234567890:AAF..."
              />
              <p className="font-mono text-xs text-black/40 pt-1">
                You can find your webhook URL in Settings after signup.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="flex-1 border border-black bg-white py-2.5 font-mono text-sm uppercase tracking-widest text-black hover:bg-black/5 active:bg-black/10 transition-all"
              >
                Back
              </button>
              <button
                type="button"
                disabled={isLoading}
                onClick={(e) => { e.preventDefault(); handleSubmit(e as unknown as FormEvent); }}
                className="flex-1 border border-black bg-white py-2.5 font-mono text-sm uppercase tracking-widest text-black hover:bg-black/5 transition-all disabled:opacity-50"
              >
                Skip
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="flex-1 border border-black bg-black py-2.5 font-mono text-sm uppercase tracking-widest text-white shadow-[2px_2px_0px_0px_#666] hover:bg-black/90 active:shadow-none active:translate-x-[2px] active:translate-y-[2px] disabled:opacity-50 transition-all"
              >
                {isLoading ? 'Creating...' : 'Create Account'}
              </button>
            </div>
          </form>
        )}

        <div className="border-t border-black px-8 py-4">
          <p className="font-mono text-xs text-black/60 text-center">
            Already have an account?{' '}
            <Link href="/auth/login" className="text-[#1D4ED8] underline hover:no-underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
