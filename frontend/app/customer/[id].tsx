import { useQuery } from "@tanstack/react-query";
import { View, Text, ScrollView, Pressable, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState, StatusBadge, PrimaryButton } from "@/src/ui";
import { formatDate, inr } from "@/src/format";
import { useAuth } from "@/src/auth";

export default function CustomerProfile() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const { data, refetch, isRefetching } = useQuery({ queryKey: ["cust", id], queryFn: () => api.customer(id) });
  const c = data?.customer; const services = data?.services || [];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title={c?.name || "Customer"} back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}>
        {c && (
          <View style={{ backgroundColor: colors.brandTertiary, padding: spacing.lg, borderRadius: radius.md, marginBottom: spacing.lg }}>
            <Text style={{ fontSize: 22, fontWeight: "800", color: colors.onBrandTertiary }}>{c.name}</Text>
            <Text style={{ color: colors.onBrandTertiary, marginTop: 4 }}>📱 {c.mobile}</Text>
            {c.alt_mobile ? <Text style={{ color: colors.onBrandTertiary }}>📞 {c.alt_mobile}</Text> : null}
            {c.address ? <Text style={{ color: colors.onBrandTertiary, marginTop: 4 }}>📍 {c.address}{c.city ? `, ${c.city}` : ""}</Text> : null}
            {c.notes ? <Text style={{ color: colors.onBrandTertiary, marginTop: 6, fontStyle: "italic" }}>{c.notes}</Text> : null}
          </View>
        )}

        <View style={{ flexDirection: "row", gap: 8, marginBottom: spacing.md }}>
          {user?.role !== "technician" && (
            <View style={{ flex: 1 }}>
              <PrimaryButton testID="cust-new-svc" label="+ New Service" onPress={() => router.push({ pathname: "/service/new", params: { customer_id: id } })} />
            </View>
          )}
        </View>

        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 8 }}>SERVICE HISTORY ({services.length})</Text>
        {services.length === 0 ? <EmptyState label="No services yet" /> : services.map((s: any) => (
          <Pressable key={s.id} testID={`hist-${s.id}`} onPress={() => router.push(`/service/${s.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, padding: spacing.md, borderRadius: radius.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
              <Text style={{ fontWeight: "700", color: colors.onSurface }}>{s.service_type}</Text>
              <StatusBadge status={s.status} />
            </View>
            <Text style={{ color: colors.muted, fontSize: 12 }}>{formatDate(s.scheduled_date)}</Text>
            {user?.role !== "technician" && s.charges != null && <Text style={{ color: colors.brandPrimary, fontWeight: "700" }}>{inr(s.charges)}</Text>}
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}
