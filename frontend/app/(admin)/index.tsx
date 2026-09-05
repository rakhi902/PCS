import { useQuery } from "@tanstack/react-query";
import { View, Text, ScrollView, Pressable, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { inr } from "@/src/format";
import { ScreenHeader } from "@/src/ui";
import { useAuth } from "@/src/auth";

function Kpi({ label, value, tone, testID, onPress }: any) {
  const { colors } = useTheme();
  const tones: any = { primary: colors.brandPrimary, warning: colors.warning, success: colors.success, error: colors.error, muted: colors.surfaceTertiary };
  const bg = tone === "muted" ? colors.surfaceSecondary : tones[tone] || colors.surfaceSecondary;
  const fg = tone === "muted" ? colors.onSurface : "#fff";
  return (
    <Pressable testID={testID} onPress={onPress} style={{ flex: 1, backgroundColor: bg, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border }}>
      <Text style={{ color: fg === "#fff" ? "rgba(255,255,255,0.85)" : colors.muted, fontSize: 12, fontWeight: "600" }}>{label}</Text>
      <Text style={{ color: fg, fontSize: 22, fontWeight: "800", marginTop: 4 }}>{value}</Text>
    </Pressable>
  );
}

export default function AdminHome() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const { data, refetch, isRefetching } = useQuery({ queryKey: ["dashAdmin"], queryFn: api.dashAdmin });
  const d = data || {};

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title={`Hello, ${user?.name || "Owner"}`} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xl }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.brandPrimary} />}>
        <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 8, fontWeight: "700" }}>REVENUE</Text>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg }}>
          <Kpi testID="kpi-today-amt" label="Today" value={inr(d.today_amount)} tone="primary" />
          <Kpi testID="kpi-month-amt" label="This Month" value={inr(d.month_amount)} tone="success" />
        </View>
        <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 8, fontWeight: "700" }}>SERVICES</Text>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
          <Kpi testID="kpi-today-svc" label="Today" value={d.today_services ?? 0} tone="muted" onPress={() => router.push("/(admin)/services")} />
          <Kpi testID="kpi-pending" label="Pending" value={d.pending_services ?? 0} tone="warning" onPress={() => router.push({ pathname: "/(admin)/services", params: { status: "pending" } })} />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
          <Kpi testID="kpi-completed" label="Completed Today" value={d.completed_today ?? 0} tone="muted" />
          <Kpi testID="kpi-month-pending" label="Month Pending" value={d.month_pending ?? 0} tone="muted" />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg }}>
          <Kpi testID="kpi-amc" label="AMC Due (Month)" value={d.amc_due_this_month ?? 0} tone="muted" onPress={() => router.push("/amc")} />
          <Kpi testID="kpi-reminders" label="Reminders" value={d.reminders_upcoming ?? 0} tone="muted" onPress={() => router.push("/reminders")} />
        </View>
        {(d.reminders_overdue ?? 0) > 0 && (
          <Pressable onPress={() => router.push("/reminders")} style={{ backgroundColor: colors.error, padding: spacing.md, borderRadius: radius.md, marginBottom: spacing.lg }}>
            <Text style={{ color: "#fff", fontWeight: "700" }}>⚠️ {d.reminders_overdue} overdue reminder(s)</Text>
          </Pressable>
        )}

        <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 8, fontWeight: "700" }}>QUICK ACTIONS</Text>
        <View style={{ flexDirection: "row", gap: spacing.md, flexWrap: "wrap" }}>
          <QuickAction testID="qa-add-customer" label="+ Customer" onPress={() => router.push("/customer/new")} />
          <QuickAction testID="qa-add-service" label="+ Service" onPress={() => router.push("/service/new")} />
          <QuickAction testID="qa-add-amc" label="+ AMC" onPress={() => router.push("/amc/new")} />
          <QuickAction testID="qa-add-reminder" label="+ Reminder" onPress={() => router.push("/reminders")} />
          <QuickAction testID="qa-users" label="Users" onPress={() => router.push("/users")} />
          <QuickAction testID="qa-reports" label="Reports" onPress={() => router.push("/reports")} />
        </View>
      </ScrollView>
    </View>
  );
}

function QuickAction({ label, onPress, testID }: any) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={{ flexBasis: "48%", flexGrow: 1, backgroundColor: colors.brandTertiary, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.brandSecondary, alignItems: "center" }}>
      <Text style={{ color: colors.onBrandTertiary, fontWeight: "700" }}>{label}</Text>
    </Pressable>
  );
}
