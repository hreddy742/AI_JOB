"use client";

import { motion } from "framer-motion";
import { Radar } from "lucide-react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar as ReRadar, RadarChart, ResponsiveContainer } from "recharts";

import MatchList from "@/components/premium/MatchList";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { rankedMatches } from "@/lib/premium-data";

const radarData = [
  { skill: "Python", score: 92 },
  { skill: "ML Ops", score: 76 },
  { skill: "Cloud", score: 84 },
  { skill: "SQL", score: 88 },
  { skill: "System Design", score: 71 }
];

export default function AIMatchingPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">AI Matching</h1>
      <div className="grid gap-3 xl:grid-cols-[1fr_1.25fr]">
        <Card>
          <div className="mb-2 flex items-center gap-2">
            <Radar className="h-4 w-4 text-primary" />
            <CardTitle>Resume Embedding Radar</CardTitle>
          </div>
          <CardDescription className="mb-3">
            Multi-dimensional representation of your current resume against high-signal hiring features.
          </CardDescription>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="skill" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} />
                <ReRadar name="Profile" dataKey="score" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.35} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <MatchList items={rankedMatches} />
      </div>
    </div>
  );
}
