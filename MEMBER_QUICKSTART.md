# 成员快速开始

这份说明给项目成员使用。目标是：从 GitHub clone 后，在自己电脑上独立抓取财经新闻，并导出 Excel/CSV/JSONL。

## 你需要准备

- Python 3.11 或更高版本。
- Windows PowerShell。
- 可以访问外网新闻源。

当前项目不需要额外安装 Python 包，`requirements.txt` 只是用于说明依赖状态。

## 1. Clone 仓库

```powershell
git clone <你的GitHub仓库地址>
cd NewsIngestionV1
```

如果仓库名不是 `NewsIngestionV1`，进入实际目录即可。

## 2. 自检

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1
```

看到 `doctor_ok=True` 就可以继续。

## 3. 跑样例

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 sample
```

输出位置：

```text
data/samples/
```

这一步不抓真实新闻，只验证本地工具链能跑通。

## 4. 抓真实新闻

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 daily
```

输出位置：

```text
data/daily/YYYYMMDD/
```

核心文件：

- `articles_YYYYMMDD.jsonl`
- `rejected_YYYYMMDD.jsonl`
- `crawl_report_YYYYMMDD.md`
- `run_metadata_YYYYMMDD.jsonl`

## 5. 导出给自己使用

启动本地 API：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_api.ps1 -HostName 127.0.0.1 -Port 19080 -RefreshIntervalMinutes 0 -NoRefreshOnStart
```

浏览器打开：

```text
http://127.0.0.1:19080/health
```

下载当天全套数据包：

```text
http://127.0.0.1:19080/api/v1/export/daily.zip
```

下载热点 Excel：

```text
http://127.0.0.1:19080/api/v1/export/hot.xlsx?limit=50
```

下载全量新闻 Excel：

```text
http://127.0.0.1:19080/api/v1/export/articles.xlsx?limit=500
```

## 6. 常见问题

### PowerShell 不让执行脚本

使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 sample
```

### `python` 找不到

先安装 Python 3.11+，然后重新打开 PowerShell。

### 抓取条数为 0

检查：

- 电脑是否能访问新闻源网页。
- 是否被代理、防火墙或校园网拦截。
- `config/source_registry.v1.json` 是否被改坏。

### API 端口被占用

换一个端口：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_api.ps1 -HostName 127.0.0.1 -Port 19100 -RefreshIntervalMinutes 0 -NoRefreshOnStart
```

### 数据在哪里

默认在项目目录下：

```text
data/daily/
data/samples/
```

这些数据不会提交到 GitHub，因为 `.gitignore` 已经排除。

## 7. 给组长提交问题

如果抓取失败，把这些信息发给组长：

- 运行的命令。
- `data/daily/YYYYMMDD/crawl_report_YYYYMMDD.md`。
- 报错截图或终端输出。
- 你的系统版本和 Python 版本。
