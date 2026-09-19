export interface ValidationResult {
  valid: boolean;
  errors: Record<string, string>;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;

export function validateEmail(email: string): string | null {
  if (!email.trim()) return 'Email is required';
  if (!EMAIL_RE.test(email.trim())) return 'Enter a valid email address';
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password) return 'Password is required';
  if (password.length < MIN_PASSWORD_LENGTH)
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
  return null;
}

export function validateName(name: string): string | null {
  if (!name.trim()) return 'Full name is required';
  if (name.trim().length < 2) return 'Name must be at least 2 characters';
  return null;
}

export function validateRegistration(
  name: string,
  email: string,
  password: string,
): ValidationResult {
  const errors: Record<string, string> = {};
  const nameErr = validateName(name);
  if (nameErr) errors.name = nameErr;
  const emailErr = validateEmail(email);
  if (emailErr) errors.email = emailErr;
  const pwErr = validatePassword(password);
  if (pwErr) errors.password = pwErr;
  return { valid: Object.keys(errors).length === 0, errors };
}

export function validateLogin(email: string, password: string): ValidationResult {
  const errors: Record<string, string> = {};
  const emailErr = validateEmail(email);
  if (emailErr) errors.email = emailErr;
  if (!password) errors.password = 'Password is required';
  return { valid: Object.keys(errors).length === 0, errors };
}

export function categoriseAuthError(message: string): string {
  const m = (message || '').toLowerCase();
  if (m.includes('invalid login credentials') || m.includes('invalid_credentials'))
    return 'Invalid email or password. Please check your credentials and try again.';
  if (m.includes('email not confirmed') || m.includes('email_not_confirmed'))
    return 'Please verify your email address before logging in. Check your inbox for a confirmation link.';
  if (m.includes('user already registered') || m.includes('already registered'))
    return 'An account with this email already exists. Please log in instead.';
  if (m.includes('network') || m.includes('fetch') || m.includes('failed to fetch'))
    return 'Network error. Please check your connection and try again.';
  if (m.includes('rate limit') || m.includes('too many'))
    return 'Too many attempts. Please wait a moment and try again.';
  return message;
}
