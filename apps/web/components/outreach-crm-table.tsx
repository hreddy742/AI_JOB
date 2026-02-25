"use client";

export function OutreachCrmTable({ rows }: { rows: Array<{ id: string; name: string; company: string; status: string }> }) {
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-left"><th>Name</th><th>Company</th><th>Status</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="border-t"><td>{r.name}</td><td>{r.company}</td><td>{r.status}</td></tr>
        ))}
      </tbody>
    </table>
  );
}
