import { useQuery } from "@tanstack/react-query";
import { View, Text, ScrollView, RefreshControl, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, StatusBadge, EmptyState } from "@/src/ui";
import { formatDate } from "@/src/format";
import { useAuth } from "@/src/auth";

function Kpi({ label, value, tone, testID, onPress }: any) {
  const { colors } = useTheme();
  const tones: any = { warning: colors.warning, primary: colors.brandPrimary, muted: colors.surfaceSecondary };
  const bg = tones[tone] || colors.surfaceSecondary;
  const fg = tone === "muted" ? colors.onSurface : "#fff";
  return (
    <Pressable testID={testID} onPress={onPress} style={{ flex: 1, backgroundColor: bg, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border }}>
      <Text style={{ color: tone === "muted" ? colors.muted : "rgba(255,255,255,0.85)", fontSize: 12, fontWeight: "600" }}>{label}</Text>
      <Text style={{ color: fg, fontSize: 22, fontWeight: "800", marginTop: 4 }}>{value}</Text>
    </Pressable>
  );
}

export default function ManagerHome() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const { data, refetch, isRefetching } = useQuery({ queryKey: ["dashMgr"], queryFn: api.dashManager });
  const d = data || {};
  const recent = d.recent_completed || [];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title={`Hello, ${user?.name || "Manager"}`} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
          <Kpi testID="mgr-pending-svc" label="Pending Services" value={d.pending_services ?? 0} tone="warning" onPress={() => router.push("/(manager)/services")} />
          <Kpi testID="mgr-pending-pay" label="Pending Payments" value={d.pending_payments ?? 0} tone="primary" />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg }}>
          <Kpi testID="mgr-reminders" label="Upcoming Reminders" value={d.upcoming_reminders ?? 0} tone="muted" onPress={() => router.push("/reminders")} />
          <Kpi testID="mgr-completed" label="Recently Done" value={recent.length} tone="muted" />
        </View>

        <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 8, fontWeight: "700" }}>RECENTLY COMPLETED</Text>
        {recent.length === 0 ? <EmptyState label="Nothing completed yet" /> : recent.map((s: any) => (
          <Pressable key={s.id} testID={`recent-${s.id}`} onPress={() => router.push(`/service/${s.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
              <Text style={{ fontWeight: "700", color: colors.onSurface }}>{s.service_type}</Text>
              <StatusBadge status="completed" />
            </View>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{formatDate(s.completed_at || s.scheduled_date)}</Text>
          </Pressable>
        ))}

        <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 8, marginTop: spacing.lg, fontWeight: "700" }}>QUICK ACTIONS</Text>
        <View style={{ flexDirection: "row", gap: spacing.md, flexWrap: "wrap" }}>
          {[
            { l: "+ Customer", p: "/customer/new", t: "qa-cust" },
            { l: "+ Service", p: "/service/new", t: "qa-svc" },
            { l: "+ AMC", p: "/amc/new", t: "qa-amc" },
            { l: "+ Reminder", p: "/reminders", t: "qa-rem" },
          ].map(a => (
            <Pressable key={a.l} testID={a.t} onPress={() => router.push(a.p as any)}
              style={{ flexBasis: "48%", flexGrow: 1, backgroundColor: colors.brandTertiary, padding: spacing.md, borderRadius: radius.md, alignItems: "center", borderWidth: 1, borderColor: colors.brandSecondary }}>
              <Text style={{ color: colors.onBrandTertiary, fontWeight: "700" }}>{a.l}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}
