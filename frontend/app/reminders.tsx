import { useState, useEffect } from "react";
import { View, Text, FlatList, Pressable, RefreshControl, ScrollView, Linking } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState, PrimaryButton, LabeledInput, DateField, Chip, StatusBadge } from "@/src/ui";
import { formatDate } from "@/src/format";

export default function Reminders() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["reminders"], queryFn: api.reminders });
  const { data: customers = [] } = useQuery({ queryKey: ["custs-all"], queryFn: () => api.customers() });
  const { data: types = [] } = useQuery({ queryKey: ["types"], queryFn: api.serviceTypes });

  const [cust, setCust] = useState(""); const [type, setType] = useState("");
  const [date, setDate] = useState(new Date(Date.now() + 30 * 86400000).toISOString());
  const [notes, setNotes] = useState(""); const [busy, setBusy] = useState(false);

  useEffect(() => { if (!type && types[0]) setType(types[0].name); }, [types]);

  const add = async () => {
    if (!cust) return;
    setBusy(true);
    try { await api.createReminder({ customer_id: cust, service_type: type, due_date: date, notes }); setCust(""); setNotes(""); refetch(); } finally { setBusy(false); }
  };
  const done = async (id: string) => { await api.completeReminder(id); refetch(); };

  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const nudge = (item: any) => {
    const due = new Date(item.due_date);
    const dueStr = `${String(due.getDate()).padStart(2, "0")}/${String(due.getMonth() + 1).padStart(2, "0")}/${due.getFullYear()}`;
    const gUrl = settings?.google_review_url || "";
    const defaultTmpl = "Hi {name}, this is a friendly reminder that your {service_type} service is due on {due_date}. Please contact us to schedule. {link}";
    const tmpl = (settings?.whatsapp_template && settings.whatsapp_template.includes("{due_date}") ? settings.whatsapp_template : defaultTmpl)
      .replace("{name}", item.customer_name || "there")
      .replace("{service_type}", item.service_type || "pest control")
      .replace("{due_date}", dueStr)
      .replace("{link}", gUrl || "");
    const mobile = (item.customer_mobile || "").replace(/\D/g, "");
    Linking.openURL(`https://wa.me/${mobile}?text=${encodeURIComponent(tmpl)}`);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Reminders" back onBack={() => router.back()} />
      <FlatList data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListHeaderComponent={
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg }}>
            <Text style={{ fontWeight: "700", color: colors.onSurface, marginBottom: 8 }}>Add Reminder</Text>
            <Text style={{ fontSize: 12, color: colors.muted, marginBottom: 6, fontWeight: "600" }}>CUSTOMER</Text>
            <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
              {customers.map((c: any) => <Chip key={c.id} label={c.name} selected={cust === c.id} onPress={() => setCust(c.id)} />)}
            </ScrollView>
            <Text style={{ fontSize: 12, color: colors.muted, marginBottom: 6, fontWeight: "600" }}>TYPE</Text>
            <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
              {types.map((t: any) => <Chip key={t.id} label={t.name} selected={type === t.name} onPress={() => setType(t.name)} />)}
            </ScrollView>
            <DateField label="Due Date" value={date} onChange={setDate} />
            <LabeledInput label="Notes" value={notes} onChangeText={setNotes} />
            <PrimaryButton testID="add-reminder" label="Add" onPress={add} loading={busy} disabled={!cust} />
          </View>
        }
        ListEmptyComponent={<EmptyState label="No reminders" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
              <Text style={{ fontWeight: "700", color: colors.onSurface }}>{item.customer_name}</Text>
              <StatusBadge status={item.computed} />
            </View>
            <Text style={{ color: colors.muted, fontSize: 13 }}>{item.service_type} · Due {formatDate(item.due_date)}</Text>
            {item.notes ? <Text style={{ color: colors.muted, fontSize: 12, marginTop: 2 }}>{item.notes}</Text> : null}
            {item.status !== "completed" && (
              <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
                <Pressable testID={`rem-done-${item.id}`} onPress={() => done(item.id)} style={{ paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.brandPrimary, borderRadius: radius.pill }}>
                  <Text style={{ color: "#fff", fontWeight: "700", fontSize: 12 }}>Mark Done</Text>
                </Pressable>
                <Pressable testID={`rem-nudge-${item.id}`} onPress={() => nudge(item)} style={{ paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.success, borderRadius: radius.pill }}>
                  <Text style={{ color: "#fff", fontWeight: "700", fontSize: 12 }}>💬 Nudge on WhatsApp</Text>
                </Pressable>
              </View>
            )}
          </View>
        )} />
    </View>
  );
}
