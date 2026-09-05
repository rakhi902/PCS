import { useState } from "react";
import { View, Text, FlatList, ScrollView, RefreshControl, Pressable, Modal } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTheme, spacing, radius } from "@/src/theme";
import { ScreenHeader, Chip, LabeledInput, EmptyState, StatusBadge, DateField, PrimaryButton } from "@/src/ui";
import { api } from "@/src/api";
import { formatDate, inr } from "@/src/format";
import { useAuth } from "@/src/auth";

const STATUSES = ["all", "pending", "assigned", "in_progress", "completed", "cancelled"];

export default function Services() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user } = useAuth();
  const params = useLocalSearchParams<{ status?: string }>();
  const [status, setStatus] = useState<string>(params.status || "all");
  const [q, setQ] = useState("");
  const [serviceType, setServiceType] = useState<string>("");
  const [technicianId, setTech] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const { data: types = [] } = useQuery({ queryKey: ["types"], queryFn: api.serviceTypes });
  const { data: techs = [] } = useQuery({ queryKey: ["techs"], queryFn: () => api.users("technician") });

  const queryParams: Record<string, string> = {};
  if (status !== "all") queryParams.status = status;
  if (q) queryParams.q = q;
  if (serviceType) queryParams.service_type = serviceType;
  if (technicianId) queryParams.technician_id = technicianId;
  if (dateFrom) queryParams.date_from = dateFrom;
  if (dateTo) queryParams.date_to = dateTo;

  const { data = [], refetch, isRefetching } = useQuery({
    queryKey: ["services", JSON.stringify(queryParams)],
    queryFn: () => api.services(queryParams),
  });

  const activeCount = (serviceType ? 1 : 0) + (technicianId ? 1 : 0) + (dateFrom ? 1 : 0) + (dateTo ? 1 : 0);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
      <ScreenHeader title="Services" right={
        user?.role !== "technician" ? (
          <Pressable testID="add-service" onPress={() => router.push("/service/new")} style={{ backgroundColor: colors.brandPrimary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill }}>
            <Text style={{ color: "#fff", fontWeight: "700" }}>+ New</Text>
          </Pressable>
        ) : null
      } />
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md }}>
        <LabeledInput testID="search-services" label="Search by name / mobile" value={q} onChangeText={setQ} placeholder="Search..." />
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: spacing.lg, paddingBottom: 12 }} style={{ maxHeight: 56 }}>
        {STATUSES.map(s => <Chip key={s} testID={`chip-${s}`} label={s.replace("_", " ").toUpperCase()} selected={status === s} onPress={() => setStatus(s)} />)}
        <Pressable testID="open-filters" onPress={() => setFiltersOpen(true)}
          style={{ paddingHorizontal: 14, height: 36, borderRadius: radius.pill, backgroundColor: activeCount ? colors.brandTertiary : colors.surfaceTertiary, borderWidth: 1, borderColor: activeCount ? colors.brandSecondary : colors.border, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 6, flexShrink: 0 }}>
          <Text style={{ color: activeCount ? colors.onBrandTertiary : colors.onSurface, fontWeight: "700", fontSize: 13 }}>⚙ Filters{activeCount ? ` (${activeCount})` : ""}</Text>
        </Pressable>
      </ScrollView>
      <FlatList
        data={data} keyExtractor={(item: any) => item.id}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
        ListEmptyComponent={<EmptyState label="No services" testID="empty-services" />}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <Pressable testID={`service-${item.id}`} onPress={() => router.push(`/service/${item.id}`)}
            style={{ backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm, borderWidth: 1, borderColor: colors.border }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <Text style={{ fontWeight: "700", color: colors.onSurface, fontSize: 15 }}>{item.customer_name || "—"}</Text>
              <StatusBadge status={item.status} />
            </View>
            <Text style={{ color: colors.muted, fontSize: 13 }}>{item.service_type} · {formatDate(item.scheduled_date)}</Text>
            <Text style={{ color: colors.muted, fontSize: 12, marginTop: 2 }}>{item.customer_mobile}</Text>
            {user?.role !== "technician" && item.charges != null && <Text style={{ color: colors.brandPrimary, fontWeight: "700", marginTop: 4 }}>{inr(item.charges)}</Text>}
          </Pressable>
        )}
      />

      <Modal visible={filtersOpen} transparent animationType="slide" onRequestClose={() => setFiltersOpen(false)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" }}>
          <View style={{ backgroundColor: colors.surface, padding: spacing.lg, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingBottom: insets.bottom + spacing.lg, maxHeight: "85%" }}>
            <ScrollView>
              <Text style={{ fontSize: 18, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.md }}>Filters</Text>

              <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>SERVICE TYPE</Text>
              <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
                <Chip label="All" selected={!serviceType} onPress={() => setServiceType("")} />
                {types.map((t: any) => <Chip key={t.id} testID={`f-type-${t.name}`} label={t.name} selected={serviceType === t.name} onPress={() => setServiceType(t.name)} />)}
              </ScrollView>

              {user?.role !== "technician" && (
                <>
                  <Text style={{ fontSize: 13, color: colors.muted, fontWeight: "700", marginBottom: 6 }}>TECHNICIAN</Text>
                  <ScrollView horizontal contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
                    <Chip label="Any" selected={!technicianId} onPress={() => setTech("")} />
                    {techs.map((t: any) => <Chip key={t.id} testID={`f-tech-${t.id}`} label={t.name} selected={technicianId === t.id} onPress={() => setTech(t.id)} />)}
                  </ScrollView>
                </>
              )}

              <DateField testID="f-date-from" label="Date from" value={dateFrom} onChange={setDateFrom} />
              <DateField testID="f-date-to" label="Date to" value={dateTo} onChange={setDateTo} />

              <View style={{ flexDirection: "row", gap: 8, marginTop: spacing.md }}>
                <View style={{ flex: 1 }}>
                  <PrimaryButton testID="clear-filters" variant="ghost" label="Clear all" onPress={() => { setServiceType(""); setTech(""); setDateFrom(""); setDateTo(""); }} />
                </View>
                <View style={{ flex: 1 }}>
                  <PrimaryButton testID="apply-filters" label="Apply" onPress={() => setFiltersOpen(false)} />
                </View>
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}
