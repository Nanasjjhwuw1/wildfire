// Presentation-layer only: plain-language strings + formatting helpers.
// No backend value is changed here — we only translate/format what the API returns.

// ---- static UI strings -----------------------------------------------------
const STR = {
  appTitle: { th: 'ไฟป่า: ความเสี่ยง & การลาม', en: 'Wildfire Risk & Spread' },
  area: { th: 'จังหวัดเชียงใหม่', en: 'Chiang Mai province' },

  stepWeather: { th: 'ปรับสภาพอากาศ', en: 'Set conditions' },
  stepIgnite: { th: 'แตะจุดบนแผนที่เพื่อจุดไฟ', en: 'Tap the map to start a fire' },
  stepResult: { th: 'ดูผล & คำแนะนำ', en: 'See results & advice' },

  deep: { th: 'ข้อมูลเชิงลึก', en: 'Technical details' },

  secNow: { th: 'สถานการณ์วันนี้ (ของจริง)', en: "Today's situation (real)" },
  secSettings: { th: 'ตั้งค่าการจำลอง', en: 'Simulation settings' },
  secResult: { th: 'ผลการจำลอง (สมมติ)', en: 'Simulation result (what-if)' },
  secAdvice: { th: 'คำแนะนำการรับมือ', en: 'Response advice' },
  secLayers: { th: 'ชั้นข้อมูลบนแผนที่', en: 'Map layers' },
  secLegend: { th: 'คำอธิบายสัญลักษณ์', en: 'Legend' },

  dangerToday: { th: 'ระดับอันตรายวันนี้', en: "Today's danger" },
  air: { th: 'อากาศ', en: 'Air' },
  humidity: { th: 'ความชื้น', en: 'Humidity' },
  rain24: { th: 'ฝน 24 ชม.', en: 'Rain 24h' },
  windLabel: { th: 'ลม', en: 'Wind' },
  source: { th: 'ที่มาข้อมูล', en: 'Data source' },
  indices: { th: 'ดัชนีเชื้อเพลิง / การลาม (FFMC/ISI)', en: 'Fuel / spread index (FFMC/ISI)' },

  dryness: { th: 'ความแห้งของเชื้อเพลิง', en: 'Fuel dryness' },
  drynessLo: { th: 'หน้าฝน', en: 'Wet' },
  drynessHi: { th: 'หน้าแล้ง', en: 'Dry' },
  windStrength: { th: 'ความแรงลม', en: 'Wind speed' },
  windDir: { th: 'ทิศทางลม (ลมมาจาก)', en: 'Wind direction (from)' },
  weak: { th: 'เบา', en: 'calm' },
  strong: { th: 'แรง', en: 'strong' },
  mcRuns: { th: 'จำนวนรอบจำลอง (Monte-Carlo)', en: 'Monte-Carlo runs' },

  btnRerun: { th: '🔄 จำลองใหม่', en: '🔄 Re-run' },
  btnPlay: { th: '▶ ดูไฟลาม', en: '▶ Play spread' },
  btnPause: { th: '⏸ หยุด', en: '⏸ Pause' },
  spreadStage: { th: 'ระยะการลาม', en: 'Spread stage' },

  burnedCover: { th: 'ไฟลามครอบคลุม', en: 'Fire covers' },
  ofArea: { th: 'ของพื้นที่', en: 'of the area' },
  windUsed: { th: 'ลมที่ใช้จำลอง', en: 'Wind used' },
  youSet: { th: 'คุณตั้งเอง', en: 'your setting' },
  liveVal: { th: 'ค่าจริง', en: 'live' },
  rawMaxProb: { th: 'โอกาสไหม้สูงสุด (ค่าดิบ)', en: 'Max burn prob (raw)' },
  frames: { th: 'จำนวนเฟรม', en: 'frames' },
  timeApprox: { th: 'เวลาโดยประมาณ', en: 'Approx. time' },
  spreadTimeTotal: { th: 'เวลาลามทั้งหมด', en: 'Total spread time' },
  assumedRos: { th: 'อัตราการลามสมมติ (ม./นาที)', en: 'Assumed spread rate (m/min)' },
  approx: { th: 'ประมาณ', en: 'approx.' },

  assetsThreatened: { th: 'ชุมชนที่เสี่ยง', en: 'Communities at risk' },
  places: { th: 'แห่ง', en: '' },
  suppressPoints: { th: 'จุดที่ควรส่งทีมดับไฟ', en: 'Send crews to' },
  points: { th: 'จุด', en: 'points' },
  order: { th: 'ลำดับ', en: 'Priority' },
  nearComm: { th: 'ใกล้ชุมชน', en: 'near' },
  chance: { th: 'โอกาสไหม้', en: 'burn chance' },

  layerRisk: { th: 'แผนที่ความเสี่ยงไฟ', en: 'Fire-risk map' },
  layerBurn: { th: 'พื้นที่ที่ไฟจะลาม', en: 'Burn probability' },
  layerPlan: { th: 'แผนสกัดไฟ', en: 'Suppression plan' },
  layerFirms: { th: 'จุดไฟในอดีต (ดาวเทียม)', en: 'Past fires (satellite)' },
  layerRiskMl: { th: 'AI ทำนายจุดเสี่ยง', en: 'AI fire-prone areas' },
  notTrained: { th: 'ยังไม่เทรน', en: 'not trained' },
  mlAuc: { th: 'ความแม่น AI (AUC)', en: 'AI accuracy (AUC)' },
  mlFires: { th: 'เรียนจากไฟจริง (จุด)', en: 'learned from fires (pts)' },
  none: { th: 'ไม่มี', en: 'none' },

  layerBase: { th: 'ชั้นความเสี่ยงพื้นฐาน', en: 'Base risk layer' },
  layerNone: { th: 'ไม่แสดง', en: 'None' },
  layerFwi: { th: 'ความเสี่ยงจากอากาศ (FWI)', en: 'Weather risk (FWI)' },
  reset: { th: 'เริ่มใหม่', en: 'Reset' },
  ignitionPoint: { th: 'จุดเกิดไฟ', en: 'Ignition' },
  demoNote: { th: 'ตัวอย่างอัตโนมัติ — แตะแผนที่เพื่อจุดไฟเอง', en: 'Auto demo — tap the map to ignite your own' },
  infoDanger: { th: 'ระดับอันตรายจากสภาพอากาศวันนี้ (ดัชนี FWI): เขียว=ต่ำ → แดง=สูงสุด', en: "Today's weather danger (FWI): green=low → red=extreme" },
  infoDryness: { th: 'ความแห้งของเชื้อเพลิง — ยิ่งแห้ง (หน้าแล้ง) ไฟยิ่งติดและลามเร็ว', en: 'Fuel dryness — drier fuel ignites and spreads faster' },
  infoFwi: { th: 'FFMC = ความแห้งเชื้อเพลิงผิว · ISI = ความเร็วการลามเริ่มต้น (ยิ่งสูงยิ่งอันตราย)', en: 'FFMC = fine-fuel dryness · ISI = initial spread rate' },
  infoAuc: { th: 'ความแม่นโมเดล AI: 0.5 = เดาสุ่ม, 1.0 = สมบูรณ์แบบ', en: 'AI accuracy: 0.5 = random, 1.0 = perfect' },
  infoBurn: { th: 'โอกาสที่ไฟจะลามมาถึงจุดนี้ (เฉลี่ยจากการจำลองหลายรอบ)', en: 'Chance the fire reaches this cell (avg over runs)' },
  welcomeTitle: { th: 'เช็กความเสี่ยงไฟป่า', en: 'Check wildfire risk' },
  welcomeDesc: { th: 'ดูว่าพื้นที่ไหนเสี่ยงเกิดไฟป่า และถ้าเกิดไฟ จะลามไปทางไหน', en: 'See which areas are fire-prone, and how a fire would spread' },
  wStep1: { th: 'สีบนแผนที่ = ระดับความเสี่ยง', en: 'Map colour = risk level' },
  wStep2: { th: 'แตะจุดบนแผนที่ = ดูไฟลาม', en: 'Tap the map = see fire spread' },
  wStep3: { th: 'อ่านคำแนะนำว่าควรทำอะไร', en: 'Read what to do' },
  start: { th: 'เริ่มใช้งาน', en: 'Start' },
  riskHigh: { th: 'เสี่ยงมาก', en: 'High' },
  riskMed: { th: 'ปานกลาง', en: 'Medium' },
  riskLow: { th: 'น้อย', en: 'Low' },
  seeDetail: { th: 'ดูละเอียด', en: 'Details' },
  simpleBack: { th: 'โหมดง่าย', en: 'Simple' },
  todayRisk: { th: 'วันนี้เชียงใหม่ เสี่ยงไฟ', en: 'Chiang Mai fire risk today' },
  tapToSim: { th: '👉 แตะบนแผนที่ เพื่อดูว่าถ้าไฟเริ่มตรงนั้น จะลามไปทางไหน', en: '👉 Tap the map to see how a fire there would spread' },
  sendCrews: { th: 'ควรส่งทีมดับไฟ', en: 'Send crews to' },
  newFire: { th: 'ลองจุดใหม่', en: 'Try a new spot' },
  exampleNote: { th: 'นี่คือตัวอย่าง', en: 'This is an example' },
  riskLess: { th: 'เสี่ยงน้อย', en: 'Lower' },
  riskMore: { th: 'เสี่ยงมาก', en: 'Higher' },
  colorScale: { th: 'สีบนแผนที่ = ระดับความเสี่ยง', en: 'Map colour = risk level' },
  natTitle: { th: 'ความเสี่ยงไฟป่าทั้งประเทศ', en: 'Nationwide wildfire risk' },
  natNote: { th: 'AI ทำนายจากไฟจริงในอดีต — สียิ่งแดงเข้ม ยิ่งเสี่ยงเกิดไฟมาก', en: 'AI from past fires — deeper red = higher fire risk' },

  national: { th: 'ทั้งประเทศ (AI)', en: 'Whole country (AI)' },
  localView: { th: 'กลับมุมพื้นที่', en: 'Back to local' },
  nationalBuilding: { th: 'แผนที่ทั้งประเทศกำลังสร้าง — ลองใหม่อีกครู่', en: 'National map is still building — try again shortly' },
  infoNational: { th: 'AI ทำนายจุดเสี่ยงไฟทั้งไทย เรียนจากไฟดาวเทียมทั่วประเทศ (ความละเอียดหยาบ ~5 กม.)', en: 'AI fire-prone areas across Thailand, learned from nationwide satellite fires (~5 km)' },

  chanceLow: { th: 'น้อย', en: 'low' },
  chanceHigh: { th: 'มาก', en: 'high' },
  legFireHead: { th: 'หัวไฟ (ไฟพุ่งแรงสุด)', en: 'Fire head (fastest spread)' },
  legIgnition: { th: 'จุดเริ่มไฟ', en: 'Ignition point' },
  legSuppress: { th: 'จุดส่งทีมดับไฟ', en: 'Send-crew point' },
  legFirebreak: { th: 'แนวกันไฟแนะนำ', en: 'Suggested firebreak' },
  legWater: { th: 'แนวน้ำธรรมชาติ', en: 'Natural water barrier' },
  legCommunity: { th: 'ชุมชน / จุดสำคัญ', en: 'Community / asset' },

  mapHintFirst: { th: '👆 แตะในกรอบเพื่อจุดไฟ', en: '👆 Tap inside the box to start a fire' },
  mapHintAgain: { th: '🔥 แตะที่อื่นเพื่อย้ายจุดเริ่มไฟ', en: '🔥 Tap elsewhere to move the ignition' },
  outsideMsg: { th: 'แตะภายในกรอบเส้นประเพื่อจุดไฟ', en: 'Tap inside the dashed box to start a fire.' },
  simFailed: { th: 'จำลองไม่สำเร็จ', en: 'Simulation failed' },
  loadFailed: { th: 'โหลดข้อมูลพื้นที่ไม่สำเร็จ', en: 'Failed to load area' },
}

export function makeT(lang) {
  return (key) => (STR[key] ? STR[key][lang] ?? STR[key].th : key)
}

// ---- numeric formatting ----------------------------------------------------
export const r0 = (x) => (x == null ? '–' : Math.round(Number(x)))
export const r1 = (x) => (x == null ? '–' : Math.round(Number(x) * 10) / 10)
export const pct0 = (x) => (x == null ? '–' : Math.round(Number(x) * 100))

// ---- compass / wind --------------------------------------------------------
const DIR_WORDS = {
  th: ['เหนือ', 'ตะวันออกเฉียงเหนือ', 'ตะวันออก', 'ตะวันออกเฉียงใต้',
       'ใต้', 'ตะวันตกเฉียงใต้', 'ตะวันตก', 'ตะวันตกเฉียงเหนือ'],
  en: ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
}
const ARROWS = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖'] // points TOWARD the bearing

const dirIndex = (deg) => Math.round((((deg % 360) + 360) % 360) / 45) % 8
export const dirWord = (deg, lang) => DIR_WORDS[lang][dirIndex(deg)]
export const dirArrow = (deg) => ARROWS[dirIndex(deg)]

// Wind shown as "comes FROM"; arrow points the way it BLOWS (from + 180).
export function windPhrase(speedMs, fromDeg, lang) {
  const w = windWord(speedMs, lang)
  const from = dirWord(fromDeg, lang)
  const arrow = dirArrow(fromDeg + 180)
  return lang === 'th' ? `${w} จากทิศ${from} ${arrow}` : `${w} from ${from} ${arrow}`
}

export function windWord(ms, lang) {
  const t = lang === 'th'
  if (ms < 2) return t ? 'ลมสงบ' : 'Calm'
  if (ms < 5) return t ? 'ลมเบา' : 'Light'
  if (ms < 8) return t ? 'ลมปานกลาง' : 'Moderate'
  if (ms < 12) return t ? 'ลมแรง' : 'Strong'
  return t ? 'ลมแรงมาก' : 'Very strong'
}

export function drynessWord(pct, lang) {
  const t = lang === 'th'
  if (pct < 30) return t ? 'ชื้น' : 'Wet'
  if (pct < 60) return t ? 'ปานกลาง' : 'Moderate'
  if (pct < 85) return t ? 'ค่อนข้างแห้ง' : 'Fairly dry'
  return t ? 'แห้งจัด' : 'Very dry'
}

export function chanceWord(p01, lang) {
  const t = lang === 'th'
  if (p01 < 0.33) return t ? 'ต่ำ' : 'low'
  if (p01 < 0.66) return t ? 'ปานกลาง' : 'medium'
  return t ? 'สูง' : 'high'
}

// Human-friendly duration. Time is an ESTIMATE only (see App: steps x cell / rate).
export function formatDuration(min, lang) {
  const t = lang === 'th'
  if (min == null || !isFinite(min)) return '–'
  if (min < 1) return t ? 'ไม่ถึง 1 นาที' : 'under 1 min'
  if (min < 60) return `${Math.round(min)} ${t ? 'นาที' : 'min'}`
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  if (t) return `${h} ชม.${m ? ` ${m} นาที` : ''}`
  return `${h} h${m ? ` ${m} min` : ''}`
}

// ---- danger class ----------------------------------------------------------
const DANGER = {
  Low: { th: 'ต่ำ', en: 'Low', color: '#1f7a4d', emoji: '🟢' },
  Moderate: { th: 'ปานกลาง', en: 'Moderate', color: '#b8a31f', emoji: '🟡' },
  High: { th: 'สูง', en: 'High', color: '#c77d2e', emoji: '🟠' },
  'Very High': { th: 'สูงมาก', en: 'Very High', color: '#c0431f', emoji: '🔴' },
  Extreme: { th: 'อันตรายสุดขีด', en: 'Extreme', color: '#c01f1f', emoji: '🔥' },
}
export function dangerInfo(klass, lang) {
  const d = DANGER[klass] || DANGER.Low
  return { label: d[lang], color: d.color, emoji: d.emoji }
}

// ---- geometry (display-only, from coords the API already returns) ----------
export function bearingDeg(lat1, lon1, lat2, lon2) {
  const midLat = ((lat1 + lat2) / 2) * Math.PI / 180
  const east = (lon2 - lon1) * Math.cos(midLat)
  const north = lat2 - lat1
  return ((Math.atan2(east, north) * 180) / Math.PI + 360) % 360
}

export function distanceKm(lat1, lon1, lat2, lon2) {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

// nearest community/asset to a (lon,lat); returns { name, km } or null
export function nearestAsset(lon, lat, assets) {
  if (!assets || !assets.length) return null
  let best = null
  for (const a of assets) {
    const km = distanceKm(lat, lon, a.lat, a.lon)
    if (!best || km < best.km) best = { name: a.name, km }
  }
  return best
}
