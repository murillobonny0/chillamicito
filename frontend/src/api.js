import axios from 'axios';
import { authSession } from './authSession.js';

// Cliente HTTP centralizado para consumir la API Django desde React.
export function createApiClient(baseURL, session = authSession) {
  const api = axios.create({ baseURL, timeout: 60000 });

  // Cada peticion utiliza la credencial de esta pestana.
  api.interceptors.request.use((config) => {
    const token = session.getToken();
    config.chillamicitoSessionToken = token;

    if (token && !config.headers.Authorization) {
      // DRF TokenAuthentication espera el formato: Authorization: Token <token>.
      config.headers.Authorization = `Token ${token}`;
    }

    return config;
  });

  api.interceptors.response.use((response) => {
    // Una respuesta pendiente no debe cargar datos tras cambiar de usuario.
    if (response.config.chillamicitoSessionToken !== session.getToken()) {
      throw new axios.CanceledError('La sesion ha cambiado.', response.config);
    }
    return response;
  });

  return api;
}

const api = createApiClient(import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000/api');

export default api;
