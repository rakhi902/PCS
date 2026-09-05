import { useState, useEffect } from "react";
import { View, Text, ScrollView, Pressable, Image, Linking, Platform, ActivityIndicator, Alert } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { useTheme, spacing, radius } from "@/src/theme";
import { api, fileUrl, getToken } from "@/src/api";
import { ScreenHeader, StatusBadge, PrimaryButton, LabeledInput, Chip, DateField } from "@/src/ui";
import { formatDate, formatDateTime, inr } from "@/src/format";
import { useAuth } from "@/src/auth";

export default function ServiceDetail() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data, refetch, isLoading } = useQuery({ queryKey: ["svc", id], queryFn: () => api.service(id) });
  const { data: techs = [] } = useQuery({ queryKey: ["techs"], queryFn: () => api.users("technician") });
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [token, setToken] = useState<string>("");
  useEffect(() => { getToken().then(t => setToken(t || "")); }, []);

  const s = data;
  const [editing, setEditing] = useState(false);
  const [medicine, setMedicine] = useState(""); const [quantity, setQuantity] = useState("");
  const [techNotes, setTechNotes] = useState("");
  const [charges, setCharges] = useState(""); const [paymentStatus, setPaymentStatus] = useState("unpaid");
  const [scheduled, setScheduled] = useState(""); const [assignedTech, setAssignedTech] = useState("");
  const [uploading, setUploading] = useState<string | null>(null);

  useEffect(() => {
    if (s) {
      setMedicine(s.medicine || ""); setQuantity(s.quantity || ""); setTechNotes(s.technician_notes || "");
      setCharges(String(s.charges ?? "")); setPaymentStatus(s.payment_status || "unpaid");
      setScheduled(s.scheduled_date); setAssignedTech(s.technician_id || "");
    }
  }, [s]);

  if (isLoading || !s) return <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}><ActivityIndicator color={colors.brandPrimary} /></View>;

  const locked = s.status === "completed" && user?.role !== "admin";
  const isTech = user?.role === "technician";
  const canEdit = !isTech && !locked;

  const pickPhoto = async (phase: "before" | "during" | "after") => {
    if (Platform.OS !== "web") {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) { const gal = await ImagePicker.requestMediaLibraryPermissionsAsync(); if (!gal.granted) return; }
    }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7 });
    if (res.canceled || !res.assets?.[0]) return;
    setUploading(phase);
    try {
      await api.uploadPhoto(id, phase, res.assets[0].uri);
      await refetch();
    } catch (e: any) {
      if (Platform.OS === "web") { alert("Upload failed: " + e.message); } else { Alert.alert("Upload failed", e.message); }
    } finally { setUploading(null); }
  };

  const saveEdits = async () => {
    const body: any = {};
    if (isTech) { body.medicine = medicine; body.quantity = quantity; body.technician_notes = techNotes; }
    else {
      body.charges = charges ? parseFloat(charges) : 0;
      body.payment_status = paymentStatus;
      body.scheduled_date = scheduled;
      body.technician_id = assignedTech || null;
      body.medicine = medicine; body.quantity = quantity; body.technician_notes = techNotes;
    }
    await api.updateService(id, body);
    setEditing(false); qc.invalidateQueries(); refetch();
  };

  const startJob = async () => { await api.updateService(id, { status: "in_progress" }); refetch(); };
  const completeJob = async () => {
    try {
      await api.completeService(id, { medicine, quantity, technician_notes: techNotes });
      refetch();
    } catch (e: any) {
      Platform.OS === "web" ? alert(e.message) : Alert.alert("Cannot complete", e.message);
    }
  };
  const cancelSvc = async () => { await api.updateService(id, { status: "cancelled" }); refetch(); };

  const shareFeedback = async () => {
    const gUrl = settings?.google_review_url || "";
    const tmpl = (settings?.whatsapp_template || "Hi {name}, please share your feedback: {link}")
      .replace("{name}", s.customer?.name || "").replace("{link}", gUrl || "https://google.com");
    const url = `https://wa.me/${(s.customer?.mobile || "").replace(/\D/g, "")}?text=${encodeURIComponent(tmpl)}`;
    Linking.openURL(url);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Service" back onBack={() => router.back()} right={<StatusBadge status={s.status} />} />
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 160 }}>
        <View style={{ backgroundColor: colors.surfaceSecondary, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.md }}>
          <Text style={{ fontSize: 18, fontWeight: "800", color: colors.onSurface }}>{s.customer?.name}</Text>
          <Text style={{ color: colors.muted, marginTop: 4 }}>📱 {s.customer?.mobile}</Text>
          {s.customer?.address && <Text style={{ color: colors.muted, marginTop: 2 }}>📍 {s.customer.address}</Text>}
          <View style={{ height: 1, backgroundColor: colors.divider, marginVertical: 10 }} />
          <Text style={{ color: colors.onSurface }}><Text style={{ color: colors.muted }}>Service:</Text> {s.service_type}</Text>
          <Text style={{ color: colors.onSurface }}><Text style={{ color: colors.muted }}>Scheduled:</Text> {formatDateTime(s.scheduled_date)}</Text>
          {s.completed_at && <Text style={{ color: colors.onSurface }}><Text style={{ color: colors.muted }}>Completed:</Text> {formatDateTime(s.completed_at)}</Text>}
          {user?.role === "admin" && <Text style={{ color: colors.brandPrimary, fontWeight: "700", marginTop: 4 }}>{inr(s.charges)} · {s.payment_status}</Text>}
          {s.instructions ? <Text style={{ color: colors.onSurface, marginTop: 6, fontStyle: "italic" }}>Instructions: {s.instructions}</Text> : null}
        </View>

        {["before", "during", "after"].map(phase => (
          <View key={phase} style={{ marginBottom: spacing.md }}>
            <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>{phase.toUpperCase()} PHOTOS</Text>
            <ScrollView horizontal contentContainerStyle={{ gap: 8 }}>
              {(s.photos?.[phase] || []).map((p: string, i: number) => (
                <Image key={i} source={{ uri: fileUrl(p, token), headers: Platform.OS !== "web" ? { Authorization: `Bearer ${token}` } : undefined } as any}
                  style={{ width: 100, height: 100, borderRadius: radius.md, backgroundColor: colors.surfaceTertiary }} />
              ))}
              {(isTech || canEdit) && s.status !== "completed" && (
                <Pressable testID={`upload-${phase}`} onPress={() => pickPhoto(phase as any)}
                  style={{ width: 100, height: 100, borderRadius: radius.md, borderWidth: 2, borderColor: colors.border, borderStyle: "dashed", alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary }}>
                  {uploading === phase ? <ActivityIndicator color={colors.brandPrimary} /> : <Text style={{ fontSize: 30, color: colors.muted }}>＋</Text>}
                </Pressable>
              )}
            </ScrollView>
          </View>
        ))}

        {(isTech || editing) && s.status !== "completed" && (
          <>
            <LabeledInput testID="fld-medicine" label="Medicine / Chemical" value={medicine} onChangeText={setMedicine} />
            <LabeledInput testID="fld-quantity" label="Quantity" value={quantity} onChangeText={setQuantity} />
            <LabeledInput testID="fld-tech-notes" label="Notes" value={techNotes} onChangeText={setTechNotes} multiline />
          </>
        )}

        {editing && canEdit && (
          <>
            <DateField testID="fld-schedule" label="Scheduled Date" value={scheduled} onChange={setScheduled} mode="datetime" />
            {user?.role === "admin" && <LabeledInput testID="fld-charges" label="Charges (₹)" value={charges} onChangeText={setCharges} keyboardType="numeric" />}
            <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>PAYMENT</Text>
            <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
              {["unpaid", "paid", "pending", "amc"].map(p => <Chip key={p} label={p} selected={paymentStatus === p} onPress={() => setPaymentStatus(p)} />)}
            </ScrollView>
            <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>ASSIGN TECHNICIAN</Text>
            <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
              <Chip label="None" selected={!assignedTech} onPress={() => setAssignedTech("")} />
              {techs.map((t: any) => <Chip key={t.id} label={t.name} selected={assignedTech === t.id} onPress={() => setAssignedTech(t.id)} />)}
            </ScrollView>
          </>
        )}

        <View style={{ gap: 8 }}>
          {canEdit && !editing && <PrimaryButton testID="edit-svc" label="Edit Service" onPress={() => setEditing(true)} />}
          {editing && <PrimaryButton testID="save-svc" label="Save Changes" onPress={saveEdits} />}
          {isTech && s.status === "assigned" && <PrimaryButton testID="start-job" label="Start Service" onPress={startJob} />}
          {isTech && s.status === "in_progress" && <PrimaryButton testID="save-progress" label="Save Progress" onPress={saveEdits} />}
          {(isTech || canEdit) && s.status !== "completed" && s.status !== "cancelled" && (
            <PrimaryButton testID="complete-job" label="Mark Completed" onPress={completeJob} />
          )}
          {canEdit && s.status !== "completed" && s.status !== "cancelled" && (
            <PrimaryButton testID="cancel-job" variant="danger" label="Cancel Service" onPress={cancelSvc} />
          )}
          {s.status === "completed" && (
            <PrimaryButton testID="share-fb" label="Send Feedback (WhatsApp)" onPress={shareFeedback} />
          )}
        </View>
      </ScrollView>
    </View>
  );
}
