import { useState, useEffect } from "react";
import { View, Text, ScrollView, Pressable, Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { ScreenHeader, LabeledInput, PrimaryButton, DateField, Chip } from "@/src/ui";
import { useAuth } from "@/src/auth";

export default function NewService() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ customer_id?: string }>();
  const { user } = useAuth();

  const { data: customers = [] } = useQuery({ queryKey: ["custs-all"], queryFn: () => api.customers() });
  const { data: types = [] } = useQuery({ queryKey: ["types"], queryFn: api.serviceTypes });
  const { data: techs = [] } = useQuery({ queryKey: ["techs"], queryFn: () => api.users("technician") });

  const [customer_id, setCust] = useState<string>(params.customer_id || "");
  const [service_type, setType] = useState<string>("");
  const [scheduled_date, setDate] = useState<string>(new Date().toISOString());
  const [technician_id, setTech] = useState<string>("");
  const [charges, setCharges] = useState<string>("");
  const [instructions, setInst] = useState<string>("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!service_type && types[0]) setType(types[0].name); }, [types]);

  const submit = async () => {
    if (!customer_id || !service_type) return;
    setBusy(true);
    try {
      await api.createService({
        customer_id, service_type, scheduled_date,
        technician_id: technician_id || undefined,
        charges: charges ? parseFloat(charges) : 0,
        instructions,
      });
      router.back();
    } finally { setBusy(false); }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="New Service" back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}>
        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>CUSTOMER</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
          {customers.map((c: any) => <Chip key={c.id} testID={`sel-cust-${c.id}`} label={c.name} selected={customer_id === c.id} onPress={() => setCust(c.id)} />)}
        </ScrollView>

        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6, marginTop: 8 }}>SERVICE TYPE</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
          {types.map((t: any) => <Chip key={t.id} testID={`sel-type-${t.name}`} label={t.name} selected={service_type === t.name} onPress={() => setType(t.name)} />)}
        </ScrollView>

        <DateField testID="svc-date" label="Scheduled Date" value={scheduled_date} onChange={setDate} mode="datetime" />

        <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>TECHNICIAN (optional)</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
          <Chip label="None" selected={!technician_id} onPress={() => setTech("")} />
          {techs.map((t: any) => <Chip key={t.id} testID={`sel-tech-${t.id}`} label={t.name} selected={technician_id === t.id} onPress={() => setTech(t.id)} />)}
        </ScrollView>

        {user?.role !== "technician" && (
          <LabeledInput testID="svc-charges" label="Charges (₹)" value={charges} onChangeText={setCharges} keyboardType="numeric" />
        )}
        <LabeledInput testID="svc-instr" label="Instructions" value={instructions} onChangeText={setInst} multiline />
        <PrimaryButton testID="save-service" label="Create Service" onPress={submit} loading={busy} disabled={!customer_id || !service_type} />
      </ScrollView>
    </View>
  );
}
