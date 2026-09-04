/**
 * src/context/AuthContext.jsx — Authentication State Provider
 * =============================================================
 * Provides login state, token management, and user identity across all React components
 * without needing prop-drilling.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('access_token') || null);
  const [loading, setLoading] = useState(true);

  // Rehydrate auth state on app start if token exists in localStorage
  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          const profile = await authApi.getMe();
          setUser(profile);
        } catch (err) {
          console.error("Failed to load user profile:", err);
          // Token invalid or expired
          logout();
        }
      }
      setLoading(false);
    };

    initAuth();
  }, [token]);

  const login = async (email, password) => {
    const data = await authApi.login(email, password);
    const accessToken = data.access_token;

    localStorage.setItem('access_token', accessToken);
    setToken(accessToken);

    // Immediately fetch profile for logged-in user
    const profile = await authApi.getMe();
    setUser(profile);
    return profile;
  };

  const signup = async (userData) => {
    const newUser = await authApi.signup(userData);
    return newUser;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
