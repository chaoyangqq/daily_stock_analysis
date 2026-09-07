# -*- coding: utf-8 -*-
"""
A股 & 港股波段交易战术复盘看板 - 极简高清长图生成器
基于 Pillow 渲染，零外部繁重依赖，支持 macOS 和 GitHub Actions (Ubuntu)。
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
    market_score: int = 62,
    market_mood: str = "偏暖进攻",
    suggested_position: str = "60%",
    indices: Optional[List[Dict[str, Any]]] = None,
    holdings: Optional[List[Dict[str, Any]]] = None,
    top_sectors: Optional[List[str]] = None,
    disciplines: Optional[List[str]] = None
) -> str:
    """生成 1000 x 1400 高清暗黑金融终端风格交易复盘长图"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 默认数据保底
    if not indices:
        indices = [
            {"name": "上证指数", "price": "3936.96", "change": "+0.17%", "is_up": True},
            {"name": "创业板指", "price": "3344.95", "change": "+1.78%", "is_up": True},
            {"name": "恒生指数", "price": "25650.87", "change": "+1.74%", "is_up": True},
            {"name": "恒生科技", "price": "4569.80", "change": "+0.00%", "is_up": True},
        ]
        
    if not holdings:
        holdings = [
            {"name": "电力ETF广发", "code": "159611", "cost": 0.947, "current": 1.039, "pnl": "+9.75%", "pnl_val": 9.75, "action": "顺移止盈 1.010", "status": "多头主升"},
            {"name": "有色ETF汇添富", "code": "159652", "cost": 1.529, "current": 1.615, "pnl": "+5.65%", "pnl_val": 5.65, "action": "逼近前高减1/3", "status": "高位蓄势"},
            {"name": "西部矿业", "code": "601168", "cost": 38.75, "current": 38.25, "pnl": "-1.29%", "pnl_val": -1.29, "action": "企稳持有 37.50", "status": "缩量震荡"},
            {"name": "海康威视", "code": "002415", "cost": 35.76, "current": 34.74, "pnl": "-2.86%", "pnl_val": -2.86, "action": "逢反弹减亏 34.00", "status": "支撑企稳"},
            {"name": "科创新药ETF", "code": "589120", "cost": 0.842, "current": 0.817, "pnl": "-2.91%", "pnl_val": -2.91, "action": "底线防守 0.800", "status": "底部筑底"},
        ]
        
    if not top_sectors:
        top_sectors = ["印制电路板 +4.74%", "种植业 +4.42%", "半导体元件 +4.04%"]
        
    if not disciplines:
        disciplines = [
            "大盘偏暖但成交仍处地量，严禁盲目追高，仓位严控在 60% 上限；",
            "盈利持仓坚决顺移防守止盈线，破位 MA20 无条件止损保护本金。"
        ]

    W, H = 1000, 1420
    # 色彩方案：深灰蓝暗黑金融终端底色
    BG_COLOR = (15, 18, 25)
    PANEL_BG = (23, 28, 38)
    PANEL_BORDER = (38, 46, 62)
    TEXT_WHITE = (255, 255, 255)
    TEXT_MUTED = (148, 163, 184)
    COLOR_RED = (239, 68, 68)     # A股涨/盈利
    COLOR_GREEN = (34, 197, 94)   # A股跌/浮亏
    COLOR_BLUE = (59, 130, 246)
    COLOR_GOLD = (245, 158, 11)

    img = Image.new("RGB", (W, H), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 字体预备
    font_title = get_chinese_font(32)
    font_subtitle = get_chinese_font(18)
    font_section = get_chinese_font(22)
    font_body = get_chinese_font(18)
    font_sm = get_chinese_font(15)
    font_lg_num = get_chinese_font(28)

    # --- 1. 顶部 Header ---
    draw_rounded_rect(draw, (30, 30, W - 30, 110), 12, fill=PANEL_BG, outline=PANEL_BORDER)
    # 装饰光条
    draw.rectangle([30, 30, 38, 110], fill=COLOR_BLUE)
    draw.text((55, 42), "A股 & 港股波段交易战术复盘", font=font_title, fill=TEXT_WHITE)
    today_str = datetime.date.today().strftime("%Y年%m月%d日")
    draw.text((55, 80), f"收盘战术看板 · 四步闭环决策系统 · {today_str}", font=font_subtitle, fill=TEXT_MUTED)

    # --- 2. 大盘定调 & 建议仓位 ---
    card_y = 125
    draw_rounded_rect(draw, (30, card_y, W - 30, card_y + 130), 12, fill=PANEL_BG, outline=PANEL_BORDER)
    # 绘制金色圆点
    draw.ellipse([50, card_y + 24, 62, card_y + 36], fill=COLOR_GOLD)
    draw.text((72, card_y + 18), "大盘多空环境与仓位定调", font=font_section, fill=COLOR_GOLD)
    
    # 多空分与仓位标签
    score_text = f"多空温度: {market_score}/100 ({market_mood})"
    draw.text((50, card_y + 55), score_text, font=font_body, fill=TEXT_WHITE)
    pos_text = f"建议总仓位上限: {suggested_position}"
    draw.text((550, card_y + 55), pos_text, font=font_body, fill=COLOR_BLUE)

    # 绘制进度条
    bar_x1, bar_y1, bar_x2, bar_y2 = 50, card_y + 90, 480, card_y + 110
    draw.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=6, fill=(40, 48, 64))
    fill_w = int((bar_x2 - bar_x1) * (market_score / 100.0))
    draw.rounded_rectangle([bar_x1, bar_y1, bar_x1 + fill_w, bar_y2], radius=6, fill=COLOR_RED)

    bar2_x1, bar2_y1, bar2_x2, bar2_y2 = 550, card_y + 90, 930, card_y + 110
    draw.rounded_rectangle([bar2_x1, bar2_y1, bar2_x2, bar2_y2], radius=6, fill=(40, 48, 64))
    pos_val = int(suggested_position.replace("%", "").strip() or "50")
    fill_w2 = int((bar2_x2 - bar2_x1) * (pos_val / 100.0))
    draw.rounded_rectangle([bar2_x1, bar2_y1, bar2_x1 + fill_w2, bar2_y2], radius=6, fill=COLOR_BLUE)

    # --- 3. 核心指数走势卡片 ---
    idx_y = card_y + 145
    draw.ellipse([35, idx_y + 6, 45, idx_y + 16], fill=COLOR_BLUE)
    draw.text((55, idx_y), "核心指数实时映射", font=font_section, fill=TEXT_WHITE)
    
    idx_w = (W - 60 - 30) // 4
    for i, idx in enumerate(indices[:4]):
        cx1 = 30 + i * (idx_w + 10)
        cx2 = cx1 + idx_w
        cy1 = idx_y + 35
        cy2 = cy1 + 95
        is_up = "+" in idx["change"]
        badge_color = COLOR_RED if is_up else COLOR_GREEN
        draw_rounded_rect(draw, (cx1, cy1, cx2, cy2), 10, fill=PANEL_BG, outline=PANEL_BORDER)
        draw.text((cx1 + 15, cy1 + 15), idx["name"], font=font_body, fill=TEXT_MUTED)
        draw.text((cx1 + 15, cy1 + 45), idx["price"], font=font_lg_num, fill=TEXT_WHITE)
        # 涨跌标签
        draw.rounded_rectangle([cx2 - 80, cy1 + 15, cx2 - 12, cy1 + 40], radius=4, fill=badge_color)
        draw.text((cx2 - 74, cy1 + 18), idx["change"], font=font_sm, fill=TEXT_WHITE)

    # --- 4. 重点持仓盈亏柱状对比图 (核心视觉亮点) ---
    hold_y = idx_y + 150
    draw_rounded_rect(draw, (30, hold_y, W - 30, hold_y + 440), 12, fill=PANEL_BG, outline=PANEL_BORDER)
    draw.ellipse([50, hold_y + 24, 62, hold_y + 36], fill=COLOR_BLUE)
    draw.text((72, hold_y + 18), "个人持仓盈亏对比与移动风控", font=font_section, fill=COLOR_BLUE)
    draw.text((50, hold_y + 50), "实时跟踪持仓成本基准、动态止盈保护位与防守信号", font=font_sm, fill=TEXT_MUTED)

    item_start_y = hold_y + 85
    for j, h in enumerate(holdings[:5]):
        iy = item_start_y + j * 68
        # 标的名称与代码
        draw.text((50, iy), f"{h['name']}", font=font_body, fill=TEXT_WHITE)
        draw.text((50, iy + 25), f"成本:{h['cost']:.3f} | 现价:{h['current']:.3f}", font=font_sm, fill=TEXT_MUTED)

        # 盈亏数值
        pnl_val = h["pnl_val"]
        is_pos = pnl_val >= 0
        pnl_color = COLOR_RED if is_pos else COLOR_GREEN
        draw.text((280, iy + 8), f"{h['pnl']}", font=font_section, fill=pnl_color)

        # 柱状图对比 (基准中线 520)
        center_x = 520
        draw.line([(center_x, iy), (center_x, iy + 35)], fill=(70, 80, 100), width=1)
        max_bar = 160
        bar_len = int(min(abs(pnl_val) / 15.0, 1.0) * max_bar)
        if is_pos:
            draw.rounded_rectangle([center_x, iy + 8, center_x + bar_len, iy + 28], radius=4, fill=COLOR_RED)
        else:
            draw.rounded_rectangle([center_x - bar_len, iy + 8, center_x, iy + 28], radius=4, fill=COLOR_GREEN)

        # 专属动作预案胶囊
        draw_rounded_rect(draw, (710, iy + 4, 920, iy + 36), 6, fill=(35, 45, 65), outline=(50, 65, 95))
        draw.text((725, iy + 9), h["action"], font=font_sm, fill=COLOR_GOLD)

        # 分割线
        if j < 4:
            draw.line([(50, iy + 52), (W - 50, iy + 52)], fill=(32, 38, 50), width=1)

    # --- 5. 主线板块与明日交易纪律 ---
    strat_y = hold_y + 455
    draw_rounded_rect(draw, (30, strat_y, W - 30, strat_y + 195), 12, fill=PANEL_BG, outline=PANEL_BORDER)
    draw.ellipse([50, strat_y + 24, 62, strat_y + 36], fill=COLOR_GOLD)
    draw.text((72, strat_y + 18), "今日领涨主线 & 明日操盘铁律", font=font_section, fill=COLOR_GOLD)

    # 主线标签
    draw.text((50, strat_y + 55), "最强主线:", font=font_body, fill=TEXT_MUTED)
    sec_x = 150
    for s in top_sectors[:3]:
        sec_w = 190
        draw_rounded_rect(draw, (sec_x, strat_y + 50, sec_x + sec_w, strat_y + 80), 6, fill=(45, 30, 35), outline=(90, 40, 50))
        draw.text((sec_x + 12, strat_y + 55), s, font=font_sm, fill=COLOR_RED)
        sec_x += sec_w + 15

    # 纪律条目
    for k, d in enumerate(disciplines[:2]):
        dy = strat_y + 100 + k * 35
        draw.ellipse([50, dy + 5, 58, dy + 13], fill=COLOR_BLUE)
        draw.text((70, dy), f"纪律 {k+1}: {d}", font=font_body, fill=TEXT_WHITE)

    # --- 6. 底部版权与免责声明 ---
    foot_y = H - 55
    draw.text((50, foot_y), "Daily Stock Analysis · DeepSeek-V4-Flash 自动化复盘 · 仅供量化策略研究参考，不构成实盘买卖建议", font=font_sm, fill=(100, 110, 130))

    img.save(output_path, "PNG", quality=95)
    logger.info("交易复盘长图海报已成功生成: %s", output_path)
    return output_path

if __name__ == "__main__":
    out = generate_tactical_poster("reports/tactical_poster.png")
    print("Poster saved to:", out)
