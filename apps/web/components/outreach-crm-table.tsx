"use client";

type OutreachRow = {
  id: string;
  contactId: string;
  name: string;
  company: string;
  status: string;
  draftText: string;
  sentAt?: string | null;
  followUpAt?: string | null;
};

type Props = {
  rows: OutreachRow[];
  busyId: string | null;
  onApprove: (id: string) => Promise<void>;
  onSend: (id: string) => Promise<void>;
  onUpdateStatus: (id: string, status: string) => Promise<void>;
};

export function OutreachCrmTable({ rows, busyId, onApprove, onSend, onUpdateStatus }: Props) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left">
          <tr>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Company</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Draft</th>
            <th className="px-3 py-2">Activity</th>
            <th className="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row) => {
              const isBusy = busyId === row.id;
              return (
                <tr key={row.id} className="border-t align-top">
                  <td className="px-3 py-2 font-medium">{row.name}</td>
                  <td className="px-3 py-2">{row.company || "-"}</td>
                  <td className="px-3 py-2 capitalize">{row.status.replaceAll("_", " ")}</td>
                  <td className="max-w-xl px-3 py-2 text-slate-600">
                    <div className="line-clamp-4 whitespace-pre-wrap">{row.draftText || "-"}</div>
                  </td>
                  <td className="px-3 py-2 text-slate-500">
                    <div>{row.sentAt ? `Sent: ${new Date(row.sentAt).toLocaleString()}` : "Not sent"}</div>
                    <div>{row.followUpAt ? `Follow-up: ${new Date(row.followUpAt).toLocaleString()}` : "No follow-up scheduled"}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={isBusy || row.status !== "draft"}
                        onClick={() => void onApprove(row.id)}
                        className="rounded border px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        disabled={isBusy || !["approved", "queued", "sending"].includes(row.status)}
                        onClick={() => void onSend(row.id)}
                        className="rounded border px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                      >
                        Send
                      </button>
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onUpdateStatus(row.id, "replied")}
                        className="rounded border px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                      >
                        Mark replied
                      </button>
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onUpdateStatus(row.id, "meeting_booked")}
                        className="rounded border px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                      >
                        Meeting booked
                      </button>
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => void onUpdateStatus(row.id, "no_reply")}
                        className="rounded border px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                      >
                        No reply
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={6} className="px-3 py-6 text-center text-slate-500">
                No outreach items yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
