# -*- coding: utf-8 -*-
"""
A股 & 港股 ICT 板块结构机会日报 - 手机端高清长图生成器
设计规范：
1. 强制白底商务科技风：纯白底色 (#FFFFFF) + 藏青深蓝 (#0B2341) + 中国联通红 (#E60012)
2. 聚焦大盘与板块结构（Market Regime & Sector Regime），严禁冗长个股指导
3. 适合手机屏幕全屏阅读（1080 x 1780 高分辨率，卡片化高密度排版）
"""

import os
import sys
import datetime
import logging
from typing import Dict, List, Any, Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

def get_chinese_font(size: int = 20, bold: bool = False) -> ImageFont.ImageFont:
    candidate_fonts = [
        # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        # Ubuntu / Debian (GitHub Actions)
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]
    for p in candidate_fonts:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_rounded_rect(draw: ImageDraw.ImageDraw, coords, radius: int, fill, outline=None, width=1):
    x1, y1, x2, y2 = coords
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)

def generate_tactical_poster(
    output_path: str = "reports/tactical_poster.png",
    period_title: str = "早盘盘前指导 · 结构定调与准入计划",
    report_date: Optional[str] = None,
    overall_regime: str = "Bearish",
    regime_desc: str = "上证/沪深300双指数收盘确认Bearish MSS/BOS，均处MA20下方",
    wait_condition: str = "环境层等指数收盘价向上结构确认；核心板块仅看折价区回踩，严禁追高",
    indices: Optional[List[Dict[str, Any]]] = None,
    sectors: Optional[List[Dict[str, Any]]] = None,
    disciplines: Optional[List[str]] = None
) -> str:
    """生成 1080 x 1780 高清白底商务科技风 ICT 板块机会看板长图"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    today_str = report_date or datetime.date.today().strftime("%Y-%m-%d")

    # 默认指数数据保底 (参考用户 ICT 报告实际数据)
    if not indices:
        indices = [
            {"name": "上证指数", "price": "3813.79", "change": "+0.05%", "trend": "Bearish", "evidence": "Bear MSS CONFIRMED", "location": "14.0% Discount"},
            {"name": "沪深300", "price": "4317.26", "change": "+0.16%", "trend": "Bearish", "evidence": "Bear BOS CONFIRMED", "location": "9.4% Discount"},
            {"name": "创业板指", "price": "3043.33", "change": "+0.22%", "trend": "Neutral", "evidence": "BOS↓ SWEEP 假破", "location": "22.5% Discount"},
            {"name": "恒生指数", "price": "24211.35", "change": "+1.79%", "trend": "Neutral", "evidence": "MA20 上方震荡反弹", "location": "35.0% Discount"},
        ]

    # 默认核心板块数据保底 (覆盖用户核心行业)
    if not sectors:
        sectors = [
            {"name": "PCB/算力硬件", "regime": "Neutral", "pd": "20.4% 折价", "event": "MSS↑ FAILED / BOS↓ SWEEP", "advice": "观察回踩 勿追"},
            {"name": "光模块/CPO", "regime": "Neutral", "pd": "20.4% 折价", "event": "缩量震荡筑底 / 等待放量", "advice": "折价区观察"},
            {"name": "重卡/工程机械", "regime": "Bullish", "pd": "65.9% 溢价", "event": "MSS↑ CONFIRMED 偏多走势", "advice": "顺势跟随 设防"},
            {"name": "创新药/生物", "regime": "Neutral", "pd": "69.1% 溢价", "event": "MSS↓ FAILED 企稳拉锯", "advice": "区间拉锯 观望"},
            {"name": "芯片设计/设备", "regime": "Neutral", "pd": "28.0% 折价", "event": "BOS↓ SWEEP 假破底探底", "advice": "等待放量突破"},
            {"name": "有色金属", "regime": "Bearish", "pd": "15.5% 折价", "event": "BOS↓ CONFIRMED 破位偏空", "advice": "严守防守位 减仓"},
            {"name": "能源/电力", "regime": "Bullish", "pd": "65.9% 溢价", "event": "MSS↑ CONFIRMED 趋势保持", "advice": "移动止盈 保护"},
            {"name": "券商保险", "regime": "Neutral", "pd": "15.2% 折价", "event": "BOS↓ FAILED 探底企稳", "advice": "防守观察 等风"},
            {"name": "食品饮料", "regime": "Neutral", "pd": "22.9% 折价", "event": "窄幅盘整 / 暂无右侧信号", "advice": "多看少动 观望"},
            {"name": "船舶/军工", "regime": "Bearish", "pd": "15.0% 折价", "event": "MSS↓ CONFIRMED 弱势运行", "advice": "防守规避 不抄"},
        ]

    if not disciplines:
        disciplines = [
            "【折价区准入】处于 Discount (<30%) 且出现 MSS↑/Sweep 收盘确认前，严禁左侧盲目猜底；",
            "【溢价区防守】处于 Premium (>60%) 板块严禁追涨，以移动止盈线保护利润；",
            "【收盘价确认】盘中分时波动假突破居多，以 14:50 临近收盘的真实确认价为执行基准。"
        ]

    W, H = 1080, 1780

    # 规范调色板：纯白底色 + 中国联通红 + 藏青深蓝 + 商务冷灰
    BG_CANVAS = (248, 250, 252)       # #F8FAFC 浅灰白底色，温润不刺眼
    PANEL_BG = (255, 255, 255)        # #FFFFFF 纯白卡片面板
    PANEL_BORDER = (226, 232, 240)    # #E2E8F0 精致卡片边框
    NAVY_PRIMARY = (11, 35, 65)       # #0B2341 藏青深蓝（联通/政企标准主色）
    RED_UNICOM = (230, 0, 18)         # #E60012 中国联通红（焦点与强调色）
    TEXT_MAIN = (15, 23, 42)          # #0F172A 浓黑主标题文字
    TEXT_MUTED = (100, 116, 139)      # #64748B 次要灰阶文字
    TEXT_LIGHT = (148, 163, 184)      # #94A3B8 辅助提示文字
    GREEN_BEAR = (22, 163, 74)        # #16A34A 稳健绿 (跌/空头/防守)
    AMBER_NEUTRAL = (217, 119, 6)     # #D97706 琥珀金 (中性/震荡)

    img = Image.new("RGB", (W, H), color=BG_CANVAS)
    draw = ImageDraw.Draw(img)

    # 字体预备
    font_header_title = get_chinese_font(34, bold=True)
    font_header_sub = get_chinese_font(18)
    font_section_title = get_chinese_font(22, bold=True)
    font_body = get_chinese_font(18)
    font_body_bold = get_chinese_font(18, bold=True)
    font_sm = get_chinese_font(15)
    font_badge = get_chinese_font(14, bold=True)
    font_number = get_chinese_font(24, bold=True)

    # ==========================================
    # 1. 顶部 Header (藏青主色 + 联通红底标)
    # ==========================================
    draw.rectangle([0, 0, W, 140], fill=NAVY_PRIMARY)
    # 底部 4px 联通红强调线
    draw.rectangle([0, 136, W, 140], fill=RED_UNICOM)

    # 主标题与副标题
    draw.text((45, 30), "ICT 板块结构机会日报", font=font_header_title, fill=(255, 255, 255))
    draw.text((45, 82), f"【{period_title}】  日期：{today_str}  ·  日线周期 (HTF 130D / 40D)", font=font_header_sub, fill=(203, 213, 225))

    # 右侧标签
    draw_rounded_rect(draw, (W - 220, 42, W - 45, 88), 8, fill=RED_UNICOM)
    draw.text((W - 200, 52), "手机端极简看板", font=font_section_title, fill=(255, 255, 255))

    # ==========================================
    # 2. 今日核心结论 (Executive Summary 卡片)
    # ==========================================
    c1_y = 160
    draw_rounded_rect(draw, (35, c1_y, W - 35, c1_y + 165), 14, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    # 联通红左侧标志装饰竖条
    draw.rounded_rectangle([35, c1_y, 43, c1_y + 165], radius=4, fill=RED_UNICOM)

    # 标题栏
    draw.text((60, c1_y + 18), "📌 今日核心结论 (Executive Summary)", font=font_section_title, fill=NAVY_PRIMARY)

    # 市场多空环境 Badge
    regime_bg = (254, 242, 242) if overall_regime == "Bearish" else ((240, 253, 244) if overall_regime == "Bullish" else (255, 251, 235))
    regime_fg = RED_UNICOM if overall_regime == "Bearish" else (GREEN_BEAR if overall_regime == "Bullish" else AMBER_NEUTRAL)
    draw_rounded_rect(draw, (W - 250, c1_y + 15, W - 55, c1_y + 50), 6, fill=regime_bg, outline=regime_fg)
    draw.text((W - 235, c1_y + 20), f"Market Regime: {overall_regime}", font=font_badge, fill=regime_fg)

    # 结论文字描述
    draw.text((60, c1_y + 60), f"环境定调：{regime_desc}", font=font_body_bold, fill=TEXT_MAIN)
    draw.text((60, c1_y + 92), f"关键等待：{wait_condition}", font=font_body, fill=RED_UNICOM)
    draw.text((60, c1_y + 125), "准入纪律：环境偏空时否决激进追单；仅在折价区(Discount)且关键结构确认时布局。", font=font_sm, fill=TEXT_MUTED)

    # ==========================================
    # 3. Market Regime 大盘指数结构化判定
    # ==========================================
    c2_y = c1_y + 185
    draw_rounded_rect(draw, (35, c2_y, W - 35, c2_y + 245), 14, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.rounded_rectangle([35, c2_y, 43, c2_y + 245], radius=4, fill=NAVY_PRIMARY)

    draw.text((60, c2_y + 18), "🌡️ Market Regime 指数结构判定 (基于收盘价确认)", font=font_section_title, fill=NAVY_PRIMARY)

    # 指数卡片 4 列排布
    card_w = (W - 70 - 45) // 4
    for i, idx in enumerate(indices[:4]):
        ix1 = 55 + i * (card_w + 15)
        ix2 = ix1 + card_w
        iy1 = c2_y + 60
        iy2 = iy1 + 165
        draw_rounded_rect(draw, (ix1, iy1, ix2, iy2), 10, fill=(248, 250, 252), outline=PANEL_BORDER)

        # 指数名称与涨跌
        draw.text((ix1 + 12, iy1 + 12), idx["name"], font=font_body_bold, fill=NAVY_PRIMARY)
        is_up = "+" in str(idx.get("change", ""))
        color_change = RED_UNICOM if is_up else GREEN_BEAR
        draw.text((ix1 + 12, iy1 + 38), idx["price"], font=font_number, fill=TEXT_MAIN)
        draw.text((ix1 + 12, iy1 + 72), f"{idx.get('change', '0.00%')}", font=font_sm, fill=color_change)

        # 趋势评级徽章
        t_str = idx.get("trend", "Neutral")
        t_bg = (254, 242, 242) if t_str == "Bearish" else ((240, 253, 244) if t_str == "Bullish" else (255, 251, 235))
        t_fg = RED_UNICOM if t_str == "Bearish" else (GREEN_BEAR if t_str == "Bullish" else AMBER_NEUTRAL)
        draw_rounded_rect(draw, (ix1 + 12, iy1 + 98, ix2 - 12, iy1 + 124), 5, fill=t_bg, outline=t_fg)
        draw.text((ix1 + 20, iy1 + 102), f"趋势: {t_str}", font=font_badge, fill=t_fg)

        # 结构与位置
        draw.text((ix1 + 12, iy1 + 132), f"PD: {idx.get('location', '-')}", font=font_sm, fill=TEXT_MUTED)

    # ==========================================
    # 4. Sector Regime 核心板块多空结构表 (纯板块，无个股)
    # ==========================================
    c3_y = c2_y + 265
    draw_rounded_rect(draw, (35, c3_y, W - 35, c3_y + 770), 14, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.rounded_rectangle([35, c3_y, 43, c3_y + 770], radius=4, fill=RED_UNICOM)

    draw.text((60, c3_y + 18), "🧭 Sector Regime 核心板块结构矩阵 (日线结构透视)", font=font_section_title, fill=NAVY_PRIMARY)
    draw.text((W - 320, c3_y + 22), "纯行业板块视角 · 拒绝个股噪音", font=font_sm, fill=TEXT_MUTED)

    # 表头
    th_y = c3_y + 60
    draw.rectangle([50, th_y, W - 50, th_y + 36], fill=(241, 245, 249))
    draw.text((65, th_y + 8), "板块名称", font=font_badge, fill=NAVY_PRIMARY)
    draw.text((250, th_y + 8), "评级", font=font_badge, fill=NAVY_PRIMARY)
    draw.text((370, th_y + 8), "PD区间位置", font=font_badge, fill=NAVY_PRIMARY)
    draw.text((540, th_y + 8), "关键结构事件 (Evidence)", font=font_badge, fill=NAVY_PRIMARY)
    draw.text((850, th_y + 8), "战术指导建议", font=font_badge, fill=NAVY_PRIMARY)

    # 板块条目 (10 行)
    sec_start_y = th_y + 44
    for s_idx, sec in enumerate(sectors[:10]):
        sy = sec_start_y + s_idx * 65
        # 隔行浅灰背景
        if s_idx % 2 == 1:
            draw.rectangle([50, sy - 4, W - 50, sy + 56], fill=(250, 250, 252))

        # 板块名
        draw.text((65, sy + 10), sec["name"], font=font_body_bold, fill=NAVY_PRIMARY)

        # 评级徽章
        s_reg = sec.get("regime", "Neutral")
        s_bg = (240, 253, 244) if s_reg == "Bullish" else ((254, 242, 242) if s_reg == "Bearish" else (255, 251, 235))
        s_fg = GREEN_BEAR if s_reg == "Bullish" else (RED_UNICOM if s_reg == "Bearish" else AMBER_NEUTRAL)
        draw_rounded_rect(draw, (245, sy + 8, 335, sy + 38), 6, fill=s_bg, outline=s_fg)
        draw.text((255, sy + 13), s_reg, font=font_badge, fill=s_fg)

        # PD 位置
        pd_text = sec.get("pd", "-")
        pd_color = RED_UNICOM if "折价" in pd_text or "Discount" in pd_text else NAVY_PRIMARY
        draw.text((370, sy + 12), pd_text, font=font_sm, fill=pd_color)

        # 关键结构事件
        draw.text((540, sy + 12), sec.get("event", "-"), font=font_sm, fill=TEXT_MAIN)

        # 战术指导建议胶囊
        draw_rounded_rect(draw, (840, sy + 7, W - 65, sy + 40), 6, fill=(241, 245, 249), outline=(203, 213, 225))
        draw.text((855, sy + 12), sec.get("advice", "-"), font=font_sm, fill=NAVY_PRIMARY)

        # 底部分割线
        draw.line([(50, sy + 58), (W - 50, sy + 58)], fill=(241, 245, 249), width=1)

    # ==========================================
    # 5. 操盘铁律与风险护栏 (Discipline)
    # ==========================================
    c4_y = c3_y + 790
    draw_rounded_rect(draw, (35, c4_y, W - 35, c4_y + 190), 14, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.rounded_rectangle([35, c4_y, 43, c4_y + 190], radius=4, fill=NAVY_PRIMARY)

    draw.text((60, c4_y + 18), "🛡️ 操盘战术护栏 (09:20 盘前准入 / 14:50 尾盘确认)", font=font_section_title, fill=NAVY_PRIMARY)

    for d_i, disc in enumerate(disciplines[:3]):
        dy = c4_y + 60 + d_i * 40
        draw.ellipse([60, dy + 5, 70, dy + 15], fill=RED_UNICOM)
        draw.text((80, dy), disc, font=font_body, fill=TEXT_MAIN)

    # ==========================================
    # 6. 底部版权与免责说明
    # ==========================================
    foot_y = H - 45
    draw.text((50, foot_y), "中国联通 · ICT 市场结构分析引擎 | DeepSeek-V4-Flash | 仅供量化策略研究参考，严守交易纪律", font=font_sm, fill=TEXT_LIGHT)

    img.save(output_path, "PNG", quality=95)
    logger.info("✅ 白底商务科技风战术海报已成功生成: %s", output_path)
    return output_path

if __name__ == "__main__":
    out = generate_tactical_poster("reports/tactical_poster.png")
    print("Poster saved to:", out)
