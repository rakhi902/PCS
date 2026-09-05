import { useState, useEffect } from "react";
import { View, Text, ScrollView } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, LabeledInput, PrimaryButton } from "@/src/ui";

export default function Settings() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data } = useQuery({ queryKey: ["settings-page"], queryFn: api.settings });
  const [google, setGoogle] = useState(""); const [tmpl, setTmpl] = useState("");
  const [busy, setBusy] = useState(false); const [ok, setOk] = useState(false);
  useEffect(() => { if (data) { setGoogle(data.google_review_url || ""); setTmpl(data.whatsapp_template || ""); } }, [data]);
  const save = async () => {
    setBusy(true); try { await api.updateSettings({ google_review_url: google, whatsapp_template: tmpl }); setOk(true); setTimeout(() => setOk(false), 2000); } finally { setBusy(false); }
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Settings" back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
        <LabeledInput testID="settings-google" label="Google Business Review URL" value={google} onChangeText={setGoogle} placeholder="https://g.page/r/..." autoCapitalize="none" />
        <LabeledInput testID="settings-template" label="WhatsApp feedback template" value={tmpl} onChangeText={setTmpl} multiline placeholder="Use {name} and {link}" />
        <PrimaryButton testID="save-settings" label={ok ? "Saved ✓" : "Save"} onPress={save} loading={busy} />
      </ScrollView>
    </View>
  );
}
