import { useCallback, useEffect, useRef } from 'react';

import { foresightClient } from '../../api/foresightClient';

const EVENT_CALLBACKS = {
  'agent.started': 'onAgentStarted',
  'agent.completed': 'onAgentCompleted',
  'gate.passed': 'onGatePassed',
  'task.completed': 'onTaskCompleted',
  'task.failed': 'onTaskFailed',
};

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
        const isTerminal = eventName === 'task.completed' || eventName === 'task.failed';
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
