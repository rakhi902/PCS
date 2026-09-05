import { useState } from "react";
import { View, Text, ScrollView } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing } from "@/src/theme";
import { PrimaryButton, LabeledInput } from "@/src/ui";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";

export default function ChangePin() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, refresh } = useAuth();
  const [p1, setP1] = useState(""); const [p2, setP2] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr(null);
    if (p1.length !== 4 || !/^\d{4}$/.test(p1)) return setErr("PIN must be 4 digits");
    if (p1 !== p2) return setErr("PINs do not match");
    setBusy(true);
    try {
      await api.changePin(p1);
      await refresh();
      const AsyncStorage = require("@react-native-async-storage/async-storage").default;
      const u = { ...(user || {}), must_change_pin: false };
      await AsyncStorage.setItem("pest_auth_user", JSON.stringify(u));
      await refresh();
      router.replace(`/(${user?.role})` as any);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top + spacing.lg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.xl }}>
        <Text style={{ fontSize: 22, fontWeight: "800", color: colors.onSurface, marginBottom: 4 }}>Change your PIN</Text>
        <Text style={{ color: colors.muted, marginBottom: spacing.xl }}>Set a new 4-digit PIN before continuing.</Text>
        <LabeledInput testID="new-pin" label="New PIN" value={p1} onChangeText={setP1} keyboardType="number-pad" secureTextEntry maxLength={4} />
        <LabeledInput testID="confirm-pin" label="Confirm PIN" value={p2} onChangeText={setP2} keyboardType="number-pad" secureTextEntry maxLength={4} />
        {err && <Text style={{ color: colors.error, marginBottom: 8 }}>{err}</Text>}
        <PrimaryButton testID="save-pin" label="Save New PIN" onPress={submit} loading={busy} />
      </ScrollView>
    </View>
  );
}
