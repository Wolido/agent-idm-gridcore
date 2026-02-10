# IDM-GridCore Skill

Agent 的算力调用工具 - 透明利用分布式集群加速"小计算、大批量"任务。

## 目录结构

```
idm-gridcore-skill/
├── SKILL.md                  # 主要文档（使用指南）
├── README.md                 # 本文件
├── .gitignore               # Git 忽略配置
├── templates/               # 代码模板
│   ├── consumer.py          # Python 消费者模板
│   └── Dockerfile           # Docker 镜像模板
├── scripts/                 # 辅助脚本
│   └── check_env.py         # 环境检查脚本
└── examples/                # 使用示例
    ├── square_calc.py       # 平方计算示例
    ├── image_processor.py   # 图片处理示例
    └── batch_http.py        # 批量 HTTP 请求示例
```

## 快速开始

1. 阅读 `SKILL.md` 了解完整使用指南
2. 运行 `scripts/check_env.py` 检查环境
3. 参考 `examples/` 中的示例快速上手

## 核心功能

- **从零启动**：3 分钟内在本地启动计算集群
- **连接已有**：使用预设的公司/团队计算集群
- **任务封装**：用户提供计算逻辑，自动打包并行执行
- **数据推送**：支持多种数据源（列表、CSV、文件等）
- **结果获取**：自动聚合、格式化返回

## 使用场景

- 批量图片处理（缩略图、水印、格式转换）
- 批量 API 调用（数据抓取、接口测试）
- 批量数据处理（CSV/JSON 转换、清洗）
- 数值计算（蒙特卡洛模拟、参数扫描）

## 依赖

- Docker（必须）
- Python 3.8+（示例脚本需要）
- curl（下载二进制）
- Rust/Cargo（可选，本地编译 fallback）

## License

MIT
