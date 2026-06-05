// src/pages/RegisterPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { getApiBase } from '../config';
import { validateEmail, validatePassword, validatePasswordMatch } from '../utils/validation';

const FRIENDLY_ERRORS = {
  "invalid_email": "Hmm, that email doesn't look right 🤔",
  "email_taken": "This email is already registered! Login instead?",
  "weak_password": "Password needs to be stronger 💪",
  "server_error": "Something went wrong. Please try again."
};

export default function RegisterPage() {
  const navigate = useNavigate();

  // Form fields
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [mt5Login, setMt5Login] = useState('');
  const [mt5Password, setMt5Password] = useState('');
  const [mt5Server, setMt5Server] = useState('MetaQuotes-Demo');

  // Real-time validation states
  const [emailValid, setEmailValid] = useState(null);
  const [emailError, setEmailError] = useState(null);
  const [emailChecking, setEmailChecking] = useState(false);
  const [emailTaken, setEmailTaken] = useState(false);
  
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Email validation with debounce (500ms)
  useEffect(() => {
    if (!email) {
      setEmailValid(null);
      setEmailError(null);
      setEmailTaken(false);
      return;
    }

    const valResult = validateEmail(email);
    if (!valResult.valid) {
      setEmailValid(false);
      setEmailError(valResult.error);
      setEmailTaken(false);
      return;
    }

    setEmailError(null);
    setEmailValid(null); // Neutral state while debouncing/fetching

    const timer = setTimeout(async () => {
      setEmailChecking(true);
      try {
        const base = getApiBase();
        const res = await fetch(`${base}/api/auth/check-email?email=${encodeURIComponent(email)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.available) {
            setEmailValid(true);
            setEmailTaken(false);
            setEmailError(null);
          } else {
            setEmailValid(false);
            setEmailTaken(data.reason === 'already_registered');
            setEmailError(
              data.reason === 'already_registered' 
                ? 'Email already registered. Login instead?' 
                : 'Invalid email domain extension'
            );
          }
        }
      } catch (err) {
        console.error("Email checking failed", err);
      } finally {
        setEmailChecking(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [email]);

  // Password strength validation metrics
  const pwdCheck = validatePassword(password);
  const pwdStrength = pwdCheck.strength;
  
  const check8Chars = password.length >= 8;
  const checkUpper = /[A-Z]/.test(password);
  const checkNumber = /[0-9]/.test(password);
  const checkSpecial = /[!@#$%^&*]/.test(password);

  // Confirm password matches validation
  const matchResult = validatePasswordMatch(password, confirmPassword);
  const passwordsMatch = confirmPassword ? matchResult.valid : null;

  // Final register button validation
  const isFormValid = 
    emailValid && 
    !emailTaken && 
    (pwdStrength === 'Strong' || pwdStrength === 'Medium') && 
    passwordsMatch && 
    displayName.trim() !== '' && 
    mt5Login !== '' && 
    mt5Password !== '' && 
    mt5Server !== '';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isFormValid) return;

    setError('');
    setLoading(true);

    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName,
          mt5_login: parseInt(mt5Login, 10),
          mt5_password: mt5Password,
          mt5_server: mt5Server
        })
      });

      const data = await res.json();

      if (!res.ok) {
        const errMsg = data.detail || 'Registration failed';
        throw new Error(FRIENDLY_ERRORS[errMsg] || errMsg);
      }

      // Redirect to login page on success
      navigate('/login');
    } catch (err) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card" style={{ maxWidth: '500px' }}>
        <h1 className="auth-title">Create <span>Account</span></h1>
        <p className="auth-subtitle">Register to set up your personal trading terminal</p>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input 
              type="text" 
              className="form-input" 
              placeholder="Abu Sahil"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email Address</label>
            <div className="input-feedback-wrap">
              <input 
                type="email" 
                className="form-input form-input-feedback" 
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              {email && !emailChecking && emailValid === true && (
                <span className="input-feedback-icon valid">✓</span>
              )}
              {email && !emailChecking && emailValid === false && (
                <span className="input-feedback-icon invalid">✗</span>
              )}
              {emailChecking && (
                <span className="input-feedback-icon valid spin">⏳</span>
              )}
            </div>
            {emailError && (
              <div className="form-field-error">
                {emailTaken ? (
                  <>
                    Email already registered. <Link to="/login" className="auth-link">Login instead?</Link>
                  </>
                ) : emailError}
              </div>
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Password</label>
              <div className="input-feedback-wrap">
                <input 
                  type={showPassword ? "text" : "password"} 
                  className="form-input form-input-feedback" 
                  placeholder="Min 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <span 
                  className="password-toggle-eye" 
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? "👁️" : "👁️‍🗨️"}
                </span>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Confirm Password</label>
              <div className="input-feedback-wrap">
                <input 
                  type={showConfirmPassword ? "text" : "password"} 
                  className="form-input form-input-feedback" 
                  placeholder="Repeat password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
                <span 
                  className="password-toggle-eye" 
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                >
                  {showConfirmPassword ? "👁️" : "👁️‍🗨️"}
                </span>
              </div>
            </div>
          </div>

          {/* ─── COMPONENT: Password Strength Bar & Checklist ─── */}
          {password && (
            <div className={`password-strength-container strength-${pwdStrength}`}>
              <div className="password-strength-text">
                Password Strength: <span style={{ 
                  fontWeight: 'bold', 
                  color: pwdStrength === 'Strong' ? 'var(--green)' : pwdStrength === 'Medium' ? 'var(--yellow)' : 'var(--red)'
                }}>{pwdStrength}</span>
              </div>
              <div className="password-strength-bar">
                <div className="password-strength-segment"></div>
                <div className="password-strength-segment"></div>
                <div className="password-strength-segment"></div>
                <div className="password-strength-segment"></div>
                <div className="password-strength-segment"></div>
              </div>
              
              <div className="password-checklist">
                <div className={`checklist-item ${check8Chars ? 'met' : ''}`}>
                  <span className="checklist-item-icon">{check8Chars ? '✓' : '✗'}</span> 8+ Characters
                </div>
                <div className={`checklist-item ${checkUpper ? 'met' : ''}`}>
                  <span className="checklist-item-icon">{checkUpper ? '✓' : '✗'}</span> 1 Uppercase Letter
                </div>
                <div className={`checklist-item ${checkNumber ? 'met' : ''}`}>
                  <span className="checklist-item-icon">{checkNumber ? '✓' : '✗'}</span> 1 Number
                </div>
                <div className={`checklist-item ${checkSpecial ? 'met' : ''}`}>
                  <span className="checklist-item-icon">{checkSpecial ? '✓' : '✗'}</span> 1 Special Character
                </div>
              </div>
            </div>
          )}

          {/* Confirm match feedback indicator */}
          {confirmPassword && (
            <div 
              className={`checklist-item ${passwordsMatch ? 'met' : ''}`}
              style={{ marginTop: 6, color: passwordsMatch ? 'var(--green)' : 'var(--red)' }}
            >
              <span className="checklist-item-icon">{passwordsMatch ? '✓' : '✗'}</span>
              {passwordsMatch ? 'Passwords match' : 'Passwords do not match'}
            </div>
          )}

          <div style={{ margin: '8px 0', borderBottom: '1px solid var(--border)' }} />
          <p className="form-label" style={{ color: 'var(--accent)', marginBottom: '8px' }}>MT5 Terminal Credentials</p>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">MT5 Login ID</label>
              <input 
                type="number" 
                className="form-input" 
                placeholder="5051162456"
                value={mt5Login}
                onChange={(e) => setMt5Login(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">MT5 Password</label>
              <input 
                type="password" 
                className="form-input" 
                placeholder="Password"
                value={mt5Password}
                onChange={(e) => setMt5Password(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">MT5 Server Name</label>
            <input 
              type="text" 
              className="form-input" 
              placeholder="MetaQuotes-Demo"
              value={mt5Server}
              onChange={(e) => setMt5Server(e.target.value)}
              required
            />
          </div>

          <button 
            type="submit" 
            className="auth-btn" 
            disabled={!isFormValid || loading}
            style={{ 
              backgroundColor: isFormValid ? 'var(--accent)' : 'var(--border)',
              cursor: isFormValid ? 'pointer' : 'not-allowed',
              color: isFormValid ? '#ffffff' : 'var(--text-3)'
            }}
          >
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login" className="auth-link">Log in here</Link>
        </div>
      </div>
    </div>
  );
}
