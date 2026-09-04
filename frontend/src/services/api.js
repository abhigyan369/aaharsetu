/**
 * src/services/api.js — Centralized API Client
 * =============================================
 * Standardized HTTP fetch wrapper for interacting with FastAPI backend.
 * Automatically injects the JWT Bearer token from localStorage.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function apiFetch(endpoint, options = {}) {
  const token = localStorage.getItem('access_token');

  const headers = { ...options.headers };

  // Attach token if present and not explicitly skipped
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Set Content-Type to application/json unless body is FormData (file upload)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // If unauthorized, token might be expired
    // Clear invalid token if present
    // localStorage.removeItem('access_token');
  }

  let data = null;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  }

  if (!response.ok) {
    let errorMessage = `API request failed with status ${response.status}`;
    if (typeof data?.detail === 'string') {
      errorMessage = data.detail;
    } else if (Array.isArray(data?.detail)) {
      errorMessage = data.detail
        .map((e) => {
          if (typeof e === 'string') return e;
          const field = Array.isArray(e.loc) && e.loc.length > 1 ? e.loc[e.loc.length - 1] : '';
          const msg = e.msg || e.detail || JSON.stringify(e);
          return field && field !== 'body' ? `${field}: ${msg}` : msg;
        })
        .join(', ');
    }
    const error = new Error(errorMessage);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

// ── Auth Endpoints ────────────────────────────────────────────────────────────
export const authApi = {
  login: async (email, password) => {
    // OAuth2 Password Grant requires x-www-form-urlencoded format
    const body = new URLSearchParams();
    body.append('username', email); // OAuth2 standard uses 'username' for email
    body.append('password', password);

    return apiFetch('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });
  },

  signup: async (userData) => {
    return apiFetch('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },

  getMe: async () => {
    return apiFetch('/auth/me');
  },
};

// ── Listings Endpoints ────────────────────────────────────────────────────────
export const listingsApi = {
  getAll: async (params = {}) => {
    const query = new URLSearchParams();
    if (params.food_type) query.append('food_type', params.food_type);
    if (params.status) query.append('status', params.status);
    if (params.lat) query.append('lat', params.lat);
    if (params.lng) query.append('lng', params.lng);
    if (params.max_distance_km) query.append('max_distance_km', params.max_distance_km);

    const queryString = query.toString() ? `?${query.toString()}` : '';
    return apiFetch(`/listings${queryString}`);
  },

  getById: async (id) => {
    return apiFetch(`/listings/${id}`);
  },

  create: async (formData) => {
    // Expects FormData instance for multipart/form-data support (image uploads)
    return apiFetch('/listings/', {
      method: 'POST',
      body: formData,
    });
  },

  claim: async (id, notes = '') => {
    return apiFetch(`/listings/${id}/claim`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
  },

  complete: async (id) => {
    return apiFetch(`/listings/${id}/complete`, {
      method: 'POST',
    });
  },
};

// ── Admin Endpoints ───────────────────────────────────────────────────────────
export const adminApi = {
  getStats: async () => {
    return apiFetch('/admin/stats');
  },
};

// ── Chat Endpoints ────────────────────────────────────────────────────────────
export const chatApi = {
  getHistory: async (channelId = 'global') => {
    return apiFetch(`/chat/history?channel_id=${encodeURIComponent(channelId)}`);
  },
};
