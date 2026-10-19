import { useEffect, useRef, useState } from 'react';
import { FileAudio, Mic, Square, Upload } from 'lucide-react';
import { api, errorMessage, post } from '../api.ts';
import { useLang } from '../i18n.tsx';
import type { Health, TranscriptionResult, WsStreamEvent } from '../shared/types.ts';
import { btnDanger, btnGhost, btnPrimary, CaptionLine, ErrorBox, Field, input, PageHeader, Panel, SectionTitle } from '../ui.tsx';

// shortcut: fixed-length segments can cut a word in half at the boundary; move to the provider's
// streaming API (gemini-3.5-transcribe-live) or silence-based cutting when latency/accuracy matter.
const SEGMENT_MS = 4000;

type LiveState = 'idle' | 'connecting' | 'live' | 'stopping';

const blobToBase64 = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });

export default function Playground() {
  const { t } = useLang();
  const [health, setHealth] = useState<Health | null>(null);
  const [engineId, setEngineId] = useState('');
  const [vocabulary, setVocabulary] = useState('');

  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const [consent, setConsent] = useState(false);
  const [live, setLive] = useState<LiveState>('idle');
  const [captions, setCaptions] = useState<WsStreamEvent[]>([]);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<number | undefined>(undefined);
  const stoppingRef = useRef(false);

  useEffect(() => {
    api<Health>('/v1/health').then((h) => {
      setHealth(h);
      setEngineId(h.engines.find((e) => e.engine_id === h.default_engine && e.configured)?.engine_id ?? h.engines.find((e) => e.configured)?.engine_id ?? '');
    });
    return () => teardown();
  }, []);

  const engine = health?.engines.find((e) => e.engine_id === engineId);
  const sendsToGoogle = engineId.startsWith('gemini');

  const transcribeFile = async () => {
    if (!file) return;
    setBusy(true);
    setFileError(null);
    setResult(null);
    const form = new FormData();
    form.append('file', file);
    form.append('engine_id', engineId);
    if (vocabulary.trim()) form.append('prompt_hint', vocabulary);
    try {
      setResult(await post<TranscriptionResult>('/v1/transcriptions', form));
    } catch (e) {
      setFileError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // Each segment is a separate MediaRecorder run, so every chunk is a complete, decodable file.
  // (A single recorder with a timeslice only puts the container header in the first chunk.)
  const recordSegment = (stream: MediaStream, ws: WebSocket) => {
    const recorder = new MediaRecorder(stream);
    const parts: Blob[] = [];
    recorder.ondataavailable = (e) => e.data.size && parts.push(e.data);
    recorder.onstop = async () => {
      const blob = new Blob(parts, { type: recorder.mimeType });
      if (blob.size && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'audio.chunk', audio_base64: await blobToBase64(blob), is_final: true }));
      }
      if (stoppingRef.current && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'session.complete' }));
    };
    recorder.start();
    recorderRef.current = recorder;
  };

  const teardown = () => {
    window.clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
  };

  const startLive = async () => {
    setLiveError(null);
    setLiveNotice(null);
    setCaptions([]);
    setLive('connecting');
    stoppingRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const { token } = await post<{ token: string }>('/v1/auth/session-token');
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${window.location.host}/v1/listen?token=${encodeURIComponent(token)}&engine_id=${encodeURIComponent(engineId)}`);
      wsRef.current = ws;

      ws.onmessage = (msg) => {
        const ev: WsStreamEvent = JSON.parse(msg.data);
        if (ev.type === 'session.started') {
          ws.send(JSON.stringify({ type: 'session.init', prompt_hint: vocabulary }));
          setLive('live');
          recordSegment(stream, ws);
          timerRef.current = window.setInterval(() => {
            recorderRef.current?.stop();
            recordSegment(stream, ws);
          }, SEGMENT_MS);
        } else if (ev.type === 'transcript.final' || ev.type === 'transcript.partial') {
          if (ev.text) setCaptions((c) => [...c, ev]);
          if (ev.warnings?.length) setLiveNotice(ev.warnings[0]);
        } else if (ev.type === 'error') {
          setLiveError(ev.error?.message ?? t('Stream error.', 'មានបញ្ហាក្នុងការផ្សាយ។'));
        } else if (ev.type === 'session.completed') {
          teardown();
          setLive('idle');
        }
      };
      ws.onclose = () => {
        teardown();
        setLive('idle');
      };
    } catch (e) {
      teardown();
      setLive('idle');
      setLiveError(e instanceof DOMException ? `${t('Microphone unavailable', 'មិនអាចប្រើមីក្រូហ្វូន')}: ${e.message}` : errorMessage(e));
    }
  };

  const stopLive = () => {
    setLive('stopping');
    stoppingRef.current = true;
    window.clearInterval(timerRef.current);
    recorderRef.current?.stop(); // its onstop sends the last chunk, then session.complete
    streamRef.current?.getTracks().forEach((track) => track.stop());
  };

  const stateLabel: Record<LiveState, string> = {
    idle: t('Ready', 'រួចរាល់'),
    connecting: t('Connecting', 'កំពុងភ្ជាប់'),
    live: t('Live', 'ផ្ទាល់'),
    stopping: t('Finishing', 'កំពុងបញ្ចប់'),
  };

  return (
    <>
      <PageHeader
        title={t('Playground', 'សាកល្បង')}
        subtitle={t('Test with your own voice or a recording. Requests count toward your usage.', 'សាកល្បងជាមួយសំឡេងរបស់អ្នក ឬឯកសារថត។ សំណើទាំងនេះរាប់ចូលក្នុងការប្រើប្រាស់របស់អ្នក។')}
      />

      <Panel>
        <div className="grid md:grid-cols-2 gap-5">
          <Field label={t('Speech engine', 'ម៉ាស៊ីនបំលែងសំឡេង')}>
            <select value={engineId} onChange={(e) => setEngineId(e.target.value)} disabled={live !== 'idle'} className={input}>
              {health?.engines.map((e) => (
                <option key={e.engine_id} value={e.engine_id} disabled={!e.configured}>
                  {e.display_name}
                  {!e.configured ? ` — ${t('not configured', 'មិនទាន់កំណត់')}` : ''}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('Words to expect (optional)', 'ពាក្យដែលរំពឹងថានឹងឮ (ស្រេចចិត្ត)')} hint={t('Comma-separated, e.g. GitHub, deploy, Zoom', 'បំបែកដោយក្បៀស ឧ. GitHub, deploy, Zoom')}>
            <input value={vocabulary} onChange={(e) => setVocabulary(e.target.value)} className={input} />
          </Field>
        </div>
        {health && !engine?.configured && (
          <ErrorBox
            message={t(
              'No working speech engine is configured on the server. Set GEMINI_API_KEY in .env and restart the API.',
              'មិនមានម៉ាស៊ីនបំលែងសំឡេងនៅលើ server ទេ។ សូមដាក់ GEMINI_API_KEY ក្នុង .env ហើយចាប់ផ្តើម API ឡើងវិញ។'
            )}
          />
        )}
        {engine?.is_mock && (
          <p className="text-sm text-orange">
            {t('The mock engine returns a fixed sentence and does not listen to your audio.', 'ម៉ាស៊ីនសាកល្បង (mock) ផ្តល់ប្រយោគថេរ ហើយមិនស្តាប់សំឡេងរបស់អ្នកទេ។')}
          </p>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <Panel raised className="lg:col-span-7">
          <div className="flex items-center justify-between gap-4">
            <SectionTitle>{t('Live captions', 'អក្សររត់ផ្ទាល់')}</SectionTitle>
            <span className="k-label flex items-center gap-2" aria-live="polite">
              <span className={`w-2 h-2 rounded-full ${live === 'live' ? 'bg-orange motion-safe:animate-pulse' : live === 'idle' ? 'bg-tarmac' : 'bg-silver'}`} aria-hidden />
              {stateLabel[live]}
            </span>
          </div>
          <label className="flex items-start gap-3 text-sm text-silver cursor-pointer">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 w-4 h-4" />
            <span>
              {t('I agree to send my microphone audio to Kethra for captioning.', 'ខ្ញុំយល់ព្រមផ្ញើសំឡេងពីមីក្រូហ្វូនរបស់ខ្ញុំទៅ Kethra ដើម្បីបង្កើតអក្សររត់។')}{' '}
              {sendsToGoogle &&
                t(
                  "This engine forwards audio to Google's Gemini API; on Gemini's free tier Google may use it to improve its products.",
                  'ម៉ាស៊ីននេះបញ្ជូនសំឡេងទៅ Gemini API របស់ Google។ ក្នុងកម្រិតឥតគិតថ្លៃ Google អាចប្រើវាដើម្បីកែលម្អផលិតផលរបស់ខ្លួន។'
                )}{' '}
              {t('Kethra does not store the audio.', 'Kethra មិនរក្សាទុកសំឡេងទេ។')}
            </span>
          </label>
          {live === 'idle' ? (
            <button type="button" onClick={startLive} disabled={!consent || !engine?.configured} className={btnPrimary}>
              <Mic className="w-4 h-4" /> {t('Start microphone', 'បើកមីក្រូហ្វូន')}
            </button>
          ) : (
            <button type="button" onClick={stopLive} disabled={live !== 'live'} className={btnDanger}>
              <Square className="w-4 h-4" />{' '}
              {live === 'stopping' ? t('Finishing…', 'កំពុងបញ្ចប់…') : live === 'connecting' ? t('Connecting…', 'កំពុងភ្ជាប់…') : t('Stop', 'បញ្ឈប់')}
            </button>
          )}
          <ErrorBox message={liveError} />
          <div aria-live="polite" className="k-track min-h-48 max-h-96 overflow-y-auto bg-graphite border border-track-2 p-5 space-y-3">
            {captions.length === 0 ? (
              <p className="text-tarmac">
                {live === 'live'
                  ? t(`Listening… captions arrive every ${SEGMENT_MS / 1000} seconds.`, `កំពុងស្តាប់… អក្សររត់មកដល់រៀងរាល់ ${SEGMENT_MS / 1000} វិនាទី។`)
                  : t('Captions will appear here.', 'អក្សររត់នឹងបង្ហាញនៅទីនេះ។')}
              </p>
            ) : (
              captions.map((c) => (
                <div key={c.sequence} className="flex items-baseline gap-3">
                  <CaptionLine text={c.text ?? ''} animate stepMs={60} className="text-xl text-decal" />
                  {c.is_mock_engine && <span className="k-label !text-orange shrink-0">mock</span>}
                </div>
              ))
            )}
          </div>
          {liveNotice && <p className="text-xs text-tarmac">{liveNotice}</p>}
        </Panel>

        <Panel className="lg:col-span-5">
          <div className="flex items-center justify-between">
            <SectionTitle>{t('Transcribe a file', 'បំលែងឯកសារ')}</SectionTitle>
            <FileAudio className="w-5 h-5 text-tarmac" aria-hidden />
          </div>
          {/* The native file input's own text never translates, so it is hidden and driven by a label. */}
          <div className="space-y-1.5">
            <span className="k-label block">{t('Audio file', 'ឯកសារសំឡេង')}</span>
            <div className="flex items-center gap-3 bg-graphite border border-track-2 p-1.5 focus-within:border-acid">
              <label className={`${btnGhost} !min-h-9 !px-3 !text-xs`}>
                <input type="file" accept="audio/*,video/webm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="sr-only" />
                {t('Choose a file', 'ជ្រើសឯកសារ')}
              </label>
              <span className="text-sm text-silver truncate">{file?.name ?? t('No file chosen', 'មិនទាន់ជ្រើសឯកសារ')}</span>
            </div>
            <span className="block text-xs text-tarmac">{t('WAV, MP3, WebM, OGG, M4A or FLAC, up to 25 MB.', 'WAV, MP3, WebM, OGG, M4A ឬ FLAC រហូតដល់ 25 MB។')}</span>
          </div>
          <button type="button" onClick={transcribeFile} disabled={!file || busy || !engine?.configured} className={btnPrimary}>
            <Upload className="w-4 h-4" /> {busy ? t('Transcribing…', 'កំពុងបំលែង…') : t('Transcribe', 'បំលែងជាអក្សរ')}
          </button>
          <ErrorBox message={fileError} />
          {result && (
            <div className="space-y-3 border-t border-track-2 pt-4">
              {result.is_mock_engine && <p className="text-sm text-orange">{result.warnings[0]}</p>}
              <div className="bg-graphite border border-track-2 p-4">
                {result.normalized_transcript ? (
                  <CaptionLine text={result.normalized_transcript} className="text-lg text-decal" />
                ) : (
                  <p className="text-tarmac">{t('No speech detected.', 'រកមិនឃើញការនិយាយទេ។')}</p>
                )}
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm tabular-nums">
                <dt className="k-label">{t('Khmer characters', 'តួអក្សរខ្មែរ')}</dt>
                <dd className="text-decal">{result.normalization.khmer_char_count}</dd>
                <dt className="k-label">{t('English words', 'ពាក្យ English')}</dt>
                <dd className="text-decal">{result.normalization.latin_word_count}</dd>
                <dt className="k-label">{t('Language switches', 'ការប្តូរភាសា')}</dt>
                <dd className="text-decal">{result.normalization.switch_points}</dd>
                <dt className="k-label">{t('Time', 'រយៈពេល')}</dt>
                <dd className="text-decal">{(result.processing_latency_ms / 1000).toFixed(1)} s</dd>
              </dl>
              {result.raw_transcript !== result.normalized_transcript && (
                <details className="text-sm text-silver">
                  <summary className="cursor-pointer hover:text-decal">{t('Raw engine output', 'លទ្ធផលដើមពីម៉ាស៊ីន')}</summary>
                  <p className="mt-2 text-decal">{result.raw_transcript}</p>
                </details>
              )}
              {!result.is_mock_engine &&
                result.warnings.map((w) => (
                  <p key={w} className="text-xs text-tarmac">
                    {w}
                  </p>
                ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
