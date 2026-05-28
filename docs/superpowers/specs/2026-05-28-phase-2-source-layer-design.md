# Phase 2 Source Layer 设计

## 目标

Phase 2 Source Layer 的目标是把 CompEye Agent 的信息采集从“运行时临时搜索”升级为“多源、分频率、可追溯、可复用”的来源情报层。当前 Collector 只通过 `WebSearchTool` 搜索公开信息，容易得到泛化摘要或口径不一致的结果，导致 Verifier 判定报告缺少证据、存在逻辑冲突或缺少竞品对比。

Source Layer 需要在 Agent 写报告之前提供结构化 evidence，让后续 Collector / Analyzer / Writer 消费稳定来源，而不是在报告生成后再从 Markdown 中反向提取 URL。

## 范围

第一阶段实现可本地运行的来源索引闭环：

- 官方网站、产品页面、定价页、帮助文档的每日增量采集。
- Jina Reader 页面正文抽取。
- Raw Document 存储、去重、刷新时间记录。
- Evidence Item 抽取和 provenance 字段。
- Collector 可读取 indexed evidence。
- 现有报告 URL 提取逻辑保留为兼容路径，但不再作为主要来源机制。

第二阶段扩展外部数据源：

- 新闻媒体：News API + Google Search RSS。
- 技术博客：Blog Crawler 每周扫描。
- GitHub：GitHub API 每日轮询 repo、star、release、contributor 趋势。
- 社交媒体：Twitter / Reddit API 关键词监控。
- 财务数据：Crunchbase API 季度更新。
- 专利数据：Patent API 月度扫描。

## 来源分类

| 来源类型 | 主要内容 | 工具 | 默认频率 | 默认可信度 |
| --- | --- | --- | --- | --- |
| official | 官网、产品页、定价页、帮助文档 | Web Scraper + Jina Reader | daily | high |
| news | 产品发布、融资、合作、市场动作 | News API + Google Search RSS | realtime / daily | medium |
| blog | 技术架构、工程博客、开源贡献说明 | Blog Crawler | weekly | medium |
| github | repo、release、star、issue、contributor 趋势 | GitHub API | daily | medium |
| social | 用户反馈、舆情、抱怨点 | Twitter / Reddit API | realtime | low |
| finance | 营收、用户量、估值、融资 | Crunchbase API | quarterly | high |
| patent | 专利申请、技术布局 | Patent API | monthly | high |

## 架构

```text
Source Connectors
      |
      v
RawDocument Store
      |
      v
Evidence Extractor
      |
      v
Evidence Index / Provenance Index
      |
      v
Collector / Analyzer / Writer
```

Source Connectors 负责拉取原始内容，不做复杂分析。RawDocument Store 负责保存来源 URL、正文、hash、抓取时间和来源类型。Evidence Extractor 把 RawDocument 转成可被 Agent 使用的结构化证据。Collector 读取 Evidence Index，并在证据不足时才触发补充抓取。

## 数据模型

新增 `models/source_layer.py`，集中定义 Source Layer 对象。

`SourceProvider`：

- `official`
- `news`
- `blog`
- `github`
- `social`
- `finance`
- `patent`

`RefreshCadence`：

- `realtime`
- `daily`
- `weekly`
- `monthly`
- `quarterly`
- `manual`

`RawDocument` 字段：

- `document_id`
- `provider`
- `competitor`
- `url`
- `title`
- `content`
- `content_hash`
- `fetched_at`
- `published_at`
- `metadata`

`EvidenceItem` 字段：

- `evidence_id`
- `document_id`
- `provider`
- `competitor`
- `dimension`
- `indicator`
- `claim`
- `snippet`
- `url`
- `confidence`
- `observed_at`

`SourceSeed` 字段：

- `provider`
- `competitor`
- `url`
- `label`
- `cadence`
- `enabled`
- `metadata`

## 存储设计

Phase 2 继续使用 SQLite，保持和 `SQLiteRunStore` 一致的轻量部署体验。新增 `storage/source_store.py`，避免把来源索引表塞进 `run_store.py`。

表：

- `source_seeds`
- `raw_documents`
- `evidence_items`
- `source_fetch_events`

`raw_documents.content_hash` 用于增量判断。相同 URL 且 hash 未变化时，只更新 `fetched_at` 和 fetch event，不重复生成 evidence。相同 URL 但 hash 变化时，新增或更新 document 内容，并重新抽取 evidence。

## Connector 设计

所有 connector 实现统一接口：

```python
class SourceConnector(Protocol):
    provider: SourceProvider

    def fetch(self, seed: SourceSeed) -> list[RawDocument]:
        ...
```

第一批只实现：

- `OfficialJinaConnector`
- `NewsRssConnector` 的空骨架
- `GithubConnector` 的空骨架

`OfficialJinaConnector` 使用 Jina Reader URL：

```text
https://r.jina.ai/http://example.com/path
https://r.jina.ai/http://https://example.com/path
```

实现时需要对 URL scheme 做规范化，实际请求格式以 Jina Reader 当前可用格式为准。Jina 请求失败时记录 fetch event，不能让整个 run 崩溃。

## Evidence 抽取策略

Phase 2 初版不引入复杂 LLM 抽取。先用规则抽取：

- 如果 seed label 或页面标题包含“定价”“价格”“pricing”，默认 dimension 为 `定价`。
- 如果正文包含“免费”“免费版”“免费套餐”“Free”，生成 `免费套餐` evidence。
- snippet 使用命中关键词周围的 240 字符窗口。
- confidence 根据 provider 默认值设定，official / finance / patent 为 high，news / blog / github 为 medium，social 为 low。

后续可以把规则抽取替换为 LLM extractor，但数据契约不变。

## Collector 集成

短期不重写 CrewAI 主链路。新增 `services/evidence_service.py`，提供：

- `index_seed(seed)`
- `index_competitor_sources(competitor, seeds)`
- `query_evidence(competitor, dimensions)`
- `format_evidence_for_prompt(evidence_items)`

`collect_task` 的 prompt 更新为：优先使用 Evidence Index 中的 evidence；只有 evidence 不足时才调用搜索工具补充。

## API 和前端

Phase 2 Source Layer 初版先提供后端 API，不急于做前端管理台。

API：

- `POST /api/sources/seeds`
- `GET /api/sources/seeds`
- `POST /api/sources/index`
- `GET /api/sources/evidence`

Dashboard 后续可以增加 Source Coverage 面板，显示各竞品在各维度上的 evidence 覆盖率。

## 配置

新增环境变量：

- `JINA_READER_BASE_URL=https://r.jina.ai/http://`
- `NEWS_API_KEY`
- `GITHUB_TOKEN`
- `CRUNCHBASE_API_KEY`
- `PATENT_API_KEY`
- `SOURCE_STORE_PATH=data/source_store.sqlite3`

除 Jina Reader 和 GitHub 公共 API 外，其他外部 API key 都是可选。未配置时 connector 应返回明确的 disabled event，而不是抛出未捕获异常。

## 验收标准

- 可以创建 official source seed。
- 可以用 Jina Reader 抓取一个官方页面并写入 `raw_documents`。
- 相同内容重复抓取不会重复生成 document。
- 可以从官方页面正文抽取 `EvidenceItem`。
- `query_evidence()` 能按竞品和维度返回 evidence。
- Collector prompt 能包含 evidence 片段和 URL。
- 后端测试覆盖 source store、official connector、evidence extractor、evidence service。
- 不需要真实 API key 也能跑完整测试；外部请求使用 mock。

## 风险

- Jina Reader 对部分页面可能返回空内容或被目标站点限制，需要记录失败事件。
- 新闻、社媒、财务、专利 API 的成本和权限差异很大，不能在初版强依赖。
- 社交媒体噪音高，默认可信度必须低，不能直接支撑确定性结论。
- 官方页面也可能有营销口径，Verifier 仍需区分“官方声称”和“事实指标”。
