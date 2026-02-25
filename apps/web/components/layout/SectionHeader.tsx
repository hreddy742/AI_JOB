export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h2 className="display-sm">{title}</h2>
      {subtitle ? <p className="body-sm mt-1">{subtitle}</p> : null}
    </div>
  );
}
