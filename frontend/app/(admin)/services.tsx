import { useState } from "react";
import { View, Text, FlatList, ScrollView, RefreshControl, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { ScreenHeader, Chip, LabeledInput, EmptyState, StatusBadge } from "@/src/ui";
import { api } from "@/src/api";
import { formatDate, inr } from "@/src/format";
import { useAuth } from "@/src/auth";

const STATUSES = ["all", "pending", "assigned", "in_progress", "completed", "cancelled"];

export default function Services() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const params = useLocalSearchParams<{ status?: string }>();
  const [status, setStatus] = useState<string>(params.status || "all");
  const [q, setQ] = useState("");

  const { data = [], refetch, isRefetching } = useQuery({
    queryKey: ["services", status, q],
    queryFn: () => api.services({ ...(status !== "all" ? { status } : {}), ...(q ? { q } : {}) }),
  });

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Services" right={
        user?.role !== "technician" ? (
          <Pressable testID="add-service" onPress={() => router.push("/service/new")} style={{ backgroundColor: colors.brandPrimary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill }}>
            <Text style={{ color: "#fff", fontWeight: "700" }}>+ New</Text>
          </Pressable>
        ) : null
      } />
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md }}>
        <LabeledInput testID="search-services" label="Search by name / mobile" value={q} onChangeText={setQ} placeholder="Search..." />
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: spacing.lg, paddingBottom: 12 }} style={{ maxHeight: 56 }}>
        {STATUSES.map(s => <Chip key={s} testID={`chip-${s}`} label={s.replace("_", " ").toUpperCase()} selected={status === s} onPress={() => setStatus(s)} />)}
      </ScrollView>
      <FlatList
        data={data} keyExtractor={(item: any) => item.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No services" testID="empty-services" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <Pressable testID={`service-${item.id}`} onPress={() => router.push(`/service/${item.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <Text style={{ fontWeight: "700", color: colors.onSurface, fontSize: 15 }}>{item.customer_name || "—"}</Text>
              <StatusBadge status={item.status} />
            </View>
            <Text style={{ color: colors.muted, fontSize: 13 }}>{item.service_type} · {formatDate(item.scheduled_date)}</Text>
            <Text style={{ color: colors.muted, fontSize: 12, marginTop: 2 }}>{item.customer_mobile}</Text>
            {user?.role === "admin" && item.charges != null && <Text style={{ color: colors.brandPrimary, fontWeight: "700", marginTop: 4 }}>{inr(item.charges)}</Text>}
          </Pressable>
        )}
      />
    </View>
  );
}
