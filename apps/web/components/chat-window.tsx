"use client";

import { useState } from "react";

export function ChatWindow({ messages, onSend, streaming }: { messages: Array<{ role: string; content: string }>; onSend: (text: string) => Promise<void>; streaming: boolean }) {
  const [value, setValue] = useState("");
  return (
    <div className="flex h-[70vh] flex-col rounded-xl border">
      <div className="flex-1 space-y-2 overflow-auto p-3">
        {messages.map((m, idx) => (
          <div key={idx} className={`max-w-[80%] rounded-lg p-2 text-sm ${m.role === "user" ? "ml-auto bg-cyan-700 text-white" : "bg-slate-100"}`}>
            <p>{m.content}</p>
          </div>
        ))}
        {streaming ? <p className="text-xs text-slate-500">Thinking...</p> : null}
      </div>
      <div className="border-t p-2">
        <textarea className="w-full rounded border p-2 text-sm" rows={3} value={value} onChange={(e) => setValue(e.target.value)} />
        <button className="mt-2 rounded bg-slate-900 px-3 py-2 text-xs text-white" onClick={async () => { if (!value.trim()) return; const text = value; setValue(""); await onSend(text); }}>Send</button>
      </div>
    </div>
  );
}
