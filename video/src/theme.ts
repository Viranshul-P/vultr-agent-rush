import { loadFont as loadGeist } from "@remotion/google-fonts/Geist";
import { loadFont as loadGeistMono } from "@remotion/google-fonts/GeistMono";

export const sans = loadGeist("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] }).fontFamily;
export const mono = loadGeistMono("normal", { weights: ["400", "600"], subsets: ["latin"] }).fontFamily;

// Airlock's own tokens (web/src/styles.css)
export const C = {
  ink: "#0D1420",
  ink2: "#141C2B",
  inkLine: "#24304A",
  paper: "#F4F5F7",
  white: "#FFFFFF",
  text: "#EEF1F6",
  textDim: "#C9D2E0",
  textMute: "#8A95A6",
  bodyDark: "#465161",
  accent: "#2B55F0",
  accentLight: "#7C95FF",
  clear: "#4CD38A",
  hold: "#F5B54A",
  block: "#FF7A70",
  quar: "#B597FF",
} as const;
