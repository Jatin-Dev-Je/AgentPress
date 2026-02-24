import axios from 'axios';

const baseURL = (import.meta.env.VITE_BACKEND_URL as string) || '';

export const api = axios.create({
  // When VITE_BACKEND_URL is empty, requests stay same-origin and hit the Vite proxy.
  baseURL: baseURL ? baseURL.replace(/\/$/, '') : '',
  withCredentials: true,
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const message = error?.response?.data?.detail || error.message || 'Request failed';
    return Promise.reject(new Error(message));
  }
);
