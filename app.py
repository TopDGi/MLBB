"""
MLBB — My Lip Best Bag
실행: python -m streamlit run app.py
"""

import os
import io
import base64
import tempfile
import numpy as np
import streamlit as st
from PIL import Image, ImageOps

st.set_page_config(page_title="mlbb.ai", page_icon="💄", layout="wide")

# ─────────────────────────────────────────────────────
# 여기서 결과 컴포넌트의 크기를 조정하세요
CELL_WIDTH  = 450
CELL_HEIGHT = 600
# ─────────────────────────────────────────────────────

TONE_PALETTE = [
    {"key": "봄웜_라이트",     "label": "봄웜\n라이트",    "color": "#f9c8a0"},
    {"key": "봄웜_브라이트",   "label": "봄웜\n브라이트",  "color": "#f0a070"},
    {"key": "가을웜_뮤트",     "label": "가을웜\n뮤트",    "color": "#c0856a"},
    {"key": "가을웜_딥",       "label": "가을웜\n딥",      "color": "#8b4c39"},
    {"key": "여름쿨_라이트",   "label": "여름쿨\n라이트",  "color": "#e8b4c0"},
    {"key": "여름쿨_뮤트",     "label": "여름쿨\n뮤트",    "color": "#c090a0"},
    {"key": "겨울쿨_브라이트", "label": "겨울쿨\n브라이트","color": "#9060a0"},
    {"key": "겨울쿨_딥",       "label": "겨울쿨\n딥",      "color": "#503060"},
]

COLOR_LABELS   = ["NUDE TERRA", "DUSTY ROSE", "BRICK SOUL", "WARM TAUPE"]
TEXTURE_LABELS = ["VELVET TEXTURE", "SILK SATIN", "MATTE BOLD", "GLOSSY FINISH"]
PAGE_PADDING   = "48px"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;500;700&family=DM+Sans:wght@300;400;500;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap');

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; -webkit-font-smoothing: antialiased; }}
.stApp {{ background-color: #faf8f6; }}
header[data-testid="stHeader"] {{ display: none !important; }}
.block-container {{ padding: 0 !important; max-width: 100% !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}

/* ── 네비바 ── */
.navbar {{
    position: sticky; top: 0; z-index: 50;
    background: rgba(253,248,247,0.9); backdrop-filter: blur(12px);
    border-bottom: 1px solid #d1c4c2;
    padding: 0 {PAGE_PADDING}; height: 64px;
    display: flex; justify-content: space-between; align-items: center;
}}
.navbar-logo {{ font-family: 'EB Garamond', serif; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; color: #645d5c; }}
.navbar-nav {{ display: flex; gap: 32px; }}
.navbar-nav a {{ font-size: 15px; color: #645d5c; text-decoration: none; font-weight: 500; border-bottom: 1px solid #645d5c; padding-bottom: 2px; }}

/* ── 페이지 래퍼 ── */
.page-wrap {{ max-width: 1280px; margin: 0 auto; padding: 36px {PAGE_PADDING} 0; }}
.section-wrap {{ max-width: 1280px; margin: 0 auto; padding: 20px {PAGE_PADDING} 0; }}

/* ── 업로드 존 ── */
.upload-zone-wrap {{ position: relative; margin-bottom: 12px; max-width : 140px; }}
.upload-zone {{
    border: 1px dashed #7f7574; border-radius: 1rem;
    padding: 28px 20px; display: flex; flex-direction: column;
    align-items: center; justify-content: center; text-align: center;
    background: rgba(255,255,255,0.5); min-height: 120px;
    transition: background 0.2s, border-color 0.2s;
}}
.upload-zone:hover {{ background: #f7f2f2; border-color: #645d5c; }}
.upload-zone p {{ font-size: 13px; color: #4e4544; font-weight: 300; margin-top: 6px; }}
.upload-zone-wrap {{ 
    position: relative; 
    margin-bottom: 12px; 
    width: 280px;
    max-width: 100%;
}}

/* 1번: 업로드 미리보기 절반 크기 */
.upload-preview-wrap {{
    width: 50%;
    margin: 0 auto 12px;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(209,196,194,0.3);
}}
.upload-preview-wrap img {{ width: 20%; display: block; }}

/* ── 버튼 ── */
.stButton > button {{
    width: 100% !important; background: #645d5c !important;
    color: #ffffff !important; border: none !important;
    border-radius: 9999px !important; padding: 12px 28px !important;
    font-size: 14px !important; font-weight: 500 !important;
    transition: opacity 0.2s !important;
}}
.stButton > button:hover {{ opacity: 0.88 !important; }}

/* 7번: 결과 헤더 정렬 - flex로 완전히 통제 */
.result-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    gap: 12px;
}}

/* 3번: tone badge - 진단된 톤 색상을 배경으로 */
.tone-badge {{
    display: inline-flex; align-items: center; gap: 10px;
    padding: 10px 22px; border-radius: 9999px;
    font-size: 13px; font-weight: 600;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #ffffff; flex-shrink: 0;
}}
.tone-dot {{ width: 10px; height: 10px; border-radius: 50%; background: rgba(255,255,255,0.5); flex-shrink: 0; }}

/* Save 버튼 */
.stDownloadButton > button {{
    border: 1.5px solid #645d5c !important; padding: 10px 22px !important;
    border-radius: 9999px !important; font-size: 13px !important;
    color: #645d5c !important; background: transparent !important; width: auto !important;
    font-weight: 500 !important; white-space: nowrap !important;
}}
.stDownloadButton > button:hover {{ background: #645d5c !important; color: #ffffff !important; }}

/* ── 립 셀 ── */
.lip-cell-wrap {{
    position: relative; border-radius: 14px; overflow: hidden;
    background: #f0ebe6; margin: 5px;
}}
.lip-cell-wrap img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}

/* 6번: 색상 라벨 → 일자 색상 바로 변경 */
.lip-color-bar {{
    position: absolute; top: 0; left: 0; right: 0;
    height: 5px;
}}

/* 상단 텍스처 라벨 */
.lip-label-top {{
    position: absolute; top: 10px; left: 10px;
    background: rgba(255,255,255,0.88); backdrop-filter: blur(4px);
    border-radius: 9999px; padding: 3px 10px;
    font-size: 14px; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #645d5c;
    cursor: default;
}}

/* 5번: 스코어 라벨 */
.lip-score-label {{
    position: absolute; top: 10px; right: 10px;
    background: rgba(255,255,255,0.88); backdrop-filter: blur(4px);
    border-radius: 9999px; padding: 3px 10px;
    font-size: 14px; font-weight: 700; letter-spacing: 0.1em;
    color: #8b4c39;
}}

/* 4번: 톤 맵 → 4×2, 좌측 컬럼에 배치 */
.tone-map-wrap {{
    background: #ffffff;
    border: 1px solid rgba(209,196,194,0.3);
    border-radius: 1rem;
    padding: 16px;
    margin-top: 12px;
}}
.tone-map-title {{
    font-size: 9px; font-weight: 600; letter-spacing: 0.18em;
    text-transform: uppercase; color: #9e8e86; margin-bottom: 12px;
}}
.tone-map-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
}}
.tone-chip {{
    display: flex; flex-direction: column; align-items: center; gap: 5px;
    padding: 8px 4px; border-radius: 10px;
    border: 2px solid transparent;
    transition: transform 0.2s;
}}
.tone-chip.active {{
    border-color: #645d5c;
    background: #f5f0ed;
    transform: scale(1.06);
}}
.tone-swatch {{
    width: 26px; height: 26px; border-radius: 50%;
    border: 1px solid rgba(0,0,0,0.08);
}}
.tone-chip-label {{
    font-size: 8px; font-weight: 500; color: #645d5c;
    text-align: center; line-height: 1.3; white-space: pre-line;
}}
.tone-chip.active .tone-chip-label {{ font-weight: 700; color: #3d2e28; }}

/* Streamlit 컬럼 간격 */
[data-testid="column"] {{
    padding-left: 5px !important;
    padding-right: 5px !important;
}}

/* ── 제품 카드 ── */
.product-card {{
    background: #ffffff; border: 1px solid rgba(209,196,194,0.4);
    border-radius: 1rem; padding: 18px; display: flex;
    flex-direction: column; height: 100%;
    transition: transform 0.3s cubic-bezier(0.2,0,0,1), box-shadow 0.3s;
}}
.product-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 24px rgba(26,16,8,0.07); }}
.card-swatch {{ height: 4px; width: 100%; border-radius: 9999px; margin-bottom: 16px; }}
.card-name {{ font-family: 'EB Garamond', serif; font-size: 20px; line-height: 1.2; color: #1c1b1b; margin-bottom: 5px; flex-grow: 1; }}
.card-score {{ font-size: 10px; font-weight: 700; letter-spacing: 0.1em; color: #625d5d; text-transform: uppercase; margin-bottom: 16px; }}
.card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(209,196,194,0.2); padding-top: 10px; }}
.card-product-name {{ font-size: 11px; color: #645d5c; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 80%; }}
.card-add {{ font-family: 'Material Symbols Outlined'; font-size: 20px; color: #7f7574; text-decoration: none; flex-shrink: 0; }}
.card-add:hover {{ color: #645d5c; }}

/* ── Section label ── */
.section-label {{ font-size: 10px; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase; color: #7f7574; margin-bottom: 12px; }}

/* ── Empty state ── */
.empty-state {{ display: flex; flex-direction: column; align-items: center; justify-content: center; height: 380px; gap: 12px; }}
.empty-glyph {{ font-family: 'EB Garamond', serif; font-size: 52px; color: #e6e1e1; font-style: italic; }}
.empty-text {{ font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #b0a098; }}

/* ── 푸터 ── */
.footer {{
    background: #fdf8f7; border-top: 1px solid #d1c4c2;
    padding: 32px {PAGE_PADDING}; display: flex;
    justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; margin-top: 40px;
}}
.footer-logo {{ font-family: 'EB Garamond', serif; font-size: 20px; font-weight: 700; color: #645d5c; }}
.footer-links {{ display: flex; gap: 24px; }}
.footer-links a {{ font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #4e4544; text-decoration: none; }}
.footer-links a:hover {{ color: #645d5c; }}
.footer-copy {{ font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: #7f7574; }}

[data-testid="stFileUploaderDropzone"] label {{ display: none !important; }}
section[data-testid="stFileUploaderDropzone"] {{ border: none !important; background: transparent !important; padding: 0 !important; }}
div[data-testid="stFileUploader"] {{ margin-bottom: 0 !important; }}
</style>
""", unsafe_allow_html=True)


# ── 모델 로드 ─────────────────────────────────────
@st.cache_resource
def load_models():
    from harmony_analyzer import HarmonyAnalyzer
    from matcher_v3 import LipstickMatcher_v2
    from visualizer_v2 import LipVisualizer_v2
    return HarmonyAnalyzer(), LipstickMatcher_v2(), LipVisualizer_v2()


def bgr_to_hex(bgr: list) -> str:
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def apply_top4_individually(analysis_result, top4, visualizer, img_bgr):
    import cv2 as _cv2
    results = []
    blended_hexes = []
    landmarks = analysis_result["raw_landmarks"]

    for item in top4:
        lip_bgr = item["bgr"]
        texture_map = {"MATTE": "matte", "GLOSSY": "glossy", "TINT": "tint", "SATIN": "matte", "BALM": "glossy", "LIPSTICK": "tint"}
        texture_str = texture_map.get(item.get("texture", ""), "matte")
        rendered, blended_bgr = visualizer.apply_lipstick(img_bgr, landmarks, lip_bgr, intensity=0.55, texture=texture_str)
        src = rendered

        blended_hexes.append(bgr_to_hex(blended_bgr))

        try:
            pil = Image.fromarray(_cv2.cvtColor(src, _cv2.COLOR_BGR2RGB))
        except Exception:
            pil = Image.fromarray(_cv2.cvtColor(img_bgr.copy(), _cv2.COLOR_BGR2RGB))
        results.append(pil)

    return results, blended_hexes


def run_pipeline(image_path, pil_img=None):
    import cv2 as _cv2
    analyzer, matcher, visualizer = load_models()
    analysis = analyzer.analyze(image_path)
    if "error" in analysis:
        return None, None, None, analysis["error"]
    top4_result = matcher.get_top4(analysis)
    top4 = top4_result.get("top4", [])
    img_bgr = (
        _cv2.cvtColor(np.array(pil_img.convert("RGB")), _cv2.COLOR_RGB2BGR)
        if pil_img is not None else _cv2.imread(image_path)
    )
    lip_images, blended_hexes = apply_top4_individually(analysis, top4, visualizer, img_bgr)
    return lip_images, top4_result, blended_hexes, None


def pil_to_b64(img: Image.Image, size=None, quality=88) -> str:
    out = img.copy()
    if size:
        out.thumbnail(size, Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def resize_letterbox(img: Image.Image, w: int, h: int) -> Image.Image:
    out = img.copy()
    out.thumbnail((w, h), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (240, 235, 230))
    canvas.paste(out, ((w - out.width) // 2, (h - out.height) // 2))
    return canvas


def make_grid_png(lip_images) -> bytes:
    if not lip_images:
        return b""
    w, h = CELL_WIDTH, CELL_HEIGHT
    cells = [resize_letterbox(img.copy(), w, h) for img in lip_images]
    gap = 6
    grid = Image.new("RGB", (w * 2 + gap, h * 2 + gap), (245, 242, 239))
    for i, cell in enumerate(cells[:4]):
        grid.paste(cell, ((i % 2) * (w + gap), (i // 2) * (h + gap)))
    buf = io.BytesIO()
    grid.save(buf, format="PNG")
    return buf.getvalue()


def get_tone_color(tone_key: str) -> str:
    for t in TONE_PALETTE:
        if t["key"] == tone_key:
            return t["color"]
    return "#645d5c"


def tone_map_html(active_tone: str) -> str:
    chips = ""
    for t in TONE_PALETTE:
        is_active = t["key"] == active_tone
        active_cls = "active" if is_active else ""
        chips += f"""
        <div class="tone-chip {active_cls}">
            <div class="tone-swatch" style="background:{t['color']}"></div>
            <div class="tone-chip-label">{t['label']}</div>
        </div>"""
    return f"""
    <div class="tone-map-wrap">
        <div class="tone-map-title">Your Tone in the Spectrum</div>
        <div class="tone-map-grid">{chips}</div>
    </div>"""


# ── 네비바 ───────────────────────────────────────
st.markdown("""
<div class="navbar">
    <div class="navbar-logo">mlbb.ai</div>
    <span style="font-family:'Material Symbols Outlined';font-size:24px;color:#645d5c;">shopping_bag</span>
</div>
""", unsafe_allow_html=True)

st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)

left_col, right_col = st.columns([2, 8], gap="large")

# ── 좌측 ──────────────────────────────────────────
with left_col:
    upload_col, _ = st.columns([3, 1])
    with upload_col:
        st.markdown("<div class='upload-zone-wrap'>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "사진 업로드", type=["jpg", "jpeg", "png"],
            label_visibility="collapsed", key="uploader",
        )
    if uploaded:
        pil_img = ImageOps.exif_transpose(Image.open(uploaded))
        preview_b64 = pil_to_b64(pil_img, size=(600, 800))
        st.markdown(f"""
        <div style="display:inline-block;max-width:100%;border-radius:1rem;
                    overflow:hidden;border:1px solid #645d5c;">
        <img src="data:image/jpeg;base64,{preview_b64}"
            style="max-height:280px;max-width:100%;width:auto;display:block;"/>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="upload-zone" style="pointer-events:none;">
            <p style="font-size:1.4rem;margin-bottom:4px;">📷</p>
            <p>클릭하거나 사진을 드래그하세요</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    analyze_btn = st.button("Discover My Colors")

    if analyze_btn:
        if not uploaded:
            st.warning("사진을 먼저 올려주세요.")
        else:
            pil_img = ImageOps.exif_transpose(Image.open(uploaded))
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                pil_img.save(tmp, format="PNG")
                tmp_path = tmp.name
            with st.spinner("분석 중..."):
                lip_images, top4_result, blended_hexes, error = run_pipeline(tmp_path, pil_img=pil_img)
            os.unlink(tmp_path)
            if error:
                st.error(f"분석 실패: {error}")
            else:
                st.session_state["result"] = (lip_images, top4_result, blended_hexes)

    if "result" in st.session_state:
        _, top4_result, _ = st.session_state["result"]
        tone = top4_result.get("user_diagnosed_tone", "")
        st.markdown(tone_map_html(tone), unsafe_allow_html=True)

# ── 우측 ──────────────────────────────────────────
with right_col:
    if "result" in st.session_state:
        lip_images, top4_result, blended_hexes = st.session_state["result"]
        tone       = top4_result.get("user_diagnosed_tone", "")
        top4       = top4_result.get("top4", [])
        tone_color = get_tone_color(tone)

        hdr_badge, hdr_save = st.columns([3, 1])
        with hdr_badge:
            st.markdown(f"""
            <div style="padding-top:4px;">
                <div class="tone-badge" style="background:{tone_color};">
                    <span class="tone-dot"></span>
                    Personal Lip Color &amp; Tone &nbsp;·&nbsp; {tone}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with hdr_save:
            st.download_button(
                "☁ Save",
                data=make_grid_png(lip_images),
                file_name="mlbb_result.png",
                mime="image/png",
            )

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        row1_c1, row1_c2 = st.columns(2, gap="small")
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        row2_c1, row2_c2 = st.columns(2, gap="small")
        grid_cells = [row1_c1, row1_c2, row2_c1, row2_c2]

        for i, (cell, lip_pil) in enumerate(zip(grid_cells, lip_images)):
            with cell:
                full_name  = top4[i].get("name", "") if i < len(top4) else ""
                short_name = full_name[:10] + "…" if len(full_name) > 10 else full_name
                score      = top4[i].get("score", 0) if i < len(top4) else 0
                # 색상 바: 렌더링 후 실제 발린 색 사용
                bar_hex    = blended_hexes[i] if i < len(blended_hexes) else "#8b4c39"
                fixed      = resize_letterbox(lip_pil.copy(), CELL_WIDTH, CELL_HEIGHT)
                img_b64    = pil_to_b64(fixed)

                st.markdown(f"""
                <div class="lip-cell-wrap"
                    style="width:100%;max-width:320px;aspect-ratio:3/4;margin:0 auto;">
                    <img src="data:image/jpeg;base64,{img_b64}"/>
                    <div class="lip-color-bar" style="background:{bar_hex};"></div>
                    <div class="lip-label-top" title="{full_name}">{short_name}</div>
                    <div class="lip-score-label">{score}%</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-glyph">✦</div>
            <p class="empty-text">Upload your photo to begin</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# ── 제품 카드 ─────────────────────────────────────
if "result" in st.session_state:
    _, top4_result, blended_hexes = st.session_state["result"]
    top4 = top4_result.get("top4", [])

    st.markdown("<div class='section-wrap'>", unsafe_allow_html=True)
    st.markdown("<p class='section-label'>Select Your Color</p>", unsafe_allow_html=True)

    card_cols = st.columns(4, gap="medium")
    for i, item in enumerate(top4[:4]):
        with card_cols[i]:
            name    = item.get("name", "")
            score   = item.get("score", 0)
            link    = item.get("link", "")
            short   = name[:24] + "…" if len(name) > 24 else name
            texture = item.get("texture", "")
            clabel  = name[:20]
            # 카드 스와치도 블렌딩된 색 사용
            bar_hex = blended_hexes[i] if i < len(blended_hexes) else "#8b4c39"
            add_html = (
                f"<a class='card-add' href='{link}' target='_blank'>add_circle</a>"
                if link else "<span class='card-add'>add_circle</span>"
            )
            st.markdown(f"""
            <a href="{link}" target="_blank" style="text-decoration:none;" 
                {"" if link else "style='pointer-events:none;'"}>
            <div class="product-card">
                <div class="card-swatch" style="background:{bar_hex}"></div>
                <div class="card-name" title="{name}">{texture.title()}<br/>{clabel}</div>
                <div class="card-score">{score}% Match Score</div>
                <div class="card-footer">
                    <span class="card-product-name">{short}</span>
                    <span class="card-add">open_in_new</span>
                </div>
            </div>
            </a>
            """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── 푸터 ─────────────────────────────────────────
st.markdown("""
<div class="footer">
    <div class="footer-logo">mlbb.ai</div>
    <div class="footer-links">
        <a href="#">Privacy</a>
        <a href="#">Terms</a>
        <a href="#">Contact</a>
    </div>
    <div class="footer-copy">© 2025 mlbb.ai. Precision Skincare Aesthetics.</div>
</div>
""", unsafe_allow_html=True)