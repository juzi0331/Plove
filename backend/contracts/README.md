# contracts —— 三端共用的唯一事实源

这个目录解决一件事：**后端、爬虫、前端对同一份数据的理解不允许有第二种说法。**

## 唯一来源是 Pydantic 模型，不是这里的 JSON

真正的源头在 [backend/app/schemas/](../backend/app/schemas/) —— 一组 Pydantic 模型。
`contracts/schemas/*.json` 是**由它导出的生成物**：

```bash
cd \u540e\u7aef
python tools/export_contracts.py          # 导出（改完模型就重跑一次）
python tools/export_contracts.py --check  # 只比对不写，CI / 测试用
```

所以规矩是：

* **不要手改 `schemas/` 下的 JSON**，改了会被下一次导出覆盖；
* 改模型 → 重新导出 → **把生成物一起提交**；
* `pytest` 里有一条 `test_contracts_are_not_stale`，模型改了却忘了导出，测试直接红。

## 谁能读

| 读的人 | 怎么用 |
| --- | --- |
| 后端 | 直接用 Pydantic 模型校验出入参（FastAPI 原生支持） |
| 爬虫 | 只用标准库，读这份 JSON 做**最小校验**（`required` / `type` / `enum`） |
| 前端 | 由它生成 TS 类型，契约改了在编译期就报错 |

爬虫为什么不能直接用 Pydantic？因为爬虫被硬约束为"只准 `import crawler_kit` + 标准库"
（理由见 [crawler-plan.md](../docs/crawler-plan.md)）。所以它只能读 JSON 文件——
这也是为什么事实源必须能落成文件，而不能只活在代码里。

## 命名约定

**全链路 snake_case**：`vod_id`、`has_more`、`request_id`。
爬虫那侧早就这么写了（`vod_id`/`ep_index`/`has_more`），后端和前端跟着对齐，
不要出现 `requestId` 这种 camelCase 混用。

## 文件

| 文件 | 对应什么 |
| --- | --- |
| `envelope.json` | 后端 HTTP 统一响应信封 |
| `error-info.json` | 错误对象（`code` / `message` / `detail`） |
| `vod-item.json` | 全站统一影片卡片 |
| `vod-category.json` | 分类（`tid` / `name`） |
| `episode.json` | 单集（`ep_index` 1 起算，多线路带 `line`） |
| `line-info.json` | 播放线路 |
| `playback.json` | 播放地址（`url` / `format` / `headers`） |
| `site-meta.json` | 爬虫 `meta` 命令的输出 + 能力清单 |
| `catalog-home.json` / `catalog-list.json` / `catalog-detail.json` | 三个目录接口的载荷 |
| `health.json` | 健康检查载荷 |

## 统一信封

与爬虫命令行信封**同构**，只多一个 `request_id`：

```json
{ "ok": true,  "data": { }, "error": null, "request_id": "…" }
{ "ok": false, "data": null, "error": { "code": "UPSTREAM_TIMEOUT", "message": "…" }, "request_id": "…" }
```

好处是前端只写一套错误处理；出问题时拿 `request_id` 能从网关日志一路串到爬虫的 stderr。

爬虫的 `TIMEOUT` / `HTTP_ERROR` / `PARSE_ERROR` / `BLOCKED` 在网关侧统一翻译成
`UPSTREAM_*`，前端因此不需要知道爬虫长什么样。
