import type { ReactNode } from 'react';
import { useLang } from '../i18n.tsx';
import { Code, PageHeader } from '../ui.tsx';

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="space-y-4 scroll-mt-24 pt-2">
      <h2 className="k-display text-2xl text-decal">{title}</h2>
      <div className="space-y-4 text-silver leading-relaxed max-w-[70ch]">{children}</div>
    </section>
  );
}

const C = ({ children }: { children: ReactNode }) => <code className="font-mono text-[0.875em] text-acid [overflow-wrap:anywhere]">{children}</code>;

export default function Docs() {
  const { t } = useLang();

  const sections: [string, string][] = [
    ['quickstart', t('Quick start', 'ចាប់ផ្តើមរហ័ស')],
    ['auth', t('Authentication', 'ការផ្ទៀងផ្ទាត់')],
    ['transcriptions', 'POST /v1/transcriptions'],
    ['streaming', t('Live captions', 'អក្សររត់ផ្ទាល់')],
    ['audio', t('Formats & limits', 'ទម្រង់ និងដែនកំណត់')],
    ['errors', t('Errors', 'កំហុស')],
    ['sdks', 'SDKs'],
    ['privacy', t('Privacy', 'ឯកជនភាព')],
  ];

  const errors: [string, string, string][] = [
    ['400', 'invalid_request, missing_audio, empty_audio, unsupported_engine', t('Fix the request; retrying it unchanged will fail again.', 'កែសំណើ ព្រោះការផ្ញើដដែលនឹងបរាជ័យម្តងទៀត។')],
    ['401', 'unauthorized', t('Missing, invalid or revoked API key.', 'API key បាត់ មិនត្រឹមត្រូវ ឬត្រូវបានដកសិទ្ធិ។')],
    ['403', 'insufficient_scope', t('The key lacks the permission this endpoint needs.', 'Key នេះគ្មានសិទ្ធិដែល endpoint នេះត្រូវការ។')],
    ['413', 'payload_too_large', t('The file is over the size limit.', 'ឯកសារធំជាងដែនកំណត់។')],
    ['415', 'unsupported_media_type', t('The file is not a supported audio format.', 'ឯកសារមិនមែនជាទម្រង់សំឡេងដែលគាំទ្រ។')],
    ['429', 'rate_limited', t('Too many requests. Wait a minute, then retry.', 'សំណើច្រើនពេក។ រង់ចាំមួយនាទី ហើយសាកម្តងទៀត។')],
    ['502', 'speech_engine_error', t('The speech engine failed. Safe to retry.', 'ម៉ាស៊ីនបំលែងសំឡេងមានបញ្ហា។ អាចសាកម្តងទៀតបាន។')],
    ['503', 'engine_not_configured', t('That engine is not available on this server.', 'ម៉ាស៊ីននោះមិនមាននៅលើ server នេះទេ។')],
    ['504', 'speech_engine_timeout', t('The engine took over 30 seconds. Safe to retry.', 'ម៉ាស៊ីនប្រើពេលលើស ៣០ វិនាទី។ អាចសាកម្តងទៀតបាន។')],
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
      <nav aria-label={t('On this page', 'នៅលើទំព័រនេះ')} className="lg:col-span-3 lg:sticky lg:top-24 self-start">
        <ul className="flex lg:flex-col gap-x-5 gap-y-2 overflow-x-auto lg:border-l lg:border-track-2 text-sm">
          {sections.map(([id, label]) => (
            <li key={id}>
              <a href={`#/docs`} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }); }} className="block whitespace-nowrap lg:pl-4 py-1 text-silver hover:text-acid">
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="lg:col-span-9 space-y-14 min-w-0">
        <PageHeader
          title={t('Kethra API', 'Kethra API')}
          subtitle={t(
            'Speech-to-text for Khmer, English, and both mixed in one sentence. Every path starts with /v1 on your Kethra host.',
            'Speech-to-text សម្រាប់ខ្មែរ English និងការនិយាយលាយគ្នាក្នុងប្រយោគតែមួយ។ គ្រប់ path ចាប់ផ្តើមដោយ /v1 នៅលើ host Kethra របស់អ្នក។'
          )}
        />

        <Section id="quickstart" title={t('Quick start', 'ចាប់ផ្តើមរហ័ស')}>
          <ol className="list-decimal pl-5 space-y-1.5 marker:text-acid">
            <li>{t('Create an account, then open API keys.', 'បង្កើតគណនី រួចបើកទំព័រ API keys។')}</li>
            <li>{t('Create a key and copy it. It is shown once.', 'បង្កើត key ហើយចម្លងវា។ វាបង្ហាញតែម្តង។')}</li>
            <li>{t('Send an audio file:', 'ផ្ញើឯកសារសំឡេង៖')}</li>
          </ol>
          <Code>{`curl https://<your-kethra-host>/v1/transcriptions \\
  -H "Authorization: Bearer $KETHRA_API_KEY" \\
  -F "file=@meeting.wav" \\
  -F "prompt_hint=GitHub, deploy"`}</Code>
        </Section>

        <Section id="auth" title={t('Authentication', 'ការផ្ទៀងផ្ទាត់')}>
          <p>
            {t('Send your key in the header', 'ផ្ញើ key របស់អ្នកក្នុង header')} <C>Authorization: Bearer kth_live_…</C>.{' '}
            {t('Keys carry permissions', 'Keys មានសិទ្ធិ')} (<C>transcriptions:write</C>, <C>stream:listen</C>, <C>usage:read</C>){' '}
            {t('and can be revoked at any time.', 'ហើយអាចដកសិទ្ធិបានគ្រប់ពេល។')}
          </p>
          <p>
            <strong className="text-decal">{t('Keep keys on your server.', 'ទុក keys នៅលើ server របស់អ្នក។')}</strong>{' '}
            {t(
              'Anything shipped inside a mobile app, desktop app or web page can be extracted. For those, your server calls',
              'អ្វីៗដែលដាក់ក្នុង app ទូរស័ព្ទ app កុំព្យូទ័រ ឬទំព័រវេប អាចត្រូវគេទាញយកបាន។ សម្រាប់ករណីនោះ server របស់អ្នកហៅ'
            )}{' '}
            <C>POST /v1/auth/session-token</C>{' '}
            {t(
              'and hands the token to the app. It works once, for one live session, and expires after 5 minutes.',
              'ហើយផ្តល់ token ទៅ app។ វាប្រើបានតែម្តង សម្រាប់វគ្គផ្ទាល់មួយ ហើយផុតកំណត់ក្រោយ ៥ នាទី។'
            )}
          </p>
          <Code>{`curl -X POST https://<your-kethra-host>/v1/auth/session-token \\
  -H "Authorization: Bearer $KETHRA_API_KEY"

{ "token": "kth_sess_…", "session_id": "sess_…", "expires_at": "…", "single_use": true }`}</Code>
        </Section>

        <Section id="transcriptions" title="POST /v1/transcriptions">
          <p>
            {t('Multipart upload. Fields:', 'បង្ហោះជា multipart។ Fields៖')} <C>file</C> {t('(required)', '(ចាំបាច់)')}, <C>engine_id</C>{' '}
            {t('(optional)', '(ស្រេចចិត្ត)')}, <C>prompt_hint</C>{' '}
            {t('(optional comma-separated words the speaker may use). Needs', '(ពាក្យដែលអ្នកនិយាយអាចប្រើ បំបែកដោយក្បៀស ស្រេចចិត្ត)។ ត្រូវការ')} <C>transcriptions:write</C>.
          </p>
          <Code>{`{
  "id": "tr_…",
  "status": "completed",
  "engine_id": "gemini-3.5-transcribe",
  "is_mock_engine": false,
  "raw_transcript": "ខ្ញុំនឹងsend it to you tomorrow",
  "normalized_transcript": "ខ្ញុំនឹង send it to you tomorrow",
  "normalization": { "switch_points": 1, "is_code_switched": true, "applied_rules": ["script_boundary_spacing"] },
  "processing_latency_ms": 1840,
  "warnings": ["…"]
}`}</Code>
          <p>
            <C>raw_transcript</C>{' '}
            {t('is exactly what the engine returned.', 'គឺជាអ្វីដែលម៉ាស៊ីនបានផ្តល់មកពិតៗ។')} <C>normalized_transcript</C>{' '}
            {t(
              'only fixes Unicode form and spacing between Khmer and English; it never changes or translates words. Always check',
              'គ្រាន់តែកែទម្រង់ Unicode និងចន្លោះរវាងខ្មែរ និង English ប៉ុណ្ណោះ មិនដែលប្តូរ ឬបកប្រែពាក្យឡើយ។ ត្រូវពិនិត្យ'
            )}{' '}
            <C>is_mock_engine</C>
            {t(': mock output is a fixed test sentence.', '៖ លទ្ធផល mock គឺជាប្រយោគសាកល្បងថេរ។')}
          </p>
        </Section>

        <Section id="streaming" title={t('Live captions (WebSocket)', 'អក្សររត់ផ្ទាល់ (WebSocket)')}>
          <p>
            {t('Connect to', 'ភ្ជាប់ទៅ')} <C>wss://&lt;host&gt;/v1/listen?token=&lt;session token&gt;</C>.{' '}
            {t('Server-to-server clients may send the', 'Client ពី server ទៅ server អាចផ្ញើ header')} <C>Authorization: Bearer</C>{' '}
            {t('header instead. API keys are never accepted in the URL.', 'ជំនួសវិញ។ API keys មិនត្រូវបានទទួលក្នុង URL ឡើយ។')}
          </p>
          <p>{t('Messages you send (JSON text frames):', 'សារដែលអ្នកផ្ញើ (JSON text frames)៖')}</p>
          <Code>{`{ "type": "session.init", "engine_id": "gemini-3.5-transcribe", "prompt_hint": "Zoom, deploy" }
{ "type": "audio.chunk", "audio_base64": "<a complete audio file, e.g. 3-5 s of WebM>", "is_final": true }
{ "type": "session.complete" }`}</Code>
          <p>{t('Events you receive:', 'ព្រឹត្តិការណ៍ដែលអ្នកទទួល៖')}</p>
          <Code>{`{ "type": "session.started", "session_id": "sess_…", "engine_id": "…" }
{ "type": "transcript.final", "sequence": 1, "text": "…", "raw_text": "…", "latency_ms": 900 }
{ "type": "error", "error": { "code": "rate_limited", "message": "…", "retryable": true } }
{ "type": "session.completed" }`}</Code>
          <p>
            {t(
              'Each audio.chunk must be a complete, playable file, not a raw fragment. Chunks are processed in order. Sessions close after 60 seconds without messages or 10 minutes in total; reconnect with a new session token. Word-by-word partial results are not available yet.',
              'audio.chunk នីមួយៗត្រូវតែជាឯកសារពេញលេញដែលអាចចាក់បាន មិនមែនជាបំណែកទេ។ Chunks ត្រូវបានដំណើរការតាមលំដាប់។ វគ្គនឹងបិទក្រោយ ៦០ វិនាទីគ្មានសារ ឬសរុប ១០ នាទី។ សូមភ្ជាប់ឡើងវិញដោយ session token ថ្មី។ លទ្ធផលមួយពាក្យម្តងៗមិនទាន់មានទេ។'
            )}
          </p>
        </Section>

        <Section id="audio" title={t('Formats & limits', 'ទម្រង់ និងដែនកំណត់')}>
          <ul className="list-disc pl-5 space-y-1.5 marker:text-acid">
            <li>{t('Formats: WAV, MP3, WebM, OGG, M4A/MP4, FLAC, detected from the file contents.', 'ទម្រង់៖ WAV, MP3, WebM, OGG, M4A/MP4, FLAC ដែលត្រូវបានរកឃើញពីខ្លឹមសារឯកសារ។')}</li>
            <li>{t('Uploads up to 25 MB. Live chunks up to 5 MB each.', 'បង្ហោះបានរហូតដល់ 25 MB។ Chunk ផ្ទាល់នីមួយៗរហូតដល់ 5 MB។')}</li>
            <li>{t('30 speech requests per minute per account; each live chunk counts as one.', 'សំណើ ៣០ ក្នុងមួយនាទីសម្រាប់គណនីនីមួយៗ ហើយ chunk ផ្ទាល់នីមួយៗរាប់ជាមួយ។')}</li>
            <li>{t('Up to 2 live sessions open at once per account.', 'វគ្គផ្ទាល់អតិបរមា ២ ក្នុងពេលតែមួយសម្រាប់គណនីនីមួយៗ។')}</li>
          </ul>
        </Section>

        <Section id="errors" title={t('Errors', 'កំហុស')}>
          <p>{t('Every error has the same shape:', 'កំហុសទាំងអស់មានទម្រង់ដូចគ្នា៖')}</p>
          <Code>{`{ "error": { "code": "rate_limited", "message": "Too many requests. Try again in a minute.", "retryable": true } }`}</Code>
          <div className="overflow-x-auto border border-track-2">
            <table className="w-full text-left text-sm">
              <thead className="k-label border-b border-track-2 bg-pit">
                <tr>
                  <th scope="col" className="py-2.5 px-3 font-[inherit]">HTTP</th>
                  <th scope="col" className="py-2.5 px-3 font-[inherit]">code</th>
                  <th scope="col" className="py-2.5 px-3 font-[inherit]">{t('Meaning', 'អត្ថន័យ')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-track-2">
                {errors.map(([status, code, meaning]) => (
                  <tr key={status}>
                    <td className="py-2.5 px-3 font-mono text-decal">{status}</td>
                    <td className="py-2.5 px-3 font-mono text-xs text-acid">{code}</td>
                    <td className="py-2.5 px-3">{meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section id="sdks" title="SDKs">
          <p>
            {t(
              'Official SDKs (Python first, then Dart/Flutter and TypeScript) are not released yet. Until then, any HTTP and WebSocket library works with the endpoints above. The interactive API reference is at /docs on the API server.',
              'SDK ផ្លូវការ (Python មុន បន្ទាប់មក Dart/Flutter និង TypeScript) មិនទាន់ចេញទេ។ មុននោះ អ្នកអាចប្រើ library HTTP និង WebSocket ណាមួយជាមួយ endpoints ខាងលើ។ ឯកសារ API អន្តរកម្មមាននៅ /docs លើ API server។'
            )}
          </p>
        </Section>

        <Section id="privacy" title={t('Privacy', 'ឯកជនភាព')}>
          <ul className="list-disc pl-5 space-y-1.5 marker:text-acid">
            <li>{t('Kethra never stores audio or transcripts. It keeps request metadata only: time, size, status, latency.', 'Kethra មិនដែលរក្សាទុកសំឡេង ឬអត្ថបទទេ។ វារក្សាតែព័ត៌មានសំណើ៖ ពេលវេលា ទំហំ ស្ថានភាព និងពេលឆ្លើយតប។')}</li>
            <li>
              {t(
                "The gemini-3.5-transcribe engine sends audio to Google. On Gemini's free tier Google may use it to improve its products. Get consent from the people you record.",
                'ម៉ាស៊ីន gemini-3.5-transcribe ផ្ញើសំឡេងទៅ Google។ ក្នុងកម្រិតឥតគិតថ្លៃ Google អាចប្រើវាដើម្បីកែលម្អផលិតផលរបស់ខ្លួន។ សូមសុំការយល់ព្រមពីអ្នកដែលអ្នកថតសំឡេង។'
              )}
            </li>
          </ul>
        </Section>
      </div>
    </div>
  );
}
