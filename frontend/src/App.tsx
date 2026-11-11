import { FormEvent, useCallback, useEffect, useState } from "react";

type Source = {
  document_id: string;
  filename: string;
  chunk_index: number;
  page_number: number | null;
  content: string;
  similarity: number;
};
type DocumentItem = {
  document_id: string;
  filename: string;
  created_at: string;
  status: string;
  chunks_count: number;
};
type Answer = {
  answer: string;
  sources: Source[];
  outcome?: string;
  trace?: string[];
};
type Message = { question: string; result?: Answer; error?: string; pending?: boolean };

const API = import.meta.env.VITE_API_BASE_URL || "/api";

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("docmind-token") || "");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [useAgent, setUseAgent] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadDocuments = useCallback(async () => {
    if (!token) return;
    try {
      const result = await request<{ items: DocumentItem[] }>("/documents?limit=100", token);
      setDocuments(result.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load documents");
    }
  }, [token]);

  useEffect(() => { void loadDocuments(); }, [loadDocuments]);

  function saveToken(value: string) {
    sessionStorage.setItem("docmind-token", value);
    setToken(value);
    setError("");
  }

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const body = JSON.stringify({ email: form.get("email"), password: form.get("password") });
    try {
      if (submitter?.value === "register") await request("/auth/register", "", { method: "POST", body });
      const result = await request<{ access_token: string }>("/auth/login", "", { method: "POST", body });
      saveToken(result.access_token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not sign in");
    } finally { setBusy(false); }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    const data = new FormData();
    data.append("file", file);
    try {
      await request("/documents", token, { method: "POST", body: data });
      input.value = "";
      await loadDocuments();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed");
    } finally { setBusy(false); }
  }

  async function removeDocument(id: string) {
    setError("");
    try {
      await request(`/documents/${id}`, token, { method: "DELETE" });
      await loadDocuments();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete document");
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || busy) return;
    setQuestion("");
    setBusy(true);
    setMessages((current) => [...current, { question: prompt, pending: true }]);
    try {
      const path = useAgent ? "/rag/agent" : "/rag/ask";
      const result = await request<Answer>(path, token, {
        method: "POST",
        body: JSON.stringify({ question: prompt }),
      });
      setMessages((current) => current.map((message, index) =>
        index === current.length - 1 ? { question: prompt, result } : message));
    } catch (reason) {
      setMessages((current) => current.map((message, index) =>
        index === current.length - 1
          ? { question: prompt, error: reason instanceof Error ? reason.message : "Question failed" }
          : message));
    } finally { setBusy(false); }
  }

  function signOut() {
    sessionStorage.removeItem("docmind-token");
    setToken("");
    setDocuments([]);
    setMessages([]);
  }

  if (!token) return <main className="auth-page">
    <section className="auth-card">
      <Brand />
      <h1>Your documents,<br />ready to answer.</h1>
      <p className="muted">Sign in or create an account to start a private, document-grounded conversation.</p>
      <form onSubmit={authenticate} className="auth-form">
        <label>Email<input name="email" type="email" autoComplete="email" required /></label>
        <label>Password<input name="password" type="password" minLength={8} autoComplete="current-password" required /></label>
        <div className="auth-actions">
          <button name="mode" value="login" className="button primary" disabled={busy}>{busy ? "Please wait…" : "Sign in"}</button>
          <button name="mode" value="register" className="button secondary" disabled={busy}>Create account</button>
        </div>
      </form>
      {error && <p className="notice error">{error}</p>}
      <p className="auth-foot">Your access token stays in this browser session.</p>
    </section>
  </main>;

  return <div className="app-shell">
    <aside className="sidebar">
      <Brand />
      <div className="side-heading"><span>YOUR LIBRARY</span><span className="count">{documents.length}</span></div>
      <form className="upload-card" onSubmit={upload}>
        <label className="upload-button">
          <span className="plus">＋</span><span><strong>Add a document</strong><small>PDF, DOCX or TXT · 10 MB max</small></span>
          <input type="file" name="file" accept=".pdf,.docx,.txt" onChange={(event) => {
            if (event.currentTarget.files?.length) event.currentTarget.form?.requestSubmit();
          }} />
        </label>
        {busy && <small className="muted">Working…</small>}
      </form>
      <div className="document-list">
        {documents.length === 0 && <p className="empty-library">Your library is empty.<br />Upload a document to begin.</p>}
        {documents.map((document) => <div className="document-row" key={document.document_id}>
          <span className="file-icon">▤</span>
          <span className="document-meta"><strong title={document.filename}>{document.filename}</strong><small>{document.chunks_count} passages · {document.status}</small></span>
          <button className="icon-button" title={`Delete ${document.filename}`} onClick={() => void removeDocument(document.document_id)}>×</button>
        </div>)}
      </div>
      <div className="account-row"><span className="avatar">D</span><span><strong>DocMind account</strong><small>Private workspace</small></span><button className="signout" onClick={signOut}>Sign out</button></div>
    </aside>

    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">DOCUMENT ASSISTANT</span><h2>Ask your library</h2></div><div className="engine-chip"><span className="pulse" /> Gemini · {useAgent ? "Agent mode" : "Standard RAG"}</div></header>
      {error && <div className="notice error global-error" role="alert">{error}<button onClick={() => setError("")}>Dismiss</button></div>}
      <section className="conversation" aria-live="polite">
        {messages.length === 0 ? <div className="welcome">
          <div className="welcome-mark">✳</div><span className="eyebrow">A CLEARER WAY TO FIND ANSWERS</span>
          <h1>What would you like<br />to know?</h1>
          <p>Ask a question about the documents in your library.<br />Answers include the passages they came from.</p>
          {documents.length === 0 && <div className="tip">Start by adding a document from the sidebar.</div>}
          {documents.length > 0 && <div className="suggestions"><button onClick={() => setQuestion("Summarize the key points in my documents")}>Summarize my documents <span>↗</span></button><button onClick={() => setQuestion("What deadlines should I know about?")}>Find important deadlines <span>↗</span></button></div>}
        </div> : <div className="message-list">{messages.map((message, index) => <article className="exchange" key={`${message.question}-${index}`}>
          <div className="user-message"><span className="avatar user-avatar">You</span><p>{message.question}</p></div>
          <div className="assistant-message"><span className="assistant-mark">✳</span><div className="answer-body">
            {message.pending && <p className="muted">Searching your documents…</p>}
            {message.error && <p className="inline-error">{message.error}</p>}
            {message.result && <>
              <div className="answer-label"><span>ANSWER</span>{message.result.outcome && <span className={`outcome ${message.result.outcome}`}>{message.result.outcome.replace("_", " ")}</span>}</div>
              <p className="answer-text">{message.result.answer}</p>
              {message.result.sources.length > 0 && <div className="sources"><div className="source-heading">SOURCES <span>{message.result.sources.length}</span></div>{message.result.sources.map((source, sourceIndex) => <details className="source" key={`${source.document_id}-${source.chunk_index}`}>
                <summary><span className="source-number">{sourceIndex + 1}</span><strong>{source.filename}</strong><span className="source-location">{source.page_number ? `Page ${source.page_number}` : `Passage ${source.chunk_index + 1}`}</span><span className="similarity">{Math.round(source.similarity * 100)}%</span></summary>
                <p>{source.content}</p>
              </details>)}</div>}
              {message.result.trace && <details className="trace"><summary>Agent reasoning trace <span>{message.result.trace.length} steps</span></summary><ol>{message.result.trace.map((step, stepIndex) => <li key={stepIndex}>{step}</li>)}</ol></details>}
            </>}
          </div></div>
        </article>)}</div>}
      </section>
      <div className="composer-wrap"><form className="composer" onSubmit={ask}>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); }
        }} placeholder="Ask a question about your documents…" rows={2} maxLength={2000} />
        <div className="composer-footer"><label className="agent-toggle"><input type="checkbox" checked={useAgent} onChange={(event) => setUseAgent(event.target.checked)} /><span className="toggle-track" /><span>Agent mode</span><span className="help" title="Agent mode rewrites queries and checks answers against sources.">ⓘ</span></label><span className="composer-hint">Enter to send · Shift + Enter for a new line</span><button className="send-button" type="submit" disabled={!question.trim() || busy} aria-label="Send question">↑</button></div>
      </form><p className="disclaimer">DocMind answers from your uploaded files. Check important details in the cited source.</p></div>
    </main>
  </div>;
}

function Brand() {
  return <div className="brand"><span className="brand-icon">✳</span><span>docmind<span className="brand-ai">.ai</span></span></div>;
}
