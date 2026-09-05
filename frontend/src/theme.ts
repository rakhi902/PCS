import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme } from "react-native";

export type ColorScheme = "light" | "dark";

const light = {
  surface: "#F9FAFB",
  onSurface: "#111827",
  surfaceSecondary: "#FFFFFF",
  onSurfaceSecondary: "#111827",
  surfaceTertiary: "#F3F4F6",
  onSurfaceTertiary: "#374151",
  surfaceInverse: "#1F2937",
  onSurfaceInverse: "#F9FAFB",
  muted: "#6B7280",

  brand: "#14532D",
  onBrand: "#FFFFFF",
  brandPrimary: "#16A34A",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#22C55E",
  onBrandSecondary: "#111827",
  brandTertiary: "#DCFCE7",
  onBrandTertiary: "#166534",

  success: "#10B981",
  onSuccess: "#FFFFFF",
  warning: "#EAB308",
  onWarning: "#111827",
  error: "#DC2626",
  onError: "#FFFFFF",
  info: "#475569",
  onInfo: "#FFFFFF",

  border: "#E5E7EB",
  borderStrong: "#D1D5DB",
  divider: "#F3F4F6",
};

export type ThemeColors = typeof light;
export const defaultScheme = "light" satisfies ColorScheme;
export const themes: { light: ThemeColors; dark?: ThemeColors } = { light };

export function setColorScheme(scheme: ColorScheme | null) {
  Appearance.setColorScheme?.(scheme);
}
setColorScheme?.(themes.dark ? null : defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  const system = useColorScheme();
  const scheme: ColorScheme = system && themes[system] ? system : defaultScheme;
  return { scheme, colors: themes[scheme] ?? themes.light };
}

export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors)), [colors]);
  };
}

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32, "3xl": 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };
