import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 45000,
});

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

export const systemApi = {
  getStatus: async () => {
    const response = await api.get("/system/status");
    return response.data;
  },
};

export default api;
