/** Thin API client; business decisions remain in the backend. */
export const api = (path, options) => fetch(`/api${path}`, options);
