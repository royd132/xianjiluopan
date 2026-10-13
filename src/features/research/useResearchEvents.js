import { useCallback, useEffect, useRef } from 'react';

import { foresightClient } from '../../api/foresightClient';

const EVENT_CALLBACKS = {
  'agent.started': 'onAgentStarted',
  'agent.completed': 'onAgentCompleted',
  'gate.passed': 'onGatePassed',
  'task.completed': 'onTaskCompleted',
  'task.failed': 'onTaskFailed',
  'task.cancelled': 'onTaskCancelled',
};

// The runtime emits these three to end a run; the stream stops there, so the
// EventSource has to be closed on the same set of names or a cancelled task
// would leave a live connection behind.
const TERMINAL_EVENTS = new Set(['task.completed', 'task.failed', 'task.cancelled']);

export function useResearchEvents() {
  const sourceRef = useRef(null);

  const disconnect = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  const connect = useCallback((taskId, callbacks) => {
    disconnect();
    const source = foresightClient.openResearchEvents(taskId);
    sourceRef.current = source;

    Object.entries(EVENT_CALLBACKS).forEach(([eventName, callbackName]) => {
      source.addEventListener(eventName, (event) => {
        const isTerminal = TERMINAL_EVENTS.has(eventName);
        let payload = null;
        if (event.data) {
          try {
            payload = JSON.parse(event.data);
          } catch {
            payload = null;
          }
        }
        if (isTerminal) disconnect();
        callbacks[callbackName]?.(payload);
      });
    });

    source.onerror = () => callbacks.onConnectionError?.();
    return source;
  }, [disconnect]);

  useEffect(() => disconnect, [disconnect]);

  return { connect, disconnect };
}
