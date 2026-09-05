import { View, Text, FlatList, Pressable, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState } from "@/src/ui";
import { useAuth } from "@/src/auth";

export default function Feedback() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["fb"], queryFn: api.feedback });
  const approve = async (id: string) => { await api.approveFeedback(id); refetch(); };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Feedback" back onBack={() => router.back()} />
      <FlatList data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No feedback yet" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <Text style={{ fontWeight: "700", color: colors.onSurface }}>{item.customer_name || "Customer"} · ⭐ {item.rating}</Text>
            {item.comment ? <Text style={{ color: colors.muted, marginTop: 4 }}>{item.comment}</Text> : null}
            <Text style={{ color: item.approved ? colors.success : colors.warning, fontSize: 12, marginTop: 6, fontWeight: "700" }}>{item.approved ? "APPROVED" : "PENDING"}</Text>
            {user?.role === "admin" && !item.approved && (
              <Pressable testID={`approve-${item.id}`} onPress={() => approve(item.id)} style={{ marginTop: 8, alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.brandPrimary, borderRadius: radius.pill }}>
                <Text style={{ color: "#fff", fontWeight: "700", fontSize: 12 }}>Approve</Text>
              </Pressable>
            )}
          </View>
        )} />
    </View>
  );
}
