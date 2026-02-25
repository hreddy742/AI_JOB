"use client";

import { useEffect, useState } from "react";
import { ChatWindow } from "@/components/chat-window";
import { InterviewPrepPanel } from "@/components/interview-prep-panel";
import { api, streamCopilotMessage } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";
import { useCopilotStore } from "@/lib/store/copilot-store";

export default function CopilotPage() {
  const token = useAuthStore((s) => s.accessToken);
  const activeSessionId = useCopilotStore((s) => s.activeSessionId);
  const setActiveSessionId = useCopilotStore((s) => s.setActiveSessionId);
  const mode = useCopilotStore((s) => s.mode);
  const setMode = useCopilotStore((s) => s.setMode);
  const [sessions, setSessions] = useState<any[]>([]);
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [streaming, setStreaming] = useState(false);
  const [questions, setQuestions] = useState<Array<{ category: string; question: string; tips?: string }>>([]);

  useEffect(() => {
    if (!token) return;
    api.listCopilotSessions(token).then((s: any) => {
      setSessions(s || []);
      if (!activeSessionId && s?.[0]?.id) setActiveSessionId(s[0].id);
    });
  }, [token, activeSessionId, setActiveSessionId]);

  async function newSession() {
    if (!token) return;
    const created = await api.createCopilotSession(token, { mode }) as any;
    setActiveSessionId(created.id);
    setMessages([]);
    setSessions((s) => [created, ...s]);
  }

  async function sendMessage(text: string) {
    if (!token || !activeSessionId) return;
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setStreaming(true);
    await streamCopilotMessage(token, activeSessionId, text, (chunk) => {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = { role: "assistant", content: (next[next.length - 1]?.content || "") + chunk };
        return next;
      });
    });
    setStreaming(false);
  }

  return (
    <div className="grid h-[78vh] gap-3 md:grid-cols-[260px_1fr]">
      <aside className="rounded-xl border p-3">
        <button className="w-full rounded bg-cyan-700 px-3 py-2 text-white" onClick={newSession}>New Session</button>
        <select className="mt-2 w-full rounded border p-2 text-sm" value={mode} onChange={(e) => setMode(e.target.value as any)}>
          <option value="general">General</option>
          <option value="interview_prep">Interview Prep</option>
          <option value="resume_review">Resume Review</option>
          <option value="job_strategy">Job Strategy</option>
        </select>
        <div className="mt-3 space-y-1">
          {sessions.map((s) => (
            <button key={s.id} className={`block w-full rounded px-2 py-1 text-left text-sm ${activeSessionId === s.id ? "bg-slate-900 text-white" : "bg-slate-100"}`} onClick={() => setActiveSessionId(s.id)}>{s.title || s.id.slice(0, 8)}</button>
          ))}
        </div>
      </aside>
      <section className="space-y-3">
        {mode === "interview_prep" ? (
          <button className="rounded bg-amber-600 px-3 py-2 text-xs text-white" onClick={async () => {
            if (!token || !activeSessionId) return;
            const q = await api.getInterviewQuestions(token, activeSessionId) as any[];
            setQuestions(q);
          }}>Generate Questions</button>
        ) : null}
        {questions.length > 0 ? <InterviewPrepPanel questions={questions} onAskFeedback={async (answer, question) => {
          await sendMessage(`Question: ${question}\nAnswer: ${answer}\nGive structured feedback.`);
          return "Feedback added in chat.";
        }} /> : null}
        <ChatWindow messages={messages} onSend={sendMessage} streaming={streaming} />
      </section>
    </div>
  );
}
