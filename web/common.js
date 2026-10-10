// Shared by the farmer, buyer and agent pages: crop names in si/ta and a picture for each crop.
// Pictures are inline SVG so they look the same on every phone (old Android lacks most produce emoji).
// Sinhala and Tamil names need a native speaker's review before the demo.
const GOVI = (() => {
  const C = {
    carrot: { si: "කැරට්", ta: "கேரட்", bg: "#fde7d4",
      svg: '<path d="M30 14c-3 0-6 2-8 6L11 42c-1 2 1 4 3 3l22-11c4-2 6-5 6-8 0-7-5-12-12-12z" fill="#f08a24"/><path d="M19 30l4 2M16 36l4 2M24 24l3 2" stroke="#c96a12" stroke-width="2" stroke-linecap="round"/><path d="M36 12c0-5 3-7 6-7-1 4-2 6-5 8M38 16c4-3 7-3 9-1-3 2-6 3-9 2M34 12c-2-4-1-7 1-8 1 3 1 6-1 8" fill="#3d9a4f" stroke="#3d9a4f" stroke-width="2" stroke-linejoin="round"/>' },
    tomato: { si: "තක්කාලි", ta: "தக்காளி", bg: "#fbe0dc",
      svg: '<circle cx="24" cy="27" r="15" fill="#e2412f"/><ellipse cx="18" cy="22" rx="4" ry="2.6" fill="#f58a7c" transform="rotate(-30 18 22)"/><path d="M24 13l3-4 1 5 5-1-3 4 4 3-6 0-4 3-1-5-5 0 4-3z" fill="#3d9a4f"/>' },
    beans: { si: "බෝංචි", ta: "பீன்ஸ்", bg: "#e2f2d9",
      svg: '<path d="M9 34c6-1 10-6 14-13s9-11 16-11c1 0 1 2 0 2-5 2-8 6-11 12-4 8-10 13-18 13-2 0-3-3-1-3z" fill="#4caf50"/><path d="M14 36c4-2 7-6 10-11M27 19c3-4 6-6 9-7" stroke="#2e7d32" stroke-width="1.6" fill="none" stroke-linecap="round"/><circle cx="17" cy="32" r="2" fill="#7cc576"/><circle cx="22" cy="26" r="2" fill="#7cc576"/><circle cx="27" cy="20" r="2" fill="#7cc576"/><path d="M39 10c2-2 3-4 3-6" stroke="#2e7d32" stroke-width="2" stroke-linecap="round"/>' },
    leeks: { si: "ලීක්ස්", ta: "லீக்ஸ்", bg: "#e6f1df",
      svg: '<path d="M20 44h8V24h-8z" fill="#f4f1e4" stroke="#d8d2b8" stroke-width="1.2"/><path d="M20 26c-3-8-8-14-12-18 6 1 11 6 14 13M28 26c3-9 7-15 12-19-2 7-6 13-10 19M24 24c-1-7 0-14 2-20 2 6 2 13 0 20" fill="#3d9a4f"/><path d="M21 44l-2 3M24 44v4M27 44l2 3" stroke="#b5a77d" stroke-width="1.5" stroke-linecap="round"/>' },
    "red onion": { si: "රතු ළූණු", ta: "சின்ன வெங்காயம்", bg: "#f1e0ee",
      svg: '<path d="M24 12c2 4 13 9 13 20 0 8-6 12-13 12s-13-4-13-12c0-11 11-16 13-20z" fill="#9b3b7a"/><path d="M24 15c-3 6-6 11-6 18M24 15c3 6 6 11 6 18" stroke="#c46aa4" stroke-width="1.6" fill="none"/><path d="M24 12c0-3 1-6 3-8" stroke="#6b8f3d" stroke-width="2.4" stroke-linecap="round"/><path d="M21 44l-1 3M24 44v3M27 44l1 3" stroke="#a88a6a" stroke-width="1.4" stroke-linecap="round"/>' },
    "green chilli": { si: "අමු මිරිස්", ta: "பச்சை மிளகாய்", bg: "#e0f2dc",
      svg: '<path d="M33 15c-2 12-9 22-23 27-2 1-1 3 1 3 17-2 27-13 27-28z" fill="#43a047"/><path d="M15 39c8-4 14-11 17-19" stroke="#7cc576" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M35 16c0-4 2-8 6-10" stroke="#2e7d32" stroke-width="3" stroke-linecap="round" fill="none"/><path d="M31 15c2-2 6-2 8 0-2 2-6 3-8 0z" fill="#2e7d32"/>' },
  };
  const leaf = '<path d="M12 36c0-14 9-23 26-24-1 17-10 26-24 26" fill="#4caf50"/><path d="M10 40l18-18" stroke="#2e7d32" stroke-width="2.5" stroke-linecap="round"/>';
  const key = (c) => String(c || "").toLowerCase().trim();
  return {
    name(c, lang) { const x = C[key(c)]; return (x && x[lang]) || String(c || "").replace(/\b\w/g, (m) => m.toUpperCase()); },
    icon(c, size = 40) {
      const x = C[key(c)];
      return `<span class="crop-ic" style="width:${size}px;height:${size}px;background:${x ? x.bg : "#e3f1e6"}" aria-hidden="true"><svg viewBox="0 0 48 48" width="${Math.round(size * .78)}" height="${Math.round(size * .78)}">${x ? x.svg : leaf}</svg></span>`;
    },
  };
})();
