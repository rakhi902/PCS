import { useState } from "react";
import { View, Text, FlatList, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, LabeledInput, PrimaryButton, EmptyState } from "@/src/ui";

export default function ServiceTypes() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["stypes"], queryFn: api.serviceTypes });
  const [name, setName] = useState(""); const [busy, setBusy] = useState(false);
  const add = async () => { if (!name) return; setBusy(true); try { await api.createServiceType(name); setName(""); refetch(); } catch {} finally { setBusy(false); } };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Service Types" back onBack={() => router.back()} />
      <FlatList data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        ListHeaderComponent={
          <View style={{ backgroundColor: colors.surfaceSecondary, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.md }}>
            <LabeledInput label="New service type" value={name} onChangeText={setName} placeholder="e.g. Bed bug" />
            <PrimaryButton testID="add-type" label="Add" onPress={add} loading={busy} disabled={!name} />
          </View>
        }
        ListEmptyComponent={<EmptyState label="None" />}
        renderItem={({ item }: any) => (
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <Text style={{ color: colors.onSurface, fontWeight: "600" }}>{item.name}</Text>
          </View>
        )} />
    </View>
  );
}
