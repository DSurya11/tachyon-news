/*
  Google Identity Services ("Continue with Google"). The script is loaded only when the
  API reports a GOOGLE_CLIENT_ID; Google renders its own button inside `el`.
*/
interface GsiButtonOptions {
  type?: 'standard' | 'icon'
  theme?: 'outline' | 'filled_blue' | 'filled_black'
  size?: 'large' | 'medium' | 'small'
  text?: 'signin_with' | 'signup_with' | 'continue_with'
  shape?: 'rectangular' | 'pill'
  logo_alignment?: 'left' | 'center'
  width?: number
}

interface Gsi {
  accounts: {
    id: {
      initialize(opts: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: 'popup'; auto_select?: boolean; itp_support?: boolean }): void
      renderButton(el: HTMLElement, opts: GsiButtonOptions): void
      disableAutoSelect(): void
    }
  }
}

declare global {
  interface Window { google?: Gsi }
}

let loading: Promise<Gsi> | null = null

export function loadGoogle(): Promise<Gsi> {
  if (window.google?.accounts) return Promise.resolve(window.google)
  loading ??= new Promise<Gsi>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true
    s.onload = () => (window.google ? resolve(window.google) : reject(new Error('Google sign-in did not load')))
    s.onerror = () => { loading = null; reject(new Error('Google sign-in could not be loaded')) }
    document.head.appendChild(s)
  })
  return loading
}

export async function renderGoogleButton(el: HTMLElement, clientId: string, dark: boolean, onCredential: (credential: string) => void) {
  const g = await loadGoogle()
  g.accounts.id.initialize({ client_id: clientId, callback: (r) => onCredential(r.credential), ux_mode: 'popup', auto_select: false, itp_support: true })
  el.replaceChildren()
  g.accounts.id.renderButton(el, {
    type: 'standard', theme: dark ? 'filled_black' : 'outline', size: 'large', text: 'continue_with',
    shape: 'rectangular', logo_alignment: 'center', width: Math.min(400, Math.round(el.getBoundingClientRect().width)),
  })
}
