import { useQuery } from "@tanstack/react-query";
import { View, Text, FlatList, RefreshControl, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, StatusBadge, EmptyState } from "@/src/ui";
import { formatDate } from "@/src/format";
import { useAuth } from "@/src/auth";

export function TechServicesList({ title, params }: { title: string; params: Record<string, string> }) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data = [], refetch, isRefetching } = useQuery({
    queryKey: ["tech-svc", JSON.stringify(params)],
    queryFn: () => api.services(params),
  });

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title={title} />
      <FlatList
        data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No jobs" testID="empty-tech" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <Pressable testID={`tech-job-${item.id}`} onPress={() => router.push(`/service/${item.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, marginBottom: spacing.md, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text style={{ fontWeight: "800", color: colors.onSurface, fontSize: 16 }}>{item.customer_name}</Text>
              <StatusBadge status={item.status} />
            </View>
            <Text style={{ color: colors.onSurface, fontSize: 14 }}>{item.service_type}</Text>
            <Text style={{ color: colors.muted, fontSize: 13, marginTop: 4 }}>📅 {formatDate(item.scheduled_date)}</Text>
            <Text style={{ color: colors.muted, fontSize: 13 }}>📱 {item.customer_mobile}</Text>
            {item.customer_address && <Text style={{ color: colors.muted, fontSize: 13 }}>📍 {item.customer_address}</Text>}
          </Pressable>
        )}
      />
    </View>
  );
}

export default function TechToday() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).toISOString();
  return <TechServicesList title="Today's Jobs" params={{ date_from: start, date_to: end }} />;
}
