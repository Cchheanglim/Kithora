import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, RotateCcw } from 'lucide-react';
import { errorMessage, post } from '../api.ts';
import { useLang } from '../i18n.tsx';
import type { User } from '../shared/types.ts';
import { btnGhost, btnPrimary, CaptionLine, Code, ErrorBox, go, splitCaption, Stripes } from '../ui.tsx';

// Hand-typed examples that show the output format. Labeled as examples on the page; not engine output.
const EXAMPLES = [
  'ខ្ញុំនឹង send it to you tomorrow មុនម៉ោងប្រាំ។',
  'សូមជួយ check pull request នៅក្នុង GitHub ផង។',
  'ចាំខ្ញុំ share screen ក្នុង Zoom call តែម្តង។',
];

function Telemetry() {
  const { t } = useLang();
  const [index, setIndex] = useState(0);
  const [run, setRun] = useState(0); // bump to replay the lap
  const text = EXAMPLES[index];
  const words = splitCaption(text);
  const switches = words.filter((w) => w.switched).length;
  const khmerWords = words.filter((w) => w.script === 'km').length;
  const englishWords = words.length - khmerWords;

  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = panelRef.current;
    if (!el || !('IntersectionObserver' in window)) return;
    let first = true;
    const io = new IntersectionObserver(([entry]) => {
      // Visible on load (desktop): the mount animation already plays, so don't restart it.
      if (first) {
        first = false;
        if (entry.intersectionRatio >= 0.6) io.disconnect();
        return;
      }
      if (entry.intersectionRatio >= 0.6) {
        setRun((r) => r + 1);
        io.disconnect();
      }
    }, { threshold: 0.6 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const next = () => {
    setIndex((i) => (i + 1) % EXAMPLES.length);
    setRun((r) => r + 1);
  };

  return (
    <div ref={panelRef} className="k-chamfer k-panel k-panel-raised !p-0 overflow-hidden" style={{ ['--k-cut' as string]: '28px' }}>
      <div className="flex items-center justify-between gap-4 px-6 pt-5">
        <span className="k-label flex items-center gap-2">
          <span className="w-2 h-2 rotate-45 bg-tarmac" aria-hidden />
          {t('Example replay', 'ឧទាហរណ៍')} · {index + 1}/{EXAMPLES.length}
        </span>
        <span className="k-label">km-KH + en-US</span>
      </div>

      <div className="relative k-track px-6 py-10 sm:py-14 overflow-hidden" key={run}>
        <div className="k-streak absolute left-0 right-0 top-1/2 h-px bg-linear-to-r from-transparent via-acid to-transparent" aria-hidden />
        <CaptionLine text={text} animate className="relative text-3xl sm:text-4xl xl:text-[2.75rem] leading-snug text-decal" />
      </div>

      <dl className="grid grid-cols-3 border-t border-track-2 text-center">
        {[
          [t('Khmer words', 'ពាក្យខ្មែរ'), String(khmerWords)],
          [t('English words', 'ពាក្យ English'), String(englishWords)],
          [t('Language switches', 'ការប្តូរភាសា'), String(switches)],
        ].map(([label, value]) => (
          <div key={label} className="px-3 py-4 border-r border-track-2 last:border-r-0">
            <dt className="k-label">{label}</dt>
            <dd className="k-display text-xl sm:text-3xl text-decal mt-1 tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-track-2">
        <p className="text-sm text-silver max-w-sm">
          {t('Example sentences we typed to show the format. Try your own voice in the playground.', 'ប្រយោគឧទាហរណ៍ដែលយើងវាយបញ្ចូល ដើម្បីបង្ហាញទម្រង់។ សាកល្បងសំឡេងរបស់អ្នកនៅទំព័រសាកល្បង។')}
        </p>
        <div className="flex gap-2">
          <button type="button" onClick={() => setRun((r) => r + 1)} className={`${btnGhost} !min-h-9 !px-3`} aria-label={t('Replay', 'លេងម្តងទៀត')}>
            <RotateCcw className="w-4 h-4" />
          </button>
          <button type="button" onClick={next} className={`${btnGhost} !min-h-9 !px-4 !text-xs`}>
            {t('Next example', 'ឧទាហរណ៍បន្ទាប់')}
          </button>
        </div>
      </div>
    </div>
  );
}

function HeroSignup({ onAuthenticated }: { onAuthenticated: (u: User) => void }) {
  const { t } = useLang();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { user } = await post<{ user: User }>('/v1/auth/register', { email, password });
      onAuthenticated(user);
      go('keys');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3 max-w-xl" aria-label={t('Create an account', 'បង្កើតគណនី')}>
      <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-2">
        <label className="sr-only" htmlFor="hero-email">{t('Email', 'អ៊ីមែល')}</label>
        <input id="hero-email" type="email" required autoComplete="email" placeholder={t('Email', 'អ៊ីមែល')} value={email} onChange={(e) => setEmail(e.target.value)} className="k-input" />
        <label className="sr-only" htmlFor="hero-password">{t('Password (8+ characters)', 'ពាក្យសម្ងាត់ (៨ តួ ឡើងទៅ)')}</label>
        <input id="hero-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" placeholder={t('Password', 'ពាក្យសម្ងាត់')} value={password} onChange={(e) => setPassword(e.target.value)} className="k-input" />
        <button type="submit" disabled={busy} className={btnPrimary}>
          {busy ? t('Creating…', 'កំពុងបង្កើត…') : t('Get an API key', 'យក API key')}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
      <ErrorBox message={error} />
      <p className="text-sm text-tarmac">
        {t('Password: 8+ characters. Free learning project.', 'ពាក្យសម្ងាត់៖ ៨ តួឡើងទៅ។ គម្រោងសិក្សា ឥតគិតថ្លៃ។')}{' '}
        <a href="#/login" className="text-silver underline hover:text-decal">
          {t('Already have an account? Log in', 'មានគណនីហើយ? ចូលគណនី')}
        </a>
      </p>
    </form>
  );
}

const STEPS = [
  ['Create an account', 'បង្កើតគណនី', 'Email and password. One minute.', 'អ៊ីមែល និងពាក្យសម្ងាត់។ មួយនាទីប៉ុណ្ណោះ។'],
  ['Create an API key', 'បង្កើត API key', 'Shown once. Keep it on your server.', 'បង្ហាញតែម្តង។ ទុកវានៅលើ server របស់អ្នក។'],
  ['Send audio', 'ផ្ញើសំឡេង', 'Upload a file, or stream live from a microphone.', 'បង្ហោះឯកសារ ឬផ្សាយផ្ទាល់ពីមីក្រូហ្វូន។'],
  ['Get both languages back', 'ទទួលបានភាសាទាំងពីរ', 'Khmer in Khmer script, English in English, every switch marked.', 'ខ្មែរជាអក្សរខ្មែរ English ជាអក្សរ English ហើយរាល់ការប្តូរភាសាត្រូវបានសម្គាល់។'],
];

export default function Landing({ user, onAuthenticated }: { user: User | null | undefined; onAuthenticated: (u: User) => void }) {
  const { t, lang } = useLang();

  const specs = [
    [t('Languages', 'ភាសា'), 'km-KH + en-US'],
    [t('Recorded audio', 'សំឡេងដែលបានថត'), 'REST /v1/transcriptions'],
    [t('Live captions', 'អក្សររត់ផ្ទាល់'), 'WebSocket /v1/listen'],
    [
      t('Engine', 'ម៉ាស៊ីន'),
      t(
        "Gemini 3.5 Transcribe. Audio is sent to Google; on the free tier Google may use it to improve its products.",
        'Gemini 3.5 Transcribe។ សំឡេងត្រូវបានផ្ញើទៅ Google ហើយក្នុងកម្រិតឥតគិតថ្លៃ Google អាចប្រើវាដើម្បីកែលម្អផលិតផលរបស់ខ្លួន។'
      ),
    ],
    [t('Audio stored by Kethra', 'Kethra រក្សាទុកសំឡេង'), t('Never', 'មិនដែល')],
    [t('Accuracy on mixed speech', 'ភាពត្រឹមត្រូវលើការនិយាយលាយ'), t('Still being measured', 'កំពុងវាស់វែង')],
  ];

  return (
    <>
      {/* First viewport: headline + working sign-up on the left, the caption lap on the right. */}
      <section className="relative overflow-hidden border-b border-track-2">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-8 py-14 lg:py-16 grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-10 items-center min-h-[calc(100svh-4rem)]">
          <div className="lg:col-span-6 space-y-7">
            <h1 className="space-y-3">
              <span lang="km" className={`k-khmer-display block text-acid ${lang === 'km' ? 'text-5xl sm:text-6xl' : 'text-3xl sm:text-4xl'}`}>
                គ្រប់ពាក្យ ឮច្បាស់
              </span>
              <span lang="en" className={`k-display k-display-max block text-decal ${lang === 'km' ? 'text-4xl sm:text-5xl' : 'text-[clamp(2.75rem,4.6vw,4.75rem)]'}`}>
                <span className="block">Every word,</span>
                <span className="block text-acid">clearly</span>
                <span className="flex items-center gap-[0.25em] text-acid">
                  heard.
                  <Stripes className="h-[0.62em] text-orange shrink-0" />
                </span>
              </span>
            </h1>
            <p className="text-lg text-silver max-w-xl">
              {t(
                'A speech-to-text API for people who switch between Khmer and English mid-sentence. Kethra writes down both languages exactly as spoken. It never translates.',
                'Speech-to-text API សម្រាប់អ្នកដែលនិយាយខ្មែរ និង English លាយគ្នាក្នុងប្រយោគតែមួយ។ Kethra សរសេរភាសាទាំងពីរ ដូចដែលបាននិយាយ ហើយមិនបកប្រែឡើយ។'
              )}
            </p>
            {user ? (
              <div className="flex flex-wrap gap-3">
                <a href="#/playground" className={btnPrimary}>
                  {t('Open the playground', 'បើកទំព័រសាកល្បង')} <ArrowRight className="w-4 h-4" />
                </a>
                <a href="#/keys" className={btnGhost}>
                  {t('Your API keys', 'API keys របស់អ្នក')}
                </a>
              </div>
            ) : (
              <HeroSignup onAuthenticated={onAuthenticated} />
            )}
          </div>
          <div className="lg:col-span-6">
            <Telemetry />
          </div>
        </div>
      </section>

      {/* The sequence is real: these four steps happen in this order. */}
      <section className="max-w-7xl mx-auto px-4 sm:px-8 py-20 space-y-12">
        <h2 className="k-display text-3xl sm:text-4xl text-decal max-w-2xl">{t('Four steps to your first transcript', 'បួនជំហានទៅកាន់អត្ថបទដំបូង')}</h2>
        <ol className="relative grid gap-10 md:grid-cols-4 md:gap-6">
          <div className="hidden md:block absolute left-0 right-0 top-[1.6rem] h-[3px] bg-track-2" aria-hidden />
          {STEPS.map(([en, km, enBody, kmBody], i) => (
            <li key={en} className="relative space-y-3">
              <span className="k-display relative inline-flex items-center justify-center w-14 h-14 text-2xl text-graphite k-chamfer" style={{ ['--k-fill' as string]: 'var(--color-decal)', ['--k-cut' as string]: '10px' }}>
                {i + 1}
              </span>
              <h3 className="text-lg font-semibold text-decal">{t(en, km)}</h3>
              <p className="text-silver">{t(enBody, kmBody)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-track-2 bg-pit">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-20 grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          <div className="lg:col-span-5 space-y-5">
            <h2 className="k-display text-3xl sm:text-4xl text-decal">{t('One request. Both languages back.', 'សំណើមួយ។ ទទួលបានភាសាទាំងពីរ។')}</h2>
            <p className="text-silver">
              {t(
                'raw_transcript is exactly what the engine heard. normalized_transcript only fixes the spacing between Khmer and English. It never changes a word.',
                'raw_transcript គឺអ្វីដែលម៉ាស៊ីនបានឮពិតៗ។ normalized_transcript គ្រាន់តែកែចន្លោះរវាងខ្មែរ និង English ប៉ុណ្ណោះ មិនដែលប្តូរពាក្យឡើយ។'
              )}
            </p>
            <a href="#/docs" className="inline-flex items-center gap-2 font-semibold text-acid hover:text-decal">
              {t('Read the docs', 'អានឯកសារ')} <ArrowRight className="w-4 h-4" />
            </a>
          </div>
          <div className="lg:col-span-7 space-y-3 min-w-0">
            <Code>{`curl https://<your-kethra-host>/v1/transcriptions \\
  -H "Authorization: Bearer $KETHRA_API_KEY" \\
  -F "file=@meeting.wav"`}</Code>
            <Code>{`{
  "raw_transcript":        "ខ្ញុំនឹងsend it to you tomorrow",
  "normalized_transcript": "ខ្ញុំនឹង send it to you tomorrow",
  "normalization": { "switch_points": 1, "is_code_switched": true },
  "is_mock_engine": false
}`}</Code>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-8 py-20 space-y-8">
        <h2 className="k-display text-3xl sm:text-4xl text-decal">{t('Spec sheet', 'លក្ខណៈបច្ចេកទេស')}</h2>
        <dl className="grid sm:grid-cols-2 lg:grid-cols-3 border-t border-l border-track-2">
          {specs.map(([label, value]) => (
            <div key={label} className="border-r border-b border-track-2 px-5 py-5 space-y-1">
              <dt className="k-label">{label}</dt>
              <dd className="text-decal font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* The page ends on the livery: one acid band, one action. */}
      <section className="bg-acid text-graphite">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-14 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <p className="k-display text-4xl sm:text-5xl flex items-center gap-4">
            {t('Get your API key.', 'យក API key របស់អ្នក។')}
            <Stripes className="h-[0.7em] text-graphite shrink-0" />
          </p>
          <a
            href={user ? '#/keys' : '#/register'}
            className="k-chamfer k-btn self-start md:self-auto text-decal"
            style={{ ['--k-fill' as string]: 'var(--color-graphite)' }}
          >
            {user ? t('Go to API keys', 'ទៅ API keys') : t('Create an account', 'បង្កើតគណនី')} <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>
    </>
  );
}
