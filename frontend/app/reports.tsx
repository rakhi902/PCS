import { useQuery } from "@tanstack/react-query";
import { View, Text, ScrollView, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader } from "@/src/ui";
import { inr } from "@/src/format";

export default function Reports() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data, refetch, isRefetching } = useQuery({ queryKey: ["reports"], queryFn: api.reports });
  const d = data || {};

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Reports" back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg }}>
          <Kpi label="Total Revenue" value={inr(d.total_revenue)} tone={colors.brandPrimary} />
          <Kpi label="This Month" value={inr(d.month_revenue)} tone={colors.success} />
        </View>

        <Text style={{ fontWeight: "700", color: colors.muted, marginBottom: 8 }}>REVENUE BY SERVICE TYPE</Text>
        <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg }}>
          {Object.entries(d.by_service_type || {}).length === 0 ? <Text style={{ color: colors.muted }}>No data</Text> :
            Object.entries(d.by_service_type || {}).map(([k, v]: any) => (
              <View key={k} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 }}>
                <Text style={{ color: colors.onSurface }}>{k}</Text>
                <Text style={{ color: colors.brandPrimary, fontWeight: "700" }}>{inr(v)}</Text>
              </View>
            ))}
        </View>

        <Text style={{ fontWeight: "700", color: colors.muted, marginBottom: 8 }}>TECHNICIAN PERFORMANCE</Text>
        <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: colors.border }}>
          {(d.technicians || []).length === 0 ? <Text style={{ color: colors.muted }}>No technicians</Text> :
            (d.technicians || []).map((t: any) => (
              <View key={t.id} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 }}>
                <Text style={{ color: colors.onSurface }}>{t.name}</Text>
                <Text style={{ color: colors.onSurface, fontWeight: "700" }}>{t.completed} jobs</Text>
              </View>
            ))}
        </View>
      </ScrollView>
    </View>
  );
}
function Kpi({ label, value, tone }: any) {
  return (
    <View style={{ flex: 1, backgroundColor: tone, padding: spacing.lg, borderRadius: radius.md }}>
      <Text style={{ color: "rgba(255,255,255,0.85)", fontSize: 12, fontWeight: "600" }}>{label}</Text>
      <Text style={{ color: "#fff", fontSize: 22, fontWeight: "800", marginTop: 4 }}>{value}</Text>
    </View>
  );
}
