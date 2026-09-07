# -*- coding: utf-8 -*-
"""
生成战术复盘长图并自动推送到飞书聊天
"""

import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
import logging
import requests

from src.services.visual_card_generator import generate_tactical_poster

logger = logging.getLogger(__name__)

def send_poster_to_feishu(
    image_path: str = "reports/tactical_poster.png",
    app_id: str = None,
    app_secret: str = None,
    chat_id: str = None
) -> bool:
    app_id = app_id or os.getenv("FEISHU_APP_ID")
    app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
    chat_id = chat_id or os.getenv("FEISHU_CHAT_ID")

    if not app_id or not app_secret or not chat_id:
        logger.warning("[PosterSender] 缺少飞书凭据 (FEISHU_APP_ID / SECRET / CHAT_ID)，跳过长图推送")
        return False

    if not os.path.exists(image_path):
        logger.warning("[PosterSender] 长图不存在: %s", image_path)
        return False

    try:
        # 1. 获取 token
        auth_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10
        ).json()
        token = auth_res.get("tenant_access_token")
        if not token:
            logger.error("[PosterSender] 获取飞书 tenant_access_token 失败: %s", auth_res)
            return False

        # 2. 上传图片获取 image_key
        with open(image_path, "rb") as f:
            files = {"image": ("tactical_poster.png", f, "image/png")}
            data = {"image_type": "message"}
            upload_res = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data,
                timeout=30
            ).json()

        if upload_res.get("code") != 0:
            logger.error("[PosterSender] 飞书图片上传失败: %s", upload_res)
            return False

        image_key = upload_res["data"]["image_key"]
        logger.info("[PosterSender] 飞书图片上传成功, image_key: %s", image_key)

        # 3. 发送图片消息
        send_res = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "receive_id": chat_id,
                "msg_type": "image",
                "content": json.dumps({"image_key": image_key})
            },
            timeout=15
        ).json()

        if send_res.get("code") == 0:
            logger.info("[PosterSender] ✅ 战术长图已成功推送到飞书群！")
            return True
        else:
            logger.error("[PosterSender] 飞书图片消息发送失败: %s", send_res)
            return False

    except Exception as e:
        logger.exception("[PosterSender] 发送海报异常: %s", e)
        return False

def run_poster_pipeline():
    poster_path = generate_tactical_poster("reports/tactical_poster.png")
    return send_poster_to_feishu(poster_path)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    ok = run_poster_pipeline()
    print("Poster pipeline executed, success:", ok)
