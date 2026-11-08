import axios from "axios";

const rawApiUrl = import.meta.env.VITE_API_URL ? String(import.meta.env.VITE_API_URL).trim() : "";
let normalizedHost = rawApiUrl;
if (normalizedHost) {
  if (!normalizedHost.startsWith("http://") && !normalizedHost.startsWith("https://")) {
    normalizedHost = `https://${normalizedHost}`;
  }
  // Strip trailing slashes and any trailing /api/v1 to avoid double-prefixing
  normalizedHost = normalizedHost.replace(/\/api\/v1\/?$/, "").replace(/\/+$/, "");
}

export const API_BASE_URL = normalizedHost ? `${normalizedHost}/api/v1` : "/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000,
});

const ACCESS_TOKEN_KEY = "researchpilot_access_token";
const REFRESH_TOKEN_KEY = "researchpilot_refresh_token";

// Attach JWT access token to every outgoing request if available
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401s and auto-refresh rotated tokens
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Do not attempt refresh on auth endpoints to avoid loops
    const isAuthRoute =
      originalRequest.url?.includes("/auth/login") ||
      originalRequest.url?.includes("/auth/register") ||
      originalRequest.url?.includes("/auth/refresh");

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRoute) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!storedRefreshToken) {
        isRefreshing = false;
        return Promise.reject(error);
      }

      try {
        const refreshResponse = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: storedRefreshToken,
        });

        const { access_token, refresh_token } = refreshResponse.data;
        localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
        if (refresh_token) {
          localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
        }

        api.defaults.headers.common.Authorization = `Bearer ${access_token}`;
        originalRequest.headers.Authorization = `Bearer ${access_token}`;

        processQueue(null, access_token);
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        window.dispatchEvent(new CustomEvent("researchpilot:logout"));
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export const authApi = {
  register: async (credentials) => {
    const response = await api.post("/auth/register", credentials);
    return response.data;
  },

  login: async (credentials) => {
    const response = await api.post("/auth/login", credentials);
    return response.data;
  },

  refresh: async (refreshToken) => {
    const response = await api.post("/auth/refresh", { refresh_token: refreshToken });
    return response.data;
  },

  logout: async (data = {}) => {
    const response = await api.post("/auth/logout", data);
    return response.data;
  },

  changePassword: async (passwords) => {
    const response = await api.post("/auth/change-password", passwords);
    return response.data;
  },

  getMe: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },

  listUsers: async () => {
    const response = await api.get("/auth/users");
    return response.data;
  },

  updateUser: async (userId, data) => {
    const response = await api.patch(`/auth/users/${userId}`, data);
    return response.data;
  },
};

export const documentApi = {
  upload: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post("/documents/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  list: async () => {
    const response = await api.get("/documents");
    return response.data;
  },

  get: async (id) => {
    const response = await api.get(`/documents/${id}`);
    return response.data;
  },

  getChunks: async (id) => {
    const response = await api.get(`/documents/${id}/chunks`);
    return response.data;
  },

  delete: async (id) => {
    const response = await api.delete(`/documents/${id}`);
    return response.data;
  },

  getStatus: async (id) => {
    const response = await api.get(`/documents/${id}/status`);
    return response.data;
  },
};

export const qaApi = {
  query: async (query, documentId = null, topK = 5, threshold = null) => {
    const payload = {
      query,
      document_id: documentId || null,
      top_k: topK,
      threshold: threshold,
    };
    const response = await api.post("/qa/query", payload);
    return response.data;
  },

  search: async (query, documentId = null, topK = 5, threshold = null) => {
    const payload = {
      query,
      document_id: documentId || null,
      top_k: topK,
      threshold: threshold,
    };
    const response = await api.post("/qa/search", payload);
    return response.data;
  },
};

export const researchApi = {
  createJob: async (jobData) => {
    const response = await api.post("/research/jobs", jobData);
    return response.data;
  },

  listJobs: async () => {
    const response = await api.get("/research/jobs");
    return response.data;
  },

  getJob: async (id) => {
    const response = await api.get(`/research/jobs/${id}`);
    return response.data;
  },

  getEvents: async (id) => {
    const response = await api.get(`/research/jobs/${id}/events`);
    return response.data;
  },

  getStreamUrl: (id, token = null) => {
    const t = token || localStorage.getItem(ACCESS_TOKEN_KEY);
    return `${API_BASE_URL}/research/jobs/${id}/stream${t ? `?token=${encodeURIComponent(t)}` : ""}`;
  },

  getReport: async (id) => {
    const response = await api.get(`/research/jobs/${id}/report`);
    return response.data;
  },

  downloadPdf: async (id) => {
    const response = await api.get(`/research/jobs/${id}/pdf`, {
      responseType: "blob",
    });
    return response.data;
  },
};

export const healthApi = {
  check: async () => {
    const response = await api.get("/health");
    return response.data;
  },
};

export const usageApi = {
  getMyUsage: async () => {
    const response = await api.get("/usage/me");
    return response.data;
  },

  getMyHistory: async (page = 1, pageSize = 20, provider = null) => {
    const params = { page, page_size: pageSize };
    if (provider) params.provider = provider;
    const response = await api.get("/usage/history", { params });
    return response.data;
  },

  getMyLimits: async () => {
    const response = await api.get("/usage/limits");
    return response.data;
  },

  getAdminSummary: async () => {
    const response = await api.get("/admin/usage");
    return response.data;
  },

  getAdminUsers: async (page = 1, pageSize = 50) => {
    const response = await api.get("/admin/usage/users", {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
};

export const systemApi = {
  getStatus: async () => {
    const response = await api.get("/system/status");
    return response.data;
  },
};

export const billingApi = {
  getWallet: async () => {
    const response = await api.get("/billing/wallet");
    return response.data;
  },

  getOverview: async () => {
    const response = await api.get("/billing/overview");
    return response.data;
  },

  getTransactions: async (limit = 50) => {
    const response = await api.get("/billing/transactions", { params: { limit } });
    return response.data;
  },

  createCheckout: async (amountUsd, successUrl = null, cancelUrl = null) => {
    const response = await api.post("/billing/checkout", {
      amount_usd: amountUsd,
      success_url: successUrl,
      cancel_url: cancelUrl,
    });
    return response.data;
  },

  getAdminOverview: async () => {
    const response = await api.get("/billing/admin/financials/overview");
    return response.data;
  },

  getAdminUsers: async (limit = 50) => {
    const response = await api.get("/billing/admin/financials/users", { params: { limit } });
    return response.data;
  },

  getAdminPricing: async () => {
    const response = await api.get("/billing/admin/pricing");
    return response.data;
  },
};

export default api;
