# AIHelper DingTalk Chat Agent

一个面向钉钉场景的智能助手项目，围绕 `LangChain Agent + FastAPI + Redis + Qdrant + DingTalk Stream` 构建，支持知识库问答、实时搜索、待办与日程协同，以及一键式本地启动。

## 项目定位

AIHelper 是一个面向企业协同场景的智能助手示例项目，目标是将大模型能力接入钉钉对话入口，并结合知识库检索、工具调用和会话记忆，提供可落地的智能客服/办公助手体验。

## 技术栈

- `Python 3.10+`
- `Poetry`：依赖管理与项目构建
- `LangChain`：Agent 编排、工具调用、Prompt 组织、对话链路
- `FastAPI + Uvicorn`：知识库文档接入 API
- `Redis`：会话记忆存储
- `Qdrant`：本地向量存储与检索
- `OpenAI / DeepSeek Compatible API`：对话模型与嵌入模型接入
- `DingTalk Stream SDK`：钉钉机器人长连接接入

## 核心能力

- `Agent 对话编排`
  基于 LangChain Agent 统一调度搜索、知识库检索、待办创建、日程查询与修改等工具。

- `知识库问答`
  通过 FastAPI 接收 URL 文档，切分后写入 Qdrant，本地检索后参与回答生成。

- `情绪感知`
  根据用户输入识别情绪状态，并动态调整系统提示词和回答策略。

- `钉钉工作流接入`
  支持钉钉 Stream 消息接入、待办创建、日程查询/新增/修改/删除。

- `会话记忆`
  使用 Redis 保存聊天历史，并在长对话场景下进行摘要压缩。

- `一键启动`
  通过 `python main.py` 同时拉起 Redis、FastAPI 服务和钉钉机器人进程。

## 工程亮点

- 模块职责拆分清晰：
  `Agents` 负责主对话代理，`Tools` 负责工具能力，`Memory` 负责会话记忆，`AddDoc` 负责知识库入库，`DingWebHook` 负责钉钉事件入口。

- 本地运行链路完整：
  仓库内保留 Windows 版 `redis-stack` 运行包，方便本地演示和面试场景快速启动。

- 服务编排与诊断能力：
  `main.py` 提供 `doctor / agent / server / ding / ding-send / all` 等入口，便于本地排查与演示。

- 端口与日志治理：
  启动脚本会优先处理固定端口占用，并将子进程日志转发到主控制台，便于观察 FastAPI 与钉钉连接状态。

## 目录说明

```text
.
├── main.py                 # 一键启动与诊断入口
├── ding_send_test.py       # 钉钉单发测试脚本
├── src/
│   ├── Agents.py           # LangChain Agent 主链路
│   ├── Prompt.py           # 系统提示词与情绪策略
│   ├── Memory.py           # Redis 会话记忆
│   ├── Emotion.py          # 情绪识别
│   ├── Tools.py            # 搜索 / 知识库 / 钉钉工具集
│   ├── AddDoc.py           # 文档抓取与向量化
│   ├── Server.py           # FastAPI 文档接入服务
│   └── DingWebHook.py      # 钉钉 Stream 入口
└── redis-stack/            # 本地 Redis 运行包
```

## 本地启动

### 1. 安装依赖

```bash
poetry install
```

### 2. 配置环境变量

参考仓库中的 `.env.example`，补充以下配置：

- 大模型与嵌入模型 API 配置
- SerpAPI 搜索配置
- 钉钉应用 `AppKey / AppSecret / RobotCode / UserId`

### 3. 一键启动

```bash
python main.py
```

默认会启动：

- Redis：`127.0.0.1:6379`
- FastAPI：`0.0.0.0:8000`
- DingTalk Stream 机器人

### 4. 常用命令

```bash
python main.py doctor
python main.py agent "你好"
python main.py server
python main.py ding
python main.py ding-send --userid <user_id> --text "你好"
```

## 适合展示的能力点

- 大模型 Agent 工程落地能力
- 知识库检索增强生成（RAG）实践
- 企业 IM 平台对接经验
- 服务编排、端口治理与本地调试能力
- 面向真实业务场景的工具调用链路设计

## 说明

本仓库为了面试展示，已移除真实环境配置、日志与本地运行缓存。运行项目时请使用自己的 API Key 与钉钉应用配置。
