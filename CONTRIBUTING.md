# 协作说明

欢迎成员基于本仓库改进财经新闻采集器。

## 分工建议

| 模块 | 主要文件 | 适合负责的人 |
| --- | --- | --- |
| 数据源适配 | `src/news_ingestion/fetchers.py`、`config/source_registry.v1.json` | 爬虫/数据同学 |
| 数据质量 | `src/news_ingestion/quality.py`、`config/quality_rules.v1.json` | 数据治理同学 |
| API 与导出 | `src/news_ingestion/api_server.py` | 后端/API 同学 |
| 文档与交付 | `README.md`、`MEMBER_QUICKSTART.md`、`DEPLOY.md` | 组长/产品同学 |

## 提交前必须做

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1 sample
```

如果改了真实源抓取，再跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 daily
```

## 不要提交

- `.env`
- `data/daily/`
- `data/samples/`
- `data/realtest/`
- `data/multisource_test/`
- `dist/`
- `__pycache__/`

## 新增数据源流程

1. 在 `config/source_registry.v1.json` 添加 source。
2. 在 `src/news_ingestion/fetchers.py` 添加适配器。
3. 输出必须包含 `title`、`url`、`source`、`crawled_at`。
4. 尽量补 `published_at`、`content`、`hot_features`。
5. 跑 `daily` 并查看 `crawl_report_YYYYMMDD.md`。

## 质量原则

- 缺失值保持 `null`，不要伪造成 0。
- 抓取失败要进入错误记录或报告，不要静默吞掉。
- 不要为了条数牺牲质量。
