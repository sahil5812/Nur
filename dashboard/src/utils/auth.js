// src/utils/auth.js
import { getApiBase } from '../config';

const AVATAR_COLORS = [
  '#6366f1', // indigo
  '#8b5cf6', // violet  
  '#ec4899', // pink
  '#f59e0b', // amber
  '#10b981', // emerald
  '#3b82f6', // blue
  '#ef4444', // red
  '#14b8a6', // teal
];

const STORAGE_KEY = "nur_accounts";

const loadStorage = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { active_email: null, accounts: [] };
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.accounts)) {
      return { active_email: null, accounts: [] };
    }
    return parsed;
  } catch (e) {
    return { active_email: null, accounts: [] };
  }
};

const saveStorage = (store) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
};

export const isTokenValid = (account) => {
  if (!account || !account.token || !account.token_expiry) return false;
  return new Date(account.token_expiry) > new Date();
};

export const saveAccount = (userData, token, rememberMe) => {
  const store = loadStorage();
  const email = userData.email.toLowerCase().trim();
  
  // Calculate expiry
  const duration = rememberMe ? 30 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
  const expiryDate = new Date(Date.now() + duration).toISOString();
  
  // Check if account already exists
  let account = store.accounts.find(acc => acc.email === email);
  
  if (account) {
    // Update existing
    account.token = token;
    account.token_expiry = expiryDate;
    account.display_name = userData.display_name;
    account.mt5_login = userData.mt5_login;
    account.last_active = new Date().toISOString();
    account.remember_me = rememberMe;
    account.auth_provider = userData.auth_provider || 'email';
    account.avatar_url = userData.avatar_url || null;
  } else {
    // Create new
    const randColor = AVATAR_COLORS[Math.floor(Math.random() * AVATAR_COLORS.length)];
    account = {
      email,
      display_name: userData.display_name,
      token,
      token_expiry: expiryDate,
      mt5_login: userData.mt5_login,
      avatar_color: randColor,
      last_active: new Date().toISOString(),
      remember_me: rememberMe,
      auth_provider: userData.auth_provider || 'email',
      avatar_url: userData.avatar_url || null
    };
    store.accounts.push(account);
  }
  
  store.active_email = email;
  
  // Max 10 accounts enforcement
  if (store.accounts.length > 10) {
    // Sort oldest last_active first
    store.accounts.sort((a, b) => new Date(a.last_active) - new Date(b.last_active));
    // Remove oldest
    store.accounts.shift();
  }
  
  saveStorage(store);
  
  // Sync active token to standard localStorage key for hooks/fallbacks
  localStorage.setItem('token', token);
  
  return account;
};

export const getSavedAccounts = () => {
  const store = loadStorage();
  // Filter out expired tokens
  const validAccounts = store.accounts.filter(acc => isTokenValid(acc));
  
  if (validAccounts.length !== store.accounts.length) {
    store.accounts = validAccounts;
    // Check if active_email is now invalid
    const activeValid = validAccounts.some(acc => acc.email === store.active_email);
    if (!activeValid) {
      store.active_email = validAccounts.length > 0 ? validAccounts[0].email : null;
    }
    saveStorage(store);
  }
  
  // Sort descending by last_active
  return [...validAccounts].sort((a, b) => new Date(b.last_active) - new Date(a.last_active));
};

export const getActiveAccount = () => {
  const store = loadStorage();
  if (!store.active_email) return null;
  const account = store.accounts.find(acc => acc.email === store.active_email);
  if (account && isTokenValid(account)) {
    return account;
  }
  return null;
};

export const switchAccount = (email) => {
  const store = loadStorage();
  const normalized = email.toLowerCase().trim();
  const account = store.accounts.find(acc => acc.email === normalized);
  if (account && isTokenValid(account)) {
    store.active_email = normalized;
    account.last_active = new Date().toISOString();
    saveStorage(store);
    // Sync active token to standard localStorage key
    localStorage.setItem('token', account.token);
    return account.token;
  }
  return null;
};

export const removeAccount = (email) => {
  const store = loadStorage();
  const normalized = email.toLowerCase().trim();
  store.accounts = store.accounts.filter(acc => acc.email !== normalized);
  
  if (store.active_email === normalized) {
    // Switch to first remaining
    if (store.accounts.length > 0) {
      store.active_email = store.accounts[0].email;
      // Sync new active token
      localStorage.setItem('token', store.accounts[0].token);
    } else {
      store.active_email = null;
      localStorage.removeItem('token');
    }
  }
  
  saveStorage(store);
  return getActiveAccount();
};

export const addNewAccount = () => {
  const store = loadStorage();
  store.active_email = null;
  saveStorage(store);
  // Clear the standard token key so PrivateRoute redirects to login
  localStorage.removeItem('token');
};

export const autoRefreshToken = async (account) => {
  if (!account || !account.token || !account.token_expiry) return null;
  
  const expiryTime = new Date(account.token_expiry).getTime();
  const timeLeft = expiryTime - Date.now();
  const threeDaysMs = 3 * 24 * 60 * 60 * 1000;
  
  // Refresh only if valid but expires in less than 3 days
  if (timeLeft > 0 && timeLeft < threeDaysMs) {
    try {
      const base = getApiBase();
      const response = await fetch(`${base}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${account.token}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.token) {
          const updated = saveAccount(
            {
              email: account.email,
              display_name: data.user.display_name,
              mt5_login: data.user.mt5_login,
              auth_provider: account.auth_provider,
              avatar_url: account.avatar_url
            },
            data.token,
            account.remember_me
          );
          return updated.token;
        }
      }
    } catch (err) {
      console.error("Token refresh failed:", err);
    }
  }
  return null;
};

export const invalidateTokenByValue = (tokenVal) => {
  if (!tokenVal) {
    localStorage.removeItem('token');
    return;
  }
  const store = loadStorage();
  const account = store.accounts.find(acc => acc.token === tokenVal);
  if (account) {
    account.token = null;
    account.token_expiry = null;
    account.remember_me = false;
  }
  if (store.active_email && account && account.email === store.active_email) {
    store.active_email = null;
  }
  saveStorage(store);
  localStorage.removeItem('token');
};
