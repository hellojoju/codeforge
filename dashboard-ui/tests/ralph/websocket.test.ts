import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { RalphEvent, RalphEventType } from '@/lib/ralph-types';
import { RalphWebSocket } from '@/lib/ralph-websocket';

// Create a proper WebSocket mock class
function createMockWebSocketClass() {
  const instances: MockWebSocketInstance[] = [];

  class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    url: string;
    readyState = 0;
    onopen: ((event?: Event) => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onclose: ((event?: CloseEvent) => void) | null = null;
    onerror: ((event?: Event) => void) | null = null;

    send = vi.fn();
    close = vi.fn();

    constructor(url: string) {
      this.url = url;
      instances.push(this);
    }
  }

  return { MockWebSocket, instances };
}

type MockWebSocketInstance = {
  url: string;
  readyState: number;
  onopen: ((event?: Event) => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: ((event?: CloseEvent) => void) | null;
  onerror: ((event?: Event) => void) | null;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
};

describe('RalphWebSocket', () => {
  let ws: RalphWebSocket;
  let mockInstances: MockWebSocketInstance[] = [];

  beforeEach(() => {
    vi.useFakeTimers();

    const { MockWebSocket, instances } = createMockWebSocketClass();
    mockInstances = instances;

    // @ts-expect-error - mocking global WebSocket
    global.WebSocket = MockWebSocket;

    ws = new RalphWebSocket('http://localhost:18753');
  });

  afterEach(() => {
    ws.disconnect();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe('constructor', () => {
    it('should convert http URL to ws URL', () => {
      const ws1 = new RalphWebSocket('http://localhost:8000');
      ws1.connect();
      expect(mockInstances.length).toBe(1);
      expect(mockInstances[0].url).toBe('ws://localhost:8000/');
    });

    it('should convert https URL to wss URL', () => {
      const ws1 = new RalphWebSocket('https://api.example.com');
      ws1.connect();
      expect(mockInstances[0].url).toBe('wss://api.example.com/');
    });

    it('should handle URL with trailing slash', () => {
      const ws1 = new RalphWebSocket('http://localhost:8000/');
      ws1.connect();
      expect(mockInstances[0].url).toBe('ws://localhost:8000/');
    });

    it('should initialize with sequence 0', () => {
      expect(ws.sequence).toBe(0);
    });
  });

  describe('connect', () => {
    it('should establish WebSocket connection', () => {
      ws.connect();
      expect(mockInstances.length).toBe(1);
      expect(mockInstances[0].url).toBe('ws://localhost:18753/');
    });

    it('should include after_sequence parameter on reconnect', () => {
      ws.connect();

      // Simulate receiving events to increment sequence
      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(ws.sequence).toBe(1);

      // Disconnect and trigger reconnect
      mockInstances[0].onclose?.();
      vi.advanceTimersByTime(1000);

      // Check that reconnect uses after_sequence
      expect(mockInstances.length).toBe(2);
      expect(mockInstances[1].url).toBe('ws://localhost:18753/?after_sequence=1');
    });

    it('should not include after_sequence on first connect', () => {
      ws.connect();
      expect(mockInstances[0].url).not.toContain('after_sequence');
    });
  });

  describe('disconnect', () => {
    it('should close WebSocket connection', () => {
      ws.connect();
      ws.disconnect();
      expect(mockInstances[0].close).toHaveBeenCalled();
    });

    it('should prevent automatic reconnection after disconnect', () => {
      ws.connect();
      ws.disconnect();

      mockInstances[0].onclose?.();
      vi.advanceTimersByTime(30000);

      // Should not attempt to reconnect
      expect(mockInstances.length).toBe(1); // Only initial connect
    });
  });

  describe('event handling', () => {
    it('should call registered handlers when events are received', () => {
      const handler = vi.fn();
      ws.on(handler);
      ws.connect();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: { title: 'Test Work' },
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: 'agent-1',
        tags: ['test'],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(handler).toHaveBeenCalledWith(expect.objectContaining({ event_id: 'evt-1', sequence: 1 }));
    });

    it('should support multiple handlers', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      ws.on(handler1);
      ws.on(handler2);
      ws.connect();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(handler1).toHaveBeenCalled();
      expect(handler2).toHaveBeenCalled();
    });

    it('should return unsubscribe function', () => {
      const handler = vi.fn();
      const unsubscribe = ws.on(handler);
      ws.connect();

      unsubscribe();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 1,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(handler).not.toHaveBeenCalled();
    });

    it('should deduplicate events with sequence <= lastSequence', () => {
      const handler = vi.fn();
      ws.on(handler);
      ws.connect();

      const event1: RalphEvent = {
        event_id: 'evt-1',
        sequence: 5,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event1) });
      expect(handler).toHaveBeenCalledTimes(1);
      expect(ws.sequence).toBe(5);

      // Send duplicate event with lower sequence
      const duplicateEvent: RalphEvent = {
        ...event1,
        event_id: 'evt-2',
        sequence: 3,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(duplicateEvent) });
      expect(handler).toHaveBeenCalledTimes(1); // Still 1, not 2
    });

    it('should reset sequence when receiving sequence_reset event', () => {
      const handler = vi.fn();
      ws.on(handler);
      ws.connect();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 10,
        event_type: 'heartbeat' as RalphEventType,
        work_id: null,
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'system',
        agent_name: null,
        tags: [],
        sequence_reset: true,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(ws.sequence).toBe(0);
    });

    it('should update sequence for events with higher sequence numbers', () => {
      ws.connect();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 42,
        event_type: 'work_unit_status_changed' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(ws.sequence).toBe(42);
    });

    it('should handle malformed messages gracefully', () => {
      const handler = vi.fn();
      ws.on(handler);
      ws.connect();

      // Send invalid JSON
      mockInstances[0].onmessage?.({ data: 'not valid json' });
      expect(handler).not.toHaveBeenCalled();

      // Send event without required fields
      mockInstances[0].onmessage?.({ data: JSON.stringify({ invalid: 'data' }) });
      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('reconnection with exponential backoff', () => {
    it('should reconnect after connection closes', () => {
      ws.connect();
      expect(mockInstances.length).toBe(1);

      mockInstances[0].onclose?.();
      vi.advanceTimersByTime(1000);

      expect(mockInstances.length).toBe(2);
    });

    it('should use exponential backoff (1s, 2s, 4s, 8s, 16s, max 30s)', () => {
      ws.connect();

      const delays = [1000, 2000, 4000, 8000, 16000, 30000, 30000];

      for (const expectedDelay of delays) {
        const currentInstance = mockInstances[mockInstances.length - 1];
        currentInstance.onclose?.();
        vi.advanceTimersByTime(expectedDelay - 1);
        const callCountBefore = mockInstances.length;

        vi.advanceTimersByTime(1);
        const callCountAfter = mockInstances.length;

        expect(callCountAfter).toBe(callCountBefore + 1);
      }
    });

    it('should reset backoff after successful connection', () => {
      ws.connect();

      // First disconnect - should reconnect after 1s
      mockInstances[0].onclose?.();
      vi.advanceTimersByTime(1000);
      expect(mockInstances.length).toBe(2);

      // Simulate successful connection
      mockInstances[1].onopen?.();

      // Second disconnect - should reconnect after 1s (not 2s)
      mockInstances[1].onclose?.();
      vi.advanceTimersByTime(1000);
      expect(mockInstances.length).toBe(3);
    });

    it('should include after_sequence in reconnect URL', () => {
      ws.connect();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 5,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });

      mockInstances[0].onclose?.();
      vi.advanceTimersByTime(1000);

      expect(mockInstances[1].url).toBe('ws://localhost:18753/?after_sequence=5');
    });
  });

  describe('sequence getter', () => {
    it('should return current sequence number', () => {
      expect(ws.sequence).toBe(0);

      ws.connect();

      const event: RalphEvent = {
        event_id: 'evt-1',
        sequence: 100,
        event_type: 'work_unit_created' as RalphEventType,
        work_id: 'work-1',
        command_id: null,
        data: {},
        timestamp: new Date().toISOString(),
        source: 'test',
        agent_name: null,
        tags: [],
        sequence_reset: false,
        correlation_id: null,
      };

      mockInstances[0].onmessage?.({ data: JSON.stringify(event) });
      expect(ws.sequence).toBe(100);
    });
  });
});
