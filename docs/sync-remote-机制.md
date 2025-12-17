# TrendRadar 远程存储同步机制详解

## 📖 概述

TrendRadar 支持将爬取的新闻数据存储到远程S3兼容的云存储服务，并允许从远程拉取数据到本地进行分析。本文档详细介绍了该机制的工作原理、配置方式和使用方法。

## 🏗️ 架构设计

### 数据流向

```
┌─────────────────┐    爬取    ┌─────────────────┐    上传    ┌─────────────────┐
│  新闻源平台      │ ────────→ │  TrendRadar主   │ ────────→ │  远程S3存储     │
│  (各大平台API)   │          │  程序           │          │  (CloudflareR2) │
└─────────────────┘          └─────────────────┘          └─────────────────┘
                                          ↓
                              MCP Server拉取
                                          ↓
┌─────────────────┐    读取    ┌─────────────────┐    分析    ┌─────────────────┐
│  本地文件系统    │ ←──────── │  TrendRadar MCP │ ────────→ │  AI分析结果     │
│  (output目录)   │          │  Server         │          │  (JSON响应)     │
└─────────────────┘          └─────────────────┘          └─────────────────┘
```

### 核心组件

- **RemoteStorageBackend**: 远程存储后端，负责S3兼容协议的读写操作
- **StorageSyncTools**: MCP工具，负责数据同步和状态查询
- **ParserService**: 数据解析服务，支持本地和远程数据读取

## 🔐 认证机制

### 配置方式

TrendRadar采用**双重配置**方式，支持两种存储途径：

#### 1. 配置文件方式（不推荐生产环境）

位置：`config/config.yaml`

```yaml
storage:
  remote:
    endpoint_url: ""          # 服务端点
    bucket_name: ""           # 存储桶名称
    access_key_id: ""         # 访问密钥ID
    secret_access_key: ""     # 访问密钥
    region: ""                # 区域
    retention_days: 60        # 数据保留天数
```

#### 2. 环境变量方式（推荐，更安全）

```bash
S3_ENDPOINT_URL="https://xxx.r2.cloudflarestorage.com"
S3_BUCKET_NAME="my-bucket"
S3_ACCESS_KEY_ID="your-access-key"
S3_SECRET_ACCESS_KEY="your-secret-key"
S3_REGION=""  # 可选
```

### 读取机制

从 `storage_sync.py:54-67` 可以看出具体的读取逻辑：

```python
def _get_remote_config(self) -> dict:
    """
    获取远程存储配置（合并配置文件和环境变量）
    """
    storage_config = self._get_storage_config()
    remote_config = storage_config.get("remote", {})

    return {
        "endpoint_url": remote_config.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL", ""),
        "bucket_name": remote_config.get("bucket_name") or os.environ.get("S3_BUCKET_NAME", ""),
        "access_key_id": remote_config.get("access_key_id") or os.environ.get("S3_ACCESS_KEY_ID", ""),
        "secret_access_key": remote_config.get("secret_access_key") or os.environ.get("S3_SECRET_ACCESS_KEY", ""),
        "region": remote_config.get("region") or os.environ.get("S3_REGION", ""),
    }
```

**读取优先级**：`环境变量 > 配置文件`

### 安全验证

```python
def _has_remote_config(self) -> bool:
    """检查是否有有效的远程存储配置"""
    config = self._get_remote_config()
    return bool(
        config.get("bucket_name") and
        config.get("access_key_id") and
        config.get("secret_access_key") and
        config.get("endpoint_url")
    )
```

## 🚀 支持的云存储服务

### S3兼容协议服务

| 服务商 | 端点URL格式 | 备注 |
|--------|-------------|------|
| **Cloudflare R2** | `https://<account_id>.r2.cloudflarestorage.com` | 推荐，免费额度大 |
| **阿里云OSS** | `https://oss-cn-hangzhou.aliyuncs.com` | 需要指定region |
| **腾讯云COS** | `https://cos.ap-guangzhou.myqcloud.com` | 需要指定region |
| **AWS S3** | `https://s3.amazonaws.com` | 原生S3服务 |
| **MinIO** | `http://localhost:9000` | 自建对象存储 |

### 数据格式

远程存储的数据结构：

```
news/
├── 2025-12-17.db      # SQLite数据库文件
├── 2025-12-16.db
├── 2025-12-15.db
└── ...
```

每个SQLite文件包含：
- `news_items`: 新闻条目表
- `platforms`: 平台信息表
- `rank_history`: 排名历史表
- `crawl_records`: 爬取记录表
- `title_changes`: 标题变更记录表

## 📊 同步流程

### 数据上传流程

1. **初始化远程后端**
   ```python
   from trendradar.storage.remote import RemoteStorageBackend

   remote_backend = RemoteStorageBackend(
       bucket_name=remote_config["bucket_name"],
       access_key_id=remote_config["access_key_id"],
       secret_access_key=remote_config["secret_access_key"],
       endpoint_url=remote_config["endpoint_url"],
       region=remote_config.get("region", "")
   )
   ```

2. **下载现有数据**
   ```python
   local_path = self._download_sqlite(date)
   ```

3. **数据合并**
   - 通过URL进行去重
   - 记录标题变更
   - 保存排名历史

4. **上传回远程**
   ```python
   success = self._upload_sqlite(date)
   ```

### 数据拉取流程

1. **检查远程配置**
   ```python
   if not self._has_remote_config():
       return {"success": False, "error": "未配置远程存储"}
   ```

2. **获取可用日期列表**
   ```python
   remote_dates = remote_backend.list_remote_dates()
   ```

3. **选择性下载**
   ```python
   for date_str in target_dates:
       if date_str not in local_dates:
           self.s3_client.download_file(bucket_name, remote_key, local_path)
   ```

## 🛠️ MCP工具接口

### 主要同步工具

#### 1. `sync_from_remote`

从远程存储拉取数据到本地：

```python
# 调用示例
result = await sync_from_remote(days=7)

# 返回结果
{
    "success": true,
    "synced_files": 5,
    "synced_dates": ["2025-12-17", "2025-12-16", ...],
    "skipped_dates": ["2025-12-15"],  # 本地已存在
    "failed_dates": [],
    "message": "成功同步 5 天数据，跳过 1 天（本地已存在）"
}
```

#### 2. `get_storage_status`

获取存储状态信息：

```python
# 调用示例
result = await get_storage_status()

# 返回结果
{
    "success": true,
    "backend": "auto",
    "local": {
        "data_dir": "output",
        "retention_days": 30,
        "total_size": "125.67 MB",
        "date_count": 15,
        "earliest_date": "2025-12-03",
        "latest_date": "2025-12-17"
    },
    "remote": {
        "configured": true,
        "endpoint_url": "https://xxx.r2.cloudflarestorage.com",
        "bucket_name": "trendradar-data",
        "date_count": 30,
        "earliest_date": "2025-11-18",
        "latest_date": "2025-12-17"
    },
    "pull": {
        "enabled": true,
        "days": 7
    }
}
```

#### 3. `list_available_dates`

列出可用日期范围：

```python
# 调用示例
result = await list_available_dates(source="both")

# 返回结果
{
    "success": true,
    "local": {
        "dates": ["2025-12-17", "2025-12-16", ...],
        "count": 10,
        "earliest": "2025-12-08",
        "latest": "2025-12-17"
    },
    "remote": {
        "configured": true,
        "dates": ["2025-12-17", "2025-12-16", ...],
        "count": 30,
        "earliest": "2025-11-18",
        "latest": "2025-12-17"
    },
    "comparison": {
        "only_local": ["2025-12-07"],  # 仅本地存在
        "only_remote": ["2025-11-18", "2025-11-19", ...],  # 仅远程存在
        "both": ["2025-12-17", "2025-12-16", ...]  # 两边都有
    }
}
```

## ⚙️ 配置详解

### 完整配置示例

```yaml
# config/config.yaml
storage:
  backend: "auto"  # auto/local/remote

  formats:
    sqlite: true
    txt: false
    html: true

  local:
    data_dir: "output"
    retention_days: 30

  remote:
    retention_days: 60
    endpoint_url: ""  # 或环境变量 S3_ENDPOINT_URL
    bucket_name: ""   # 或环境变量 S3_BUCKET_NAME
    access_key_id: ""  # 或环境变量 S3_ACCESS_KEY_ID
    secret_access_key: ""  # 或环境变量 S3_SECRET_ACCESS_KEY
    region: ""  # 或环境变量 S3_REGION

  pull:
    enabled: true  # MCP Server启动时自动拉取
    days: 7  # 拉取最近N天数据
```

### 环境变量设置

#### Windows PowerShell
```powershell
$env:S3_ENDPOINT_URL="https://xxx.r2.cloudflarestorage.com"
$env:S3_BUCKET_NAME="trendradar-data"
$env:S3_ACCESS_KEY_ID="your-access-key"
$env:S3_SECRET_ACCESS_KEY="your-secret-key"
$env:S3_REGION="auto"
```

#### Linux/Mac
```bash
export S3_ENDPOINT_URL="https://xxx.r2.cloudflarestorage.com"
export S3_BUCKET_NAME="trendradar-data"
export S3_ACCESS_KEY_ID="your-access-key"
export S3_SECRET_ACCESS_KEY="your-secret-key"
export S3_REGION="auto"
```

#### Docker环境
```yaml
# docker-compose.yml
version: '3.8'
services:
  trendradar:
    image: trendradar:latest
    environment:
      - S3_ENDPOINT_URL=${S3_ENDPOINT_URL}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
      - S3_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}
      - S3_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY}
      - S3_REGION=${S3_REGION}
```

## 🔒 安全最佳实践

### ✅ 推荐做法

1. **使用环境变量**
   - 敏感信息通过环境变量配置
   - 避免将密钥写入配置文件

2. **GitHub Actions**
   - 使用GitHub Secrets存储敏感信息
   - 在Actions中通过环境变量注入

3. **本地开发**
   - 使用 `.env` 文件（记得添加到 `.gitignore`）
   - 使用环境变量管理工具

4. **Docker部署**
   - 使用Docker secrets
   - 或通过环境变量传递

5. **权限最小化**
   - 为S3存储桶创建最小权限的访问密钥
   - 只授予必要的读写权限

### ❌ 避免做法

1. **不要将密钥直接写入配置文件并提交到版本控制**
2. **不要在日志中打印敏感信息**
3. **不要在公开场合分享密钥信息**
4. **不要使用默认或弱密钥**

### 敏感信息脱敏

在 `get_storage_status()` 等接口中，系统会自动脱敏处理：

```python
# 脱敏显示，只显示域名部分
endpoint = merged_config.get("endpoint_url", "")
if endpoint:
    # 只显示域名，隐藏密钥信息
    sanitized_endpoint = endpoint.split('://')[0] + '://***'
    remote_status["endpoint_url"] = sanitized_endpoint
```

## 🐛 故障排除

### 常见问题

#### 1. 连接失败
```python
# 错误信息
"无法创建远程存储后端"

# 解决方案
- 检查网络连接
- 验证端点URL是否正确
- 确认密钥信息是否有效
```

#### 2. 权限错误
```python
# 错误信息
"Access Denied"

# 解决方案
- 检查访问密钥权限
- 确认存储桶是否存在
- 验证区域配置是否正确
```

#### 3. 数据不存在
```python
# 错误信息
"文件不存在，将创建新数据库"

# 解决方案
- 这是正常情况，系统会自动创建
- 确认存储桶权限允许写入
```

### 调试方法

#### 1. 检查配置
```python
# 使用MCP工具检查配置状态
await get_storage_status()
```

#### 2. 验证连接
```python
# 列出远程可用日期
await list_available_dates(source="remote")
```

#### 3. 查看日志
```bash
# 查看详细日志
tail -f trendradar.log | grep "远程存储"
```

## 📝 示例用例

### 用例1：GitHub Actions自动同步

```yaml
# .github/workflows/crawler.yml
name: News Crawler
on:
  schedule:
    - cron: '0 * * * *'  # 每小时执行

jobs:
  crawl:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run crawler
        env:
          S3_ENDPOINT_URL: ${{ secrets.S3_ENDPOINT_URL }}
          S3_BUCKET_NAME: ${{ secrets.S3_BUCKET_NAME }}
          S3_ACCESS_KEY_ID: ${{ secrets.S3_ACCESS_KEY_ID }}
          S3_SECRET_ACCESS_KEY: ${{ secrets.S3_SECRET_ACCESS_KEY }}
        run: python main.py
```

### 用例2：本地MCP Server拉取数据

```python
# 启动MCP Server时自动拉取
def start_mcp_server():
    # 检查是否配置了远程存储
    storage_status = get_storage_status()

    if storage_status["remote"]["configured"] and storage_status["pull"]["enabled"]:
        # 拉取最近N天数据
        sync_result = sync_from_remote(days=storage_status["pull"]["days"])
        print(f"自动同步结果: {sync_result['message']}")

    # 启动MCP服务器
    run_server()
```

### 用例3：数据分析工作流

```python
# 完整的数据分析工作流
async def analyze_trends():
    # 1. 同步最新数据
    sync_result = await sync_from_remote(days=7)

    # 2. 获取最新新闻
    latest_news = await get_latest_news(limit=100, include_url=True)

    # 3. 分析趋势
    trend_analysis = await analyze_topic_trend(
        topic="人工智能",
        analysis_type="trend",
        date_range={"start": "2025-12-10", "end": "2025-12-17"}
    )

    # 4. 生成报告
    report = await generate_summary_report(
        report_type="weekly",
        date_range={"start": "2025-12-11", "end": "2025-12-17"}
    )

    return {
        "sync_status": sync_result,
        "latest_news": latest_news,
        "trend_analysis": trend_analysis,
        "summary_report": report
    }
```

## 📚 参考资料

- [boto3文档](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Cloudflare R2开发指南](https://developers.cloudflare.com/r2/)
- [阿里云OSS文档](https://help.aliyun.com/product/31815.html)
- [腾讯云COS文档](https://cloud.tencent.com/document/product/436)

---

> **注意**：确保在生产环境中妥善保管所有敏感信息，定期轮换访问密钥，并监控存储使用量以避免意外费用。