import { useEffect, useState, type FormEvent } from 'react';
import { KeyRound, Trash2 } from 'lucide-react';
import { api, errorMessage, post } from '../api.ts';
import { useLang } from '../i18n.tsx';
import { ALL_SCOPES, type ApiKeyRecord, type Scope } from '../shared/types.ts';
import { btnPrimary, CopyButton, ErrorBox, Field, formatDate, input, PageHeader, Panel, SectionTitle, Stripes } from '../ui.tsx';

const SCOPE_HELP: Record<Scope, [string, string]> = {
  'transcriptions:write': ['Upload audio files for transcription', 'បង្ហោះឯកសារសំឡេង ដើម្បីបំលែងជាអក្សរ'],
  'stream:listen': ['Open live-caption sessions', 'បើកវគ្គអក្សររត់ផ្ទាល់'],
  'usage:read': ['Read your usage statistics', 'មើលស្ថិតិការប្រើប្រាស់'],
};

export default function Keys() {
  const { t, lang } = useLang();
  const [keys, setKeys] = useState<ApiKeyRecord[] | null>(null);
  const [name, setName] = useState('');
  const [scopes, setScopes] = useState<Scope[]>(ALL_SCOPES);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    api<{ data: ApiKeyRecord[] }>('/v1/keys')
      .then((r) => setKeys(r.data))
      .catch((e) => setError(errorMessage(e)));

  useEffect(() => {
    load();
  }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await post<{ plaintext_key_once: string }>('/v1/keys', { name, scopes });
      setNewKey(r.plaintext_key_once);
      setName('');
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: string) => {
    setConfirmRevoke(null);
    try {
      await post(`/v1/keys/${id}/revoke`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <>
      <PageHeader
        title="API keys"
        subtitle={t(
          'Use a key from your own server. Never ship it inside a mobile app or web page; those get a short-lived session token instead.',
          'ប្រើ key ពី server របស់អ្នក។ កុំដាក់វាក្នុង app ទូរស័ព្ទ ឬទំព័រវេប ព្រោះកន្លែងទាំងនោះគួរប្រើ session token រយៈពេលខ្លីជំនួសវិញ។'
        )}
      />
      <ErrorBox message={error} />

      {newKey && (
        <div className="k-chamfer k-panel space-y-3" style={{ ['--k-fill' as string]: 'var(--color-acid)' }}>
          <p className="k-display text-xl text-graphite flex items-center gap-3">
            {t('Copy your key now', 'ចម្លង key ឥឡូវនេះ')}
            <Stripes className="h-4 text-graphite" />
          </p>
          <p className="text-graphite/80 text-sm">{t("It is shown once. Kethra only keeps a hash, so it can't show it again.", 'វាបង្ហាញតែម្តងគត់។ Kethra រក្សាទុកតែ hash ដូច្នេះមិនអាចបង្ហាញវាម្តងទៀតបានទេ។')}</p>
          <div className="flex items-center justify-between gap-3 bg-graphite px-3 py-2.5 font-mono text-sm text-decal">
            <span className="break-all">{newKey}</span>
            <CopyButton text={newKey} label={t('Copy API key', 'ចម្លង API key')} />
          </div>
          <button type="button" onClick={() => setNewKey(null)} className="text-sm font-semibold text-graphite underline cursor-pointer">
            {t("I've saved it", 'ខ្ញុំបានរក្សាទុកហើយ')}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <Panel className="lg:col-span-5">
          <SectionTitle>{t('Create a key', 'បង្កើត key')}</SectionTitle>
          <form onSubmit={create} className="space-y-5">
            <Field label={t('Name', 'ឈ្មោះ')} hint={t('What will use it, e.g. "My app backend".', 'អ្វីនឹងប្រើវា ឧ. "My app backend"។')}>
              <input required minLength={2} maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className={input} />
            </Field>
            <fieldset className="space-y-3">
              <legend className="k-label mb-2">{t('Permissions', 'សិទ្ធិ')}</legend>
              {ALL_SCOPES.map((s) => (
                <label key={s} className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={scopes.includes(s)} onChange={(e) => setScopes(e.target.checked ? [...scopes, s] : scopes.filter((x) => x !== s))} className="mt-1.5 w-4 h-4" />
                  <span>
                    <span className="font-mono text-sm text-decal">{s}</span>
                    <span className="block text-sm text-silver">{t(...SCOPE_HELP[s])}</span>
                  </span>
                </label>
              ))}
            </fieldset>
            <button type="submit" disabled={busy || scopes.length === 0} className={btnPrimary}>
              <KeyRound className="w-4 h-4" /> {busy ? t('Creating…', 'កំពុងបង្កើត…') : t('Create key', 'បង្កើត key')}
            </button>
          </form>
        </Panel>

        <Panel className="lg:col-span-7">
          <SectionTitle>{t('Your keys', 'Keys របស់អ្នក')}</SectionTitle>
          {keys === null ? (
            <p className="text-silver">{t('Loading…', 'កំពុងផ្ទុក…')}</p>
          ) : keys.length === 0 ? (
            <p className="text-silver py-6">{t('No keys yet. Create one on the left; it takes a second.', 'មិនទាន់មាន key ទេ។ បង្កើតមួយនៅខាងឆ្វេង។')}</p>
          ) : (
            <ul className="divide-y divide-track-2">
              {keys.map((k) => (
                <li key={k.id} className={`py-4 flex flex-wrap items-start justify-between gap-4 ${k.status === 'revoked' ? 'opacity-55' : ''}`}>
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-decal">{k.name}</span>
                      <span className={`k-label !text-[0.6875rem] ${k.status === 'active' ? '!text-go' : '!text-alert'}`}>
                        {k.status === 'active' ? t('Active', 'កំពុងប្រើ') : t('Revoked', 'បានដកសិទ្ធិ')}
                      </span>
                    </div>
                    <div className="font-mono text-sm text-silver">{k.key_prefix}</div>
                    <div className="text-sm text-tarmac">
                      {t(`${k.request_count} requests`, `${k.request_count} សំណើ`)} · {t('last used', 'ប្រើចុងក្រោយ')} {formatDate(k.last_used_at, lang)}
                    </div>
                    <div className="font-mono text-xs text-tarmac">{k.scopes.join('  ')}</div>
                  </div>
                  {k.status === 'active' &&
                    (confirmRevoke === k.id ? (
                      <div className="flex items-center gap-4 text-sm">
                        <button type="button" onClick={() => revoke(k.id)} className="font-semibold text-alert hover:text-decal cursor-pointer">
                          {t('Yes, revoke it', 'បាទ/ចាស ដកសិទ្ធិ')}
                        </button>
                        <button type="button" onClick={() => setConfirmRevoke(null)} className="text-silver hover:text-decal cursor-pointer">
                          {t('Cancel', 'បោះបង់')}
                        </button>
                      </div>
                    ) : (
                      <button type="button" onClick={() => setConfirmRevoke(k.id)} className="inline-flex items-center gap-1.5 text-sm text-silver hover:text-alert cursor-pointer">
                        <Trash2 className="w-4 h-4" /> {t('Revoke', 'ដកសិទ្ធិ')}
                      </button>
                    ))}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
