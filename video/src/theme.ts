import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Geist ships as variable fonts (all weights in one file), bundled locally so renders never wait on the network.
loadFont({ family: "Geist", url: staticFile("fonts/Geist.woff2"), weight: "100 900" });
loadFont({ family: "Geist Mono", url: staticFile("fonts/GeistMono.woff2"), weight: "100 900" });

export const sans = "Geist, Arial, sans-serif";
export const mono = "'Geist Mono', 'Courier New', monospace";

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
