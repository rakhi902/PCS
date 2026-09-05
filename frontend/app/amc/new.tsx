import { useState, useEffect } from "react";
import { View, Text, ScrollView } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing } from "@/src/theme";
import { ScreenHeader, LabeledInput, PrimaryButton, DateField, Chip } from "@/src/ui";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";

const FREQS = ["monthly", "quarterly", "fortnightly", "daily", "custom"];

export default function NewAMC() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const { data: customers = [] } = useQuery({ queryKey: ["custs-all"], queryFn: () => api.customers() });
  const { data: types = [] } = useQuery({ queryKey: ["types"], queryFn: api.serviceTypes });
  const [customer_id, setC] = useState(""); const [service_type, setT] = useState("");
  const [start_date, setS] = useState(new Date().toISOString());
  const [end_date, setE] = useState(new Date(Date.now() + 365 * 86400000).toISOString());
  const [frequency, setF] = useState<string>("monthly"); const [amount, setAmt] = useState("");
  const [customDays, setCustom] = useState("30"); const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!service_type && types[0]) setT(types[0].name); }, [types]);
  const submit = async () => {
    if (!customer_id || !service_type) return;
    setBusy(true);
    try {
      await api.createAmc({
        customer_id, service_type, start_date, end_date, frequency,
        contract_amount: amount ? parseFloat(amount) : 0,
        notes, custom_interval_days: frequency === "custom" ? parseInt(customDays || "30") : undefined,
      });
      router.back();
    } finally { setBusy(false); }
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="New AMC" back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}>
        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>CUSTOMER</Text>
        <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
          {customers.map((c: any) => <Chip key={c.id} label={c.name} selected={customer_id === c.id} onPress={() => setC(c.id)} />)}
        </ScrollView>
        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>SERVICE TYPE</Text>
        <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
          {types.map((t: any) => <Chip key={t.id} label={t.name} selected={service_type === t.name} onPress={() => setT(t.name)} />)}
        </ScrollView>
        <DateField label="Start Date" value={start_date} onChange={setS} />
        <DateField label="End Date" value={end_date} onChange={setE} />
        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>FREQUENCY</Text>
        <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
          {FREQS.map(f => <Chip key={f} label={f} selected={frequency === f} onPress={() => setF(f)} />)}
        </ScrollView>
        {frequency === "custom" && <LabeledInput label="Custom Interval (days)" value={customDays} onChangeText={setCustom} keyboardType="numeric" />}
        {user?.role === "admin" && <LabeledInput label="Contract Amount (₹)" value={amount} onChangeText={setAmt} keyboardType="numeric" />}
        <LabeledInput label="Notes" value={notes} onChangeText={setNotes} multiline />
        <PrimaryButton testID="save-amc" label="Create AMC" onPress={submit} loading={busy} disabled={!customer_id || !service_type} />
      </ScrollView>
    </View>
  );
}
