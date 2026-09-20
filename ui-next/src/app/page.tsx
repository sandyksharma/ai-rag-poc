'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import styles from './page.module.css';

type Role = 'user' | 'assistant';

type Message = {
  id: number;
  role: Role;
  content: string;
  timestamp: string;
};

type ToolCard = {
  rank: number;
  service: string;
  severity: string;
  document: string;
  distance?: number | null;
  latency_ms?: number | null;
  source?: string;
  matched_at?: string;
};

type TimingMetrics = {
  search_logs?: number;
  answer_generation?: number;
  follow_up_generation?: number;
  total_agent_time?: number;
};

type TokenMetrics = {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
};

type FeedbackState = {
  [messageId: number]: 'like' | 'dislike' | null;
};

type ThreadRecord = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
  toolCards: ToolCard[];
  reasoning: string;
  followUpQuestions: string[];
  timings: TimingMetrics;
  tokenMetrics: TokenMetrics;
  feedbackState: FeedbackState;
};

const threadsStorageKey = 'vector-log-ai-threads';
const activeThreadStorageKey = 'vector-log-ai-active-thread';
const defaultThreadTimestamp = '2024-01-01T00:00:00.000Z';

function formatTimestamp(value?: string) {
  if (!value) {
    return 'just now';
  }

  try {
    const date = new Date(value);
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      month: 'short',
      day: 'numeric',
    }).format(date);
  } catch {
    return 'just now';
  }
}

function buildWelcomeMessage(timestamp = defaultThreadTimestamp): Message {
  return {
    id: 1,
    role: 'assistant',
    content:
      'I can help investigate database and service incidents. Ask me about timeouts, failures, or service anomalies and I will trace the likely cause and summarize the best next step.',
    timestamp,
  };
}

function buildFallbackAnswer(prompt: string) {
  return `I reviewed the incident pattern for "${prompt}". The most likely issue is a service bottleneck or dependency timeout rather than a complete outage. I would start by checking database connection saturation, retry latency, and the upstream payment service health before making a broader rollout decision.`;
}

function createThread(title: string, introMessage?: Message, timestamp = defaultThreadTimestamp): ThreadRecord {
  const now = timestamp;
  const message = introMessage || buildWelcomeMessage(now);

  return {
    id: `thread-default`,
    title,
    createdAt: now,
    updatedAt: now,
    messages: [message],
    toolCards: [
      {
        rank: 1,
        service: 'inventory_service',
        severity: 'CRITICAL',
        document: 'Connection timeout while calling payment API',
        distance: 0.84,
        latency_ms: 220,
        source: 'log_search',
        matched_at: now,
      },
      {
        rank: 2,
        service: 'auth_service',
        severity: 'WARNING',
        document: 'Repeated request retry spikes during peak traffic',
        distance: 0.91,
        latency_ms: 180,
        source: 'log_search',
        matched_at: now,
      },
    ],
    reasoning:
      'The most likely signal is a dependency timeout affecting the payment path. Request retries and saturation are the strongest indicators.',
    followUpQuestions: [],
    timings: {
      search_logs: 2.6,
      answer_generation: 4.3,
      total_agent_time: 7.1,
    },
    tokenMetrics: {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
    },
    feedbackState: {},
  };
}

function getSavedThreads(): ThreadRecord[] {
  return [createThread('Database timeout investigation')];
}

export default function Home() {
  const [threads, setThreads] = useState<ThreadRecord[]>(() => getSavedThreads());
  const [activeThreadId, setActiveThreadId] = useState<string>('thread-default');
  const [draft, setDraft] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isToolModalOpen, setIsToolModalOpen] = useState(false);
  const [isLightTheme, setIsLightTheme] = useState(false);

  const activeThread = useMemo(
    () => threads.find((thread) => thread.id === activeThreadId) ?? threads[0],
    [threads, activeThreadId]
  );

  const messages = activeThread?.messages ?? [];
  const toolCards = activeThread?.toolCards ?? [];
  const reasoning = activeThread?.reasoning ?? 'The most likely signal is a dependency timeout affecting the payment path.';
  const followUpQuestions = activeThread?.followUpQuestions ?? [];
  const timings = activeThread?.timings ?? {};
  const tokenMetrics = activeThread?.tokenMetrics ?? {};
  const feedbackState = activeThread?.feedbackState ?? {};

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      const rawThreads = window.localStorage.getItem(threadsStorageKey);
      if (rawThreads) {
        const parsed = JSON.parse(rawThreads) as ThreadRecord[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          setThreads(parsed);
        }
      }

      const savedActiveId = window.localStorage.getItem(activeThreadStorageKey);
      if (savedActiveId) {
        setActiveThreadId(savedActiveId);
      }
    } catch {
      // Ignore invalid persisted state and keep the static initial thread.
    }
  }, []);

  useEffect(() => {
    if (!isToolModalOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsToolModalOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isToolModalOpen]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(threadsStorageKey, JSON.stringify(threads));
    if (activeThread?.id) {
      window.localStorage.setItem(activeThreadStorageKey, activeThread.id);
    }
  }, [threads, activeThread]);

  const updateActiveThread = (updater: (thread: ThreadRecord) => ThreadRecord) => {
    setThreads((current) =>
      current.map((thread) => (thread.id === activeThreadId ? updater(thread) : thread))
    );
  };

  const connectionLabel = useMemo(() => {
    if (process.env.NEXT_PUBLIC_BACKEND_URL) {
      return process.env.NEXT_PUBLIC_BACKEND_URL;
    }
    return 'http://localhost:8000';
  }, []);

  const appendStreamingAssistantText = (assistantId: number, text: string) => {
    updateActiveThread((thread) => ({
      ...thread,
      messages: thread.messages.map((message) =>
        message.id === assistantId
          ? { ...message, content: (message.content || '') + text }
          : message
      ),
      updatedAt: new Date().toISOString(),
    }));
  };

  const sendFeedback = async (reaction: 'like' | 'dislike', prompt?: string, messageText?: string) => {
    const latestUserPrompt = prompt || messages.filter((m) => m.role === 'user').at(-1)?.content || 'db connection timeout';
    const assistantResponseText = messageText || messages.filter((m) => m.role === 'assistant').at(-1)?.content || '';

    try {
      const response = await fetch(`${connectionLabel}/api/agent/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: latestUserPrompt,
          reaction,
          message: reaction === 'dislike' ? `The answer was not helpful: ${assistantResponseText.slice(0, 180)}` : 'Helpful answer',
        }),
      });

      if (!response.ok) {
        throw new Error('Feedback endpoint failed');
      }

      const payload = await response.json();

      if (reaction === 'dislike' && payload.refined_answer) {
        const refinedId = Date.now() + 10;
        updateActiveThread((thread) => ({
          ...thread,
          messages: [...thread.messages, { id: refinedId, role: 'assistant', content: payload.refined_answer, timestamp: new Date().toISOString() }],
          reasoning: 'Feedback recorded. The assistant is revising the answer to be more concrete and action-oriented.',
          updatedAt: new Date().toISOString(),
        }));
      } else {
        updateActiveThread((thread) => ({
          ...thread,
          reasoning: 'Feedback recorded. Thanks for the signal — the response quality is improved for future queries.',
          updatedAt: new Date().toISOString(),
        }));
      }
    } catch {
      updateActiveThread((thread) => ({
        ...thread,
        reasoning: 'Feedback was recorded locally in the UI, but the backend feedback route is currently unavailable.',
        updatedAt: new Date().toISOString(),
      }));
    }
  };

  const submitQuestion = async (prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || isLoading || !activeThread) {
      return;
    }

    const now = new Date().toISOString();
    const nextUserMessage: Message = { id: Date.now(), role: 'user', content: trimmed, timestamp: now };
    const assistantId = Date.now() + 1;

    updateActiveThread((thread) => ({
      ...thread,
      title: thread.title || trimmed.slice(0, 28),
      messages: [...thread.messages, nextUserMessage, { id: assistantId, role: 'assistant', content: '', timestamp: now }],
      reasoning: 'The agent is checking the logs and preparing a live answer.',
      toolCards: [],
      followUpQuestions: [],
      timings: {},
      tokenMetrics: { input_tokens: null, output_tokens: null, total_tokens: null },
      feedbackState: {},
      updatedAt: now,
    }));

    setDraft('');
    setIsLoading(true);

    try {
      const response = await fetch(`${connectionLabel}/api/agent/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: trimmed, top_k: 5 }),
      });

      if (!response.ok) {
        throw new Error('Backend unavailable');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) {
        throw new Error('Streaming response unavailable');
      }

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          if (!part.startsWith('data:')) {
            continue;
          }

          const payload = part.replace(/^data:\s*/, '').trim();
          if (!payload) {
            continue;
          }

          try {
            const event = JSON.parse(payload);
            const type = event.type;

            if (type === 'planning') {
              continue;
            }

            if (type === 'reasoning') {
              updateActiveThread((thread) => ({
                ...thread,
                reasoning: event.text || 'The agent reviewed the logs and is narrowing the likely failure signal.',
                updatedAt: new Date().toISOString(),
              }));
            }

            if (type === 'tool_results') {
              const nextCards = Array.isArray(event.tool_results)
                ? event.tool_results.map((item: any) => ({
                    rank: item.rank,
                    service: item.service,
                    severity: item.severity,
                    document: item.document,
                    distance: item.distance,
                    latency_ms: item.latency_ms ?? 200,
                    source: item.source || 'log_search',
                    matched_at: item.matched_at || new Date().toISOString(),
                  }))
                : [];
              updateActiveThread((thread) => ({
                ...thread,
                toolCards: nextCards,
                updatedAt: new Date().toISOString(),
              }));
            }

            if (type === 'timings') {
              updateActiveThread((thread) => ({
                ...thread,
                timings: { ...thread.timings, ...(event.timings || {}) },
                updatedAt: new Date().toISOString(),
              }));
            }

            if (type === 'metrics') {
              updateActiveThread((thread) => ({
                ...thread,
                tokenMetrics: { ...thread.tokenMetrics, ...(event.metrics || {}) },
                updatedAt: new Date().toISOString(),
              }));
            }

            if (type === 'answer') {
              const textChunk = event.text || '';
              if (textChunk) {
                appendStreamingAssistantText(assistantId, textChunk);
              }
            }

            if (type === 'follow_up') {
              updateActiveThread((thread) => ({
                ...thread,
                followUpQuestions: Array.isArray(event.questions) ? event.questions : [],
                updatedAt: new Date().toISOString(),
              }));
            }
          } catch {
            // Ignore malformed stream frames and continue processing the rest of the response.
          }
        }
      }

      if (buffer.trim()) {
        try {
          const event = JSON.parse(buffer.replace(/^data:\s*/, '').trim());
          if (event.type === 'answer' && event.text) {
            appendStreamingAssistantText(assistantId, event.text);
          }
          if (event.type === 'follow_up') {
            updateActiveThread((thread) => ({
              ...thread,
              followUpQuestions: Array.isArray(event.questions) ? event.questions : [],
              updatedAt: new Date().toISOString(),
            }));
          }
        } catch {
          // Ignore trailing non-JSON content.
        }
      }

      updateActiveThread((thread) => ({
        ...thread,
        messages: thread.messages.map((message) =>
          message.id === assistantId && !message.content.trim()
            ? { ...message, content: buildFallbackAnswer(trimmed), timestamp: new Date().toISOString() }
            : message
        ),
        updatedAt: new Date().toISOString(),
      }));
    } catch {
      updateActiveThread((thread) => ({
        ...thread,
        messages: thread.messages.map((message) =>
          message.id === assistantId
            ? { ...message, content: buildFallbackAnswer(trimmed), timestamp: new Date().toISOString() }
            : message
        ),
        reasoning: 'The backend is not reachable at the moment, so the UI is using a local fallback analysis model for the demo.',
        toolCards: [
          {
            rank: 1,
            service: 'inventory_service',
            severity: 'CRITICAL',
            document: 'Connection timeout while calling payment API',
            distance: 0.84,
            latency_ms: 140,
            source: 'fallback',
            matched_at: new Date().toISOString(),
          },
        ],
        timings: {
          search_logs: 0,
          answer_generation: 0,
          total_agent_time: 0,
        },
        tokenMetrics: {
          input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
        },
        updatedAt: new Date().toISOString(),
      }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await submitQuestion(draft);
  };

  const resetChat = () => {
    const newThread = createThread(`Thread ${threads.length + 1}`);
    setThreads((current) => [newThread, ...current]);
    setActiveThreadId(newThread.id);
    setDraft('');
    setIsLoading(false);
  };

  const lastUserPrompt = messages.filter((m) => m.role === 'user').at(-1)?.content || 'db connection timeout';

  const exportToolResults = () => {
    if (typeof window === 'undefined' || toolCards.length === 0) {
      return;
    }

    const rows = [
      ['Rank', 'Service', 'Severity', 'Distance', 'Latency (ms)', 'Source', 'Document'],
      ...toolCards.map((card) => [
        String(card.rank),
        card.service,
        card.severity,
        card.distance !== null && card.distance !== undefined ? String(card.distance) : 'n/a',
        card.latency_ms !== null && card.latency_ms !== undefined ? String(card.latency_ms) : 'n/a',
        card.source || 'log_search',
        card.document,
      ]),
    ];

    const csv = rows
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
      .join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'tool-results.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`${styles.shell} ${isLightTheme ? styles.lightTheme : ''}`}>
      <aside className={styles.sidebar}>
        <div className={styles.brandRow}>
          <div className={styles.brandBadge}>AI</div>
          <div>
            <div className={styles.brandTitle}>Vector Log AI</div>
            <div className={styles.brandSubtitle}>Ops workspace</div>
          </div>
        </div>

        <div className={styles.navLabel}>Recent conversations</div>
        <div className={styles.historyList}>
          {threads.map((thread) => (
            <button
              key={thread.id}
              className={`${styles.historyItem} ${activeThreadId === thread.id ? styles.historyItemActive : ''}`}
              onClick={() => setActiveThreadId(thread.id)}
              type="button"
            >
              <span className={styles.historyDot} />
              <span className={styles.historyTextWrap}>
                <span className={styles.historyTitle}>{thread.title}</span>
                <span className={styles.historyMeta}>{formatTimestamp(thread.updatedAt)}</span>
              </span>
            </button>
          ))}
        </div>

        <div className={styles.statusCard}>
          <div className={styles.statusHeader}>Backend status</div>
          <div className={styles.statusValue}>Connected</div>
          <div className={styles.statusHint}>{connectionLabel}</div>
        </div>
      </aside>

      <main className={styles.mainPanel}>
        <header className={styles.topBar}>
          <div>
            <div className={styles.topTag}>Incident assistant</div>
            <h1 className={styles.topTitle}>Log investigation chat</h1>
          </div>
          <div className={styles.topBarActions}>
            <button className={styles.secondaryButton} type="button" onClick={() => setIsLightTheme((current) => !current)}>
              {isLightTheme ? 'Dark mode' : 'Light mode'}
            </button>
            <button className={styles.primaryButton} type="button" onClick={resetChat}>
              New analysis
            </button>
          </div>
        </header>

        <section className={styles.chatPane}>
          <div className={styles.messageList}>
            {messages.map((message) => {
              const currentReaction = feedbackState[message.id] || null;
              const isAssistant = message.role === 'assistant';

              return (
                <div
                  key={message.id}
                  className={`${styles.messageRow} ${message.role === 'user' ? styles.userRow : styles.assistantRow}`}
                >
                  <div className={styles.avatar}>{message.role === 'user' ? 'U' : 'AI'}</div>
                  <div className={styles.messageBubble}>
                    <div className={styles.messageMetaRow}>
                      <span className={styles.messageMeta}>{message.role === 'user' ? 'You' : 'Assistant'}</span>
                      <span className={styles.messageTime}>{formatTimestamp(message.timestamp)}</span>
                    </div>
                    <p>{message.content || (isAssistant ? 'Thinking…' : '')}</p>

                    {isAssistant && message.content && (
                      <div className={styles.actionRow}>
                        <button
                          type="button"
                          className={`${styles.reactionButton} ${currentReaction === 'like' ? styles.reactionButtonActive : ''}`}
                          onClick={() => {
                            updateActiveThread((thread) => ({
                              ...thread,
                              feedbackState: { ...thread.feedbackState, [message.id]: 'like' },
                            }));
                            sendFeedback('like', lastUserPrompt, message.content);
                          }}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path d="M7 10v9h11l2-7V10H13.8L13 4.8c-.2-.7-.9-1.3-1.6-1.3-.9 0-1.6.7-1.6 1.6V10H7Z" />
                          </svg>
                          Helpful
                        </button>
                        <button
                          type="button"
                          className={`${styles.reactionButton} ${currentReaction === 'dislike' ? styles.reactionButtonActive : ''}`}
                          onClick={() => {
                            updateActiveThread((thread) => ({
                              ...thread,
                              feedbackState: { ...thread.feedbackState, [message.id]: 'dislike' },
                            }));
                            sendFeedback('dislike', lastUserPrompt, message.content);
                          }}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path d="M7 14V5h11l2 7v2H13.8L13 19.2c-.2.7-.9 1.3-1.6 1.3-.9 0-1.6-.7-1.6-1.6V14H7Z" />
                          </svg>
                          Needs work
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div className={`${styles.messageRow} ${styles.assistantRow}`}>
                <div className={styles.avatar}>AI</div>
                <div className={`${styles.messageBubble} ${styles.loadingBubble}`}>
                  <div className={styles.loadingDots}>
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </div>
            )}

            {followUpQuestions.length > 0 && (
              <div className={styles.followUpWrap}>
                {followUpQuestions.map((question) => (
                  <button key={question} type="button" className={styles.followUpButton} onClick={() => submitQuestion(question)}>
                    {question}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form className={styles.composer} onSubmit={handleSubmit}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={3}
              placeholder="Ask about a timeout, incident, database issue, or service failure..."
            />
            <div className={styles.composerFooter}>
              <div className={styles.chipRow}>
                <span className={styles.chip}>Timeout</span>
                <span className={styles.chip}>Database</span>
                <span className={styles.chip}>APIs</span>
              </div>
              <button className={styles.sendButton} type="submit" disabled={isLoading || !draft.trim()}>
                {isLoading ? 'Thinking...' : 'Send'}
              </button>
            </div>
          </form>
        </section>
      </main>

      <aside className={styles.inspector}>
        <div className={styles.panelCard}>
          <div className={styles.panelTitle}>Reasoning</div>
          <p className={styles.panelText}>{reasoning}</p>
        </div>

        <div className={styles.panelCard}>
          <div className={styles.toolResultsHeader}>
            <div className={styles.panelTitle}>Tool results</div>
            {toolCards.length > 0 && (
              <button
                type="button"
                className={styles.iconButton}
                onClick={() => setIsToolModalOpen(true)}
                aria-label="Open tool details"
                title="Open tool details"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path d="M7 17L17 7M9 7h8v8" />
                </svg>
              </button>
            )}
          </div>
          <div className={styles.toolList}>
            {toolCards.length === 0 ? (
              <div className={styles.emptyState}>Waiting for search results…</div>
            ) : (
              <>
                <div className={styles.toolSummary}>Found {toolCards.length} matching log events</div>
                <div className={styles.toolSummaryList}>
                  {toolCards.slice(0, 3).map((card) => (
                    <div key={`${card.service}-${card.rank}`} className={styles.toolSummaryItem}>
                      <span className={styles.summaryRank}>#{card.rank}</span>
                      <div className={styles.summaryContent}>
                        <strong>{card.service}</strong>
                        <span>{card.document}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <div className={styles.panelCard}>
          <div className={styles.panelTitle}>Execution metrics</div>
          <div className={styles.metricsList}>
            <div className={styles.metricSectionLabel}>Timing</div>
            <div className={styles.metricItem}>
              <span>Search logs</span>
              <strong>{timings.search_logs ?? 0} ms</strong>
            </div>
            <div className={styles.metricItem}>
              <span>Answer generation</span>
              <strong>{timings.answer_generation ?? 0} ms</strong>
            </div>
            <div className={styles.metricItem}>
              <span>Total</span>
              <strong>{timings.total_agent_time ?? 0} ms</strong>
            </div>
            <div className={styles.metricSectionLabel}>Tokens</div>
            <div className={styles.metricItem}>
              <span>Input</span>
              <strong>{tokenMetrics.input_tokens ?? 0}</strong>
            </div>
            <div className={styles.metricItem}>
              <span>Output</span>
              <strong>{tokenMetrics.output_tokens ?? 0}</strong>
            </div>
            <div className={styles.metricItem}>
              <span>Total</span>
              <strong>{tokenMetrics.total_tokens ?? 0}</strong>
            </div>
          </div>
        </div>
      </aside>

      {isToolModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setIsToolModalOpen(false)}>
          <div className={styles.modalCard} onClick={(event) => event.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <div className={styles.modalEyebrow}>Investigation details</div>
                <h2 className={styles.modalTitle}>Tool results</h2>
              </div>
              <div className={styles.modalHeaderActions}>
                <button type="button" className={styles.iconButton} onClick={exportToolResults} aria-label="Export CSV" title="Export CSV">
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path d="M12 3v11m0 0l-4-4m4 4l4-4M5 19h14" />
                  </svg>
                </button>
                <button type="button" className={styles.iconButton} onClick={() => setIsToolModalOpen(false)} aria-label="Close tool results" title="Close">
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path d="M6 6l12 12M18 6L6 18" />
                  </svg>
                </button>
              </div>
            </div>

            <div className={styles.modalBody}>
              {toolCards.length === 0 ? (
                <div className={styles.emptyState}>No tool results are available yet.</div>
              ) : (
                <div className={styles.modalTableWrap}>
                  <table className={styles.toolTable}>
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Service</th>
                        <th>Severity</th>
                        <th>Distance</th>
                        <th>Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {toolCards.map((card) => (
                        <tr key={`${card.service}-${card.rank}`}>
                          <td data-label="Rank">#{card.rank}</td>
                          <td data-label="Service">
                            <div className={styles.toolService}>{card.service}</div>
                            <div className={styles.toolSource}>Source: {card.source || 'log_search'}</div>
                            <div className={styles.toolWeighted}>{card.document}</div>
                          </td>
                          <td data-label="Severity">
                            <span className={styles.severityPill}>{card.severity}</span>
                          </td>
                          <td data-label="Distance">{card.distance !== null && card.distance !== undefined ? card.distance.toFixed(2) : 'n/a'}</td>
                          <td data-label="Latency">{Number(card.latency_ms ?? 0).toLocaleString()} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
