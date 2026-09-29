/*
  The signed-in session: a bearer token from /auth/*, kept in localStorage so a reload
  stays signed in. Listeners hear about sign-in, sign-out and server-side expiry (401).
*/
const KEY = 'tsn.session'
type Listener = (token: string | null) => void
const listeners = new Set<Listener>()

function read(): string | null {
  try { return localStorage.getItem(KEY) } catch { return null }
}

let current = read()

export const session = {
  get token() { return current },
  set(token: string | null) {
    current = token
    try {
      if (token) localStorage.setItem(KEY, token)
      else localStorage.removeItem(KEY)
    } catch { /* private mode: the session lasts for this tab only */ }
    listeners.forEach((l) => l(token))
  },
  subscribe(l: Listener) {
    listeners.add(l)
    return () => { listeners.delete(l) }
  },
}

// Another tab signed in or out.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === KEY && e.newValue !== current) {
      current = e.newValue
      listeners.forEach((l) => l(current))
    }
  })
}
