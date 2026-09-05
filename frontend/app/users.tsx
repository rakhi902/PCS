import { useState } from "react";
import { View, Text, FlatList, Pressable, Modal, ScrollView, RefreshControl } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, LabeledInput, PrimaryButton, Chip, EmptyState } from "@/src/ui";

export default function Users() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data = [], refetch, isRefetching } = useQuery({ queryKey: ["all-users"], queryFn: () => api.users() });
  const [showAdd, setShowAdd] = useState(false);
  const [role, setRole] = useState<"manager" | "technician">("technician");
  const [username, setU] = useState(""); const [name, setN] = useState("");
  const [phone, setP] = useState(""); const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);

  const [resetFor, setResetFor] = useState<any>(null);
  const [resetPin, setResetPin] = useState("");

  const create = async () => {
    setErr(null); setBusy(true);
    try { await api.createUser({ username, name, role, phone, pin }); setShowAdd(false); setU(""); setN(""); setP(""); setPin(""); refetch(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const doReset = async () => {
    if (!/^\d{4}$/.test(resetPin)) return;
    await api.resetPin(resetFor.id, resetPin); setResetFor(null); setResetPin("");
  };
  const toggle = async (u: any) => { await api.updateUser(u.id, { active: !u.active }); refetch(); };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Users" back onBack={() => router.back()} right={
        <Pressable testID="add-user" onPress={() => setShowAdd(true)} style={{ backgroundColor: colors.brandPrimary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill }}>
          <Text style={{ color: "#fff", fontWeight: "700" }}>+ New</Text>
        </Pressable>
      } />
      <FlatList data={data.filter((u: any) => u.role !== "admin")} keyExtractor={(i: any) => i.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No users yet" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "700", color: colors.onSurface }}>{item.name} <Text style={{ color: colors.muted, fontWeight: "500" }}>@{item.username}</Text></Text>
                <Text style={{ color: colors.muted, fontSize: 12 }}>{item.role.toUpperCase()} · {item.active ? "Active" : "Inactive"}</Text>
              </View>
              <View style={{ flexDirection: "row", gap: 6 }}>
                <Pressable testID={`reset-${item.id}`} onPress={() => setResetFor(item)} style={{ paddingHorizontal: 10, paddingVertical: 6, backgroundColor: colors.info, borderRadius: radius.pill }}>
                  <Text style={{ color: "#fff", fontSize: 11, fontWeight: "700" }}>Reset PIN</Text>
                </Pressable>
                <Pressable testID={`toggle-${item.id}`} onPress={() => toggle(item)} style={{ paddingHorizontal: 10, paddingVertical: 6, backgroundColor: item.active ? colors.error : colors.success, borderRadius: radius.pill }}>
                  <Text style={{ color: "#fff", fontSize: 11, fontWeight: "700" }}>{item.active ? "Disable" : "Enable"}</Text>
                </Pressable>
              </View>
            </View>
          </View>
        )} />

      <Modal visible={showAdd} transparent animationType="slide" onRequestClose={() => setShowAdd(false)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" }}>
          <View style={{ backgroundColor: colors.surface, padding: spacing.lg, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingBottom: insets.bottom + spacing.lg }}>
            <Text style={{ fontSize: 18, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.md }}>New User</Text>
            <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
              <Chip label="Technician" selected={role === "technician"} onPress={() => setRole("technician")} />
              <Chip label="Manager" selected={role === "manager"} onPress={() => setRole("manager")} />
            </ScrollView>
            <LabeledInput testID="new-user-username" label="Username" value={username} onChangeText={setU} autoCapitalize="none" />
            <LabeledInput testID="new-user-name" label="Full Name" value={name} onChangeText={setN} />
            <LabeledInput testID="new-user-phone" label="Phone" value={phone} onChangeText={setP} keyboardType="phone-pad" />
            <LabeledInput testID="new-user-pin" label="Initial PIN (4 digits)" value={pin} onChangeText={setPin} keyboardType="number-pad" maxLength={4} secureTextEntry />
            {err && <Text style={{ color: colors.error, marginBottom: 8 }}>{err}</Text>}
            <View style={{ flexDirection: "row", gap: 8 }}>
              <View style={{ flex: 1 }}><PrimaryButton label="Cancel" variant="ghost" onPress={() => setShowAdd(false)} /></View>
              <View style={{ flex: 1 }}><PrimaryButton testID="submit-user" label="Create" onPress={create} loading={busy} disabled={!username || !name || pin.length !== 4} /></View>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={!!resetFor} transparent animationType="fade" onRequestClose={() => setResetFor(null)}>
        <Pressable style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "center", padding: spacing.lg }} onPress={() => setResetFor(null)}>
          <Pressable onPress={() => {}} style={{ backgroundColor: colors.surface, padding: spacing.lg, borderRadius: radius.md }}>
            <Text style={{ fontSize: 16, fontWeight: "800", color: colors.onSurface, marginBottom: 8 }}>Reset PIN for {resetFor?.name}</Text>
            <LabeledInput testID="reset-pin" label="New 4-digit PIN" value={resetPin} onChangeText={setResetPin} keyboardType="number-pad" maxLength={4} secureTextEntry />
            <PrimaryButton testID="submit-reset" label="Reset" onPress={doReset} disabled={resetPin.length !== 4} />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}
