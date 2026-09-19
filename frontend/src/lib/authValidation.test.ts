import { describe, it, expect } from 'vitest';
import {
  validateEmail,
  validatePassword,
  validateName,
  validateRegistration,
  validateLogin,
  categoriseAuthError,
} from './authValidation';

// ── validateEmail ─────────────────────────────────────────────────────────────

describe('validateEmail', () => {
  it('accepts a valid email', () => {
    expect(validateEmail('user@example.com')).toBeNull();
  });

  it('accepts email with subdomain', () => {
    expect(validateEmail('user@mail.example.co.in')).toBeNull();
  });

  it('rejects empty string', () => {
    expect(validateEmail('')).toBeTruthy();
  });

  it('rejects whitespace only', () => {
    expect(validateEmail('   ')).toBeTruthy();
  });

  it('rejects missing @', () => {
    expect(validateEmail('userexample.com')).toBeTruthy();
  });

  it('rejects missing domain', () => {
    expect(validateEmail('user@')).toBeTruthy();
  });

  it('rejects missing TLD', () => {
    expect(validateEmail('user@example')).toBeTruthy();
  });

  it('returns useful error message', () => {
    expect(validateEmail('')).toMatch(/required/i);
    expect(validateEmail('bad')).toMatch(/valid email/i);
  });
});

// ── validatePassword ──────────────────────────────────────────────────────────

describe('validatePassword', () => {
  it('accepts password of 8 characters', () => {
    expect(validatePassword('12345678')).toBeNull();
  });

  it('accepts longer password', () => {
    expect(validatePassword('SuperSecure@99!')).toBeNull();
  });

  it('rejects empty string', () => {
    expect(validatePassword('')).toBeTruthy();
  });

  it('rejects password shorter than 8 characters', () => {
    expect(validatePassword('short')).toBeTruthy();
    expect(validatePassword('1234567')).toBeTruthy();
  });

  it('error mentions minimum length', () => {
    expect(validatePassword('abc')).toMatch(/8/);
  });
});

// ── validateName ─────────────────────────────────────────────────────────────

describe('validateName', () => {
  it('accepts normal name', () => {
    expect(validateName('Ravi Kumar')).toBeNull();
  });

  it('accepts single short-but-valid name', () => {
    expect(validateName('Jo')).toBeNull();
  });

  it('rejects empty string', () => {
    expect(validateName('')).toBeTruthy();
  });

  it('rejects single character', () => {
    expect(validateName('R')).toBeTruthy();
  });

  it('rejects whitespace only', () => {
    expect(validateName('   ')).toBeTruthy();
  });
});

// ── validateRegistration ──────────────────────────────────────────────────────

describe('validateRegistration', () => {
  it('passes with valid inputs', () => {
    const result = validateRegistration('Ravi Kumar', 'ravi@example.com', 'password99');
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
  });

  it('fails with all empty fields', () => {
    const result = validateRegistration('', '', '');
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveProperty('name');
    expect(result.errors).toHaveProperty('email');
    expect(result.errors).toHaveProperty('password');
  });

  it('fails with bad email only', () => {
    const result = validateRegistration('Ravi', 'not-an-email', 'password99');
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveProperty('email');
    expect(result.errors).not.toHaveProperty('name');
    expect(result.errors).not.toHaveProperty('password');
  });

  it('fails with short password only', () => {
    const result = validateRegistration('Ravi', 'ravi@example.com', 'short');
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveProperty('password');
    expect(result.errors).not.toHaveProperty('name');
    expect(result.errors).not.toHaveProperty('email');
  });
});

// ── validateLogin ─────────────────────────────────────────────────────────────

describe('validateLogin', () => {
  it('passes with valid inputs', () => {
    const result = validateLogin('user@example.com', 'anypassword');
    expect(result.valid).toBe(true);
  });

  it('fails with empty email', () => {
    const result = validateLogin('', 'password99');
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveProperty('email');
  });

  it('fails with empty password', () => {
    const result = validateLogin('user@example.com', '');
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveProperty('password');
  });

  it('fails with both empty', () => {
    const result = validateLogin('', '');
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveProperty('email');
    expect(result.errors).toHaveProperty('password');
  });

  it('login does not require minimum password length', () => {
    // Existing users may have set passwords before policy change
    const result = validateLogin('user@example.com', 'short');
    expect(result.valid).toBe(true);
  });
});

// ── categoriseAuthError ───────────────────────────────────────────────────────

describe('categoriseAuthError', () => {
  it('handles invalid credentials', () => {
    const msg = categoriseAuthError('Invalid login credentials');
    expect(msg).toMatch(/Invalid email or password/i);
  });

  it('handles invalid_credentials code', () => {
    const msg = categoriseAuthError('invalid_credentials');
    expect(msg).toMatch(/Invalid email or password/i);
  });

  it('handles unconfirmed email', () => {
    const msg = categoriseAuthError('Email not confirmed');
    expect(msg).toMatch(/verify your email/i);
  });

  it('handles already registered', () => {
    const msg = categoriseAuthError('User already registered');
    expect(msg).toMatch(/already exists/i);
  });

  it('handles network error', () => {
    const msg = categoriseAuthError('Failed to fetch');
    expect(msg).toMatch(/network error/i);
  });

  it('handles rate limit', () => {
    const msg = categoriseAuthError('rate limit exceeded');
    expect(msg).toMatch(/Too many attempts/i);
  });

  it('returns original message for unknown errors', () => {
    const original = 'Some unexpected error from Supabase';
    expect(categoriseAuthError(original)).toBe(original);
  });

  it('handles empty string without throwing', () => {
    expect(() => categoriseAuthError('')).not.toThrow();
  });
});
