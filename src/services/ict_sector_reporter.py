# -*- coding: utf-8 -*-
"""
A股 & 港股 ICT 板块结构机会日报系统 (手机端纯文本极简 · 09:20 盘前 & 14:50 尾盘)
核心设计：
1. 交易日调度：仅在中国 A 股交易日执行，早 09:20 发盘前指导，下午 14:50 发尾盘交易指导。
2. 精准时间对齐与时效护栏：
   - 提前启动时自动精准等待至北京时间 09:20:00 或 14:50:00 再拉取最新行情并推送；
   - 严格窗口拦截（早盘仅限 09:15~09:40，尾盘仅限 14:45~15:10），若遇云端超时严重延迟自动拦截，杜绝在错误时间推送。
3. 纯文本交互式卡片：按用户要求剔除图片海报，仅发送高信噪比纯文本卡片，手机一屏秒览。
4. 真实 ICT 结构计算：实时拉取 130D 日 K 线，计算真实 PD 折溢价位置、MA20 动能、40D 摆动高低点与 BOS/MSS/Sweep 结构事件。
5. 纯板块视角：严禁个股买卖指导，聚焦大盘 Market Regime 与核心板块 Sector Regime。
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

def send_markdown_card_to_feishu(
    content: str,
    title: str = "ICT 板块结构机会日报",
    app_id: str = None,
    app_secret: str = None,
    chat_id: str = None
) -> bool:
    """发送纯文本交互式卡片消息到飞书群"""
    app_id = app_id or os.getenv("FEISHU_APP_ID")
    app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
    chat_id = chat_id or os.getenv("FEISHU_CHAT_ID")

    if not app_id or not app_secret or not chat_id:
        logger.warning("[FeishuSender] 缺少飞书凭据，跳过卡片推送")
        return False

    try:
        auth_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10
        ).json()
        token = auth_res.get("tenant_access_token")
        if not token:
            logger.error("[FeishuSender] 获取飞书 tenant_access_token 失败: %s", auth_res)
            return False

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content}
                }
            ]
        }

        send_res = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False)
            },
            timeout=15
        ).json()

        if send_res.get("code") == 0:
            logger.info("✅ 飞书纯文本交互式卡片已成功推送！")
            return True
        else:
            logger.error("飞书卡片消息发送失败: %s", send_res)
            return False
    except Exception as e:
        logger.exception("发送卡片异常: %s", e)
        return False

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


def check_and_align_trading_time(
    force_run: bool = False,
    period_arg: Optional[str] = None
) -> Tuple[bool, datetime.datetime, str]:
    """
    时间时效性校验与秒级对齐：
    1. 早盘 09:20：开盘前定调与准入计划
    2. 尾盘 14:45：抓取 14:44 快照，为 14:50 尾盘交易决策预留 5 分钟核对仓位与下单
    3. 盘后 15:20：全天收盘确认，推演明日早盘策略
    """
    now = datetime.datetime.now(CST_TZ)
    current_minutes = now.hour * 60 + now.minute

    target_morning = 9 * 60 + 20       # 09:20 (560)
    target_pre_close = 14 * 60 + 45    # 14:45 (885)
    target_post_market = 15 * 60 + 20  # 15:20 (920)

    if period_arg == "morning":
        period_title = "早盘盘前指导 · 结构定调与准入计划 (09:20)"
        target_m = target_morning
    elif period_arg in ["pre_close", "afternoon"]:
        period_title = "尾盘决策预警 · 交易信号与仓位核对 (14:45)"
        target_m = target_pre_close
    elif period_arg == "post_market":
        period_title = "盘后复盘总结 · 收盘确认与明日策略 (15:20)"
        target_m = target_post_market
    else:
        # 自动判定
        if current_minutes < 12 * 60:
            period_title = "早盘盘前指导 · 结构定调与准入计划 (09:20)"
            target_m = target_morning
        elif 12 * 60 <= current_minutes < 15 * 60:
            period_title = "尾盘决策预警 · 交易信号与仓位核对 (14:45)"
            target_m = target_pre_close
        else:
            period_title = "盘后复盘总结 · 收盘确认与明日策略 (15:20)"
            target_m = target_post_market

    if not force_run:
        # 1. 如果提前到达（提前 1~30 分钟启动），进行精准等待对齐
        diff = target_m - current_minutes
        if 0 < diff <= 30:
            target_time = now.replace(hour=target_m // 60, minute=target_m % 60, second=0, microsecond=0)
            wait_sec = (target_time - now).total_seconds()
            if wait_sec > 0:
                logger.info(
                    "⏳ 当前北京时间 %s，已提前启动，正在精准等待 %.0f 秒对齐至 %s 整点推送...",
                    now.strftime("%H:%M:%S"),
                    wait_sec,
                    target_time.strftime("%H:%M:%S")
                )
                time.sleep(wait_sec)
                now = datetime.datetime.now(CST_TZ)
                current_minutes = now.hour * 60 + now.minute

        # 2. 校验是否在有效交易窗口内
        # 早盘: 09:15~09:35；尾盘决策: 14:40~14:58；盘后复盘: 15:15~15:45
        valid_morning = (9 * 60 + 15 <= current_minutes <= 9 * 60 + 35)
        valid_pre_close = (14 * 60 + 40 <= current_minutes <= 14 * 60 + 58)
        valid_post_market = (15 * 60 + 15 <= current_minutes <= 15 * 60 + 45)

        is_valid = (
            (target_m == target_morning and valid_morning) or
            (target_m == target_pre_close and valid_pre_close) or
            (target_m == target_post_market and valid_post_market)
        )
        if not is_valid:
            logger.warning(
                "⏸️ 当前北京时间 %s 不在有效推送窗口 (早盘: 09:15~09:35, 尾盘: 14:40~14:58, 盘后: 15:15~15:45)。"
                "检测到此任务为延迟严重的陈旧调度，已安全拦截跳过，杜绝错误时间推送！",
                now.strftime("%H:%M:%S")
            )
            return False, now, period_title

    return True, now, period_title


def _fetch_kline_130d(symbol: str) -> List[List[str]]:
    """从腾讯接口获取最近 130 根日线 K 线数据"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,130,qfq"
    resp = requests.get(url, timeout=8)
    data = resp.json().get("data", {}).get(symbol, {})
    bars = data.get("day") or data.get("qfqday") or []
    return bars


def _analyze_ict_bars(bars: List[List[str]]) -> Dict[str, Any]:
    """
    基于 130D 日线 K 线与成交量计算真实 ICT 结构指标：
    - 130D 最高/最低与分位值 (折价区 <35% / 平衡区 35~65% / 溢价区 >65%)
    - MA20 均线位置与动能状态
    - 20日均量与量比计算，硬性过滤 MSS↑ 突破（成交额/量需大于20日均量 或 量比>1.2，否则降级为弱势待确认）
    - 40D 结构窗口内的摆动高低点突破 (BOS/MSS CONFIRMED vs SWEEP)
    """
    if not bars or len(bars) < 25:
        return {}

    parsed = []
    for b in bars:
        if len(b) < 5:
            continue
        vol = float(b[5]) if len(b) > 5 and b[5] else 0.0
        parsed.append({
            "date": b[0],
            "open": float(b[1]),
            "close": float(b[2]),
            "high": float(b[3]),
            "low": float(b[4]),
            "volume": vol,
        })

    latest = parsed[-1]
    prev = parsed[-2]
    curr_close = latest["close"]
    chg_pct = ((curr_close - prev["close"]) / prev["close"] * 100.0) if prev["close"] else 0.0

    # 1. 130D Range & 统一分位值文案（消除语义歧义）
    high_130 = max(x["high"] for x in parsed)
    low_130 = min(x["low"] for x in parsed)
    pd_pct = ((curr_close - low_130) / (high_130 - low_130) * 100.0) if high_130 > low_130 else 50.0
    pd_pct = max(0.0, min(100.0, pd_pct))

    if pd_pct < 35.0:
        pd_zone = "折价区"
    elif pd_pct > 65.0:
        pd_zone = "溢价区"
    else:
        pd_zone = "平衡区"

    pd_quantile_str = f"130D 分位值: {pd_pct:.1f}% ({pd_zone})"

    # 2. MA20 & Momentum
    ma20 = sum(x["close"] for x in parsed[-20:]) / 20.0
    above_ma20 = curr_close >= ma20
    ma_desc = "MA20 上方 · 偏强" if above_ma20 else "MA20 下方 · 承压"

    # 3. 20日均量与量比因子 (硬性过滤电风扇行情假突破)
    hist_bars = parsed[:-1]
    prior_20_bars = hist_bars[-20:] if len(hist_bars) >= 20 else hist_bars
    ma20_vol = (sum(x["volume"] for x in prior_20_bars) / len(prior_20_bars)) if prior_20_bars else 1.0
    latest_vol = latest["volume"]
    vol_ratio = (latest_vol / ma20_vol) if ma20_vol > 0 else 1.0
    # 放量硬性条件：当日成交量/成交额 > 20日均量 或 量比 > 1.2
    is_volume_confirmed = (latest_vol >= ma20_vol) or (vol_ratio >= 1.2)

    # 4. 40D Structure Window: Swing Highs & Swing Lows
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

    sh_date = ref_high["date"][5:]  # MM-DD
    sl_date = ref_low["date"][5:]   # MM-DD

    # 多头结构反转硬性量能过滤
    if curr_close > ref_high["high"]:
        if is_volume_confirmed:
            regime = "Bullish"
            event = f"MSS↑ CONFIRMED (放量/量比{vol_ratio:.1f} @{latest['date'][5:]})"
            advice = "顺势跟随 · 设移动防守" if pd_pct < 65.0 else "溢价放量 · 谨防冲高回落"
        else:
            # 缩量电风扇行情：硬性降级为弱势待确认
            regime = "Neutral"
            event = f"MSS↑ 弱势待确认 (缩量/量比{vol_ratio:.1f} @{latest['date'][5:]})"
            advice = "缩量防假突破 · 暂不追高"
    elif curr_close < ref_low["low"]:
        regime = "Bearish"
        event = f"BOS↓ CONFIRMED @{latest['date'][5:]}"
        advice = "严守防守位 · 破位减仓"
    elif min_recent_low < ref_low["low"] and curr_close >= ref_low["low"]:
        regime = "Neutral"
        event = f"BOS↓ SWEEP @{sl_date} 假破回抽"
        advice = "折价观察 · 等放量确认" if pd_zone == "折价区" else "区间震荡 · 保持观望"
    elif max_recent_high > ref_high["high"] and curr_close <= ref_high["high"]:
        regime = "Neutral"
        event = f"MSS↑ FAILED @{sh_date} 冲高回落"
        advice = "逢高防守 · 勿追"
    else:
        if above_ma20 and chg_pct > 0.3:
            regime = "Bullish" if pd_pct < 75.0 else "Neutral"
            event = f"MA20上方延续 (前高@{sh_date})"
            advice = "顺势持有 · 紧随防守"
        elif not above_ma20 and curr_close < (ref_high["high"] + ref_low["low"]) / 2:
            regime = "Bearish"
            event = f"Bear MSS 延续 (受制@{sh_date})"
            advice = "防守观望 · 勿盲目猜底"
        else:
            regime = "Neutral"
            event = f"区间整理 (支撑@{sl_date})"
            advice = "折价区观察 · 勿追" if pd_zone == "折价区" else "多看少动 · 观望"

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
        "pd": pd_quantile_str,
        "pd_pct": pd_pct,
        "pd_zone": pd_zone,
        "vol_ratio": vol_ratio,
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
) -> str:
    """生成手机端极简纯文本 ICT 板块结构机会日报（文本对齐列表与结构化卡片，彻底避免表格乱码）"""
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

    sh_idx = indices[0] if indices else {"name": "上证指数", "evidence": "-", "momentum": "-", "price": "-", "change": "0.00%", "pd": "130D 分位值: 50.0% (平衡区)"}
    hs_idx = indices[1] if len(indices) > 1 else {"name": "沪深300", "evidence": "-", "momentum": "-", "price": "-", "change": "0.00%", "pd": "130D 分位值: 50.0% (平衡区)"}

    regime_desc = (
        f"上证({sh_idx['price']}) {sh_idx['evidence']}，沪深300({hs_idx['price']}) {hs_idx['evidence']}；"
        f"{sh_idx['momentum']}"
    )

    bull_sectors = [s["name"] for s in sectors if s["regime"] == "Bullish"]
    disc_sectors = [s["name"] for s in sectors if s.get("pd_zone") == "折价区" and s["regime"] != "Bearish"]

    if "早盘" in period_title:
        wait_condition = (
            f"**早盘准入**：优先关注 130D 折价区（<35%）企稳板块（{('、'.join(disc_sectors[:3])) or '暂无'}）次回踩结构位机会；"
            f"强势板块（{('、'.join(bull_sectors[:2])) or '暂无'}）切勿盲目追高开。"
        )
    elif "尾盘" in period_title or "14:45" in period_title:
        wait_condition = (
            f"**尾盘决策（14:45 预警）**：距 14:50 仅剩 5 分钟，请立即核对仓位！"
            f"破位偏空板块坚决执行减仓防守；放量突破板块核对入场条件；处于 130D 溢价区（>65%）冲高回落标的锁定浮盈。"
        )
    else:
        # 盘后复盘 (15:20)
        wait_condition = (
            f"**今日收盘已确认，明日早盘策略如下**：全天结构已定型。"
            f"放量反转确认板块（{('、'.join(bull_sectors[:3])) or '暂无'}）列入明日早盘重点观察清单，等次回踩确认；"
            f"破位及 130D 溢价区（>65%）承压板块坚决规避次日补跌风险。"
        )

    badge_map = {"Bullish": "🟢 多头", "Neutral": "🟡 震荡", "Bearish": "🔴 空头"}

    # 1. 大盘指数对齐条目列表（免 markdown table 源码裸露）
    idx_list = []
    for i in indices:
        b = badge_map.get(i["trend"], i["trend"])
        idx_list.append(
            f"• **{i['name']}** ({i['price']}, {i['change']}) {b}\n"
            f"  └ 结构: {i['evidence']} ｜ 动能: {i['momentum']} ｜ {i['pd']}"
        )
    idx_formatted = "\n".join(idx_list)

    # 2. 板块按多空状态分类结构化列表
    bull_items = [s for s in sectors if s["regime"] == "Bullish"]
    neut_items = [s for s in sectors if s["regime"] == "Neutral"]
    bear_items = [s for s in sectors if s["regime"] == "Bearish"]

    sec_blocks = []
    if bull_items:
        lines = [f"🟢 **多头趋势板块 ({len(bull_items)})**:"]
        for s in bull_items:
            lines.append(
                f"• **{s['name']}** ({s['change']})\n"
                f"  ├ 结构: {s['event']} ｜ {s['pd']}\n"
                f"  └ 战术: {s['advice']}"
            )
        sec_blocks.append("\n".join(lines))

    if neut_items:
        lines = [f"🟡 **震荡/观察板块 ({len(neut_items)})**:"]
        for s in neut_items:
            lines.append(
                f"• **{s['name']}** ({s['change']})\n"
                f"  ├ 结构: {s['event']} ｜ {s['pd']}\n"
                f"  └ 战术: {s['advice']}"
            )
        sec_blocks.append("\n".join(lines))

    if bear_items:
        lines = [f"🔴 **空头/承压板块 ({len(bear_items)})**:"]
        for s in bear_items:
            lines.append(
                f"• **{s['name']}** ({s['change']})\n"
                f"  ├ 结构: {s['event']} ｜ {s['pd']}\n"
                f"  └ 战术: {s['advice']}"
            )
        sec_blocks.append("\n".join(lines))

    sec_formatted = "\n\n".join(sec_blocks)

    report = f"""# 🧭 ICT 板块结构机会日报
**【{period_title}】**
📅 行情日期：{data_date} ｜ ⏰ 推送时间：{now_str} (北京时间) ｜ 周期：日线 (130D/40D)

### 1. 📌 核心结论与时效决策
- **市场定调**: Market Regime = **{overall_regime}** ({regime_desc})
- **板块多空分布**: 🟢 多头 **{bull_cnt}** ｜ 🟡 震荡 **{neut_cnt}** ｜ 🔴 空头 **{bear_cnt}**
- **核心操作条件**: {wait_condition}

### 2. 🌡️ Market Regime（大盘指数结构判定）
{idx_formatted}

### 3. 🧭 Sector Regime（核心板块多空状态）
{sec_formatted}

### 4. 🛡️ 操盘战术护栏
1. **分位值区间准入**:
   - 🟢 **折价区 (<35%)**: 仅在放量 MSS↑ 或 Sweep 假破收盘回抽时右侧建仓，严禁在破位期盲目猜底；
   - 🟡 **平衡区 (35%~65%)**: 区间震荡对待，高抛低吸严格控制单笔仓位；
   - 🔴 **溢价区 (>65%)**: 严禁追高，持仓个股紧随移动止盈线，收长上影线或滞涨放量立即保护利润。
2. **量能硬性过滤**:
   - 板块 MSS↑ 突破必须伴随放量（成交额/量需大于 20日均量 或 量比 > 1.2），无量突破一律按“弱势待确认”防守，规避电风扇行情诱多。
3. **分时三维执行**:
   - 早盘 09:20 定准入基调；尾盘 14:45 抓取快照预留 5 分钟核对仓位并执行；盘后 15:20 确认终局推演次日策略。
"""
    return report


def run_ict_pipeline(
    force_run: bool = False,
    period_arg: Optional[str] = None,
) -> bool:
    """执行纯文本 ICT 板块日报生成与飞书卡片推送流程"""
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

    # 2. 准点对齐与时效性合法窗口检查
    should_run, now_cst, period_title = check_and_align_trading_time(
        force_run=force_run,
        period_arg=period_arg
    )
    if not should_run:
        return True

    now_str = now_cst.strftime("%Y-%m-%d %H:%M")
    logger.info("🚀 启动 ICT 板块结构机会日报流水线: %s [%s]", now_str, period_title)

    # 3. 实时拉取 130D K 线并计算真实 ICT 指标
    indices, sectors, data_date = fetch_and_compute_ict_data()

    # 4. 生成极简手机版纯文本 Markdown 报告（无图片）
    markdown_report = build_ict_markdown_report(
        period_title=period_title,
        now_str=now_str,
        data_date=data_date,
        indices=indices,
        sectors=sectors,
    )

    # 5. 保存报告文件
    os.makedirs("reports", exist_ok=True)
    report_filename = f"reports/ict_sector_{now_cst.strftime('%Y%m%d_%H%M')}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    logger.info("📄 报告已保存至: %s", report_filename)

    # 6. 推送纯文本交互式卡片到飞书（用户要求不需要图片，仅发送文本卡片）
    card_ok = send_markdown_card_to_feishu(
        content=markdown_report,
        title=f"🧭 ICT 板块结构机会日报 ({period_title.split('·')[0].strip()})"
    )

    logger.info("🏁 ICT 纯文本日报推送完毕！推送状态: %s", card_ok)
    return card_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股 ICT 板块结构机会日报")
    parser.add_argument("--force-run", action="store_true", help="强制运行（跳过交易日与时间窗口检查）")
    parser.add_argument("--period", choices=["morning", "pre_close", "post_market", "afternoon", "auto"], default="auto", help="运行周期")
    parser.add_argument("--wait-target-time", action="store_true", help="启用目标时间精准对齐等待")
    args = parser.parse_args()

    success = run_ict_pipeline(
        force_run=args.force_run,
        period_arg=None if args.period == "auto" else args.period,
    )
    sys.exit(0 if success else 1)
