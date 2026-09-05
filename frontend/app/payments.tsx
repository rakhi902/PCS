import { useState } from "react";
import { View, Text, FlatList, ScrollView, RefreshControl, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState, Chip } from "@/src/ui";
import { formatDate, formatDateTime, inr } from "@/src/format";

export default function Payments() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data, refetch, isRefetching } = useQuery({ queryKey: ["payments"], queryFn: api.payments });
  const [tab, setTab] = useState<"pending" | "paid">("pending");
  const d: any = data || {};
  const list = (tab === "pending" ? d.pending : d.paid) || [];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Payments" back onBack={() => router.back()} />

      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md }}>
        <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
          <View style={{ flex: 1, backgroundColor: colors.error, padding: spacing.md, borderRadius: radius.md }}>
            <Text style={{ color: "rgba(255,255,255,0.85)", fontSize: 12, fontWeight: "600" }}>Pending ({d.count_pending || 0})</Text>
            <Text style={{ color: "#fff", fontSize: 20, fontWeight: "800", marginTop: 4 }}>{inr(d.total_pending || 0)}</Text>
          </View>
          <View style={{ flex: 1, backgroundColor: colors.success, padding: spacing.md, borderRadius: radius.md }}>
            <Text style={{ color: "rgba(255,255,255,0.85)", fontSize: 12, fontWeight: "600" }}>Paid ({d.count_paid || 0})</Text>
            <Text style={{ color: "#fff", fontSize: 20, fontWeight: "800", marginTop: 4 }}>{inr(d.total_paid || 0)}</Text>
          </View>
        </View>
        <Text style={{ color: colors.muted, fontSize: 11, marginBottom: 8 }}>AMC contract services are excluded.</Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: spacing.lg, paddingBottom: 12 }} style={{ maxHeight: 56 }}>
        <Chip testID="tab-pending" label={`Pending (${d.count_pending || 0})`} selected={tab === "pending"} onPress={() => setTab("pending")} />
        <Chip testID="tab-paid" label={`Paid (${d.count_paid || 0})`} selected={tab === "paid"} onPress={() => setTab("paid")} />
      </ScrollView>

      <FlatList
        data={list} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label={tab === "pending" ? "No pending payments" : "No completed payments yet"} testID={`empty-${tab}`} />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <Pressable testID={`pay-${item.id}`} onPress={() => router.push(`/service/${item.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "800", color: colors.onSurface, fontSize: 15 }}>{item.customer_name}</Text>
                <Text style={{ color: colors.muted, fontSize: 12 }}>{item.customer_mobile}</Text>
                <Text style={{ color: colors.muted, fontSize: 12, marginTop: 4 }}>{item.service_type} · {formatDate(item.scheduled_date)}</Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={{ color: tab === "paid" ? colors.success : colors.error, fontWeight: "800", fontSize: 16 }}>{inr(item.charges)}</Text>
                <Text style={{ color: colors.muted, fontSize: 11, marginTop: 2 }}>{item.status.replace("_", " ")}</Text>
              </View>
            </View>
            {tab === "paid" && item.payment_marked_by_name && (
              <View style={{ marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: colors.divider }}>
                <Text style={{ color: colors.onSurface, fontSize: 12 }}>
                  <Text style={{ color: colors.muted }}>Marked paid by </Text>
                  <Text style={{ fontWeight: "700" }}>{item.payment_marked_by_name}</Text>
                  <Text style={{ color: colors.muted }}> ({item.payment_marked_by_role})</Text>
                </Text>
                {item.payment_marked_at && <Text style={{ color: colors.muted, fontSize: 11, marginTop: 2 }}>{formatDateTime(item.payment_marked_at)}</Text>}
              </View>
            )}
            {tab === "paid" && !item.payment_marked_by_name && (
              <Text style={{ color: colors.muted, fontSize: 11, marginTop: 6, fontStyle: "italic" }}>Marked paid before tracking was added</Text>
            )}
          </Pressable>
        )}
      />
    </View>
  );
}
