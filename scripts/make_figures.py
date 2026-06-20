"""
make_figures.py - Report figures (flowcharts + charts) saved to scripts/out/.
Run: python scripts/make_figures.py
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Thai-capable font (Tahoma ships with Windows and covers Thai + Latin).
plt.rcParams["font.sans-serif"] = ["Tahoma", "Leelawadee UI", "TH Sarabun New", "DejaVu Sans"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "scripts" / "out"
OUT.mkdir(exist_ok=True)
C = {"fe": "#cfe3f7", "be": "#ffd9b0", "model": "#cdebd2", "data": "#e6e6e6"}


def box(ax, x, y, w, h, text, fc):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.06",
                 lw=1.4, edgecolor="#444", facecolor=fc))
    ax.text(x, y, text, ha="center", va="center", fontsize=11)


def arrow(ax, x1, y1, x2, y2, text=None):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", lw=1.5, color="#666"))
    if text:
        ax.text((x1 + x2) / 2 + 0.15, (y1 + y2) / 2, text, fontsize=9, color="#666", va="center")


# Figure 1 — architecture
fig, ax = plt.subplots(figsize=(9, 8)); ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
box(ax, 5, 9.3, 4.2, 0.9, "ผู้ใช้ (ชาวบ้าน / เจ้าหน้าที่ / อาสา)", C["fe"])
box(ax, 5, 7.7, 4.4, 0.9, "Frontend : React + Leaflet (แผนที่)", C["fe"])
box(ax, 5, 6.0, 4.4, 0.9, "Backend : FastAPI", C["be"])
mx = [1.7, 3.9, 6.1, 8.3]
for x, l in zip(mx, ["FWI\nความเสี่ยง", "CA\nการลามไฟ", "ML/AI\nพื้นที่เสี่ยง", "คำแนะนำ\nดับไฟ"]):
    box(ax, x, 4.1, 2.0, 1.0, l, C["model"])
for x, l in zip(mx, ["Open-Meteo\n(อากาศ)", "Terrarium\n(ความสูง)", "WorldCover\n(เชื้อเพลิง)", "FIRMS\n(ไฟอดีต)"]):
    box(ax, x, 1.7, 2.0, 1.0, l, C["data"])
arrow(ax, 5, 8.85, 5, 8.18); arrow(ax, 5, 7.25, 5, 6.48, "HTTP /api")
for x in mx:
    arrow(ax, 5, 5.55, x, 4.65)
    arrow(ax, x, 2.22, x, 3.58)
ax.text(5, 0.6, "ข้อมูลจริงทั้งหมด (ฟรี) + cache บนดิสก์", ha="center", fontsize=10, color="#666")
ax.set_title("ภาพที่ 1  สถาปัตยกรรมระบบ (System Architecture)", fontsize=13, weight="bold")
fig.tight_layout(); fig.savefig(OUT / "fig_architecture.png", dpi=130, bbox_inches="tight"); plt.close(fig)

# Figure 2 — data pipeline
fig, ax = plt.subplots(figsize=(11, 3.4)); ax.set_xlim(0, 11); ax.set_ylim(0, 4); ax.axis("off")
steps = [("ข้อมูลจริง\nอากาศ·DEM·เชื้อเพลิง·ไฟอดีต", C["data"]),
         ("กริดหลัก\nอ้างพิกัด lat/lon", C["be"]),
         ("โมเดล\nFWI · CA · ML", C["model"]),
         ("ผลลัพธ์\nแผนที่เสี่ยง·การลาม·คำแนะนำ", C["fe"])]
xs = [1.5, 4.1, 6.7, 9.3]
for x, (l, c) in zip(xs, steps):
    box(ax, x, 2, 2.4, 1.5, l, c)
for i in range(len(xs) - 1):
    arrow(ax, xs[i] + 1.2, 2, xs[i + 1] - 1.2, 2)
ax.set_title("ภาพที่ 2  ลำดับการประมวลผลข้อมูล (Data Pipeline)", fontsize=13, weight="bold")
fig.tight_layout(); fig.savefig(OUT / "fig_pipeline.png", dpi=130, bbox_inches="tight"); plt.close(fig)

# Figure 3 — ML feature importance
meta = json.loads((ROOT / "backend/cache/national_meta.json").read_text())
imp = meta.get("importances", {})
names = {"elevation": "ความสูง", "dist_builtup_km": "ระยะถึงชุมชน", "fuel_factor": "ชนิดเชื้อเพลิง",
         "slope_deg": "ความชัน", "aspect_sin": "ทิศ (sin)", "aspect_cos": "ทิศ (cos)"}
items = sorted(imp.items(), key=lambda kv: kv[1])
fig, ax = plt.subplots(figsize=(8, 4.3))
vals = [v for _, v in items]
ax.barh([names.get(k, k) for k, _ in items], vals, color="#d8633a")
for i, v in enumerate(vals):
    ax.text(v + 0.006, i, f"{v:.2f}", va="center", fontsize=10)
ax.set_xlim(0, max(vals) * 1.18); ax.set_xlabel("ความสำคัญของปัจจัย")
ax.set_title(f"ภาพที่ 3  ปัจจัยทำนายพื้นที่เสี่ยงไฟ (AI · AUC = {meta.get('auc')})", fontsize=12, weight="bold")
fig.tight_layout(); fig.savefig(OUT / "fig_feature_importance.png", dpi=130, bbox_inches="tight"); plt.close(fig)

# Figure 4 — FWI responds to weather
fig, ax = plt.subplots(figsize=(6, 4.3))
ax.bar(["วันฝน\n(จริงวันนี้)", "วันแล้ง\n(สมมติ)"], [0.03, 49.7], color=["#2e9e5b", "#c0291f"])
for i, v in enumerate([0.03, 49.7]):
    ax.text(i, v + 1, f"ISI = {v}", ha="center", fontsize=10)
ax.set_ylabel("ดัชนีการลามไฟ (ISI)")
ax.set_title("ภาพที่ 4  โมเดลตอบสนองสภาพอากาศจริง (FWI)", fontsize=12, weight="bold")
fig.tight_layout(); fig.savefig(OUT / "fig_fwi_weather.png", dpi=130, bbox_inches="tight"); plt.close(fig)

print("wrote:", *[p.name for p in sorted(OUT.glob("fig_*.png"))])
