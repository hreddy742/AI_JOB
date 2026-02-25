"use client";

import { useEffect, useState } from "react";
import { ResumeDiffViewer } from "@/components/resume-diff-viewer";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type TailorParams = {
  id: string;
  jobId: string;
};

type TailorPageProps = {
  params: TailorParams;
};

export default function TailorPage({ params }: TailorPageProps) {
  const token = useAuthStore((s) => s.accessToken);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);
  const [original, setOriginal] = useState("");
  const [tailoredText, setTailoredText] = useState("");
  const [diffLog, setDiffLog] = useState<any[]>([]);

  useEffect(() => {
    if (!token) {
      return;
    }
    api.getResume(token, params.id).then((r: any) => setOriginal(r.original_text || ""));
  }, [token, params.id]);

  useEffect(() => {
    if (!token || !taskId) {
      return;
    }

    const timer = setInterval(async () => {
      const result = (await api.getTailorTask(token, taskId)) as any;
      setStatus(result);
      if (result?.status === "completed" && result?.tailored_resume_id) {
        const tailored = await api.getTailoredResume(token, result.tailored_resume_id);
        setTailoredText((tailored as any)?.tailored_text || "");
        setDiffLog((tailored as any)?.diff_log || []);
        clearInterval(timer);
      } else if (result?.status === "failed") {
        clearInterval(timer);
      }
    }, 1500);

    return () => clearInterval(timer);
  }, [token, taskId]);

  return (
    <div className="space-y-4">
      <button
        className="rounded bg-cyan-700 px-3 py-2 text-white"
        onClick={async () => {
          if (!token) {
            return;
          }
          const r = (await api.createTailorTask(token, {
            resume_id: params.id,
            job_id: params.jobId,
          })) as { task_id: string };
          setTaskId(r.task_id);
        }}
      >
        Run Tailoring
      </button>
      <p className="text-sm text-slate-600">
        Task: {taskId || "not started"} | {status?.status || "idle"}
      </p>
      <ResumeDiffViewer
        originalText={original}
        tailoredText={tailoredText || "Waiting for result..."}
        diffLog={diffLog}
      />
    </div>
  );
}
