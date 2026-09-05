import { useState } from "react";
import { View, Text, FlatList, RefreshControl, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { ScreenHeader, LabeledInput, EmptyState } from "@/src/ui";
import { api } from "@/src/api";

export default function Customers() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [q, setQ] = useState("");
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["customers", q], queryFn: () => api.customers(q) });

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Customers" right={
        <Pressable testID="add-customer" onPress={() => router.push("/customer/new")} style={{ backgroundColor: colors.brandPrimary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill }}>
          <Text style={{ color: "#fff", fontWeight: "700" }}>+ New</Text>
        </Pressable>
      } />
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md }}>
        <LabeledInput testID="search-customers" label="Search" value={q} onChangeText={setQ} placeholder="Name or mobile..." />
      </View>
      <FlatList
        data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No customers yet" testID="empty-customers" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <Pressable testID={`customer-${item.id}`} onPress={() => router.push(`/customer/${item.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <Text style={{ fontWeight: "700", color: colors.onSurface, fontSize: 15 }}>{item.name}</Text>
            <Text style={{ color: colors.muted, fontSize: 13, marginTop: 2 }}>{item.mobile}</Text>
            {item.city && <Text style={{ color: colors.muted, fontSize: 12 }}>{item.city}</Text>}
          </Pressable>
        )}
      />
    </View>
  );
}
