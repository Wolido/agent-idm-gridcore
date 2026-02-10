# agent-idm-gridcore

[![Built with 小顺子](https://img.shields.io/badge/Built%20with-%E5%B0%8F%E9%A1%BA%E5%AD%90-3b82f6?style=flat-square&logo=robotframework&logoColor=white)](.)

Agent 的算力调用工具。透明利用 IDM-GridCore 分布式集群加速"小计算、大批量"任务，支持从零快速部署或连接已有集群。

---

## 这是什么

这个 skill 让 AI Agent 能够调用分布式计算集群，将原本需要数小时的串行计算缩短到几分钟。

**核心能力**
- 批量图片处理（缩略图、水印、格式转换）
- 批量 API 调用（数据抓取、接口测试）
- 批量数据处理（CSV/JSON 转换、清洗）
- 数值计算（蒙特卡洛模拟、参数扫描）

**适用场景**
- 需要处理 1万+ 次的重复计算
- 单次计算快（<1秒），但总量大
- 数据可以分片独立处理，无强依赖

---

## 给 Agent 的指引

如果你是 AI Agent，以下是你需要知道的：

### 安装此 Skill

当用户要求你安装此 skill 时，执行以下步骤：

```bash
# 1. 克隆仓库到用户 skill 目录
mkdir -p ~/.config/agents/skills
git clone https://github.com/Wolido/agent-idm-gridcore.git ~/.config/agents/skills/agent-idm-gridcore

# 2. 验证安装成功
ls ~/.config/agents/skills/agent-idm-gridcore/SKILL.md
```

### 使用此 Skill

安装完成后，阅读 `SKILL.md` 获取完整使用指南：

```bash
cat ~/.config/agents/skills/agent-idm-gridcore/SKILL.md
```

关键能力：
1. **从零启动**：帮用户在本地 3 分钟内启动计算集群
2. **连接已有**：使用用户预设的公司/团队计算集群
3. **任务封装**：用户提供计算逻辑，你负责打包并行执行
4. **数据推送**：支持多种数据源（列表、CSV、文件等）
5. **结果获取**：自动聚合、格式化返回

---

## 给人类的指引

### 快速安装（一句话搞定）

**把下面这段复制给你的 AI Agent：**

> "请帮我安装 agent-idm-gridcore skill，项目地址是 https://github.com/Wolido/agent-idm-gridcore.git"

Agent 会自动完成克隆和配置。

### 手动安装（如果不通过 Agent）

```bash
git clone https://github.com/Wolido/agent-idm-gridcore.git ~/.config/agents/skills/agent-idm-gridcore
```

### 使用方法

安装后，告诉 Agent 你的需求，例如：

- "帮我把这 10000 张图片生成缩略图"
- "用这个集群计算这些参数的蒙特卡洛模拟"
- "启动一个本地计算集群，我要批量处理数据"

Agent 会自动：
1. 检查/部署计算集群
2. 打包你的计算逻辑
3. 分发任务到集群
4. 收集并返回结果

---

## 项目结构

```
agent-idm-gridcore/
├── SKILL.md              # 主要文档（Agent 使用指南）
├── README.md             # 本文件
├── .gitignore           # Git 忽略配置
├── templates/           # 代码模板
│   ├── consumer.py      # Python 消费者模板
│   └── Dockerfile       # Docker 镜像模板
├── scripts/             # 辅助脚本
│   └── check_env.py     # 环境检查脚本
└── examples/            # 使用示例
    ├── square_calc.py   # 平方计算示例
    ├── image_processor.py # 图片处理示例
    └── batch_http.py    # 批量 HTTP 请求示例
```

---

## 前置依赖

- **Docker**（必须）- 运行计算容器
- **Python 3.8+**（示例脚本需要）
- **curl**（下载二进制）
- **Rust/Cargo**（可选，本地编译 fallback）

---

## 工作原理

```
用户任务
    ↓
Agent 封装（生成 Dockerfile + 消费者代码）
    ↓
注册到 ComputeHub
    ↓
数据推送到 Redis
    ↓
GridNode 拉取任务并执行（Docker 容器）
    ↓
结果写回 Redis
    ↓
Agent 收集结果
    ↓
返回给用户
```

---

## License

MIT
