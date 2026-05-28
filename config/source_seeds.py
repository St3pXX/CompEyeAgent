"""Default source seed registry for Phase 2 source intelligence."""

from __future__ import annotations

from models.source_layer import RefreshCadence, SourceProvider, SourceSeed


DEFAULT_SOURCE_SEEDS: tuple[SourceSeed, ...] = (
    SourceSeed(
        provider=SourceProvider.OFFICIAL,
        competitor="钉钉",
        url="https://www.dingtalk.com",
        label="钉钉官网",
        cadence=RefreshCadence.DAILY,
        metadata={"dimension": "产品", "indicators": ["官方介绍"]},
    ),
    SourceSeed(
        provider=SourceProvider.OFFICIAL,
        competitor="钉钉",
        url="https://www.dingtalk.com/pricing",
        label="钉钉定价页",
        cadence=RefreshCadence.DAILY,
        metadata={"dimension": "定价", "indicators": ["免费套餐", "付费套餐"]},
    ),
    SourceSeed(
        provider=SourceProvider.OFFICIAL,
        competitor="飞书",
        url="https://www.feishu.cn",
        label="飞书官网",
        cadence=RefreshCadence.DAILY,
        metadata={"dimension": "产品", "indicators": ["官方介绍"]},
    ),
    SourceSeed(
        provider=SourceProvider.OFFICIAL,
        competitor="飞书",
        url="https://www.feishu.cn/pricing",
        label="飞书定价页",
        cadence=RefreshCadence.DAILY,
        metadata={"dimension": "定价", "indicators": ["免费套餐", "付费套餐"]},
    ),
    SourceSeed(
        provider=SourceProvider.OFFICIAL,
        competitor="企业微信",
        url="https://work.weixin.qq.com",
        label="企业微信官网",
        cadence=RefreshCadence.DAILY,
        metadata={"dimension": "产品", "indicators": ["官方介绍"]},
    ),
    SourceSeed(
        provider=SourceProvider.NEWS,
        competitor="钉钉",
        url="newsapi://everything?query=钉钉",
        label="钉钉新闻搜索",
        cadence=RefreshCadence.DAILY,
        metadata={"query": "钉钉", "dimension": "市场动态", "indicators": ["发布", "合作", "融资"]},
    ),
    SourceSeed(
        provider=SourceProvider.NEWS,
        competitor="飞书",
        url="newsapi://everything?query=飞书",
        label="飞书新闻搜索",
        cadence=RefreshCadence.DAILY,
        metadata={"query": "飞书", "dimension": "市场动态", "indicators": ["发布", "合作", "融资"]},
    ),
    SourceSeed(
        provider=SourceProvider.NEWS,
        competitor="企业微信",
        url="newsapi://everything?query=企业微信",
        label="企业微信新闻搜索",
        cadence=RefreshCadence.DAILY,
        metadata={"query": "企业微信", "dimension": "市场动态", "indicators": ["发布", "合作", "融资"]},
    ),
)


def default_source_seeds() -> list[SourceSeed]:
    """Return fresh seed instances so callers can safely mutate metadata."""

    return [seed.model_copy(deep=True) for seed in DEFAULT_SOURCE_SEEDS]
