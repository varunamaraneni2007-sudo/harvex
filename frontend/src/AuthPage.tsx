import React, { useState } from 'react';
import { supabase } from './lib/supabaseClient';
import {
  validateRegistration,
  validateLogin,
  categoriseAuthError,
} from './lib/authValidation';

type AuthMode = 'login' | 'register';

interface AuthPageProps {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
}

export default function AuthPage({ mode, onModeChange }: AuthPageProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const inputCls = (field: string) =>
    `w-full px-4 py-3 rounded-xl border text-sm outline-none transition bg-white placeholder:text-gray-300 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${
      fieldErrors[field] ? 'border-red-400' : 'border-gray-200'
    }`;

  const handleRegister = async () => {
    const { valid, errors } = validateRegistration(name, email, password);
    if (!valid) { setFieldErrors(errors); return; }
    setFieldErrors({});
    setGlobalError(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: { data: { full_name: name.trim() } },
      });
      if (error) {
        setGlobalError(categoriseAuthError(error.message));
      } else {
        setSuccessMessage(
          'Account created! Check your email for a confirmation link, then log in.',
        );
      }
    } catch {
      setGlobalError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    const { valid, errors } = validateLogin(email, password);
    if (!valid) { setFieldErrors(errors); return; }
    setFieldErrors({});
    setGlobalError(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) {
        setGlobalError(categoriseAuthError(error.message));
      }
      // On success supabase fires onAuthStateChange → parent updates user state
    } catch {
      setGlobalError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'register') handleRegister();
    else handleLogin();
  };

  const switchMode = (next: AuthMode) => {
    setName(''); setEmail(''); setPassword('');
    setFieldErrors({}); setGlobalError(null); setSuccessMessage(null);
    onModeChange(next);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50/60 via-white to-white flex flex-col items-center justify-center px-4 py-12">
      {/* Brand */}
      <div className="flex items-center gap-2 mb-8">
        <span className="text-3xl">🌱</span>
        <span className="text-2xl font-extrabold text-green-700 tracking-tight">Farm2Value</span>
      </div>

      <div className="w-full max-w-sm bg-white rounded-2xl border border-gray-100 shadow-lg px-8 py-8">
        <h2 className="text-xl font-bold text-gray-900 mb-1">
          {mode === 'register' ? 'Create your account' : 'Sign in to Farm2Value'}
        </h2>
        <p className="text-sm text-gray-500 mb-6">
          {mode === 'register'
            ? 'Join Harvex as a farmer or buyer — choose your role after sign-up.'
            : 'Welcome back! Enter your credentials to continue.'}
        </p>

        {/* Success */}
        {successMessage && (
          <div className="bg-green-50 border border-green-200 text-green-800 rounded-xl px-4 py-3 text-sm mb-4">
            {successMessage}
          </div>
        )}

        {/* Global error */}
        {globalError && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm mb-4">
            {globalError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Full name
              </label>
              <input
                type="text"
                autoComplete="name"
                placeholder="Ravi Kumar"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputCls('name')}
                disabled={loading}
              />
              {fieldErrors.name && (
                <p className="text-red-500 text-xs mt-1">{fieldErrors.name}</p>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email address
            </label>
            <input
              type="email"
              autoComplete={mode === 'register' ? 'email' : 'username'}
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls('email')}
              disabled={loading}
            />
            {fieldErrors.email && (
              <p className="text-red-500 text-xs mt-1">{fieldErrors.email}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputCls('password')}
              disabled={loading}
            />
            {fieldErrors.password && (
              <p className="text-red-500 text-xs mt-1">{fieldErrors.password}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white text-sm font-semibold rounded-xl shadow transition active:scale-[0.98] flex items-center justify-center gap-2 mt-2"
          >
            {loading ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                {mode === 'register' ? 'Creating account…' : 'Signing in…'}
              </>
            ) : (
              mode === 'register' ? 'Create account' : 'Sign in'
            )}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-500">
          {mode === 'register' ? (
            <>
              Already have an account?{' '}
              <button
                onClick={() => switchMode('login')}
                className="text-green-700 font-semibold hover:underline"
              >
                Sign in
              </button>
            </>
          ) : (
            <>
              Don&apos;t have an account?{' '}
              <button
                onClick={() => switchMode('register')}
                className="text-green-700 font-semibold hover:underline"
              >
                Create one
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
