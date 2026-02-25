"use client";

import ApplicationBoard from "@/components/premium/ApplicationBoard";
import { kanbanData } from "@/lib/premium-data";

export default function ApplicationsPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">Application Tracker</h1>
      <ApplicationBoard board={kanbanData} />
    </div>
  );
}
