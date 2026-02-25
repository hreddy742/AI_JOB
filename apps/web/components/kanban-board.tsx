"use client";

type AppItem = { id: string; title: string; status: string };
const lanes = ["draft", "submitted", "interviewing", "offer", "rejected"];

export function KanbanBoard({ items, onMove }: { items: AppItem[]; onMove: (id: string, status: string) => void }) {
  return (
    <div className="grid gap-3 md:grid-cols-5">
      {lanes.map((lane) => (
        <div key={lane} className="rounded-xl border p-2">
          <h3 className="mb-2 text-sm font-bold uppercase text-slate-500">{lane}</h3>
          <div className="space-y-2">
            {items.filter((i) => i.status === lane).map((i) => (
              <div key={i.id} className="rounded border bg-white p-2 text-sm">
                <p className="font-medium">{i.title}</p>
                <select className="mt-2 w-full rounded border text-xs" value={i.status} onChange={(e) => onMove(i.id, e.target.value)}>
                  {lanes.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
