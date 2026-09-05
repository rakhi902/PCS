import { useQuery } from "@tanstack/react-query";
import { View, Text, FlatList, Pressable, RefreshControl, Linking } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, EmptyState } from "@/src/ui";
import { formatDate, inr } from "@/src/format";
import { useAuth } from "@/src/auth";

export default function AMCList() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["amcs"], queryFn: api.amc });
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  const nudge = (a: any) => {
    const end = new Date(a.end_date);
    const endStr = `${String(end.getDate()).padStart(2, "0")}/${String(end.getMonth() + 1).padStart(2, "0")}/${end.getFullYear()}`;
    const tmpl = `Hi ${a.customer_name || "there"}, your AMC contract for ${a.service_type} ends on ${endStr}. Reach out to us to renew and stay protected.`;
    const mobile = (a.customer_mobile || "").replace(/\D/g, "");
    Linking.openURL(`https://wa.me/${mobile}?text=${encodeURIComponent(tmpl)}`);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="AMC Contracts" back onBack={() => router.back()} right={
        <Pressable testID="add-amc" onPress={() => router.push("/amc/new")} style={{ backgroundColor: colors.brandPrimary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill }}>
          <Text style={{ color: "#fff", fontWeight: "700" }}>+ New</Text>
        </Pressable>
      } />
      <FlatList data={data} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No AMCs yet" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <Text style={{ fontWeight: "800", color: colors.onSurface }}>{item.customer_name}</Text>
            <Text style={{ color: colors.muted, fontSize: 13 }}>{item.service_type} · {item.frequency}</Text>
            <Text style={{ color: colors.muted, fontSize: 12, marginTop: 2 }}>{formatDate(item.start_date)} → {formatDate(item.end_date)}</Text>
            {user?.role === "admin" && item.contract_amount != null && <Text style={{ color: colors.brandPrimary, fontWeight: "700", marginTop: 4 }}>{inr(item.contract_amount)}</Text>}
            <Pressable testID={`amc-nudge-${item.id}`} onPress={() => nudge(item)} style={{ marginTop: 8, alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.success, borderRadius: radius.pill }}>
              <Text style={{ color: "#fff", fontWeight: "700", fontSize: 12 }}>💬 Nudge on WhatsApp</Text>
            </Pressable>
          </View>
        )} />
    </View>
  );
}
