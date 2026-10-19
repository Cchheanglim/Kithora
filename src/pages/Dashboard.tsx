import { useEffect, useState } from 'react';
import { ArrowRight, RefreshCw } from 'lucide-react';
import { api, errorMessage } from '../api.ts';
import { useLang } from '../i18n.tsx';
import type { ApiKeyRecord, Health, UsageSummary } from '../shared/types.ts';
import { btnGhost, ErrorBox, formatDate, PageHeader, Panel, SectionTitle } from '../ui.tsx';

export default function Dashboard() {
  const { t, lang } = useLang();
  const [health, setHealth] = useState<Health | null>(null);
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [h, k, u] = await Promise.all([api<Health>('/v1/health'), api<{ data: ApiKeyRecord[] }>('/v1/keys'), api<UsageSummary>('/v1/usage')]);
      setHealth(h);
      setKeys(k.data);
      setUsage(u);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const activeKeys = keys.filter((k) => k.status === 'active').length;
  const engine = health?.engines.find((e) => e.engine_id === health.default_engine);
  const source = (id: string | null) => (id ? keys.find((k) => k.id === id)?.name ?? t('Deleted key', 'Key ដែលបានលុប') : t('Playground', 'សាកល្បង'));

  const readouts: [string, string][] = usage
    ? [
        [t('Requests', 'សំណើ'), usage.total_requests.toLocaleString()],
        [t('Audio processed', 'សំឡេងដែលបានដំណើរការ'), `${(usage.total_audio_bytes / (1024 * 1024)).toFixed(2)} MB`],
        [t('Errors', 'កំហុស'), usage.error_count.toLocaleString()],
        [t('Average latency', 'ពេលវេលាឆ្លើយតបជាមធ្យម'), usage.average_latency_ms !== null ? `${(usage.average_latency_ms / 1000).toFixed(1)} s` : '—'],
      ]
    : [];

  return (
    <>
      <PageHeader
        title={t('Dashboard', 'ផ្ទាំងគ្រប់គ្រង')}
        subtitle={t('Your usage and whether everything is ready.', 'ការប្រើប្រាស់របស់អ្នក និងស្ថានភាពប្រព័ន្ធ។')}
        action={
          <button type="button" onClick={load} disabled={loading} className={btnGhost}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'motion-safe:animate-spin' : ''}`} /> {t('Refresh', 'ផ្ទុកឡើងវិញ')}
          </button>
        }
      />
      <ErrorBox message={error} />

      {/* One timing screen, not four cards. */}
      <dl className="grid grid-cols-2 lg:grid-cols-4 border border-track-2 bg-pit">
        {(readouts.length ? readouts : [['', '…'], ['', '…'], ['', '…'], ['', '…']]).map(([label, value], i) => (
          <div key={i} className="px-5 py-5 border-track-2 [&:not(:last-child)]:border-r max-lg:[&:nth-child(2)]:border-r-0 max-lg:[&:nth-child(-n+2)]:border-b">
            <dt className="k-label">{label || ' '}</dt>
            <dd className="k-display normal-case text-3xl sm:text-4xl text-decal mt-2 tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <Panel className="lg:col-span-4">
          <SectionTitle>{t('Status', 'ស្ថានភាព')}</SectionTitle>
          <ul className="divide-y divide-track-2 text-sm">
            <li className="py-3 space-y-1">
              <div className="k-label">{t('Speech engine', 'ម៉ាស៊ីនបំលែងសំឡេង')}</div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${engine?.configured ? 'bg-go' : 'bg-alert'}`} aria-hidden />
                <span className="text-decal">{engine?.display_name ?? '—'}</span>
              </div>
              {engine && !engine.configured && <p className="text-alert">{t('Not configured on the server.', 'មិនទាន់បានកំណត់នៅលើ server។')}</p>}
            </li>
            <li className="py-3 space-y-1">
              <div className="k-label">{t('Active API keys', 'API keys ដែលកំពុងប្រើ')}</div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-decal tabular-nums">{activeKeys}</span>
                {activeKeys === 0 && !loading && (
                  <a href="#/keys" className="inline-flex items-center gap-1 font-semibold text-acid hover:text-decal">
                    {t('Create your first key', 'បង្កើត key ដំបូង')} <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </li>
            <li className="py-3 space-y-1">
              <div className="k-label">{t('Last request', 'សំណើចុងក្រោយ')}</div>
              <div className="text-decal">{usage?.logs[0] ? formatDate(usage.logs[0].timestamp, lang) : t('None yet', 'មិនទាន់មាន')}</div>
            </li>
          </ul>
        </Panel>

        <Panel className="lg:col-span-8 min-w-0">
          <SectionTitle>{t('Recent requests', 'សំណើថ្មីៗ')}</SectionTitle>
          {!usage || usage.logs.length === 0 ? (
            <div className="py-10 text-center space-y-3">
              <p className="text-silver">{loading ? t('Loading…', 'កំពុងផ្ទុក…') : t('No requests yet. Your first one will show up here.', 'មិនទាន់មានសំណើទេ។ សំណើដំបូងរបស់អ្នកនឹងបង្ហាញនៅទីនេះ។')}</p>
              {!loading && (
                <a href="#/playground" className="inline-flex items-center gap-1 font-semibold text-acid hover:text-decal">
                  {t('Try the playground', 'សាកល្បងឥឡូវនេះ')} <ArrowRight className="w-4 h-4" />
                </a>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-left text-sm">
                <thead className="k-label border-b border-track-2">
                  <tr>
                    {[t('Time', 'ពេល'), t('Source', 'ប្រភព'), 'Endpoint', t('Status', 'ស្ថានភាព'), t('Audio', 'សំឡេង'), t('Latency', 'ពេលឆ្លើយតប')].map((h) => (
                      <th key={h} scope="col" className="py-2.5 px-1 pr-4 font-[inherit] whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-track-2 text-silver">
                  {usage.logs.map((log) => (
                    <tr key={log.id} className="hover:bg-track/60">
                      <td className="py-2.5 px-1 pr-4 whitespace-nowrap">{formatDate(log.timestamp, lang)}</td>
                      <td className="py-2.5 px-1 pr-4 text-decal">{source(log.api_key_id)}</td>
                      <td className="py-2.5 px-1 pr-4 font-mono text-xs">
                        {log.endpoint}
                        {log.is_mock && <span className="ml-2 text-orange">mock</span>}
                      </td>
                      <td className={`py-2.5 px-1 pr-4 font-semibold ${log.status_code >= 400 ? 'text-alert' : 'text-go'}`}>{log.status_code}</td>
                      <td className="py-2.5 px-1 pr-4 whitespace-nowrap">{(log.audio_bytes / 1024).toFixed(1)} KB</td>
                      <td className="py-2.5 px-1 pr-4 whitespace-nowrap">{(log.latency_ms / 1000).toFixed(1)} s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
