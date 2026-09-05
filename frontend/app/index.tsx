import { View, Text, StyleSheet } from "react-native";
import { useTheme } from "@/src/theme";

export default function Index() {
  const { colors } = useTheme();
  return (
    <View style={[styles.c, { backgroundColor: colors.surface }]}>
      <Text style={{ color: colors.onSurface }}>Loading…</Text>
    </View>
  );
}
const styles = StyleSheet.create({ c: { flex: 1, alignItems: "center", justifyContent: "center" } });
