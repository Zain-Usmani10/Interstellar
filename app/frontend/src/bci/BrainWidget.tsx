import { useEffect, useRef, useState } from 'react';

type Context = {
  input_session_id: string; context_id: string; revision: number;
  allowed_targets: string[]; enabled: boolean;
};
export type DecisionResult = {
  event_id: string; accepted: boolean; reason: string; new_context_revision: number;
};
type Status = { type: 'status'; source: string; label: string; state: string; reason: string; context: Context };
type Props = {
  enabled?: boolean;
  bridgeUrl?: string;
  onDecision?: (result: DecisionResult) => void;
  onActiveChange?: (active: boolean) => void;
};

/** Optional insertion point. Core selection events, not classifier scores, open cards. */
export function BrainWidget({ enabled = false, bridgeUrl = 'ws://127.0.0.1:8766', onDecision, onActiveChange }: Props) {
  const [token, setToken] = useState('');
  const [status, setStatus] = useState<Status | null>(null);
  const [message, setMessage] = useState('Brain extension disabled');
  const [lastDecision, setLastDecision] = useState('No core decision yet');
  const [frequency, setFrequency] = useState('10');
  const [active, setActive] = useState(false);
  const [arming, setArming] = useState(false);
  const waitingForArm = useRef(false);
  const socket = useRef<WebSocket | null>(null);
  const activeContext = useRef<Context | null>(null);
  const callbacks = useRef({ onDecision, onActiveChange });
  callbacks.current = { onDecision, onActiveChange };

  function stop() {
    waitingForArm.current = false;
    setArming(false);
    activeContext.current = null;
    setActive(false);
    if (socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify({ type: 'stop', schema_version: 1 }));
    }
  }

  useEffect(() => {
    callbacks.current.onActiveChange?.(active);
  }, [active]);

  useEffect(() => {
    if (!enabled) {
      socket.current?.close();
      socket.current = null;
      waitingForArm.current = false;
      setArming(false);
      activeContext.current = null;
      setActive(false);
      setStatus(null);
    }
    return () => {
      socket.current?.close();
      activeContext.current = null;
      callbacks.current.onActiveChange?.(false);
    };
  }, [enabled, bridgeUrl]);

  useEffect(() => {
    if (!active) return;
    let frame = 0, sequence = 0, last = 0, sent = 0, largest = 0, request = 0;
    function tick(now: number) {
      const context = activeContext.current;
      if (!context) return;
      const gap = last ? now - last : 0;
      largest = Math.max(largest, gap);
      last = now;
      frame += 1;
      if (gap > 35 || document.hidden || !document.hasFocus()) {
        stop();
        setMessage('Stopped: tab, focus or frame timing changed. Rearm explicitly.');
        return;
      }
      if (now - sent >= 200 && socket.current?.readyState === WebSocket.OPEN) {
        socket.current.send(JSON.stringify({
          type: 'stimulus_state', schema_version: 1, context_id: context.context_id,
          context_revision: context.revision, sequence: sequence++, active: true,
          visible: true, focused: true, frame_count: frame, dropped_frames: 0,
          largest_frame_gap_ms: largest,
          // Synthetic references only: this milestone deliberately does not flash targets.
          effective_frequencies_hz: [10, 15],
        }));
        sent = now;
      }
      request = requestAnimationFrame(tick);
    }
    const hide = () => { if (document.hidden) stop(); };
    window.addEventListener('blur', stop);
    document.addEventListener('visibilitychange', hide);
    request = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(request);
      window.removeEventListener('blur', stop);
      document.removeEventListener('visibilitychange', hide);
    };
  }, [active]);

  function connect() {
    const url = new URL(bridgeUrl);
    if (url.protocol !== 'ws:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
      setMessage('Brain bridge must be loopback ws://');
      return;
    }
    socket.current?.close();
    setStatus(null);
    setMessage('Connecting…');
    const ws = new WebSocket(bridgeUrl);
    socket.current = ws;
    ws.onopen = () => { ws.send(JSON.stringify({ token })); setToken(''); };
    ws.onmessage = (event) => {
      if (socket.current !== ws) return;
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'status') {
          if (data.source !== 'synthetic') { ws.close(); return; }
          setStatus(data);
          setMessage(`${data.state}: ${data.reason}`);
          const previous = activeContext.current;
          if (waitingForArm.current && previous && data.state === 'ARMED' && data.reason === 'operator_rearm'
              && previous.revision === data.context.revision && previous.context_id === data.context.context_id) {
            waitingForArm.current = false;
            setArming(false);
            setActive(true);
          }
          if (waitingForArm.current) {
            if (previous && (previous.revision !== data.context.revision || previous.context_id !== data.context.context_id
                || ['context_mismatch', 'invalid_message'].includes(data.reason))) stop();
            return;
          }
          if (previous && (data.state !== 'ARMED' || previous.revision !== data.context.revision || previous.context_id !== data.context.context_id)) {
            activeContext.current = null;
            setActive(false);
          }
        } else if (data.type === 'decision_result') {
          setLastDecision(`${data.result.accepted ? 'Core accepted' : 'Core rejected'}: ${data.result.reason}`);
          callbacks.current.onDecision?.(data.result);
          activeContext.current = null;
          setActive(false);
        }
      } catch { ws.close(); }
    };
    ws.onclose = () => {
      if (socket.current !== ws) return;
      activeContext.current = null;
      waitingForArm.current = false;
      setArming(false);
      setActive(false);
      setStatus(null);
      setMessage('Brain disconnected. Ordinary controls remain available.');
    };
    ws.onerror = () => ws.close();
  }

  function arm() {
    const context = status?.context;
    if (!context?.enabled || context.allowed_targets.length !== 2 || socket.current?.readyState !== WebSocket.OPEN) return;
    socket.current.send(JSON.stringify({ type: 'configure', schema_version: 1,
      input_session_id: context.input_session_id, context_id: context.context_id,
      context_revision: context.revision, targets: context.allowed_targets,
      frequencies_hz: [10, 15], synthetic_frequency_hz: frequency === 'none' ? null : Number(frequency),
    }));
    activeContext.current = context;
    waitingForArm.current = true;
    setArming(true);
  }

  if (!enabled) return null;
  return <section aria-label="Optional synthetic brain input">
    <strong>SYNTHETIC EEG — NO LIVE BRAIN INPUT</strong>
    <p>Generated samples pass through the decoder and core validation. No flashing. Rearm for each selection.</p>
    {!status && <><label>Temporary launch token <input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} /></label>
      <button onClick={connect} disabled={!token}>Connect brain process</button></>}
    {status && <>
      <label>Synthetic signal <select value={frequency} disabled={active || arming} onChange={e => setFrequency(e.target.value)}>
        <option value="10">10 Hz → {status.context.allowed_targets[0]}</option>
        <option value="15">15 Hz → {status.context.allowed_targets[1]}</option>
        <option value="none">Noise / no target</option>
      </select></label>
      <button onClick={arm} disabled={active || arming || !status.context.enabled || status.state === 'DECISION_SENT'}>Arm one selection</button>
      <button onClick={stop}>Stop brain input</button>
      <button onClick={() => socket.current?.close()}>Disconnect</button>
    </>}
    <p role="status">{message}</p>
    <p>{lastDecision}</p>
  </section>;
}

export default BrainWidget;
