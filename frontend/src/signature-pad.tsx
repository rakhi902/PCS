import React, { useRef, useState } from "react";
import { View, Text, Modal, Pressable, Platform, ActivityIndicator } from "react-native";
import SignatureScreen from "react-native-signature-canvas";
import { useTheme, spacing, radius } from "./theme";
import { PrimaryButton } from "./ui";

type Props = {
  visible: boolean;
  onClose: () => void;
  onSave: (dataUrl: string) => Promise<void> | void;
};

export function SignaturePadModal({ visible, onClose, onSave }: Props) {
  const { colors } = useTheme();
  const ref = useRef<any>(null);
  const [saving, setSaving] = useState(false);

  const handleOK = async (sig: string) => {
    // sig is a base64 dataURL string
    setSaving(true);
    try {
      await onSave(sig);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const webStyle = `
    .m-signature-pad { box-shadow: none; border: none; margin: 0; }
    .m-signature-pad--body { border: 1px dashed ${colors.border}; border-radius: 12px; }
    .m-signature-pad--footer { display: none; }
    body, html { background: ${colors.surface}; }
  `;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" }}>
        <View style={{ backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.lg, height: "80%" }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
            <Text style={{ fontSize: 18, fontWeight: "800", color: colors.onSurface }}>Customer Signature</Text>
            <Pressable testID="sig-close" onPress={onClose}><Text style={{ color: colors.brandPrimary, fontSize: 16, fontWeight: "700" }}>Close</Text></Pressable>
          </View>
          <Text style={{ color: colors.muted, marginBottom: spacing.md }}>Please sign in the box below</Text>
          <View style={{ flex: 1, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, overflow: "hidden" }}>
            <SignatureScreen
              ref={ref}
              onOK={handleOK}
              webStyle={webStyle}
              descriptionText=""
              backgroundColor={colors.surfaceSecondary}
              penColor={colors.onSurface}
              autoClear={false}
              trimWhitespace={true}
            />
          </View>
          <View style={{ flexDirection: "row", gap: 12, marginTop: spacing.md }}>
            <View style={{ flex: 1 }}>
              <PrimaryButton testID="sig-clear" variant="ghost" label="Clear" onPress={() => ref.current?.clearSignature()} />
            </View>
            <View style={{ flex: 1 }}>
              <PrimaryButton testID="sig-save" label={saving ? "Saving..." : "Save"} loading={saving} onPress={() => ref.current?.readSignature()} />
            </View>
          </View>
          {saving && <ActivityIndicator style={{ marginTop: 8 }} color={colors.brandPrimary} />}
        </View>
      </View>
    </Modal>
  );
}
