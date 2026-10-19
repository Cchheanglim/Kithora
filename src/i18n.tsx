import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type Lang = 'en' | 'km';

const STORAGE_KEY = 'kethra-lang';

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'en' || saved === 'km') return saved;
  } catch {
    /* storage blocked: fall through to the browser language */
  }
  return navigator.language.toLowerCase().startsWith('km') ? 'km' : 'en';
}

interface LangValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Pick the string for the current language: t('Log in', 'ចូលគណនី'). */
  t: (en: string, km: string) => string;
}

const LangContext = createContext<LangValue>({ lang: 'en', setLang: () => {}, t: (en) => en });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* not persisted; still switches for this visit */
    }
  };

  return <LangContext.Provider value={{ lang, setLang, t: (en, km) => (lang === 'km' ? km : en) }}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);
