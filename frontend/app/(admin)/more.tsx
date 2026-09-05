import { View, Text, ScrollView, Pressable } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing, radius } from "@/src/theme";
import { ScreenHeader, PrimaryButton } from "@/src/ui";
import { useAuth } from "@/src/auth";

function Row({ label, onPress, testID, danger }: any) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress}
      style={{ padding: spacing.lg, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.sm, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
      <Text style={{ fontSize: 15, fontWeight: "600", color: danger ? colors.error : colors.onSurface }}>{label}</Text>
      <Text style={{ color: colors.muted }}>›</Text>
    </Pressable>
  );
}

export default function More() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="More" />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}>
        <Text style={{ color: colors.muted, fontWeight: "700", marginBottom: 8 }}>OPERATIONS</Text>
        <Row testID="menu-payments" label="Payments" onPress={() => router.push("/payments")} />
        <Row testID="menu-amc" label="AMC Contracts" onPress={() => router.push("/amc")} />
        <Row testID="menu-reminders" label="Reminders" onPress={() => router.push("/reminders")} />
        <Row testID="menu-feedback" label="Feedback" onPress={() => router.push("/feedback")} />

        {isAdmin && (
          <>
            <Text style={{ color: colors.muted, fontWeight: "700", marginTop: spacing.lg, marginBottom: 8 }}>ADMIN</Text>
            <Row testID="menu-users" label="Users (Managers & Technicians)" onPress={() => router.push("/users")} />
            <Row testID="menu-reports" label="Reports" onPress={() => router.push("/reports")} />
            <Row testID="menu-settings" label="Settings" onPress={() => router.push("/settings")} />
            <Row testID="menu-service-types" label="Service Types" onPress={() => router.push("/service-types")} />
            <Row testID="menu-audit" label="Audit Log" onPress={() => router.push("/audit")} />
          </>
        )}

        <Text style={{ color: colors.muted, fontWeight: "700", marginTop: spacing.lg, marginBottom: 8 }}>ACCOUNT</Text>
        <Row testID="menu-change-pin" label="Change my PIN" onPress={() => router.push("/change-pin")} />
        <View style={{ marginTop: spacing.lg }}>
          <PrimaryButton testID="logout-btn" variant="danger" label={`Sign out (${user?.name})`} onPress={logout} />
        </View>
      </ScrollView>
    </View>
  );
}
