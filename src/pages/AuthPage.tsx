import { useState, type FormEvent } from 'react';
import { ArrowRight } from 'lucide-react';
import { errorMessage, post } from '../api.ts';
import { useLang } from '../i18n.tsx';
import type { User } from '../shared/types.ts';
import { btnPrimary, ErrorBox, Field, go, input, Stripes } from '../ui.tsx';

export default function AuthPage({ mode, onAuthenticated }: { mode: 'login' | 'register'; onAuthenticated: (u: User) => void }) {
  const { t } = useLang();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === 'login';

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { user } = await post<{ user: User }>(isLogin ? '/v1/auth/login' : '/v1/auth/register', { email, password });
      onAuthenticated(user);
      go(isLogin ? 'dashboard' : 'keys');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto pt-4 sm:pt-10">
      <div className="k-chamfer k-panel k-panel-raised !p-8 space-y-6" style={{ ['--k-cut' as string]: '24px' }}>
        <div className="space-y-2">
          <h1 className="k-display text-4xl text-decal">
            {isLogin ? t('Log in', 'ចូលគណនី') : t('Create account', 'បង្កើតគណនី')}
            {/* nbsp keeps the decal on the same line as the last word */}
            &nbsp;
            <Stripes className="inline-block align-middle h-5 ml-1 text-orange" />
          </h1>
          <p className="text-silver">
            {isLogin
              ? t('Manage your API keys and test transcription.', 'គ្រប់គ្រង API keys និងសាកល្បងការបំលែងសំឡេង។')
              : t('Free. You can create an API key right after.', 'ឥតគិតថ្លៃ។ អ្នកអាចបង្កើត API key បានភ្លាមៗបន្ទាប់ពីនេះ។')}
          </p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <Field label={t('Email', 'អ៊ីមែល')}>
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={input} />
          </Field>
          <Field label={t('Password', 'ពាក្យសម្ងាត់')} hint={isLogin ? undefined : t('At least 8 characters.', 'យ៉ាងតិច ៨ តួ។')}>
            <input
              type="password"
              required
              minLength={isLogin ? undefined : 8}
              maxLength={128}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={input}
            />
          </Field>
          <ErrorBox message={error} />
          <button type="submit" disabled={busy} className={`${btnPrimary} w-full`}>
            {busy ? t('Please wait…', 'សូមរង់ចាំ…') : isLogin ? t('Log in', 'ចូលគណនី') : t('Create account', 'បង្កើតគណនី')}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
        <p className="text-sm text-silver border-t border-track-2 pt-4">
          {isLogin ? t('No account yet?', 'មិនទាន់មានគណនី?') : t('Already have an account?', 'មានគណនីហើយ?')}{' '}
          <a href={isLogin ? '#/register' : '#/login'} className="text-acid font-semibold hover:text-decal">
            {isLogin ? t('Create one', 'បង្កើតមួយ') : t('Log in', 'ចូលគណនី')}
          </a>
        </p>
      </div>
    </div>
  );
}
