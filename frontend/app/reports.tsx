import { useQuery } from "@tanstack/react-query";
import { View, Text, ScrollView, RefreshControl, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState } from "@/src/ui";
import { inr } from "@/src/format";

function Kpi({ label, value, tone }: any) {
  return (
    <View style={{ flex: 1, backgroundColor: tone, padding: spacing.lg, borderRadius: radius.md }}>
      <Text style={{ color: "rgba(255,255,255,0.85)", fontSize: 12, fontWeight: "600" }}>{label}</Text>
      <Text style={{ color: "#fff", fontSize: 22, fontWeight: "800", marginTop: 4 }}>{value}</Text>
    </View>
  );
}
function Card({ children, title }: any) {
  const { colors } = useTheme();
  return (
    <View style={{ marginBottom: spacing.lg }}>
      <Text style={{ fontWeight: "700", color: colors.muted, marginBottom: 8 }}>{title}</Text>
      <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border }}>
        {children}
      </View>
    </View>
  );
}

function BarRow({ label, count, max, tone }: any) {
  const { colors } = useTheme();
  const pct = max > 0 ? Math.min(100, (count / max) * 100) : 0;
  return (
    <View style={{ paddingVertical: 6 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
        <Text style={{ color: colors.onSurface, fontSize: 13, fontWeight: "600" }}>{label}</Text>
        <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700" }}>{count}</Text>
      </View>
      <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surfaceTertiary, overflow: "hidden" }}>
        <View style={{ height: 8, width: `${pct}%`, backgroundColor: tone || colors.brandPrimary, borderRadius: 4 }} />
      </View>
    </View>
  );
}

export default function Reports() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data, refetch, isRefetching } = useQuery({ queryKey: ["reports"], queryFn: api.reports });
  const d: any = data || {};
  const dailyMax = Math.max(1, ...(d.daily_services || []).map((r: any) => r.count));
  const monthMax = Math.max(1, ...(d.monthly_services || []).map((r: any) => r.count));

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Reports" back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
          <Kpi label="Total Revenue" value={inr(d.total_revenue)} tone={colors.brandPrimary} />
          <Kpi label="This Month" value={inr(d.month_revenue)} tone={colors.success} />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg }}>
          <Kpi label="Pending" value={d.pending_services_count ?? 0} tone={colors.warning} />
          <Kpi label="Customers" value={d.customers_count ?? 0} tone={colors.info} />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg }}>
          <Kpi label="AMC Contracts" value={d.amc_count ?? 0} tone={colors.brandPrimary} />
          <Kpi label="AMC Services" value={d.amc_services_count ?? 0} tone={colors.info} />
        </View>

        <Card title="DAILY SERVICES (LAST 7 DAYS)">
          {(d.daily_services || []).map((r: any) => (
            <BarRow key={r.date} label={r.date} count={r.count} max={dailyMax} tone={colors.brandPrimary} />
          ))}
        </Card>

        <Card title="MONTHLY SERVICES (LAST 6 MONTHS)">
          {(d.monthly_services || []).map((r: any) => (
            <View key={r.month} style={{ paddingVertical: 6 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
                <Text style={{ color: colors.onSurface, fontSize: 13, fontWeight: "600" }}>{r.month}</Text>
                <Text style={{ color: colors.muted, fontSize: 12, fontWeight: "700" }}>{r.count} · {inr(r.revenue)}</Text>
              </View>
              <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surfaceTertiary, overflow: "hidden" }}>
                <View style={{ height: 8, width: `${Math.min(100, (r.count / monthMax) * 100)}%`, backgroundColor: colors.success, borderRadius: 4 }} />
              </View>
            </View>
          ))}
        </Card>

        <Card title="REVENUE BY SERVICE TYPE">
          {Object.entries(d.by_service_type || {}).length === 0 ? <Text style={{ color: colors.muted }}>No data</Text> :
            Object.entries(d.by_service_type || {}).map(([k, v]: any) => (
              <View key={k} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 }}>
                <Text style={{ color: colors.onSurface }}>{k}</Text>
                <Text style={{ color: colors.brandPrimary, fontWeight: "700" }}>{inr(v)}</Text>
              </View>
            ))}
        </Card>

        <Card title="TECHNICIAN PERFORMANCE">
          {(d.technicians || []).length === 0 ? <Text style={{ color: colors.muted }}>No technicians</Text> :
            (d.technicians || []).map((t: any) => (
              <View key={t.id} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 }}>
                <Text style={{ color: colors.onSurface }}>{t.name}</Text>
                <Text style={{ color: colors.onSurface, fontWeight: "700" }}>{t.completed} jobs</Text>
              </View>
            ))}
        </Card>

        <Card title="TOP CUSTOMERS (BY SERVICE COUNT)">
          {(d.top_customers || []).length === 0 ? <Text style={{ color: colors.muted }}>No data</Text> :
            (d.top_customers || []).map((c: any) => (
              <Pressable key={c.id} onPress={() => router.push(`/customer/${c.id}`)} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.divider }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.onSurface, fontWeight: "600" }}>{c.name}</Text>
                  <Text style={{ color: colors.muted, fontSize: 11 }}>{c.mobile}</Text>
                </View>
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={{ color: colors.onSurface, fontWeight: "700" }}>{c.services} jobs</Text>
                  <Text style={{ color: colors.brandPrimary, fontSize: 12, fontWeight: "700" }}>{inr(c.revenue)}</Text>
                </View>
              </Pressable>
            ))}
        </Card>

        <Pressable testID="view-audit" onPress={() => router.push("/audit")}
          style={{ backgroundColor: colors.surfaceInverse, padding: spacing.lg, borderRadius: radius.md, alignItems: "center", marginTop: spacing.sm }}>
          <Text style={{ color: colors.onSurfaceInverse, fontWeight: "700" }}>📋 View Audit Log</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
