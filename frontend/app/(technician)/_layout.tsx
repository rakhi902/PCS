import { Tabs } from "expo-router";
import { useTheme } from "@/src/theme";
import { Text } from "react-native";
function TabIcon({ label, focused }: any) { const { colors } = useTheme(); return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.55, color: focused ? colors.brandPrimary : colors.muted }}>{label}</Text>; }
export default function TechLayout() {
  const { colors } = useTheme();
  return (
    <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: colors.brandPrimary, tabBarInactiveTintColor: colors.muted, tabBarStyle: { backgroundColor: colors.surfaceSecondary, borderTopColor: colors.border }, tabBarItemStyle: { alignSelf: "center" } }}>
      <Tabs.Screen name="index" options={{ title: "Today", tabBarIcon: ({ focused }) => <TabIcon label="📋" focused={focused} /> }} />
      <Tabs.Screen name="upcoming" options={{ title: "Upcoming", tabBarIcon: ({ focused }) => <TabIcon label="🗓️" focused={focused} /> }} />
      <Tabs.Screen name="completed" options={{ title: "Done", tabBarIcon: ({ focused }) => <TabIcon label="✅" focused={focused} /> }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarIcon: ({ focused }) => <TabIcon label="👤" focused={focused} /> }} />
    </Tabs>
  );
}
