const TOKEN_KEY = 'token';
const USER_KEY = 'chillamicito:offline-user';

// sessionStorage conserva la sesion al recargar, con una copia por pestana.
export function createAuthSession(storage) {
  const tabStorage = () => storage ?? globalThis.sessionStorage;
  const getToken = () => tabStorage().getItem(TOKEN_KEY);

  return {
    getToken,
    isCurrent: (token) => Boolean(token) && getToken() === token,
    getUser() {
      try {
        const value = tabStorage().getItem(USER_KEY);
        return value ? JSON.parse(value) : null;
      } catch {
        return null;
      }
    },
    setUser(user) {
      tabStorage().setItem(USER_KEY, JSON.stringify(user));
    },
    save(token, user) {
      tabStorage().setItem(USER_KEY, JSON.stringify(user));
      tabStorage().setItem(TOKEN_KEY, token);
    },
    clear() {
      tabStorage().removeItem(TOKEN_KEY);
      tabStorage().removeItem(USER_KEY);
    },
  };
}

export const authSession = createAuthSession();
