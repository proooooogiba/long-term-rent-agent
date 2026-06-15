import {
  panel,
  grid,
  text,
  image,
  shape,
  fixed,
  fr,
  grow,
  paint,
  stroke,
  textStyle,
} from "@oai/artifact-tool";
import fs from "node:fs/promises";
import path from "node:path";

export const COLORS = {
  ink: "#0F172A",
  muted: "#5B6473",
  panel: "#FFFFFF",
  paper: "#F4F7FB",
  blue: "#2563EB",
  cyan: "#0EA5E9",
  teal: "#0F766E",
  amber: "#F59E0B",
  red: "#DC2626",
  line: "#D7E0EA",
  greenSoft: "#ECFDF5",
  blueSoft: "#EFF6FF",
  amberSoft: "#FFF7ED",
  redSoft: "#FEF2F2",
  cyanSoft: "#ECFEFF",
};

export const styles = {
  kicker: textStyle("font: 14px Aptos; weight: 700; color: #2563EB"),
  title: textStyle("font: 30px Aptos Display; weight: 700; color: #0F172A"),
  titleSmall: textStyle("font: 24px Aptos Display; weight: 700; color: #0F172A"),
  hero: textStyle("font: 34px Aptos Display; weight: 700; color: #0F172A"),
  body: textStyle("font: 17px Aptos; color: #0F172A"),
  bodyMuted: textStyle("font: 16px Aptos; color: #5B6473"),
  bodySmall: textStyle("font: 14px Aptos; color: #5B6473"),
  cardTitle: textStyle("font: 18px Aptos Display; weight: 700; color: #0F172A"),
  cardBody: textStyle("font: 15px Aptos; color: #5B6473"),
  metric: textStyle("font: 26px Aptos Display; weight: 700; color: #0F172A"),
  metricLabel: textStyle("font: 14px Aptos; color: #5B6473"),
  overlineDark: textStyle("font: 13px Aptos; weight: 700; color: #BFDBFE"),
  darkTitle: textStyle("font: 24px Aptos Display; weight: 700; color: #FFFFFF"),
  darkBody: textStyle("font: 15px Aptos; color: #DBEAFE"),
  mono: textStyle("font: 14px Menlo; color: #0F172A"),
};

export function asset(ctx, filename) {
  return path.join(ctx.assetDir, filename);
}

export async function assetImageSource(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const contentType =
    ext === ".svg" ? "image/svg+xml" :
    ext === ".png" ? "image/png" :
    ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" :
    "application/octet-stream";
  const blob = await fs.readFile(filePath);
  return { blob, contentType };
}

export async function assetDataUrl(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const mime =
    ext === ".svg" ? "image/svg+xml" :
    ext === ".png" ? "image/png" :
    ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" :
    "application/octet-stream";
  const bytes = await fs.readFile(filePath);
  return `data:${mime};base64,${bytes.toString("base64")}`;
}

export function page(content, _footerText, options = {}) {
  return panel(
    {
      width: grow(1),
      height: grow(1),
      fill: options.fill ?? COLORS.paper,
      padding: { top: 34, right: 42, bottom: 32, left: 42 },
    },
    grid(
      {
        width: grow(1),
        height: grow(1),
        columns: [fr(1)],
        rows: [fixed(62), fr(1)],
        rowGap: 18,
      },
      [
        content.header,
        content.body,
      ],
    ),
  );
}

export function header(title, _subtitle = "", kicker = "") {
  return grid(
    {
      width: grow(1),
      columns: [fr(1)],
      rows: [fixed(20), fixed(34)],
      rowGap: 8,
    },
    [
      text(kicker.toUpperCase(), { style: styles.kicker, width: grow(1) }),
      text(title, { style: styles.title, width: grow(1) }),
    ],
  );
}

export function row(columns, children, gap = 18) {
  return grid(
    {
      width: grow(1),
      height: grow(1),
      columns,
      columnGap: gap,
      alignItems: "stretch",
    },
    children,
  );
}

export function column(rows, children, gap = 14) {
  return grid(
    {
      width: grow(1),
      height: grow(1),
      columns: [fr(1)],
      rows,
      rowGap: gap,
      alignItems: "stretch",
    },
    children,
  );
}

export function card(children, options = {}) {
  return panel(
    {
      fill: options.fill ?? COLORS.panel,
      line: options.line ?? stroke(`1px ${COLORS.line}`),
      borderRadius: options.radius ?? 26,
      padding: options.padding ?? { top: 18, right: 20, bottom: 18, left: 20 },
      width: grow(1),
      height: options.height ?? grow(1),
    },
    grid(
      {
        width: grow(1),
        height: grow(1),
        columns: [fr(1)],
        rows: options.rows,
        rowGap: options.gap ?? 8,
      },
      children,
    ),
  );
}

export function chip(label, tone = "blue") {
  const toneMap = {
    blue: [COLORS.blueSoft, COLORS.blue],
    teal: [COLORS.cyanSoft, COLORS.teal],
    amber: [COLORS.amberSoft, COLORS.amber],
    red: [COLORS.redSoft, COLORS.red],
  };
  const [fillColor, textColor] = toneMap[tone] ?? toneMap.blue;
  return card(
    [text(label.toUpperCase(), { style: textStyle(`font: 13px Aptos; weight: 700; color: ${textColor}`) })],
    {
      fill: fillColor,
      line: stroke(`1px ${fillColor}`),
      radius: 18,
      padding: { top: 7, right: 12, bottom: 7, left: 12 },
      height: "hug",
      gap: 0,
    },
  );
}

export function bulletLine(value, style = styles.cardBody) {
  return text(`- ${value}`, { style, width: grow(1) });
}

export function statCard(value, label, tone = "blue") {
  const fillMap = {
    blue: COLORS.blueSoft,
    teal: COLORS.cyanSoft,
    amber: COLORS.amberSoft,
    red: COLORS.redSoft,
  };
  return card(
    [
      text(value, { style: styles.metric }),
      text(label, { style: styles.metricLabel, width: grow(1) }),
    ],
    {
      fill: fillMap[tone] ?? COLORS.blueSoft,
      line: stroke(`1px ${COLORS.line}`),
      rows: [fixed(34), fixed(34)],
      height: "hug",
    },
  );
}

export function screenshotCard(imageSource, titleText, noteText) {
  return card(
    [
      image({ ...imageSource, fit: "cover", width: grow(1), height: fixed(184) }),
      text(titleText, { style: styles.cardTitle, width: grow(1) }),
      text(noteText, { style: styles.cardBody, width: grow(1) }),
    ],
    {
      padding: { top: 10, right: 10, bottom: 14, left: 10 },
      rows: [fixed(184), fixed(26), fr(1)],
    },
  );
}

export function darkPanel(children, options = {}) {
  return panel(
    {
      width: grow(1),
      height: grow(1),
      fill: options.fill ?? paint("linear(135deg, #0F172A, #1E3A8A)"),
      borderRadius: options.radius ?? 30,
      padding: options.padding ?? { top: 22, right: 22, bottom: 22, left: 22 },
    },
    grid(
      {
        width: grow(1),
        height: grow(1),
        columns: [fr(1)],
        rows: options.rows,
        rowGap: options.gap ?? 10,
      },
      children,
    ),
  );
}

export function spacer(height = 12) {
  return shape({ width: grow(1), height: fixed(height), fill: "#00000000" });
}
