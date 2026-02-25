export const dashboardKpis = [
  { label: "Jobs matched", value: 142, delta: "+18 this week" },
  { label: "Recommended roles", value: 27, delta: "6 high-confidence" },
  { label: "Interviews landed", value: 9, delta: "+2 in 14 days" },
  { label: "Time saved by AI", value: "19h", delta: "Auto-tailoring + autofill" }
];

export const activityTimeline = [
  { time: "08:10 AM", text: "AI matcher surfaced 12 strong backend roles in Chicago." },
  { time: "09:25 AM", text: "Tailored resume generated for Stripe Senior ML Platform Engineer." },
  { time: "10:42 AM", text: "Application packet submitted to Databricks with ATS score 91." },
  { time: "12:15 PM", text: "Copilot suggested 3 bullet upgrades for impact clarity." }
];

export const jobs = [
  {
    id: "job-ml-1",
    company: "Nexora Labs",
    logo: "NL",
    title: "Machine Learning Engineer",
    location: "Chicago, IL",
    type: "Hybrid",
    match: 0.91,
    missing: ["TensorRT optimization", "MLOps governance"]
  },
  {
    id: "job-data-2",
    company: "Vertex Commerce",
    logo: "VC",
    title: "Senior Data Engineer",
    location: "Remote (US)",
    type: "Remote",
    match: 0.84,
    missing: ["dbt semantic layer"]
  },
  {
    id: "job-ai-3",
    company: "Aureon Health",
    logo: "AH",
    title: "Applied AI Engineer",
    location: "Austin, TX",
    type: "Full-time",
    match: 0.78,
    missing: ["Clinical NLP compliance", "HIPAA audit trails"]
  }
];

export const rankedMatches = [
  {
    id: "m-1",
    title: "ML Infrastructure Engineer",
    company: "Nexora Labs",
    score: 91,
    reasons: ["Strong Python + FastAPI overlap", "Direct experience with distributed inference", "Leadership signals in delivery metrics"]
  },
  {
    id: "m-2",
    title: "Data Platform Engineer",
    company: "Vertex Commerce",
    score: 84,
    reasons: ["Excellent SQL + orchestration stack", "Good cloud architecture alignment", "Minor skill gap in dbt governance patterns"]
  },
  {
    id: "m-3",
    title: "AI Product Engineer",
    company: "Aureon Health",
    score: 79,
    reasons: ["Strong API reliability background", "Transferable experimentation workflow", "Needs more healthcare domain keywords"]
  }
];

export const kanbanData = {
  Saved: [
    { id: "a1", title: "Senior Data Engineer", company: "Vertex Commerce", resume: "v5 ML", date: "Feb 19", status: "saved", tags: ["Follow up Fri"] },
    { id: "a2", title: "AI Platform Engineer", company: "Nexora Labs", resume: "v5 ML", date: "Feb 20", status: "saved", tags: ["Referral lead"] }
  ],
  Applied: [
    { id: "a3", title: "Backend ML Engineer", company: "Aureon Health", resume: "v4 Data", date: "Feb 18", status: "applied", tags: ["Awaiting response"] }
  ],
  Interview: [
    { id: "a4", title: "MLE, Personalization", company: "Altira", resume: "v5 ML", date: "Feb 14", status: "interview", tags: ["Prep system design"] }
  ],
  Offer: [{ id: "a5", title: "Data Platform Lead", company: "Polaris AI", resume: "v4 Data", date: "Feb 10", status: "offer", tags: ["Negotiation"] }],
  Archived: [{ id: "a6", title: "Data Analyst", company: "LegacySoft", resume: "v2 General", date: "Jan 11", status: "archived", tags: ["Role mismatch"] }]
};
