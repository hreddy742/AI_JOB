"use client";

import TailoredResumeEditor from "@/components/premium/TailoredResumeEditor";
import { Accordion } from "@/components/ui/accordion";
import { Card, CardTitle } from "@/components/ui/card";

const jd = `Senior ML Infrastructure Engineer
- Own deployment reliability for low-latency inference systems
- Build observability and performance tooling for model-serving pipelines
- Partner across platform, product, and data science teams`;

const beforeResume = `Experience
- Worked on APIs used by ML team.
- Helped improve model deployment.
- Managed incidents during production failures.`;

const afterResume = `Experience
- Architected model-serving APIs used across ML product teams, prioritizing reliability and scale.
- Improved deployment workflows for low-latency inference services through pipeline hardening and release automation.
- Led production incident response and postmortem remediation to strengthen service stability and recovery speed.`;

export default function TailoredResumePage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">Tailored Resume Editor</h1>
      <TailoredResumeEditor jobDescription={jd} beforeText={beforeResume} afterText={afterResume} />
      <Card>
        <CardTitle className="mb-2">AI Context Notes</CardTitle>
        <Accordion
          items={[
            { title: "Why this role fits", body: "Strong overlap in backend infra ownership and incident recovery patterns." },
            { title: "Top ATS phrases", body: "low-latency inference, model-serving pipelines, observability tooling" }
          ]}
        />
      </Card>
    </div>
  );
}
