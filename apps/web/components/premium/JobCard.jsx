"use client";

import { motion } from "framer-motion";
import { Bookmark, ExternalLink } from "lucide-react";

import Badge from "@/components/premium/ui/Badge";
import Button from "@/components/premium/ui/Button";
import Card, { CardDescription, CardTitle } from "@/components/premium/ui/Card";

function formatSalary(job) {
  if (job.salary_min || job.salary_max) {
    const currency = job.salary_currency || "USD";
    const min = job.salary_min || "?";
    const max = job.salary_max ? ` - ${job.salary_max}` : "+";
    return `${currency} ${min}${max}`;
  }
  return "Salary not listed";
}

export default function JobCard({ job }) {
  return (
    <motion.div whileHover={{ y: -5 }} transition={{ duration: 0.2 }}>
      <Card className="h-full">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-md bg-primary/15 text-center text-xs font-semibold leading-9 text-primary">
              {job.logo}
            </div>
            <div>
              <CardTitle>{job.title}</CardTitle>
              <CardDescription>{job.company}</CardDescription>
            </div>
          </div>
          <span className="rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 px-2 py-1 text-xs font-semibold text-white">
            {Math.round((job.match || 0) * 100)}% match
          </span>
        </div>
        <p className="text-sm text-muted">
          {job.location} · {job.type}
        </p>
        <p className="mt-1 text-xs text-muted">{formatSalary(job)}</p>
        <div className="mt-3 flex flex-wrap gap-1">
          {(job.missing || []).slice(0, 3).map((skill) => (
            <motion.span key={skill} whileHover={{ scale: 1.04 }}>
              <Badge tone="warning">Missing: {skill}</Badge>
            </motion.span>
          ))}
        </div>
        <div className="mt-4 flex items-center justify-between">
          <Button
            onClick={() => {
              if (job.url) window.open(job.url, "_blank", "noopener,noreferrer");
            }}
          >
            <ExternalLink className="h-4 w-4" /> Apply
          </Button>
          <Button variant="secondary">
            <Bookmark className="h-4 w-4" /> Save
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
