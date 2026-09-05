import { useState } from "react";
import { View, Text, Pressable, StyleSheet, KeyboardAvoidingView, Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "@/src/auth";
import { useTheme, spacing, radius } from "@/src/theme";
import { PrimaryButton } from "@/src/ui";

export default function Login() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { login } = useAuth();
  const [username, setUsername] = useState("admin");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr(null); setBusy(true);
    try { await login(username, pin); }
    catch (e: any) { setErr(e.message || "Login failed"); }
    finally { setBusy(false); }
  };

  const tap = (d: string) => { if (pin.length < 4) setPin(pin + d); };
  const del = () => setPin(pin.slice(0, -1));

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <View style={{ padding: spacing.xl, alignItems: "center" }}>
          <View style={{ width: 72, height: 72, borderRadius: radius.lg, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginTop: spacing.xl }}>
            <Text style={{ fontSize: 32 }}>🛡️</Text>
          </View>
          <Text style={{ fontSize: 24, fontWeight: "800", color: colors.onSurface, marginTop: spacing.md }}>PestControlPro</Text>
          <Text style={{ color: colors.muted, marginTop: 4 }}>Sign in with PIN</Text>
        </View>

        <View style={{ paddingHorizontal: spacing.xl }}>
          <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" }}>Username</Text>
          <View style={{ backgroundColor: colors.surfaceTertiary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.md }}>
            <UsernameInput value={username} onChangeText={setUsername} />
          </View>

          <View style={{ flexDirection: "row", justifyContent: "center", gap: 12, marginVertical: spacing.md }}>
            {[0, 1, 2, 3].map((i) => (
              <View key={i} testID={`pin-dot-${i}`} style={{
                width: 18, height: 18, borderRadius: 9,
                backgroundColor: pin.length > i ? colors.brandPrimary : colors.surfaceTertiary,
                borderWidth: 1, borderColor: colors.border,
              }} />
            ))}
          </View>
          {err && <Text testID="login-error" style={{ color: colors.error, textAlign: "center", marginBottom: 8 }}>{err}</Text>}
        </View>

        <View style={{ paddingHorizontal: spacing.xl, marginTop: spacing.md }}>
          {[["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["", "0", "⌫"]].map((row, ri) => (
            <View key={ri} style={{ flexDirection: "row", justifyContent: "center", gap: 16, marginBottom: 16 }}>
              {row.map((d, i) => (
                <Pressable key={i} testID={d ? `pin-key-${d}` : undefined} onPress={() => d === "⌫" ? del() : d && tap(d)} disabled={!d}
                  style={({ pressed }) => ({
                    width: 76, height: 76, borderRadius: 38, alignItems: "center", justifyContent: "center",
                    backgroundColor: d ? (pressed ? colors.brandTertiary : colors.surfaceSecondary) : "transparent",
                    borderWidth: d ? 1 : 0, borderColor: colors.border,
                  })}>
                  <Text style={{ fontSize: 26, fontWeight: "600", color: colors.onSurface }}>{d}</Text>
                </Pressable>
              ))}
            </View>
          ))}
          <View style={{ marginTop: spacing.md, paddingBottom: insets.bottom + spacing.lg }}>
            <PrimaryButton testID="login-submit" label="Sign In" onPress={submit} loading={busy} disabled={pin.length !== 4 || !username} />
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

function UsernameInput({ value, onChangeText }: any) {
  const { colors } = useTheme();
  const { TextInput } = require("react-native");
  return (
    <TextInput
      testID="login-username"
      value={value} onChangeText={onChangeText} autoCapitalize="none" autoCorrect={false}
      placeholder="admin" placeholderTextColor={colors.muted}
      style={{ padding: 12, fontSize: 16, color: colors.onSurface }}
    />
  );
}
