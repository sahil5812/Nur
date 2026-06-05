// src/pages/AuthCallback.jsx
import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { saveAccount } from '../utils/auth';

const errorMessages = {
  'google_not_configured': 'Google login is not configured yet.',
  'google_token_failed': 'Google login failed. Please try again.',
  'google_error': 'Google sign-in error. Please try again.',
  'google_no_email': 'Could not get email from Google. Try again.',
  'google_timeout': 'Google took too long. Check your internet.',
  'email_uses_password': 'This email uses password login. Please sign in with your password.',
  'server_error': 'Something went wrong. Please try again.'
};

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get('token');
    const email = searchParams.get('email');
    const name = searchParams.get('name');
    const mt5Login = searchParams.get('mt5_login');
    const avatarUrl = searchParams.get('avatar_url');
    const authProvider = searchParams.get('auth_provider');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      const message = errorMessages[errorParam] || 'Login failed. Please try again.';
      navigate(`/login?error=${encodeURIComponent(message)}`);
      return;
    }

    if (token && email) {
      // Save Google OAuth account details
      saveAccount({
        email: email,
        display_name: name || 'Google User',
        mt5_login: mt5Login ? parseInt(mt5Login, 10) : null,
        auth_provider: authProvider || 'google',
        avatar_url: avatarUrl || null
      }, token, true); // Google logins are remembered for 30 days by default

      // Redirect to dashboard homepage
      navigate('/');
    } else {
      // Missing parameters fallback
      navigate('/login?error=google_error');
    }
  }, [searchParams, navigate]);

  return (
    <div className="auth-container">
      <div className="spinner">
        <span className="spin">⏳</span>
        <span>Completing Google Sign-In... Please wait...</span>
      </div>
    </div>
  );
}
