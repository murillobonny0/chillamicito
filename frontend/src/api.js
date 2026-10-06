import axios from 'axios';

// Cliente HTTP centralizado para consumir la API Django desde React.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api',
  timeout: 15000,
});

// Interceptor que agrega el token de autenticacion a cada peticion protegida.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');

  if (token && !config.headers.Authorization) {
    // DRF TokenAuthentication espera el formato: Authorization: Token <token>.
    config.headers.Authorization = `Token ${token}`;
  }

  return config;
});

export default api;
