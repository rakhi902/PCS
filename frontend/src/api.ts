import AsyncStorage from "@react-native-async-storage/async-storage";

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL + "/api";
const TOKEN_KEY = "pest_auth_token";
const USER_KEY = "pest_auth_user";

export type Role = "admin" | "manager" | "technician";
export type AuthUser = { id: string; username: string; name: string; role: Role; must_change_pin?: boolean };

export async function getToken() { return AsyncStorage.getItem(TOKEN_KEY); }
export async function getUser(): Promise<AuthUser | null> {
  const s = await AsyncStorage.getItem(USER_KEY);
  return s ? JSON.parse(s) : null;
}
export async function saveAuth(token: string, user: AuthUser) {
  await AsyncStorage.setItem(TOKEN_KEY, token);
  await AsyncStorage.setItem(USER_KEY, JSON.stringify(user));
}
export async function clearAuth() {
  await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
}

async function req(path: string, opts: RequestInit = {}) {
  const token = await getToken();
  const headers: any = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(API_URL + path, { ...opts, headers });
  const text = await r.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data;
}

export const api = {
  login: (username: string, pin: string) =>
    req("/auth/login", { method: "POST", body: JSON.stringify({ username, pin }) }),
  me: () => req("/auth/me"),
  changePin: (pin: string) => req("/auth/change-pin", { method: "POST", body: JSON.stringify({ pin }) }),

  users: (role?: string) => req(`/users${role ? `?role=${role}` : ""}`),
  createUser: (body: any) => req("/users", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (id: string, body: any) => req(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  resetPin: (id: string, pin: string) => req(`/users/${id}/reset-pin`, { method: "POST", body: JSON.stringify({ pin }) }),

  customers: (q?: string) => req(`/customers${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  customer: (id: string) => req(`/customers/${id}`),
  createCustomer: (body: any) => req("/customers", { method: "POST", body: JSON.stringify(body) }),
  updateCustomer: (id: string, body: any) => req(`/customers/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  serviceTypes: () => req("/service-types"),
  createServiceType: (name: string) => req("/service-types", { method: "POST", body: JSON.stringify({ name }) }),

  services: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return req(`/services${qs ? `?${qs}` : ""}`);
  },
  service: (id: string) => req(`/services/${id}`),
  createService: (body: any) => req("/services", { method: "POST", body: JSON.stringify(body) }),
  updateService: (id: string, body: any) => req(`/services/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  completeService: (id: string, body: any) => req(`/services/${id}/complete`, { method: "POST", body: JSON.stringify(body) }),
  uploadPhoto: async (id: string, phase: string, uri: string) => {
    const token = await getToken();
    const form = new FormData();
    form.append("phase", phase);
    const name = `photo_${Date.now()}.jpg`;
    if (typeof window !== "undefined" && window.navigator && (uri.startsWith("blob:") || uri.startsWith("data:") || uri.startsWith("http"))) {
      const blob = await (await fetch(uri)).blob();
      form.append("file", blob, name);
    } else {
      form.append("file", { uri, name, type: "image/jpeg" } as any);
    }
    const r = await fetch(API_URL + `/services/${id}/photos`, {
      method: "POST", body: form as any, headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) throw new Error(`Upload failed ${r.status}`);
    return r.json();
  },
  uploadSignature: async (id: string, dataUrl: string) => {
    const token = await getToken();
    const form = new FormData();
    const name = `sig_${Date.now()}.png`;
    const blob = await (await fetch(dataUrl)).blob();
    form.append("file", blob, name);
    const r = await fetch(API_URL + `/services/${id}/signature`, {
      method: "POST", body: form as any, headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) throw new Error(`Upload failed ${r.status}`);
    return r.json();
  },

  amc: () => req("/amc"),
  amcDetail: (id: string) => req(`/amc/${id}`),
  createAmc: (body: any) => req("/amc", { method: "POST", body: JSON.stringify(body) }),

  reminders: () => req("/reminders"),
  createReminder: (body: any) => req("/reminders", { method: "POST", body: JSON.stringify(body) }),
  completeReminder: (id: string) => req(`/reminders/${id}/complete`, { method: "POST" }),
  rescheduleReminder: (id: string, due_date: string) => req(`/reminders/${id}/reschedule`, { method: "POST", body: JSON.stringify({ due_date }) }),
  auditLogs: () => req("/audit-logs"),

  feedback: () => req("/feedback"),
  approveFeedback: (id: string) => req(`/feedback/${id}/approve`, { method: "POST" }),

  settings: () => req("/settings"),
  updateSettings: (body: any) => req("/settings", { method: "PATCH", body: JSON.stringify(body) }),

  dashAdmin: () => req("/dashboard/admin"),
  dashManager: () => req("/dashboard/manager"),
  dashTech: () => req("/dashboard/technician"),
  reports: () => req("/reports/summary"),
};

export function fileUrl(path: string, token: string) {
  return `${API_URL}/files/${path}?token=${encodeURIComponent(token)}`;
}
