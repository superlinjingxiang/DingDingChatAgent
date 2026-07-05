#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from alibabacloud_dingtalk.robot_1_0.client import Client as DingtalkRobotClient
from alibabacloud_dingtalk.robot_1_0 import models as robot_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    else:
        load_dotenv()


def get_access_token(app_key: str, app_secret: str) -> str:
    response = requests.post(
        "https://api.dingtalk.com/v1.0/oauth2/accessToken",
        headers={"Content-Type": "application/json;charset=utf-8"},
        json={"appKey": app_key, "appSecret": app_secret},
        timeout=20,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"accessToken 请求失败: {response.text}") from exc

    data = response.json()
    token = data.get("accessToken")
    if not token:
        raise RuntimeError(f"accessToken 获取失败: {data}")
    return token


def create_client() -> DingtalkRobotClient:
    config = open_api_models.Config()
    config.protocol = "https"
    config.region_id = "central"
    return DingtalkRobotClient(config)


def send_one_to_one_message(
    robot_code: str,
    access_token: str,
    user_id: str,
    title: str,
    text: str,
) -> dict:
    client = create_client()
    headers = robot_models.BatchSendOTOHeaders()
    headers.x_acs_dingtalk_access_token = access_token
    request = robot_models.BatchSendOTORequest(
        robot_code=robot_code,
        user_ids=[user_id],
        msg_key="sampleMarkdown",
        msg_param=json.dumps(
            {
                "title": title,
                "text": text,
            },
            ensure_ascii=False,
        ),
    )

    try:
        response = client.batch_send_otowith_options(
            request,
            headers,
            util_models.RuntimeOptions(),
        )
    except Exception as err:
        code = getattr(err, "code", "")
        message = getattr(err, "message", "")
        if code or message:
            raise RuntimeError(f"消息发送失败: {code} {message}") from err
        raise

    return response.to_map() if hasattr(response, "to_map") else {"ok": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a DingTalk OTO test message.")
    parser.add_argument(
        "--robot-code",
        default=os.getenv("DINGDING_ROBOT_CODE") or os.getenv("DINGDING_ID"),
        help="机器人 robotCode，通常就是 AppKey。",
    )
    parser.add_argument(
        "--userid",
        default=os.getenv("DINGDING_TARGET_USERID"),
        help="接收消息的 userId。",
    )
    parser.add_argument(
        "--title",
        default="钉钉测试消息",
        help="消息标题",
    )
    parser.add_argument(
        "--text",
        default="这是一条来自 Python 脚本的测试消息。",
        help="消息正文",
    )
    return parser


def main() -> int:
    load_env()
    parser = build_parser()
    args = parser.parse_args()

    app_key = os.getenv("DINGDING_ID")
    app_secret = os.getenv("DINGDING_SECRET")
    if not app_key or not app_secret:
        print("缺少 DINGDING_ID 或 DINGDING_SECRET")
        return 2
    if not args.robot_code:
        print("缺少 robotCode，请设置 DINGDING_ROBOT_CODE")
        return 2
    if not args.userid:
        print("缺少 userId，请设置 DINGDING_TARGET_USERID 或传 --userid")
        return 2

    try:
        access_token = get_access_token(app_key, app_secret)
        result = send_one_to_one_message(
            robot_code=args.robot_code,
            access_token=access_token,
            user_id=args.userid,
            title=args.title,
            text=args.text,
        )
    except Exception as exc:
        print(str(exc))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("消息发送请求已提交。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
