"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const token = useAuthStore((s) => s.accessToken);
  const [job, setJob] = useState<any>(null);

  useEffect(() => {
    if (!token) return;
    api.getJob(token, params.id).then(setJob);
  }, [token, params.id]);

  if (!job) return <p>Loading...</p>;

  return (
    <article>
      <h1 className="text-2xl font-bold">{job.title}</h1>
      <p className="text-slate-600">{job.company}</p>
      <pre className="mt-4 whitespace-pre-wrap text-sm">{job.description}</pre>
    </article>
  );
}
