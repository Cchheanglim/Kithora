import { useState, type FormEvent } from 'react';
import { errorMessage, post } from '../api.ts';
import { useLang } from '../i18n.tsx';
import type { User } from '../shared/types.ts';
import { btnDanger, btnPrimary, ErrorBox, Field, formatDate, go, input, PageHeader, Panel, SectionTitle } from '../ui.tsx';

export default function Settings({ user, onDeleted }: { user: User; onDeleted: () => void }) {
  const { t, lang } = useLang();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [pwMessage, setPwMessage] = useState<string | null>(null);
  const [pwError, setPwError] = useState<string | null>(null);
  const [deletePw, setDeletePw] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    setPwError(null);
    setPwMessage(null);
    try {
      await post('/v1/account/password', { current_password: current, new_password: next });
      setCurrent('');
      setNext('');
      setPwMessage(t('Password changed. Your other devices were logged out.', 'បានប្តូរពាក្យសម្ងាត់។ ឧបករណ៍ផ្សេងទៀតត្រូវបានចាកចេញ។'));
    } catch (err) {
      setPwError(errorMessage(err));
    }
  };

  const deleteAccount = async (e: FormEvent) => {
    e.preventDefault();
    setDeleteError(null);
    try {
      await post('/v1/account/delete', { password: deletePw });
      onDeleted();
      go('home');
    } catch (err) {
      setDeleteError(errorMessage(err));
    }
  };

  return (
    <>
      <PageHeader title={t('Settings', 'ការកំណត់')} />
      <div className="grid lg:grid-cols-2 gap-6 items-start">
        <Panel>
          <SectionTitle>{t('Account', 'គណនី')}</SectionTitle>
          <dl className="grid grid-cols-[auto_1fr] gap-x-8 gap-y-3">
            <dt className="k-label pt-0.5">{t('Email', 'អ៊ីមែល')}</dt>
            <dd className="text-decal break-all">{user.email}</dd>
            <dt className="k-label pt-0.5">{t('Member since', 'ចុះឈ្មោះតាំងពី')}</dt>
            <dd className="text-decal">{formatDate(user.created_at, lang)}</dd>
          </dl>
        </Panel>

        <Panel>
          <SectionTitle>{t('Change password', 'ប្តូរពាក្យសម្ងាត់')}</SectionTitle>
          <form onSubmit={changePassword} className="space-y-4">
            <Field label={t('Current password', 'ពាក្យសម្ងាត់បច្ចុប្បន្ន')}>
              <input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} className={input} />
            </Field>
            <Field label={t('New password', 'ពាក្យសម្ងាត់ថ្មី')} hint={t('At least 8 characters.', 'យ៉ាងតិច ៨ តួ។')}>
              <input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} className={input} />
            </Field>
            <ErrorBox message={pwError} />
            {pwMessage && (
              <p role="status" className="text-go">
                {pwMessage}
              </p>
            )}
            <button type="submit" className={btnPrimary}>
              {t('Change password', 'ប្តូរពាក្យសម្ងាត់')}
            </button>
          </form>
        </Panel>

        <Panel className="lg:col-span-2 border border-alert/40">
          <SectionTitle>{t('Delete account', 'លុបគណនី')}</SectionTitle>
          <p className="text-silver max-w-2xl">
            {t(
              'Deletes your account, every API key and your usage history. Apps using your keys stop working immediately. This cannot be undone.',
              'លុបគណនី API keys ទាំងអស់ និងប្រវត្តិការប្រើប្រាស់របស់អ្នក។ App ដែលប្រើ keys របស់អ្នកនឹងឈប់ដំណើរការភ្លាមៗ។ មិនអាចត្រឡប់វិញបានទេ។'
            )}
          </p>
          <form onSubmit={deleteAccount} className="flex flex-col sm:flex-row sm:items-end gap-3 max-w-xl">
            <div className="flex-1">
              <Field label={t('Confirm with your password', 'បញ្ជាក់ដោយពាក្យសម្ងាត់')}>
                <input type="password" required autoComplete="current-password" value={deletePw} onChange={(e) => setDeletePw(e.target.value)} className={input} />
              </Field>
            </div>
            <button type="submit" className={btnDanger}>
              {t('Delete my account', 'លុបគណនីរបស់ខ្ញុំ')}
            </button>
          </form>
          <ErrorBox message={deleteError} />
        </Panel>
      </div>
    </>
  );
}
