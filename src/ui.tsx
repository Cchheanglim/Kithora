import { useState, type CSSProperties, type ReactNode } from 'react';
import { AlertTriangle, Check, Copy } from 'lucide-react';
import { useLang } from './i18n.tsx';

export const btnPrimary = 'k-chamfer k-btn k-btn-primary';
export const btnGhost = 'k-chamfer k-btn k-btn-ghost';
export const btnDanger = 'k-chamfer k-btn k-btn-danger';
export const input = 'k-input';

export const go = (route: string) => {
  window.location.hash = `/${route}`;
};

/** The livery decal: three leaning bars. */
export function Stripes({ className = 'h-5 text-orange', title }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 54 24" className={className} fill="currentColor" role={title ? 'img' : undefined} aria-hidden={title ? undefined : true}>
      {title && <title>{title}</title>}
      <path d="M10 0h9L9 24H0zM27 0h9L26 24h-9zM44 0h10L44 24h-9z" />
    </svg>
  );
}

export function Panel({ children, className = '', raised = false, style }: { children: ReactNode; className?: string; raised?: boolean; style?: CSSProperties }) {
  return (
    <section className={`k-chamfer k-panel ${raised ? 'k-panel-raised' : ''} space-y-4 ${className}`} style={style}>
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-track-2 pb-5">
      <div className="space-y-2 max-w-2xl">
        <h1 className="k-display text-4xl sm:text-5xl text-decal flex items-center gap-3">
          {title}
          <Stripes className="h-6 text-orange shrink-0" />
        </h1>
        {subtitle && <p className="text-silver">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="k-display text-xl text-decal">{children}</h2>;
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-2.5 border border-alert/50 bg-alert/10 px-3.5 py-2.5 text-sm text-decal">
      <AlertTriangle className="w-4 h-4 text-alert shrink-0 mt-1" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="k-label block">{label}</span>
      {children}
      {hint && <span className="block text-xs text-tarmac">{hint}</span>}
    </label>
  );
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="p-1.5 text-acid hover:text-decal shrink-0 cursor-pointer"
    >
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
    </button>
  );
}

export function Code({ children }: { children: string }) {
  return (
    <pre className="bg-graphite border border-track-2 p-4 text-[13px] leading-relaxed text-silver overflow-x-auto whitespace-pre">{children}</pre>
  );
}

export function LangToggle() {
  const { lang, setLang } = useLang();
  const option = (value: 'en' | 'km', label: string, aria: string) => (
    <button
      type="button"
      lang={value}
      aria-pressed={lang === value}
      aria-label={aria}
      onClick={() => setLang(value)}
      className={`px-2.5 py-1 text-sm cursor-pointer transition-colors ${lang === value ? 'bg-decal text-graphite font-semibold' : 'text-silver hover:text-decal'}`}
    >
      {label}
    </button>
  );
  return (
    <div className="flex border border-track-2" role="group" aria-label="Language / ភាសា">
      {option('en', 'EN', 'English')}
      {option('km', 'ខ្មែរ', 'ភាសាខ្មែរ')}
    </div>
  );
}

const KHMER = /[\u1780-\u17ff\u19e0-\u19ff]/;

/** Splits a transcript into words and marks every point where the script switches between Khmer and Latin. */
export function splitCaption(text: string) {
  const words = text.split(/\s+/).filter(Boolean);
  let prev: 'km' | 'en' | null = null;
  return words.map((word) => {
    const script = KHMER.test(word) ? 'km' : /[A-Za-z]/.test(word) ? 'en' : prev ?? 'en';
    const switched = prev !== null && script !== prev;
    prev = script;
    return { word, script, switched };
  });
}

/**
 * One caption line: Khmer upright, English leaning like the livery type, an orange marker at each language switch.
 * `animate` staggers the words in (the landing replay); `stepMs` sets the pace.
 */
export function CaptionLine({ text, animate = false, stepMs = 130, className = '' }: { text: string; animate?: boolean; stepMs?: number; className?: string }) {
  const { t } = useLang();
  return (
    <p className={`flex flex-wrap items-baseline gap-x-[0.35em] gap-y-1 ${className}`}>
      {splitCaption(text).map(({ word, script, switched }, i) => (
        <span key={`${i}-${word}`} className="inline-flex items-baseline gap-[0.35em]">
          {switched && (
            <span className={animate ? 'k-marker' : ''} style={animate ? { animationDelay: `${i * stepMs}ms` } : undefined}>
              <Stripes className="h-[0.55em] text-orange" title={t('Language switch', 'ប្តូរភាសា')} />
            </span>
          )}
          <span
            lang={script === 'km' ? 'km' : 'en'}
            className={`${animate ? 'k-word' : ''} ${script === 'en' ? 'italic font-[650] [font-stretch:108%]' : 'font-[550]'}`}
            style={animate ? { animationDelay: `${i * stepMs}ms` } : undefined}
          >
            {word}
          </span>
        </span>
      ))}
    </p>
  );
}

export const formatDate = (iso: string | null, lang: 'en' | 'km' = 'en') =>
  iso ? new Date(/Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleString(lang === 'km' ? 'km-KH' : 'en-GB') : '—';
