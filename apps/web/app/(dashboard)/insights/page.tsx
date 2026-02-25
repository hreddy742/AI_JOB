import { Card, CardDescription, CardTitle } from "@/components/ui/card";

export default function InsightsPage() {
  return (
    <div className="space-y-4">
      <h1 className="font-display text-2xl font-semibold">Insights</h1>
      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <CardTitle>Application Conversion</CardTitle>
          <CardDescription>AI-tailored resumes are converting 2.1x better than baseline submissions this month.</CardDescription>
        </Card>
        <Card>
          <CardTitle>Role Heatmap</CardTitle>
          <CardDescription>Highest recruiter response rate this week: ML Infrastructure, Data Platform, and Backend AI roles.</CardDescription>
        </Card>
        <Card>
          <CardTitle>Skill Gap Trend</CardTitle>
          <CardDescription>Most frequent missing signal in shortlisted roles: MLOps governance and advanced observability language.</CardDescription>
        </Card>
        <Card>
          <CardTitle>Time Saved</CardTitle>
          <CardDescription>Jobright AI Copilot automated an estimated 19 hours of repetitive resume and application work.</CardDescription>
        </Card>
      </div>
    </div>
  );
}
