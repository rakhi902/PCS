import React from "react";
import { Pressable, Text, StyleSheet, ActivityIndicator, View, TextInput, ScrollView, Platform, Modal } from "react-native";
import { makeStyles, useTheme, spacing, radius } from "./theme";
import DateTimePicker from "@react-native-community/datetimepicker";

export const useCard = makeStyles((c) => ({
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, padding: spacing.lg, borderWidth: 1, borderColor: c.border, marginBottom: spacing.md },
}));

export function PrimaryButton({ label, onPress, loading, testID, disabled, variant = "primary" }: any) {
  const { colors } = useTheme();
  const bg = variant === "primary" ? colors.brandPrimary : variant === "danger" ? colors.error : colors.surfaceTertiary;
  const fg = variant === "primary" || variant === "danger" ? colors.onBrandPrimary : colors.onSurface;
  return (
    <Pressable testID={testID} onPress={onPress} disabled={disabled || loading}
      style={({ pressed }) => [{
        backgroundColor: bg, opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        paddingVertical: 14, paddingHorizontal: spacing.lg, borderRadius: radius.md,
        alignItems: "center", justifyContent: "center", minHeight: 48,
      }]}>
      {loading ? <ActivityIndicator color={fg} /> : <Text style={{ color: fg, fontWeight: "700", fontSize: 16 }}>{label}</Text>}
    </Pressable>
  );
}

export function LabeledInput({ label, testID, ...props }: any) {
  const { colors } = useTheme();
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" }}>{label}</Text>
      <TextInput
        testID={testID}
        placeholderTextColor={colors.muted}
        style={{
          backgroundColor: colors.surfaceTertiary, borderRadius: radius.md,
          paddingHorizontal: spacing.md, paddingVertical: 12, fontSize: 15,
          color: colors.onSurface, borderWidth: 1, borderColor: colors.border,
        }}
        {...props}
      />
    </View>
  );
}

export function Chip({ label, selected, onPress, testID }: any) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress}
      style={{
        paddingHorizontal: spacing.md, height: 36, borderRadius: radius.pill, flexShrink: 0,
        backgroundColor: selected ? colors.brandPrimary : colors.surfaceTertiary,
        borderWidth: 1, borderColor: selected ? colors.brandPrimary : colors.border,
        alignItems: "center", justifyContent: "center",
      }}>
      <Text style={{ color: selected ? colors.onBrandPrimary : colors.onSurface, fontWeight: "600", fontSize: 13 }}>{label}</Text>
    </Pressable>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const { colors } = useTheme();
  const map: any = {
    pending: colors.warning, assigned: colors.info, in_progress: colors.brandPrimary,
    completed: colors.success, cancelled: colors.error,
    unpaid: colors.error, paid: colors.success, amc: colors.info, upcoming: colors.info, overdue: colors.error, due: colors.warning
  };
  const bg = map[status] || colors.muted;
  const label = status.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase());
  return (
    <View style={{ backgroundColor: bg, paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill }}>
      <Text style={{ color: "#fff", fontSize: 11, fontWeight: "700" }}>{label}</Text>
    </View>
  );
}

export function EmptyState({ label, testID }: any) {
  const { colors } = useTheme();
  return (
    <View testID={testID} style={{ alignItems: "center", padding: spacing.xl }}>
      <Text style={{ color: colors.muted, fontSize: 14 }}>{label}</Text>
    </View>
  );
}

export function DateField({ label, value, onChange, testID, mode = "date" }: any) {
  const { colors } = useTheme();
  const [show, setShow] = React.useState(false);
  const d = value ? new Date(value) : new Date();
  const fmt = value ? `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}${mode === "datetime" ? " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0") : ""}` : "Select date";
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={{ fontSize: 13, color: colors.muted, marginBottom: 6, fontWeight: "600" }}>{label}</Text>
      <Pressable testID={testID} onPress={() => setShow(true)}
        style={{ backgroundColor: colors.surfaceTertiary, borderRadius: radius.md, padding: 12, borderWidth: 1, borderColor: colors.border }}>
        <Text style={{ color: value ? colors.onSurface : colors.muted, fontSize: 15 }}>{fmt}</Text>
      </Pressable>
      {show && Platform.OS !== "web" && (
        <DateTimePicker
          value={d} mode={mode as any} display="default"
          onChange={(_e, sel) => { setShow(false); if (sel) onChange(sel.toISOString()); }}
        />
      )}
      {show && Platform.OS === "web" && (
        <Modal transparent animationType="fade" onRequestClose={() => setShow(false)}>
          <Pressable style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", alignItems: "center" }} onPress={() => setShow(false)}>
            <View style={{ backgroundColor: colors.surfaceSecondary, padding: spacing.lg, borderRadius: radius.md, width: 320 }}>
              <Text style={{ marginBottom: 8, color: colors.onSurface, fontWeight: "700" }}>{label}</Text>
              <input
                type={mode === "datetime" ? "datetime-local" : "date"}
                defaultValue={value ? new Date(value).toISOString().slice(0, mode === "datetime" ? 16 : 10) : ""}
                onChange={(e: any) => { if (e.target.value) onChange(new Date(e.target.value).toISOString()); }}
                style={{ padding: 10, fontSize: 16, width: "100%", boxSizing: "border-box" } as any}
              />
              <View style={{ marginTop: 12 }}><PrimaryButton label="Done" onPress={() => setShow(false)} /></View>
            </View>
          </Pressable>
        </Modal>
      )}
    </View>
  );
}

export function ScreenHeader({ title, right, back, onBack }: any) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.lg, paddingVertical: spacing.md, backgroundColor: colors.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border }}>
      {back && (
        <Pressable onPress={onBack} testID="header-back" style={{ padding: 4, marginRight: 8 }}>
          <Text style={{ fontSize: 20, color: colors.brandPrimary }}>‹</Text>
        </Pressable>
      )}
      <Text style={{ fontSize: 20, fontWeight: "700", color: colors.onSurface, flex: 1 }}>{title}</Text>
      {right}
    </View>
  );
}

export function Screen({ children }: any) {
  const { colors } = useTheme();
  return <View style={{ flex: 1, backgroundColor: colors.surface }}>{children}</View>;
}
