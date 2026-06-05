// src/pages/LoginPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { saveAccount, getSavedAccounts, switchAccount, removeAccount, isTokenValid, getActiveAccount } from '../utils/auth';
import { getApiBase } from '../config';

const FRIENDLY_ERRORS = {
  "invalid_email": "Hmm, that email doesn't look right 🤔",
  "email_taken": "This email is already registered! Login instead?",
  "wrong_password": "Wrong password. Try again or reset it.",
  "account_not_found": "No account found with this email.",
  "weak_password": "Password needs to be stronger 💪",
  "google_only_login": "This email uses Google Sign-in. Click 'Continue with Google'.",
  "email_uses_password": "This email uses password login. Enter email & password.",
  "google_error": "Google sign-in failed. Try again.",
  "google_not_configured": "Google Sign-In is not configured yet. Please use email/password login, or ask your admin to set up Google OAuth credentials.",
  "server_error": "Something went wrong. Please try again."
};

export default function LoginPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // State variables
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true); // default ON
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Accounts state
  const [savedAccounts, setSavedAccounts] = useState([]);
  const [showForm, setShowForm] = useState(true);

  // Load saved accounts on mount
  useEffect(() => {
    // If user is already authenticated and not explicitly adding a new account, go to dashboard
    const isAddingAccount = searchParams.get('add_account') === 'true';
    const activeAccount = getActiveAccount();
    if (activeAccount && !isAddingAccount) {
      navigate('/', { replace: true });
      return;
    }

    const accounts = getSavedAccounts();
    setSavedAccounts(accounts);
    
    // Show form directly if adding new account or no saved accounts
    if (isAddingAccount || accounts.length === 0) {
      setShowForm(true);
    } else {
      setShowForm(false);
    }
    
    // Check for callback errors
    const errCode = searchParams.get('error');
    if (errCode && FRIENDLY_ERRORS[errCode]) {
      setError(FRIENDLY_ERRORS[errCode]);
      setShowForm(true);
    }
  }, [searchParams, navigate]);

  const handleOneTapResponse = async (response) => {
    try {
      setLoading(true);
      setError('');
      
      const base = getApiBase();
      const res = await fetch(`${base}/api/auth/google/onetap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: response.credential })
      });
      
      const data = await res.json();
      
      if (res.ok && data.token) {
        saveAccount({
          email: data.user.email,
          display_name: data.user.display_name,
          mt5_login: data.user.mt5_login,
          avatar_url: data.user.avatar_url,
          auth_provider: 'google'
        }, data.token, true);
        
        navigate('/');
      } else {
        const errMsg = data.detail || 'Google One Tap login failed. Please try again.';
        setError(FRIENDLY_ERRORS[errMsg] || errMsg);
      }
    } catch (e) {
      setError('Connection error. Is the API running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    if (!clientId || clientId.startsWith('your_')) return;

    // Expose callback globally so Google Identity Services HTML API can find it
    window.handleOneTapResponse = handleOneTapResponse;

    // Initialize Google One Tap
    if (window.google) {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: handleOneTapResponse,
        auto_select: true,        // Auto-select if only one account
        cancel_on_tap_outside: false,
        context: 'signin',
        itp_support: true
      });

      // Show the One Tap prompt
      window.google.accounts.id.prompt((notification) => {
        if (notification.isNotDisplayed()) {
          console.log('One Tap not displayed:', notification.getNotDisplayedReason());
        }
        if (notification.isDismissedMoment()) {
          console.log('One Tap dismissed:', notification.getDismissedReason());
        }
      });
    }

    // Cleanup on unmount
    return () => {
      delete window.handleOneTapResponse;
      if (window.google) {
        window.google.accounts.id.cancel();
      }
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, remember_me: rememberMe })
      });

      const data = await res.json();

      if (!res.ok) {
        const errMsg = data.detail || 'Invalid email or password';
        throw new Error(FRIENDLY_ERRORS[errMsg] || errMsg);
      }

      // Save account using account manager utility
      saveAccount({
        email: data.user.email,
        display_name: data.user.display_name,
        mt5_login: data.user.mt5_login,
        auth_provider: 'email',
        avatar_url: null
      }, data.token, rememberMe);

      // Redirect to main page
      navigate('/');
    } catch (err) {
      setError(err.message || 'Connection to authentication server failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSavedAccountClick = async (account) => {
    setError('');
    setLoading(true);
    
    try {
      const base = getApiBase();
      // Validate saved token with backend first
      const res = await fetch(`${base}/api/auth/validate`, {
        headers: {
          'Authorization': `Bearer ${account.token}`
        }
      });
      
      if (res.ok) {
        // Switch to this account
        switchAccount(account.email);
        navigate('/');
      } else {
        // Token has expired or been revoked
        setEmail(account.email);
        setShowForm(true);
        setError(`Session expired for ${account.display_name}. Please log in again.`);
      }
    } catch (err) {
      // Offline fallback: try frontend validation check
      if (isTokenValid(account)) {
        switchAccount(account.email);
        navigate('/');
      } else {
        setEmail(account.email);
        setShowForm(true);
        setError('Saved session has expired. Please enter your password.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveAccount = (e, emailToRemove) => {
    e.stopPropagation(); // prevent triggering card click
    const updated = removeAccount(emailToRemove);
    const accounts = getSavedAccounts();
    setSavedAccounts(accounts);
    if (accounts.length === 0) {
      setShowForm(true);
    }
  };

  const handleGoogleLogin = async () => {
    setError('');
    setLoading(true);
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/auth/google`);
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        // Show user-friendly message
        if (err.detail?.includes('not configured')) {
          setError(
            'Google login is not set up yet. ' +
            'Please use email/password login or contact admin.'
          );
        } else {
          setError('Google login failed. Please try again.');
        }
        setLoading(false);
        return;
      }
      
      const data = await res.json();
      if (data.auth_url) {
        // Redirect to Google OAuth page
        window.location.href = data.auth_url;
      } else {
        throw new Error('google_error');
      }
    } catch (e) {
      setError('Could not connect to server. Is the API running?');
      setLoading(false);
    }
  };

  // Get initials: "Abu Sahil" -> "AS"
  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="auth-container">
      <div 
        id="g_id_onload"
        data-client_id={import.meta.env.VITE_GOOGLE_CLIENT_ID}
        data-callback="handleOneTapResponse"
        data-auto_select="true"
        data-cancel_on_tap_outside="false"
      >
      </div>
      <div className="auth-card">
        <h1 className="auth-title">NUR <span>Trading Bot</span></h1>
        <p className="auth-subtitle">Log in to manage your automated trading engine</p>
        
        {error && <div className="auth-error">{error}</div>}

        {/* ─── COMPONENT: Saved Accounts Section ─── */}
        {!showForm && savedAccounts.length > 0 && (
          <div className="saved-accounts-container">
            <div className="saved-accounts-title">Saved Accounts</div>
            <div className="saved-accounts-list">
              {savedAccounts.map((account) => (
                <div 
                  key={account.email} 
                  className="saved-account-card"
                  onClick={() => handleSavedAccountClick(account)}
                >
                  <button 
                    className="saved-account-remove"
                    onClick={(e) => handleRemoveAccount(e, account.email)}
                    title="Remove Account"
                  >
                    ×
                  </button>
                  <div 
                    className="saved-account-avatar"
                    style={{ 
                      backgroundColor: account.avatar_color,
                      backgroundImage: account.avatar_url ? `url(${account.avatar_url})` : 'none'
                    }}
                  >
                    {!account.avatar_url && getInitials(account.display_name)}
                    <span className="saved-account-status active"></span>
                  </div>
                  <div className="saved-account-name">{account.display_name}</div>
                  <div className="saved-account-email">{account.email}</div>
                </div>
              ))}
              
              {/* Plus add account card */}
              <div 
                className="saved-account-add"
                onClick={() => setShowForm(true)}
              >
                <div className="saved-account-add-icon">+</div>
                <div className="saved-account-add-text">Add Account</div>
              </div>
            </div>
          </div>
        )}

        {showForm && (
          <>
            {/* Google Authentication Button */}
            <button 
              type="button" 
              className="google-btn" 
              onClick={handleGoogleLogin}
              disabled={loading}
            >
              <img 
                src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg" 
                alt="Google G Logo" 
                className="google-btn-icon" 
              />
              Continue with Google
            </button>

            <div className="auth-separator">or</div>

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input 
                  type="email" 
                  className="form-input" 
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <div className="input-feedback-wrap">
                  <input 
                    type={showPassword ? "text" : "password"} 
                    className="form-input" 
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    style={{ paddingRight: '36px' }}
                  />
                  <span 
                    className="password-toggle-eye" 
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? "👁️" : "👁️‍🗨️"}
                  </span>
                </div>
              </div>

              <label className="form-checkbox">
                <input 
                  type="checkbox" 
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                Keep me logged in
              </label>

              <button type="submit" className="auth-btn" disabled={loading}>
                {loading ? 'Logging in...' : 'Sign In'}
              </button>

              {savedAccounts.length > 0 && (
                <button 
                  type="button" 
                  className="auth-btn" 
                  style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-2)', marginTop: 0 }}
                  onClick={() => setShowForm(false)}
                >
                  Show Saved Accounts
                </button>
              )}
            </form>
          </>
        )}

        <div className="auth-footer">
          Don't have an account? <Link to="/register" className="auth-link">Create one here</Link>
        </div>
      </div>
    </div>
  );
}
