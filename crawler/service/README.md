# crawler_service —— 通用规则采集微服务

独立的、基于规则配置的多站点通用爬虫服务与 CLI 工具。

## 特性

1. **完全解耦与独立运行**：独立工程、独立依赖，通过 HTTP REST API 或 CLI 命令行独立提供采集能力。
2. **通用规则驱动（Config-Driven Engine）**：无需为每个站点硬编码 Python 文件。通过声明式 JSON/YAML 规则即可完成站点的抓取与解析。
   - 支持 **HTML**（CSS 选择器、属性提取、文本提取、列表循环）
   - 支持 **JSON API**（JSONPath / 点分键路径提取）
   - 支持 **Regex / 模板**（提取播放流 m3u8、URL 模板拼接）
3. **内置反爬与数据清洗**：
   - 自动破除 `cdndefend` 等 SHA-1 算力质押型闸门（纯算法 <40ms 解决）
   - 自动清洗广告域名、变体数学粗体字（如 `𝕜𝕜𝕪𝕤𝟘𝟙.𝕔𝕠𝕞`）
   - 自动补全相对路径防 SSRF
4. **统一契约与信封**：输出契约与前端、后台无缝衔接。
5. **实时规则在线调试**：提供 `/api/v1/rules/test` 接口与 CLI 测试命令，输入规则即刻返回提取结果。

## 目录结构

```
crawler_service/
├── README.md
├── requirements.txt
├── config.py             # 服务配置
├── main.py               # FastAPI 服务入口
├── cli.py                # 命令行独立调试工具
├── core/                 # 网络、反爬闸门、日志、清洗
│   ├── errors.py
│   ├── log.py
│   ├── http_client.py
│   ├── gates.py
│   └── cleaner.py
├── engine/               # 通用规则引擎
│   ├── models.py         # 规则 Pydantic 模型
│   ├── extractor_html.py # HTML CSS 解析器
│   ├── extractor_json.py # JSONPath 解析器
│   ├── scraper.py        # 统一抓取与执行调度器
│   └── rule_manager.py   # 规则持久化与动态管理
├── rules/                # 预设与自定义规则库
│   ├── ai2048.json
│   └── maccms_demo.json
├── api/                  # FastAPI 路由
│   ├── routes_system.py
│   ├── routes_rules.py
│   ├── routes_scrape.py
│   └── routes_tasks.py
└── tests/                # 独立单元测试
```

## 快速上手

### 1. 启动 HTTP 微服务

```bash
cd crawler_service
python -m uvicorn main:app --host 0.0.0.0 --port 8088 --reload
```

访问交互式 API 文档：`http://127.0.0.1:8088/docs`

### 2. 命令行调试 (CLI)

```bash
# 测试指定站点的 home 动作
python cli.py run --site ai2048 --action home

# 运行规则校验
python cli.py validate-rule rules/ai2048.json

# 启动服务
python cli.py serve --port 8088
```
