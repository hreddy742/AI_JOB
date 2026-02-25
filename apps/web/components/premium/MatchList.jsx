"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useState } from "react";

import Button from "@/components/premium/ui/Button";
import Card, { CardTitle } from "@/components/premium/ui/Card";
import Modal from "@/components/premium/ui/Modal";

export default function MatchList({ items }) {
  const [open, setOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState("");

  return (
    <>
      <Card>
        <CardTitle className="mb-2">Ranked Matches</CardTitle>
        <div className="space-y-3">
          {items.map((item, idx) => (
            <motion.div key={item.id} className="rounded-md border border-border p-3" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0, transition: { delay: idx * 0.07 } }}>
              <div className="mb-1 flex items-center justify-between">
                <p className="font-medium">
                  {item.title} · {item.company}
                </p>
                <span className="text-sm font-semibold text-primary">{item.score}%</span>
              </div>
              <div className="mb-2 h-2 overflow-hidden rounded-full bg-slate-300/40 dark:bg-slate-700/60">
                <motion.div initial={{ width: 0 }} animate={{ width: `${item.score}%` }} className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500" />
              </div>
              <ul className="space-y-1 text-sm text-muted">
                {item.reasons.map((reason) => (
                  <li key={reason}>• {reason}</li>
                ))}
              </ul>
              <div className="mt-2">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSelectedRole(item.title);
                    setOpen(true);
                  }}
                >
                  Improve
                </Button>
              </div>
            </motion.div>
          ))}
        </div>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title={`Resume rewrite suggestions · ${selectedRole}`}>
        <div className="space-y-2 text-sm">
          <p className="rounded-md border border-border bg-slate-100/60 p-2 dark:bg-slate-800/50">
            <span className="font-semibold">Before:</span> Built APIs for model-serving workflows used by data science teams.
          </p>
          <p className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-2">
            <span className="font-semibold">After:</span> Architected low-latency model-serving APIs for cross-functional ML squads, improving production inference reliability and release cadence.
          </p>
          <div className="rounded-md border border-border p-2">
            <p className="mb-1 flex items-center gap-1 font-medium">
              <Sparkles className="h-4 w-4 text-primary" /> Why this helps
            </p>
            <p className="text-muted">Stronger ownership verbs, tighter ATS-aligned phrasing, and clearer impact language with no fabricated claims.</p>
          </div>
        </div>
      </Modal>
    </>
  );
}
