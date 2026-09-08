import { View, Text, ActivityIndicator } from "react-native";
import { Redirect } from "expo-router";
import { useTheme } from "@/src/theme";
import { useAuth } from "@/src/auth";

export default function Index() {
  const { colors } = useTheme();
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
        <ActivityIndicator color={colors.brandPrimary} />
        <Text style={{ color: colors.muted, marginTop: 12 }}>Loading…</Text>
      </View>
    );
  }
  if (!user) return <Redirect href="/login" />;
  if (user.must_change_pin) return <Redirect href="/change-pin" />;
  if (user.role === "admin") return <Redirect href="/(admin)" />;
  if (user.role === "manager") return <Redirect href="/(manager)" />;
  return <Redirect href="/(technician)" />;
}
