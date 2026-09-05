import { Tabs } from "expo-router";
import { useTheme } from "@/src/theme";
import { Text, View } from "react-native";

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  const { colors } = useTheme();
  return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.55, color: focused ? colors.brandPrimary : colors.muted }}>{label}</Text>;
}

export default function AdminLayout() {
  const { colors } = useTheme();
  return (
    <Tabs screenOptions={{
      headerShown: false,
      tabBarActiveTintColor: colors.brandPrimary,
      tabBarInactiveTintColor: colors.muted,
      tabBarStyle: { backgroundColor: colors.surfaceSecondary, borderTopColor: colors.border },
      tabBarItemStyle: { alignSelf: "center" },
    }}>
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: ({ focused }) => <TabIcon label="🏠" focused={focused} /> }} />
      <Tabs.Screen name="services" options={{ title: "Services", tabBarIcon: ({ focused }) => <TabIcon label="🧾" focused={focused} /> }} />
      <Tabs.Screen name="customers" options={{ title: "Customers", tabBarIcon: ({ focused }) => <TabIcon label="👥" focused={focused} /> }} />
      <Tabs.Screen name="more" options={{ title: "More", tabBarIcon: ({ focused }) => <TabIcon label="⋯" focused={focused} /> }} />
    </Tabs>
  );
}
