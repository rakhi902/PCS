import { useState } from "react";
import { View, ScrollView } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { useTheme, spacing } from "@/src/theme";
import { ScreenHeader, LabeledInput, PrimaryButton } from "@/src/ui";
import { api } from "@/src/api";

export default function NewCustomer() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [name, setName] = useState(""); const [mobile, setMobile] = useState("");
  const [alt, setAlt] = useState(""); const [address, setAddress] = useState("");
  const [city, setCity] = useState(""); const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!name || !mobile) return;
    setBusy(true);
    try {
      await api.createCustomer({ name, mobile, alt_mobile: alt, address, city, notes });
      router.back();
    } finally { setBusy(false); }
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="New Customer" back onBack={() => router.back()} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}>
        <LabeledInput testID="cust-name" label="Name" value={name} onChangeText={setName} />
        <LabeledInput testID="cust-mobile" label="Mobile" value={mobile} onChangeText={setMobile} keyboardType="phone-pad" />
        <LabeledInput testID="cust-alt" label="Alternate Mobile" value={alt} onChangeText={setAlt} keyboardType="phone-pad" />
        <LabeledInput testID="cust-address" label="Address" value={address} onChangeText={setAddress} multiline />
        <LabeledInput testID="cust-city" label="City / Locality" value={city} onChangeText={setCity} />
        <LabeledInput testID="cust-notes" label="Notes" value={notes} onChangeText={setNotes} multiline />
        <PrimaryButton testID="save-customer" label="Add Customer" onPress={submit} loading={busy} disabled={!name || !mobile} />
      </ScrollView>
    </View>
  );
}
