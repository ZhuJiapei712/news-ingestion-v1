from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse


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
    return normalized
