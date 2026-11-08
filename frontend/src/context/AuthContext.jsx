import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { authApi } from "@/services/api";

const AuthContext = createContext(null);

const ACCESS_TOKEN_KEY = "researchpilot_access_token";
const REFRESH_TOKEN_KEY = "researchpilot_refresh_token";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(() => localStorage.getItem(ACCESS_TOKEN_KEY));
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem(REFRESH_TOKEN_KEY));
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const saveTokens = useCallback((access, refresh, mustChange = false) => {
    if (access) {
      localStorage.setItem(ACCESS_TOKEN_KEY, access);
      setAccessToken(access);
    }
    if (refresh) {
      localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
      setRefreshToken(refresh);
    }
    setMustChangePassword(Boolean(mustChange));
  }, []);

  const clearTokens = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    setMustChangePassword(false);
  }, []);

  // Fetch current user details
  const fetchCurrentUser = useCallback(async () => {
    try {
      const userData = await authApi.getMe();
      setUser(userData);
      setMustChangePassword(Boolean(userData.must_change_password));
      return userData;
    } catch (err) {
      console.warn("Failed to retrieve current user session:", err);
      clearTokens();
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [clearTokens]);

  useEffect(() => {
    if (accessToken) {
      fetchCurrentUser();
    } else {
      setIsLoading(false);
    }
  }, [accessToken, fetchCurrentUser]);

  const login = async (email, password) => {
    const data = await authApi.login({ email, password });
    saveTokens(data.access_token, data.refresh_token, data.must_change_password);
    // After login, fetch user profile
    const profile = await authApi.getMe();
    setUser(profile);
    return { ...data, user: profile };
  };

  const register = async (email, password) => {
    const data = await authApi.register({ email, password });
    saveTokens(data.access_token, data.refresh_token, data.must_change_password);
    const profile = await authApi.getMe();
    setUser(profile);
    return { ...data, user: profile };
  };

  const changePassword = async (currentPassword, newPassword) => {
    const data = await authApi.changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    });
    saveTokens(data.access_token, data.refresh_token, false);
    setMustChangePassword(false);
    const profile = await authApi.getMe();
    setUser(profile);
    return data;
  };

  const logout = async () => {
    try {
      if (refreshToken) {
        await authApi.logout({ refresh_token: refreshToken });
      }
    } catch (err) {
      console.error("Error during server logout:", err);
    } finally {
      clearTokens();
    }
  };

  const value = {
    user,
    accessToken,
    refreshToken,
    mustChangePassword,
    isLoading,
    login,
    register,
    changePassword,
    logout,
    refreshUser: fetchCurrentUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

