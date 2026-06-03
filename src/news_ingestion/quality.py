from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


CN_TZ = ZoneInfo("Asia/Shanghai")
ARTICLE_SCHEMA_VERSION = "2.0"
METRIC_FIELDS = ["read_count", "view_count", "comment_count", "like_count", "favorite_count", "share_count", "repost_count"]

DEFAULT_RULES = {
    "required_fields": ["title", "url", "source", "crawled_at"],
    "recommended_fields": ["published_at", "content"],
    "thresholds": {
        "min_title_chars": 6,
        "min_content_chars_for_full_score": 180,
        "min_content_chars_before_flag": 60,
        "valid_score": 0.75,
        "review_score": 0.45,
        "published_after_crawled_tolerance_minutes": 10,
    },
    "weights": {
        "field_completeness": 0.35,
        "content_readability": 0.25,
        "timestamp_trust": 0.2,
        "source_authority": 0.2,
    },
    "critical_flags": [
        "missing_title",
        "missing_url",
        "missing_source",
        "missing_crawled_at",
        "invalid_url",
        "invalid_crawled_at",
    ],
}


def build_source_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for source in registry.get("sources", []):
        source_id = source.get("source_id")
        name = source.get("name")
        if source_id:
            index[str(source_id)] = source
        if name:
            index[str(name)] = source
    return index


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def has_timezone(value: datetime | None) -> bool:
    return bool(value and value.tzinfo and value.tzinfo.utcoffset(value) is not None)


def is_valid_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def source_authority_score(record: dict[str, Any], source_index: dict[str, dict[str, Any]]) -> tuple[float, str]:
    source_key = record.get("source_id") or record.get("source")
    source = source_index.get(str(source_key), {})
    tier = source.get("tier") or record.get("source_tier") or "UNKNOWN"
    tier_score = {"T0": 1.0, "T1": 0.88, "T2": 0.62, "T3": 0.72, "UNKNOWN": 0.5}
    return float(source.get("quality_weight", tier_score.get(str(tier), 0.5))), str(tier)


def compact_text(value: Any, max_length: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if max_length is not None:
        return text[:max_length]
    return text


def as_cn_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=CN_TZ)
    return value.astimezone(CN_TZ)


def date_part(value: datetime | None) -> str | None:
    normalized = as_cn_datetime(value)
    return normalized.date().isoformat() if normalized else None


def age_minutes(published_at: datetime | None, crawled_at: datetime | None) -> float | None:
    published = as_cn_datetime(published_at)
    crawled = as_cn_datetime(crawled_at)
    if not published or not crawled:
        return None
    return round((crawled - published).total_seconds() / 60, 2)


def quality_grade(score: float, status: str) -> str:
    if status == "rejected":
        return "D"
    if score >= 0.95:
        return "A"
    if score >= 0.85:
        return "B"
    if score >= 0.75:
        return "C"
    return "R"


def metric_value(metrics: dict[str, Any], field: str) -> int | None:
    value = metrics.get(field)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def engagement_strength(metrics: dict[str, Any]) -> float:
    weights = {
        "read_count": 1.0,
        "view_count": 1.0,
        "comment_count": 3.0,
        "like_count": 1.5,
        "favorite_count": 1.8,
        "share_count": 2.2,
        "repost_count": 2.5,
    }
    score = 0.0
    for field, weight in weights.items():
        value = metric_value(metrics, field)
        if value is not None and value > 0:
            score += math.log10(value + 1) * weight
    return round(score, 4)


def rank_percentile(prominence: dict[str, Any]) -> float | None:
    rank = prominence.get("list_rank")
    size = prominence.get("list_size")
    if not isinstance(rank, int) or not isinstance(size, int) or size <= 0:
        return None
    return round(max(0.0, (size - rank + 1) / size), 4)


def hotness_score(quality_score: float, prominence: dict[str, Any], metrics: dict[str, Any]) -> float:
    source_priority = prominence.get("source_priority")
    priority_score = float(source_priority or 0) * 3.0
    rank_score = (rank_percentile(prominence) or 0.0) * 35.0
    metric_score = engagement_strength(metrics) * 3.0
    return round(quality_score * 30.0 + priority_score + rank_score + metric_score, 4)


def build_clear_fields(
    normalized: dict[str, Any],
    source_meta: dict[str, Any],
    quality_score: float,
    status: str,
    flags: list[str],
    published_at: datetime | None,
    crawled_at: datetime | None,
) -> dict[str, Any]:
    hot_features = normalized.get("hot_features") or {}
    prominence = hot_features.get("source_prominence") or {}
    metrics = hot_features.get("engagement_metrics") or {}
    counts = {field: metric_value(metrics, field) for field in METRIC_FIELDS}
    available_metrics = [field for field in METRIC_FIELDS if counts.get(field) is not None]
    missing_metrics = [field for field in METRIC_FIELDS if counts.get(field) is None]
    content = str(normalized.get("content") or "")
    title = str(normalized.get("title") or "")
    age_at_crawl = age_minutes(published_at, crawled_at)

    source_info = {
        "id": normalized.get("source_id"),
        "name": normalized.get("source"),
        "tier": normalized.get("source_tier"),
        "role": source_meta.get("role"),
        "priority": source_meta.get("priority") or prominence.get("source_priority"),
        "section": normalized.get("section"),
    }
    time_info = {
        "published_at": normalized.get("published_at"),
        "published_date": date_part(published_at),
        "crawled_at": normalized.get("crawled_at"),
        "crawl_date": date_part(crawled_at),
        "timezone": "Asia/Shanghai",
        "age_minutes_at_crawl": age_at_crawl,
        "published_after_crawl": age_at_crawl is not None and age_at_crawl < 0,
    }
    content_info = {
        "title_length": len(title),
        "content_length": len(content),
        "has_content": bool(content),
        "excerpt": compact_text(content, 240),
        "author": normalized.get("author"),
        "keywords": normalized.get("keywords") or [],
    }
    quality = {
        "status": status,
        "score": quality_score,
        "grade": quality_grade(quality_score, status),
        "flags": sorted(set(flags)),
        "review_required": status == "review" or bool(set(flags) - {"missing_published_at", "no_engagement_metrics_found"}),
        "downstream_usable": status in {"valid", "review"},
    }
    engagement = {
        "has_any_metric": bool(available_metrics),
        "available_metrics": available_metrics,
        "missing_metrics": missing_metrics,
        "available_metric_count": len(available_metrics),
        "counts": counts,
        "score": engagement_strength(metrics),
        "metric_source": metrics.get("source"),
        "collected_at": metrics.get("collected_at"),
        "quality_flags": metrics.get("quality_flags") or [],
        "raw": metrics.get("raw") or {},
    }
    hotness = {
        "score": hotness_score(quality_score, prominence, metrics),
        "list_rank": prominence.get("list_rank"),
        "list_size": prominence.get("list_size"),
        "rank_percentile": rank_percentile(prominence),
        "source_priority": source_info["priority"],
        "source_tier": source_info["tier"],
        "has_engagement_metrics": engagement["has_any_metric"],
        "engagement_score": engagement["score"],
    }
    extraction = {
        "entrypoint_url": normalized.get("fetch_entrypoint") or prominence.get("entrypoint"),
        "raw_html_path": normalized.get("raw_html_path"),
        "list_rank": prominence.get("list_rank"),
        "list_size": prominence.get("list_size"),
        "captured_at": prominence.get("captured_at") or normalized.get("crawled_at"),
        "method": normalized.get("section") or "source_adapter",
    }
    diagnostics = {
        "content_hash": normalized.get("content_hash"),
        "title_hash": normalized.get("title_hash"),
        "quality_flags": sorted(set(flags)),
    }
    return {
        "source_info": source_info,
        "time_info": time_info,
        "content_info": content_info,
        "quality": quality,
        "hotness": hotness,
        "engagement": engagement,
        "extraction": extraction,
        "diagnostics": diagnostics,
    }


def ordered_record(normalized: dict[str, Any]) -> dict[str, Any]:
    preferred_keys = [
        "schema_version",
        "record_type",
        "article_id",
        "title",
        "url",
        "source",
        "source_id",
        "source_tier",
        "published_at",
        "crawled_at",
        "status",
        "quality_score",
        "quality_flags",
        "hotness",
        "engagement",
        "source_info",
        "time_info",
        "content_info",
        "extraction",
        "quality",
        "content",
        "author",
        "section",
        "keywords",
        "hot_features",
        "diagnostics",
        "content_hash",
        "title_hash",
        "raw_html_path",
        "fetch_entrypoint",
    ]
    ordered = {key: normalized[key] for key in preferred_keys if key in normalized}
    for key, value in normalized.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def evaluate_record(
    record: dict[str, Any],
    registry: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or {"sources": []}
    rules = rules or DEFAULT_RULES
    thresholds = rules.get("thresholds", DEFAULT_RULES["thresholds"])
    weights = rules.get("weights", DEFAULT_RULES["weights"])
    source_index = build_source_index(registry)

    normalized = dict(record)
    flags: list[str] = list(normalized.get("quality_flags") or [])

    title = str(normalized.get("title") or "").strip()
    url = str(normalized.get("url") or "").strip()
    source = str(normalized.get("source") or "").strip()
    content = str(normalized.get("content") or "").strip()

    if not title:
        flags.append("missing_title")
    elif len(title) < thresholds.get("min_title_chars", 6):
        flags.append("short_title")
    if not url:
        flags.append("missing_url")
    elif not is_valid_url(url):
        flags.append("invalid_url")
    if not source:
        flags.append("missing_source")

    crawled_at = parse_dt(normalized.get("crawled_at"))
    published_at = parse_dt(normalized.get("published_at"))
    if not normalized.get("crawled_at"):
        flags.append("missing_crawled_at")
    elif crawled_at is None:
        flags.append("invalid_crawled_at")
    elif not has_timezone(crawled_at):
        flags.append("crawled_at_missing_timezone")

    if not normalized.get("published_at"):
        flags.append("missing_published_at")
    elif published_at is None:
        flags.append("invalid_published_at")
    elif not has_timezone(published_at):
        flags.append("published_at_missing_timezone")

    if published_at and crawled_at:
        tolerance = timedelta(minutes=thresholds.get("published_after_crawled_tolerance_minutes", 10))
        if published_at - crawled_at > tolerance:
            flags.append("published_after_crawled")

    min_content_flag = thresholds.get("min_content_chars_before_flag", 60)
    full_content_len = thresholds.get("min_content_chars_for_full_score", 180)
    if not content:
        flags.append("missing_content")
    elif len(content) < min_content_flag:
        flags.append("short_content")

    required_fields = rules.get("required_fields", DEFAULT_RULES["required_fields"])
    recommended_fields = rules.get("recommended_fields", DEFAULT_RULES["recommended_fields"])
    required_present = sum(1 for field in required_fields if normalized.get(field))
    recommended_present = sum(1 for field in recommended_fields if normalized.get(field))
    field_score = (required_present + 0.5 * recommended_present) / (len(required_fields) + 0.5 * len(recommended_fields))

    content_score = min(len(content) / max(full_content_len, 1), 1.0)
    timestamp_score = 1.0
    if "missing_published_at" in flags:
        timestamp_score -= 0.35
    if "invalid_published_at" in flags or "invalid_crawled_at" in flags:
        timestamp_score -= 0.5
    if "published_after_crawled" in flags:
        timestamp_score -= 0.35
    if "published_at_missing_timezone" in flags or "crawled_at_missing_timezone" in flags:
        timestamp_score -= 0.15
    timestamp_score = max(timestamp_score, 0.0)

    source_key = normalized.get("source_id") or normalized.get("source")
    source_meta = source_index.get(str(source_key), {})
    authority_score, source_tier = source_authority_score(normalized, source_index)
    quality_score = (
        field_score * weights.get("field_completeness", 0.35)
        + content_score * weights.get("content_readability", 0.25)
        + timestamp_score * weights.get("timestamp_trust", 0.2)
        + authority_score * weights.get("source_authority", 0.2)
    )
    quality_score = round(max(min(quality_score, 1.0), 0.0), 4)

    critical_flags = set(rules.get("critical_flags", DEFAULT_RULES["critical_flags"]))
    has_critical = any(flag in critical_flags for flag in flags)
    if has_critical:
        status = "rejected"
    elif quality_score >= thresholds.get("valid_score", 0.75):
        status = "valid"
    elif quality_score >= thresholds.get("review_score", 0.45):
        status = "review"
    else:
        status = "rejected"

    stable_id_base = url if is_valid_url(url) else f"{source}|{title}|{normalized.get('published_at') or normalized.get('crawled_at')}"
    normalized["article_id"] = normalized.get("article_id") or sha256_text(stable_id_base)[:24]
    normalized["source_tier"] = normalized.get("source_tier") or source_tier
    normalized["title"] = title
    normalized["url"] = url
    normalized["source"] = source
    normalized["content"] = content or None
    normalized["content_hash"] = normalized.get("content_hash") or (sha256_text(content) if content else None)
    normalized["title_hash"] = normalized.get("title_hash") or (sha256_text(title) if title else None)
    normalized["quality_score"] = quality_score
    normalized["quality_flags"] = sorted(set(flags))
    normalized["status"] = status
    normalized.setdefault("keywords", [])
    normalized.setdefault("author", None)
    normalized.setdefault("section", None)
    normalized.setdefault("raw_html_path", None)
    normalized.setdefault(
        "hot_features",
        {
            "source_prominence": {
                "list_rank": None,
                "list_size": None,
                "source_priority": None,
                "source_tier": normalized.get("source_tier"),
                "entrypoint": normalized.get("fetch_entrypoint"),
                "captured_at": normalized.get("crawled_at"),
            },
            "engagement_metrics": {
                "read_count": None,
                "view_count": None,
                "comment_count": None,
                "like_count": None,
                "favorite_count": None,
                "share_count": None,
                "repost_count": None,
                "collected_at": normalized.get("crawled_at"),
                "source": "not_available",
                "available_fields": [],
                "missing_fields": [
                    "read_count",
                    "view_count",
                    "comment_count",
                    "like_count",
                    "favorite_count",
                    "share_count",
                    "repost_count",
                ],
                "quality_flags": ["no_engagement_metrics_found"],
                "raw": {},
            },
        },
    )
    clear_fields = build_clear_fields(normalized, source_meta, quality_score, status, flags, published_at, crawled_at)
    normalized["schema_version"] = ARTICLE_SCHEMA_VERSION
    normalized["record_type"] = "finance_news_article"
    normalized.update(clear_fields)
    return ordered_record(normalized)
