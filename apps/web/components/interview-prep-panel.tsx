"use client";

import { useState } from "react";

export function InterviewPrepPanel({ questions, onAskFeedback }: { questions: Array<{ category: string; question: string; tips?: string }>; onAskFeedback: (answer: string, question: string) => Promise<string> }) {
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  return (
    <div className="space-y-3">
      {questions.map((q) => (
        <div key={q.question} className="rounded-xl border p-3">
          <span className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-800">{q.category}</span>
          <p className="mt-2 font-medium">{q.question}</p>
          <textarea className="mt-2 w-full rounded border p-2 text-sm" placeholder="Write your mock answer" onBlur={async (e) => {
            if (!e.target.value.trim()) return;
            const f = await onAskFeedback(e.target.value, q.question);
            setFeedback((s) => ({ ...s, [q.question]: f }));
          }} />
          {feedback[q.question] ? <p className="mt-2 rounded bg-cyan-50 p-2 text-xs text-cyan-900">{feedback[q.question]}</p> : null}
        </div>
      ))}
    </div>
  );
}
