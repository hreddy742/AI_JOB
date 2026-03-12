"use client";

import { ChangeEvent, useEffect, useState } from "react";

import { OutreachCrmTable } from "@/components/outreach-crm-table";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/lib/store/auth-store";

type Contact = {
  id: string;
  name?: string;
  company?: string;
  title?: string;
  email?: string;
  linkedin_url?: string;
};

type OutreachItem = {
  id: string;
  contact_id: string;
  status: string;
  draft_text: string;
  sent_at?: string | null;
  follow_up_at?: string | null;
};

export default function OutreachPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [rows, setRows] = useState<OutreachItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [contactName, setContactName] = useState("");
  const [contactCompany, setContactCompany] = useState("");
  const [contactTitle, setContactTitle] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactLinkedIn, setContactLinkedIn] = useState("");
  const [selectedContactId, setSelectedContactId] = useState("");
  const [jobId, setJobId] = useState("");

  async function loadData() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [contactsData, outreachData] = await Promise.all([
        api.listContacts(token) as Promise<Contact[]>,
        api.listOutreach(token) as Promise<OutreachItem[]>,
      ]);
      setContacts(contactsData || []);
      setRows(outreachData || []);
      if (!selectedContactId && contactsData?.[0]?.id) setSelectedContactId(String(contactsData[0].id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load outreach data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleCreateContact() {
    if (!token) return;
    setMessage(null);
    setError(null);
    try {
      await api.createContact(token, {
        name: contactName || undefined,
        company: contactCompany || undefined,
        title: contactTitle || undefined,
        email: contactEmail || undefined,
        linkedin_url: contactLinkedIn || undefined,
        source: "manual_ui",
      });
      setContactName("");
      setContactCompany("");
      setContactTitle("");
      setContactEmail("");
      setContactLinkedIn("");
      setMessage("Contact created.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create contact");
    }
  }

  async function handleImportLinkedIn() {
    if (!token || !importFile) return;
    setMessage(null);
    setError(null);
    try {
      const result = (await api.importLinkedInContacts(token, importFile)) as { imported: number; skipped: number };
      setImportFile(null);
      setMessage(`Imported ${result.imported} contacts, skipped ${result.skipped}.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import LinkedIn contacts");
    }
  }

  async function handleDraftOutreach() {
    if (!token || !selectedContactId) return;
    setMessage(null);
    setError(null);
    try {
      await api.draftOutreach(token, { contact_id: selectedContactId, job_id: jobId || undefined });
      setJobId("");
      setMessage("Outreach draft created.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to draft outreach");
    }
  }

  async function handleApprove(id: string) {
    if (!token) return;
    setBusyId(id);
    try {
      await api.approveOutreach(token, id);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve outreach");
    } finally {
      setBusyId(null);
    }
  }

  async function handleSend(id: string) {
    if (!token) return;
    setBusyId(id);
    try {
      await api.sendOutreach(token, id, true);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send outreach");
    } finally {
      setBusyId(null);
    }
  }

  async function handleUpdateStatus(id: string, status: string) {
    if (!token) return;
    setBusyId(id);
    try {
      await api.updateOutreachStatus(token, id, { status });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update outreach status");
    } finally {
      setBusyId(null);
    }
  }

  const contactMap: Record<string, Contact> = {};
  contacts.forEach((contact) => {
    contactMap[String(contact.id)] = contact;
  });

  const tableRows = rows.map((row) => ({
    id: String(row.id),
    contactId: String(row.contact_id),
    name: contactMap[String(row.contact_id)]?.name || "Unknown",
    company: contactMap[String(row.contact_id)]?.company || "",
    status: row.status,
    draftText: row.draft_text,
    sentAt: row.sent_at,
    followUpAt: row.follow_up_at,
  }));

  if (loading) return <div className="p-4 text-sm text-slate-400">Loading outreach...</div>;
  if (error) return <div className="rounded-md bg-red-500/20 p-3 text-sm text-red-200">{error}</div>;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 rounded-md border p-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Contacts</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            <input value={contactName} onChange={(e) => setContactName(e.target.value)} className="rounded border px-3 py-2 text-sm" placeholder="Name" />
            <input value={contactCompany} onChange={(e) => setContactCompany(e.target.value)} className="rounded border px-3 py-2 text-sm" placeholder="Company" />
            <input value={contactTitle} onChange={(e) => setContactTitle(e.target.value)} className="rounded border px-3 py-2 text-sm" placeholder="Title" />
            <input value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} className="rounded border px-3 py-2 text-sm" placeholder="Email" />
            <input value={contactLinkedIn} onChange={(e) => setContactLinkedIn(e.target.value)} className="rounded border px-3 py-2 text-sm sm:col-span-2" placeholder="LinkedIn URL" />
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => void handleCreateContact()} className="rounded border px-3 py-2 text-sm hover:bg-slate-50">
              Create contact
            </button>
            <input type="file" accept=".csv,text/csv" onChange={(e: ChangeEvent<HTMLInputElement>) => setImportFile(e.target.files?.[0] || null)} />
            <button type="button" disabled={!importFile} onClick={() => void handleImportLinkedIn()} className="rounded border px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50">
              Import LinkedIn CSV
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Draft outreach</h2>
          <select value={selectedContactId} onChange={(e) => setSelectedContactId(e.target.value)} className="w-full rounded border px-3 py-2 text-sm">
            <option value="">Select contact</option>
            {contacts.map((contact) => (
              <option key={contact.id} value={String(contact.id)}>
                {contact.name || "Unnamed"}{contact.company ? ` - ${contact.company}` : ""}
              </option>
            ))}
          </select>
          <input value={jobId} onChange={(e) => setJobId(e.target.value)} className="w-full rounded border px-3 py-2 text-sm" placeholder="Optional job ID" />
          <button type="button" disabled={!selectedContactId} onClick={() => void handleDraftOutreach()} className="rounded border px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50">
            Create outreach draft
          </button>
          {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
        </div>
      </section>

      <OutreachCrmTable
        rows={tableRows}
        busyId={busyId}
        onApprove={handleApprove}
        onSend={handleSend}
        onUpdateStatus={handleUpdateStatus}
      />
    </div>
  );
}
