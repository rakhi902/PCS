import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { LogBox, View, ActivityIndicator } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { useEffect } from "react";

import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";
import { AuthProvider, useAuth } from "@/src/auth";
import { useTheme } from "@/src/theme";

LogBox.ignoreAllLogs(true);

function RootGate() {
  const { user, loading } = useAuth();
  const segs = useSegments();
  const router = useRouter();
  const { colors } = useTheme();

  useEffect(() => {
    if (loading) return;
    const inAuth = segs[0] === "login";
    if (!user && !inAuth) router.replace("/login");
    else if (user && inAuth) {
      if (user.must_change_pin) router.replace("/change-pin");
      else router.replace(`/(${user.role})` as any);
    }
  }, [user, loading, segs.join("/")]);

  if (loading)
    return <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}><ActivityIndicator color={colors.brandPrimary} /></View>;
  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ErrorBoundary>
          <QueryClientProvider client={queryClient}>
            <AuthProvider>
              <RootGate />
            </AuthProvider>
          </QueryClientProvider>
        </ErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
