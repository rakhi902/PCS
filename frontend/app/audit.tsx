import { useQuery } from "@tanstack/react-query";
import { View, Text, FlatList, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState } from "@/src/ui";
import { formatDateTime } from "@/src/format";

export default function Audit() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["audit"], queryFn: api.auditLogs });

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Audit Log" back onBack={() => router.back()} />
      <FlatList data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No activity yet" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ fontWeight: "700", color: colors.onSurface, fontSize: 14 }}>{item.entity.toUpperCase()} · {item.action}</Text>
              <Text style={{ color: colors.muted, fontSize: 11 }}>{formatDateTime(item.at)}</Text>
            </View>
            <Text style={{ color: colors.muted, fontSize: 12, marginTop: 4 }}>by {item.user_name || "—"}</Text>
            {item.changes && Object.keys(item.changes).length > 0 && (
              <Text style={{ color: colors.onSurfaceSecondary, fontSize: 11, marginTop: 6, fontFamily: "monospace" }}>
                {Object.entries(item.changes).map(([k, v]: any) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ")}
              </Text>
            )}
          </View>
        )} />
    </View>
  );
}
