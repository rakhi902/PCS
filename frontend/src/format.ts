export function formatDate(iso?: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yy = d.getFullYear();
  return `${dd}/${mm}/${yy}`;
}
export function formatDateTime(iso?: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  return `${formatDate(iso)} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
export function inr(n?: number | null) {
  const v = Number(n || 0);
  return "₹" + v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}
export function statusColor(status: string, colors: any): string {
  switch (status) {
    case "pending": return colors.warning;
    case "assigned": return colors.info;
    case "in_progress": return colors.brandPrimary;
    case "completed": return colors.success;
    case "cancelled": return colors.error;
    default: return colors.muted;
  }
}
export function statusLabel(s: string) {
  return ({ pending: "Pending", assigned: "Assigned", in_progress: "In Progress", completed: "Completed", cancelled: "Cancelled" } as any)[s] || s;
}
