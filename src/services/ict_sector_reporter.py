# -*- coding: utf-8 -*-
"""
A股 & 港股 ICT 板块结构机会日报系统 (手机端极简 · 09:20 盘前 & 14:50 尾盘)
核心设计：
1. 交易日调度：仅在中国交易日执行，早 09:20 发盘前指导，下午 14:50 发尾盘交易指导。
2. 精准时间对齐：内置目标时刻对齐器，消除 GitHub Actions 排队延迟，准点抓取 09:20 / 14:50 实时行情并推送。
3. 真实 ICT 结构计算：实时拉取 130D 日线 K 线，计算真实 130D PD 折溢价位置、MA20 动能、40D 摆动高低点与 BOS/MSS/Sweep 结构事件。
4. 纯板块视角：严禁个股买卖指导，聚焦大盘 Market Regime 与核心板块 Sector Regime。
5. 图文并茂：推送交互式卡片 + 白底商务科技风战术海报。
"""

import os
import sys
import time
import json
import logging
import argparse
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional, Tuple
import requests
from dotenv import load_dotenv

# 确保项目根目录在 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.services.visual_card_generator import generate_tactical_poster
from src.services.poster_sender import send_poster_to_feishu, send_markdown_card_to_feishu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
logger = logging.getLogger("ICTSectorReporter")

CST_TZ = datetime.timezone(datetime.timedelta(hours=8))

# 监控的指数与核心板块代码映射（腾讯日K与实时行情源）
INDEX_LIST = [
    {"code": "sh000001", "name": "上证指数"},
    {"code": "sh000300", "name": "沪深300"},
    {"code": "sz399006", "name": "创业板指"},
    {"code": "sh000688", "name": "科创50"},
]

SECTOR_LIST = [
    {"code": "sh000993", "name": "PCB/算力硬件", "source": "全指信息"},
    {"code": "sh000994", "name": "光模块/CPO", "source": "全指通信"},
    {"code": "sh000685", "name": "芯片/半导体", "source": "科创芯片"},
    {"code": "sz399989", "name": "创新药/医疗", "source": "中证医疗"},
    {"code": "sh000928", "name": "能源/电力", "source": "中证能源"},
    {"code": "sz399971", "name": "有色金属", "source": "中证有色"},
    {"code": "sz399975", "name": "券商保险", "source": "证券公司"},
    {"code": "sz399973", "name": "船舶/军工", "source": "中证国防"},
    {"code": "sz399987", "name": "食品饮料", "source": "中证酒"},
    {"code": "sh000932", "name": "大消费/农产", "source": "中证消费"},
]


def wait_until_target_cst(max_wait_seconds: int = 1200) -> datetime.datetime:
    """
    若由 GitHub Actions 提前触发（如 09:05 启动以抵消排队延迟），
    自动等待至北京时间 09:20:00 或 14:50:00 再拉取最新行情并推送。
    """
    now = datetime.datetime.now(CST_TZ)
    target = None
    if 8 <= now.hour < 10:
        target = now.replace(hour=9, minute=20, second=0, microsecond=0)
    elif 13 <= now.hour < 15:
        target = now.replace(hour=14, minute=50, second=0, microsecond=0)

    if target and now < target:
        wait_sec = (target - now).total_seconds()
        if 0 < wait_sec <= max_wait_seconds:
            logger.info(
                "⏳ 当前北京时间 %s，距离目标推送时间 %s 还有 %.0f 秒，正在精准等待对齐...",
                now.strftime("%H:%M:%S"),
                target.strftime("%H:%M:%S"),
                wait_sec,
            )
            time.sleep(wait_sec)
            now = datetime.datetime.now(CST_TZ)
            logger.info("⏰ 已精准到达目标推送时间: %s", now.strftime("%Y-%m-%d %H:%M:%S"))
    return now


def _fetch_kline_130d(symbol: str) -> List[List[str]]:
    """从腾讯接口获取最近 130 根日线 K 线数据"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,130,qfq"
    resp = requests.get(url, timeout=8)
    data = resp.json().get("data", {}).get(symbol, {})
    bars = data.get("day") or data.get("qfqday") or []
    return bars


def _analyze_ict_bars(bars: List[List[str]]) -> Dict[str, Any]:
    """
    基于 130D 日线 K 线计算真实 ICT 结构指标：
    - 130D 最高/最低与 PD 折溢价百分比 (Discount / Premium)
    - MA20 均线位置与 ATR20 波动率
    - 40D 结构窗口内的摆动高低点突破 (BOS/MSS CONFIRMED vs SWEEP)
    """
    if not bars or len(bars) < 25:
        return {}

    parsed = []
    for b in bars:
        if len(b) < 5:
            continue
        parsed.append({
            "date": b[0],
            "open": float(b[1]),
            "close": float(b[2]),
            "high": float(b[3]),
            "low": float(b[4]),
        })

    latest = parsed[-1]
    prev = parsed[-2]
    curr_close = latest["close"]
    chg_pct = ((curr_close - prev["close"]) / prev["close"] * 100.0) if prev["close"] else 0.0

    # 1. 130D Range & PD Location
    high_130 = max(x["high"] for x in parsed)
    low_130 = min(x["low"] for x in parsed)
    pd_pct = ((curr_close - low_130) / (high_130 - low_130) * 100.0) if high_130 > low_130 else 50.0
    pd_pct = max(0.0, min(100.0, pd_pct))
    is_discount = pd_pct < 50.0
    pd_cn = f"{pd_pct:.1f}% {'折价' if is_discount else '溢价'}"
    pd_en = f"PD {pd_pct:.1f}% {'Discount' if is_discount else 'Premium'} ({curr_close:.2f})"

    # 2. MA20 & Momentum
    ma20 = sum(x["close"] for x in parsed[-20:]) / 20.0
    above_ma20 = curr_close >= ma20
    ma_desc = "MA20 上方 · 偏强" if above_ma20 else "MA20 下方 · 承压"

    # 3. 40D Structure Window: Swing Highs & Swing Lows
    win_40 = parsed[-42:-2] if len(parsed) >= 42 else parsed[:-2]
    swing_highs = []
    swing_lows = []
    for i in range(2, len(win_40) - 2):
        h = win_40[i]["high"]
        l = win_40[i]["low"]
        if h >= max(win_40[i - 2]["high"], win_40[i - 1]["high"], win_40[i + 1]["high"], win_40[i + 2]["high"]):
            swing_highs.append(win_40[i])
        if l <= min(win_40[i - 2]["low"], win_40[i - 1]["low"], win_40[i + 1]["low"], win_40[i + 2]["low"]):
            swing_lows.append(win_40[i])

    ref_high = swing_highs[-1] if swing_highs else max(win_40, key=lambda x: x["high"])
    ref_low = swing_lows[-1] if swing_lows else min(win_40, key=lambda x: x["low"])

    recent_5 = parsed[-6:]
    max_recent_high = max(x["high"] for x in recent_5)
    min_recent_low = min(x["low"] for x in recent_5)

    # 判断突破确认 (CONFIRMED) 或 假突破扫流动性 (SWEEP)
    sh_date = ref_high["date"][5:]  # MM-DD
    sl_date = ref_low["date"][5:]   # MM-DD

    if curr_close > ref_high["high"]:
        regime = "Bullish"
        event = f"MSS↑ CONFIRMED @{latest['date'][5:]}"
        advice = "顺势跟随 设防" if pd_pct < 70 else "溢价勿追 移动止盈"
    elif curr_close < ref_low["low"]:
        regime = "Bearish"
        event = f"BOS↓ CONFIRMED @{latest['date'][5:]}"
        advice = "严守防守位 减仓"
    elif min_recent_low < ref_low["low"] and curr_close >= ref_low["low"]:
        regime = "Neutral"
        event = f"BOS↓ SWEEP @{sl_date} 假破回抽"
        advice = "折价观察 等确认" if is_discount else "区间震荡 观望"
    elif max_recent_high > ref_high["high"] and curr_close <= ref_high["high"]:
        regime = "Neutral"
        event = f"MSS↑ FAILED @{sh_date} 冲高回落"
        advice = "逢高防守 勿追"
    else:
        if above_ma20 and chg_pct > 0.3:
            regime = "Bullish" if pd_pct < 75 else "Neutral"
            event = f"MA20上方延续 (前高@{sh_date})"
            advice = "顺势持有 设防"
        elif not above_ma20 and curr_close < (ref_high["high"] + ref_low["low"]) / 2:
            regime = "Bearish"
            event = f"Bear MSS 延续 (受制@{sh_date})"
            advice = "防守观望 勿抄底"
        else:
            regime = "Neutral"
            event = f"区间缩量整理 (支撑@{sl_date})"
            advice = "折价区观察 勿追" if is_discount else "多看少动 观望"

    sign = "+" if chg_pct > 0 else ""
    return {
        "price": f"{curr_close:.2f}",
        "change": f"{sign}{chg_pct:.2f}%",
        "change_val": chg_pct,
        "trend": regime,
        "regime": regime,
        "evidence": event,
        "event": event,
        "momentum": ma_desc,
        "pd": pd_cn,
        "pd_pct": pd_pct,
        "location": pd_en,
        "advice": advice,
        "latest_date": latest["date"],
    }


def fetch_and_compute_ict_data() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """并行拉取所有指数与板块的 130D K 线并计算实时 ICT 结构表"""
    all_items = INDEX_LIST + SECTOR_LIST
    codes = [item["code"] for item in all_items]

    raw_bars: Dict[str, List[List[str]]] = {}
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_fetch_kline_130d, c): c for c in codes}
            for fut in futures:
                c = futures[fut]
                try:
                    raw_bars[c] = fut.result()
                except Exception as e:
                    logger.warning("拉取 %s 日K失败: %s", c, e)
    except Exception as e:
        logger.warning("并行拉取日K异常: %s", e)

    indices_res = []
    sectors_res = []
    data_date = datetime.datetime.now(CST_TZ).strftime("%Y-%m-%d")

    for idx_meta in INDEX_LIST:
        c = idx_meta["code"]
        metrics = _analyze_ict_bars(raw_bars.get(c, []))
        if metrics:
            data_date = metrics.get("latest_date", data_date)
            indices_res.append({
                "name": idx_meta["name"],
                "code": c,
                **metrics,
            })

    for sec_meta in SECTOR_LIST:
        c = sec_meta["code"]
        metrics = _analyze_ict_bars(raw_bars.get(c, []))
        if metrics:
            sectors_res.append({
                "name": sec_meta["name"],
                "code": c,
                "source": sec_meta["source"],
                **metrics,
            })

    return indices_res, sectors_res, data_date


def build_ict_markdown_report(
    period_title: str,
    now_str: str,
    data_date: str,
    indices: List[Dict[str, Any]],
    sectors: List[Dict[str, Any]],
) -> Tuple[str, str, str, str]:
    """生成手机端高信噪比 ICT 板块结构日报"""
    bull_cnt = sum(1 for s in sectors if s["regime"] == "Bullish")
    neut_cnt = sum(1 for s in sectors if s["regime"] == "Neutral")
    bear_cnt = sum(1 for s in sectors if s["regime"] == "Bearish")

    idx_trends = [i["trend"] for i in indices[:2]]
    if all(t == "Bearish" for t in idx_trends):
        overall_regime = "Bearish"
    elif all(t == "Bullish" for t in idx_trends):
        overall_regime = "Bullish"
    else:
        overall_regime = "Neutral"

    sh_idx = indices[0] if indices else {"name": "上证指数", "evidence": "-", "momentum": "-", "price": "-"}
    hs_idx = indices[1] if len(indices) > 1 else {"name": "沪深300", "evidence": "-", "momentum": "-", "price": "-"}

    regime_desc = (
        f"上证({sh_idx['price']}) {sh_idx['evidence']}，沪深300({hs_idx['price']}) {hs_idx['evidence']}；"
        f"{sh_idx['momentum']}"
    )

    bull_sectors = [s["name"] for s in sectors if s["regime"] == "Bullish"]
    disc_sectors = [s["name"] for s in sectors if s.get("pd_pct", 50) < 30 and s["regime"] != "Bearish"]

    if "早盘" in period_title:
        wait_condition = (
            f"早盘准入：优先关注折价区企稳板块（{('、'.join(disc_sectors[:3])) or '暂无'}）回踩结构位机会；"
            f"强势板块（{('、'.join(bull_sectors[:2])) or '暂无'}）不追溢价高开。"
        )
    else:
        wait_condition = (
            f"尾盘确认：14:50 检视收盘价是否有效确认结构突破；"
            f"破位偏空板块坚决执行减仓防守，溢价区（>60%）收长上影线锁定利润。"
        )

    badge_map = {"Bullish": "🟢 Bullish", "Neutral": "🟡 Neutral", "Bearish": "🔴 Bearish"}

    idx_rows = []
    for i in indices:
        b = badge_map.get(i["trend"], i["trend"])
        idx_rows.append(
            f"| **{i['name']}** | {b} ({i['change']}) | {i['evidence']} | {i['momentum']} | {i['pd']} ({i['price']}) |"
        )
    idx_table = "\n".join(idx_rows)

    sec_rows = []
    for s in sectors:
        b = badge_map.get(s["regime"], s["regime"])
        sec_rows.append(
            f"| **{s['name']}** | {b} ({s['change']}) | {s['pd']} | {s['event']} | {s['advice']} |"
        )
    sec_table = "\n".join(sec_rows)

    report = f"""# 🧭 ICT 板块结构机会日报
**【{period_title}】**
行情日期：{data_date} ｜ 推送时间：{now_str} (北京时间) ｜ 周期：日线 (HTF 130D / 40D)

### 1. 📌 今日核心结论
- **市场环境**: Market Regime = **{overall_regime}**（{regime_desc}）
- **板块结构分布**: 🟢 Bullish **{bull_cnt}** 个 ｜ 🟡 Neutral **{neut_cnt}** 个 ｜ 🔴 Bearish **{bear_cnt}** 个
- **核心行动条件**: {wait_condition}

### 2. 🌡️ Market Regime（指数结构化判定）
| 指数 | 趋势 (当日) | 结构证据 (40D) | 均线动能 | 130D PD位置 |
| :--- | :--- | :--- | :--- | :--- |
{idx_table}

### 3. 🧭 Sector Regime（核心板块多空表 · 纯板块指导）
| 板块 | 评级 (当日) | 130D PD区间 | 关键结构事件 | 战术建议 |
| :--- | :--- | :--- | :--- | :--- |
{sec_table}

### 4. 🛡️ 操盘战术护栏
1. **折价区准入**: 仅在 Discount (<35%) 且出现 MSS↑/Sweep 收盘确认时布局，严禁在 Bearish 破位期左侧盲目猜底；
2. **溢价区防守**: 处于 Premium (>60%) 的板块严禁追高，持仓以移动止盈线保护浮盈；
3. **收盘价确认**: 盘中假突破极多，早盘 09:20 看准入位置，尾盘 14:50 以临近收盘价确认最终去留。
"""
    return report, overall_regime, regime_desc, wait_condition


def run_ict_pipeline(
    force_run: bool = False,
    period_arg: Optional[str] = None,
    wait_target: bool = False,
) -> bool:
    """执行完整的 ICT 板块日报生成与双重推送流程"""
    load_dotenv()

    # 1. 交易日检查
    if not force_run:
        try:
            from src.core.trading_calendar import get_open_markets_today
            open_mkts = get_open_markets_today()
            if "cn" not in open_mkts:
                logger.info("⏸️ 今日为A股休市日/非交易日，跳过执行。使用 --force-run 可强制运行。")
                return True
        except Exception as e:
            logger.warning("交易日日历检查出现异常，继续执行: %s", e)

    # 2. 若开启准点对齐（用于抵消 GitHub Actions 排队延迟），等待至 09:20 或 14:50
    if wait_target:
        now_cst = wait_until_target_cst()
    else:
        now_cst = datetime.datetime.now(CST_TZ)

    now_str = now_cst.strftime("%Y-%m-%d %H:%M")
    hour = now_cst.hour

    if period_arg == "morning" or (period_arg is None and hour < 12):
        period_title = "早盘盘前指导 · 结构定调与准入计划 (09:20)"
    else:
        period_title = "尾盘交易指导 · 关键确认与防守执行 (14:50)"

    logger.info("🚀 启动 ICT 板块结构机会日报流水线: %s [%s]", now_str, period_title)

    # 3. 实时拉取 130D K 线并计算真实 ICT 指标
    indices, sectors, data_date = fetch_and_compute_ict_data()

    # 4. 生成极简手机版 Markdown 报告
    markdown_report, overall_regime, regime_desc, wait_condition = build_ict_markdown_report(
        period_title=period_title,
        now_str=now_str,
        data_date=data_date,
        indices=indices,
        sectors=sectors,
    )

    # 保存报告文件
    os.makedirs("reports", exist_ok=True)
    report_filename = f"reports/ict_sector_{now_cst.strftime('%Y%m%d_%H%M')}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    logger.info("📄 报告已保存至: %s", report_filename)

    # 5. 生成白底商务科技风战术海报
    poster_path = "reports/tactical_poster.png"
    generate_tactical_poster(
        output_path=poster_path,
        period_title=period_title,
        report_date=f"{data_date} (推送 {now_cst.strftime('%H:%M')} CST)",
        overall_regime=overall_regime,
        regime_desc=regime_desc,
        wait_condition=wait_condition,
        indices=indices,
        sectors=sectors,
    )

    # 6. 图文并茂推送到飞书
    card_ok = send_markdown_card_to_feishu(
        content=markdown_report,
        title=f"🧭 ICT 板块结构机会日报 ({period_title.split('·')[0].strip()})"
    )
    poster_ok = send_poster_to_feishu(image_path=poster_path)

    logger.info("🏁 ICT 流程执行完毕！卡片推送: %s, 海报推送: %s", card_ok, poster_ok)
    return card_ok and poster_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股 ICT 板块结构机会日报")
    parser.add_argument("--force-run", action="store_true", help="强制运行（跳过交易日检查）")
    parser.add_argument("--wait-target-time", action="store_true", help="若提前启动，精准等待至 09:20 或 14:50 CST 再执行")
    parser.add_argument("--period", choices=["morning", "afternoon", "auto"], default="auto", help="运行周期")
    args = parser.parse_args()

    success = run_ict_pipeline(
        force_run=args.force_run,
        period_arg=None if args.period == "auto" else args.period,
        wait_target=args.wait_target_time,
    )
    sys.exit(0 if success else 1)
