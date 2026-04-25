// ─── templates.js ────────────────────────────────────────────────────────────
// Tier configuration and UI constants for the CB Demo Generator.

/**
 * @typedef {Object} TierConfig
 * @property {string} key    - Property name in DemoStructure (e.g. "library_streams")
 * @property {string} label  - Human-readable label (e.g. "Library Streams")
 * @property {string} short  - Abbreviation used in Python variable names (e.g. "LIB")
 * @property {string} clr    - Light-mode text color
 * @property {string} bg     - Light-mode background color
 * @property {string} dBg    - Dark-mode background color
 * @property {string} dClr   - Dark-mode text color
 */

/** @type {TierConfig[]} */
export const TIERS = [
  { key:"library_streams",      label:"Library Streams",              short:"LIB",  clr:"#0F6E56", bg:"#E1F5EE", dBg:"#04342C", dClr:"#5DCAA5" },
  { key:"product_line_streams", label:"Product Line Streams",         short:"PL",   clr:"#534AB7", bg:"#EEEDFE", dBg:"#26215C", dClr:"#AFA9EC" },
  { key:"transform_streams",    label:"Transform Streams (PL Replica)",short:"TR",  clr:"#854F0B", bg:"#FAEEDA", dBg:"#412402", dClr:"#EF9F27" },
  { key:"release_streams",      label:"Release / Variant Streams",    short:"REL",  clr:"#185FA5", bg:"#E6F1FB", dBg:"#042C53", dClr:"#85B7EB" },
];

/** @type {Record<string, string>} */
export const TIER_LABELS = {
  library_streams:      "LIBRARY STREAMS",
  product_line_streams: "PRODUCT LINE STREAMS",
  transform_streams:    "TRANSFORM STREAMS",
  release_streams:      "RELEASE / VARIANT STREAMS",
};
