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

  // Guard: keep users out of screens they shouldn't be on after state changes.
  useEffect(() => {
    if (loading) return;
    const first = segs[0];
    if (!user) {
      if (first && first !== "login") router.replace("/login");
      return;
    }
    if (user.must_change_pin && first !== "change-pin") {
      router.replace("/change-pin");
      return;
    }
    // If a signed-in user lands on /login manually, push them to their home.
    if (first === "login") {
      if (user.role === "admin") router.replace("/(admin)");
      else if (user.role === "manager") router.replace("/(manager)");
      else router.replace("/(technician)");
    }
  }, [user, loading, segs.join("/")]);

  if (loading)
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
        <ActivityIndicator color={colors.brandPrimary} />
      </View>
    );
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
