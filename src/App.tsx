import { useEffect, useState } from 'react';
import { api, post } from './api.ts';
import { useLang } from './i18n.tsx';
import type { User } from './shared/types.ts';
import { go, LangToggle, Stripes } from './ui.tsx';
import Landing from './pages/Landing.tsx';
import AuthPage from './pages/AuthPage.tsx';
import Dashboard from './pages/Dashboard.tsx';
import Keys from './pages/Keys.tsx';
import Playground from './pages/Playground.tsx';
import Docs from './pages/Docs.tsx';
import Settings from './pages/Settings.tsx';

const PRIVATE_ROUTES = ['dashboard', 'keys', 'playground', 'settings'];

// Hash routing (#/keys) keeps this a static site with no router dependency.
function useRoute(): string {
  const read = () => window.location.hash.replace(/^#\/?/, '') || 'home';
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const onChange = () => {
      setRoute(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Stripes className="h-4 text-acid" />
      <span className="k-display text-xl text-decal tracking-[0.02em]">Kethra</span>
    </span>
  );
}

export default function App() {
  const route = useRoute();
  const { t } = useLang();
  const [user, setUser] = useState<User | null | undefined>(undefined); // undefined = still checking

  useEffect(() => {
    api<{ user: User }>('/v1/auth/me')
      .then((r) => setUser(r.user))
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (user === null && PRIVATE_ROUTES.includes(route)) go('login');
    if (user && (route === 'login' || route === 'register')) go('dashboard');
  }, [user, route]);

  const logout = async () => {
    await post('/v1/auth/logout');
    setUser(null);
    go('home');
  };

  const navLink = (to: string, en: string, km: string) => (
    <a
      href={`#/${to}`}
      aria-current={route === to ? 'page' : undefined}
      className={`relative py-1 whitespace-nowrap transition-colors hover:text-decal ${
        route === to ? 'text-acid after:absolute after:left-0 after:right-0 after:-bottom-[1.15rem] after:h-[3px] after:bg-acid' : ''
      }`}
    >
      {t(en, km)}
    </a>
  );

  let page;
  if (user === undefined || (user === null && PRIVATE_ROUTES.includes(route))) {
    page = <p className="k-label">{t('Loading…', 'កំពុងផ្ទុក…')}</p>;
  } else if (route === 'login' || route === 'register') {
    page = <AuthPage mode={route} onAuthenticated={setUser} />;
  } else if (route === 'dashboard') page = <Dashboard />;
  else if (route === 'keys') page = <Keys />;
  else if (route === 'playground') page = <Playground />;
  else if (route === 'settings' && user) page = <Settings user={user} onDeleted={() => setUser(null)} />;
  else if (route === 'docs') page = <Docs />;
  else page = <Landing user={user} onAuthenticated={setUser} />;

  const isLanding = !['dashboard', 'keys', 'playground', 'settings', 'docs', 'login', 'register'].includes(route);

  return (
    <div className="min-h-screen flex flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:bg-acid focus:text-graphite focus:px-3 focus:py-2">
        {t('Skip to content', 'រំលងទៅមាតិកា')}
      </a>
      <header className="sticky top-0 z-30 border-b border-track-2 bg-graphite/95 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 h-16 flex items-center justify-between gap-6">
          <a href="#/" aria-label="Kethra home">
            <Wordmark />
          </a>
          <nav aria-label={t('Main', 'ម៉ឺនុយ')} className="hidden md:flex items-center gap-7 text-[0.9375rem] font-medium text-silver">
            {user && navLink('dashboard', 'Dashboard', 'ផ្ទាំងគ្រប់គ្រង')}
            {user && navLink('keys', 'API keys', 'API keys')}
            {user && navLink('playground', 'Playground', 'សាកល្បង')}
            {navLink('docs', 'Docs', 'ឯកសារ')}
            {user && navLink('settings', 'Settings', 'ការកំណត់')}
          </nav>
          <div className="flex items-center gap-4 text-sm">
            <LangToggle />
            {user ? (
              <button type="button" onClick={logout} className="text-silver hover:text-decal cursor-pointer whitespace-nowrap">
                {t('Log out', 'ចាកចេញ')}
              </button>
            ) : (
              user === null &&
              route !== 'login' && (
                <a href="#/login" className="text-silver hover:text-decal whitespace-nowrap">
                  {t('Log in', 'ចូលគណនី')}
                </a>
              )
            )}
          </div>
        </div>
        <nav aria-label={t('Main', 'ម៉ឺនុយ')} className="md:hidden flex gap-6 overflow-x-auto px-4 pb-3 text-sm font-medium text-silver">
          {user && navLink('dashboard', 'Dashboard', 'ផ្ទាំងគ្រប់គ្រង')}
          {user && navLink('keys', 'API keys', 'API keys')}
          {user && navLink('playground', 'Playground', 'សាកល្បង')}
          {navLink('docs', 'Docs', 'ឯកសារ')}
          {user && navLink('settings', 'Settings', 'ការកំណត់')}
        </nav>
      </header>

      <main id="main" className={`flex-1 w-full ${isLanding ? '' : 'max-w-7xl mx-auto px-4 sm:px-8 py-10 space-y-8'}`}>
        {page}
      </main>

      <footer className="border-t border-track-2">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-sm text-tarmac">
          <Wordmark className="opacity-70" />
          <span>{t('A learning project. Audio is never stored by Kethra.', 'គម្រោងសិក្សា។ Kethra មិនរក្សាទុកសំឡេងឡើយ។')}</span>
        </div>
      </footer>
    </div>
  );
}
