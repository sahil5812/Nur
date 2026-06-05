// src/hooks/useSaaSData.js
// Custom hook — skips requests if no token, delegates 401 to AuthContext
import { useState, useEffect, useCallback } from 'react';
import { getApiBase } from '../config';
import { useAuth } from '../context/AuthContext';

export function useSaaSData(token) {
  const [users, setUsers] = useState([]);
  const [activeUser, setActiveUser] = useState(null);
  const [activeUserId, setActiveUserId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { kickToLogin } = useAuth();

  const fetchUsers = useCallback(async () => {
    // Don't fire requests without a token
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/saas/profiles`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 401) {
        kickToLogin(token);
        return;
      }
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();
      setUsers(data);
      setError(null);

      if (data && data.length > 0) {
        const existingActive = data.find(u => u.user_id === activeUserId);
        if (existingActive) {
          setActiveUser(existingActive);
        } else {
          setActiveUser(data[0]);
          setActiveUserId(data[0].user_id);
        }
      } else {
        setActiveUser(null);
        setActiveUserId(null);
      }
    } catch (err) {
      console.error("Error fetching SaaS profiles:", err);
      setError(err.message || "Failed to fetch SaaS profiles");
    } finally {
      setLoading(false);
    }
  }, [token, activeUserId, kickToLogin]);

  useEffect(() => {
    fetchUsers();
    const id = setInterval(fetchUsers, 10000);
    return () => clearInterval(id);
  }, [fetchUsers]);

  const switchUser = (userId) => {
    const targetUser = users.find(u => u.user_id === userId);
    if (targetUser) {
      setActiveUserId(userId);
      setActiveUser(targetUser);
    } else {
      console.warn(`User ID ${userId} not found in profile list`);
    }
  };

  return {
    users,
    activeUser,
    activeUserId,
    switchUser,
    loading,
    error,
    refresh: fetchUsers
  };
}
