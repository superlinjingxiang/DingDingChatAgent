#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
REDIS_DIR = PROJECT_ROOT / "redis-stack" / "Redis-8.8.0-Windows-x64-msys2"
REDIS_SERVER = REDIS_DIR / "redis-server.exe"
REDIS_CONF = REDIS_DIR / "redis.conf"
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("USER_AGENT", "dingtalk-langchain")


def ensure_project_root_on_path() -> None:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Project quick start entry for DingTalk LangChain."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="检查环境和关键模块是否可导入")
    subparsers.add_parser("all", help="同时启动知识库服务和钉钉机器人")

    agent_parser = subparsers.add_parser("agent", help="运行一次 Agent 对话")
    agent_parser.add_argument("prompt", nargs="?", help="用户输入")

    subparsers.add_parser("server", help="启动 FastAPI 文档服务")
    subparsers.add_parser("ding", help="启动钉钉 Stream 机器人")
    ding_send_parser = subparsers.add_parser("ding-send", help="给指定用户发送一条钉钉测试消息")
    ding_send_parser.add_argument(
        "--robot-code",
        help="机器人 robotCode，别把 AppKey 直接当成这个值",
    )
    ding_send_parser.add_argument("--userid", help="接收消息的 userId")
    ding_send_parser.add_argument("--title", default="钉钉测试消息", help="消息标题")
    ding_send_parser.add_argument(
        "--text",
        default="这是一条来自 Python 脚本的测试消息。",
        help="消息正文",
    )

    return parser


def cmd_doctor() -> int:
    from importlib import import_module

    checks = [
        ("src.Agents", "AgentClass"),
        ("src.Server", "app"),
        ("src.DingWebHook", "main"),
    ]
    results = []
    for module_name, attr in checks:
        try:
            module = import_module(module_name)
            ok = hasattr(module, attr)
            results.append(
                {
                    "module": module_name,
                    "status": "ok" if ok else "missing-attr",
                    "attribute": attr,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "module": module_name,
                    "status": "error",
                    "error": str(exc),
                }
            )

    env_keys = [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_API_BASE",
        "EMBEDDING_API_KEY",
        "EMBEDDING_API_BASE",
        "EMBEDDING_COLLECTION",
        "PERSIST_DIR",
        "DINGDING_ID",
        "DINGDING_SECRET",
        "DINGDING_UNION_ID",
    ]
    env_status = {key: bool(os.getenv(key)) for key in env_keys}

    print(
        json.dumps(
            {
                "env": env_status,
                "optional_env": {
                    "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/0")
                },
                "modules": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_agent(prompt: str | None) -> int:
    if not prompt:
        print("请提供 prompt，例如：python main.py agent \"你好\"")
        return 2

    from src.Agents import AgentClass

    response = AgentClass().run_agent(prompt)
    print(json.dumps(response, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_server() -> int:
    _free_port(SERVER_PORT, "server")
    from src.Server import main as server_main

    server_main()
    return 0


def cmd_ding() -> int:
    from src.DingWebHook import main as ding_main

    ding_main()
    return 0


def cmd_ding_send(
    robot_code: str | None,
    user_id: str | None,
    title: str,
    text: str,
) -> int:
    from ding_send_test import send_one_to_one_message

    app_key = os.getenv("DINGDING_ID")
    app_secret = os.getenv("DINGDING_SECRET")
    if not app_key or not app_secret:
        print("缺少 DINGDING_ID 或 DINGDING_SECRET")
        return 2
    resolved_robot_code = robot_code or os.getenv("DINGDING_ROBOT_CODE")
    if not resolved_robot_code:
        print("缺少 robotCode，请设置 DINGDING_ROBOT_CODE")
        return 2
    if not user_id:
        print("缺少 userId，请设置 DINGDING_TARGET_USERID 或传 --userid")
        return 2

    from ding_send_test import get_access_token

    access_token = get_access_token(app_key, app_secret)
    result = send_one_to_one_message(
        robot_code=resolved_robot_code,
        access_token=access_token,
        user_id=user_id,
        title=title,
        text=text,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("消息发送请求已提交。")
    return 0


def _stream_subprocess_output(stream, target, prefix: str) -> None:
    if stream is None:
        return
    try:
        for line in iter(stream.readline, ""):
            text = line.rstrip()
            if not text:
                continue
            target.write(f"[{prefix}] {text}\n")
            target.flush()
    finally:
        stream.close()


def _launch_child(name: str, module_name: str) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(
        [sys.executable, "-m", module_name],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    threading.Thread(
        target=_stream_subprocess_output,
        args=(proc.stdout, sys.stdout, name),
        daemon=True,
    ).start()
    threading.Thread(
        target=_stream_subprocess_output,
        args=(proc.stderr, sys.stderr, name),
        daemon=True,
    ).start()
    return proc


def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _find_listening_pids(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    pids: set[int] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[0] != "TCP":
            continue
        if not parts[1].endswith(f":{port}"):
            continue
        if parts[3] != "LISTENING":
            continue
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        if pid != os.getpid():
            pids.add(pid)
    return sorted(pids)


def _kill_process_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )


def _free_port(port: int, service_name: str) -> None:
    pids = _find_listening_pids(port)
    if not pids:
        return

    print(f"{service_name} 端口 {port} 已被占用，正在清理进程: {pids}", flush=True)
    for pid in pids:
        _kill_process_tree(pid)

    for _ in range(20):
        if not _find_listening_pids(port):
            print(f"{service_name} 端口 {port} 已释放", flush=True)
            return
        time.sleep(0.5)

    print(f"{service_name} 端口 {port} 仍被占用，后续启动可能失败", flush=True)


def _launch_redis() -> subprocess.Popen | None:
    _free_port(REDIS_PORT, "redis")
    if _is_port_open(REDIS_HOST, REDIS_PORT):
        print(f"Redis already running on {REDIS_HOST}:{REDIS_PORT}", flush=True)
        return None
    if not REDIS_SERVER.exists():
        print(f"未找到 Redis 启动文件: {REDIS_SERVER}", flush=True)
        return None
    if not REDIS_CONF.exists():
        print(f"未找到 Redis 配置文件: {REDIS_CONF}", flush=True)
        return None

    command = f'cd /d "{REDIS_DIR}" && start "" /B redis-server.exe redis.conf'
    proc = subprocess.Popen(command, shell=True)
    for _ in range(30):
        if _is_port_open(REDIS_HOST, REDIS_PORT):
            return proc
        time.sleep(1)
    print(f"Redis 启动超时，未检测到 {REDIS_HOST}:{REDIS_PORT} 端口", flush=True)
    return proc


def _shutdown_redis() -> None:
    if not _is_port_open(REDIS_HOST, REDIS_PORT):
        return
    if not REDIS_DIR.joinpath("redis-cli.exe").exists():
        return

    command = f'cd /d "{REDIS_DIR}" && redis-cli.exe -p {REDIS_PORT} SHUTDOWN NOSAVE'
    subprocess.run(command, shell=True, capture_output=True, text=True)


def _stop_child(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def cmd_all() -> int:
    """Start Redis, the DingTalk bot and API server together."""
    children: dict[str, tuple[str, subprocess.Popen]] = {}
    redis_started = False

    redis_proc = _launch_redis()
    if redis_proc is not None:
        redis_started = True
        print(f"redis: pid={redis_proc.pid}", flush=True)
    else:
        print("redis: already running or skipped", flush=True)

    _free_port(SERVER_PORT, "server")
    children["server"] = ("src.Server", _launch_child("server", "src.Server"))
    children["ding"] = ("src.DingWebHook", _launch_child("ding", "src.DingWebHook"))

    print("已启动一键模式：redis + server + ding", flush=True)
    for name, (_, proc) in children.items():
        print(f"{name}: pid={proc.pid}", flush=True)

    try:
        while True:
            if redis_started and not _is_port_open(REDIS_HOST, REDIS_PORT):
                print("redis 已退出，正在重新启动...", flush=True)
                redis_proc = _launch_redis()
                if redis_proc is not None:
                    print(f"redis: pid={redis_proc.pid}", flush=True)

            for name, (module_name, proc) in list(children.items()):
                code = proc.poll()
                if code is not None:
                    print(f"{name} 已退出，退出码: {code}，正在重启...", flush=True)
                    time.sleep(2)
                    if name == "server":
                        _free_port(SERVER_PORT, "server")
                    new_proc = _launch_child(name, module_name)
                    children[name] = (module_name, new_proc)
                    print(f"{name}: pid={new_proc.pid}", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("收到中断，正在停止所有子进程...", flush=True)
        for _, proc in children.values():
            _stop_child(proc)
        if redis_started:
            _shutdown_redis()
        return 130


def main() -> int:
    ensure_project_root_on_path()
    parser = build_parser()
    args = parser.parse_args()

    command = args.command or "all"
    if command == "doctor":
        return cmd_doctor()
    if command == "all":
        return cmd_all()
    if command == "agent":
        return cmd_agent(args.prompt)
    if command == "server":
        return cmd_server()
    if command == "ding":
        return cmd_ding()
    if command == "ding-send":
        return cmd_ding_send(
            args.robot_code,
            args.userid,
            args.title,
            args.text,
        )

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
