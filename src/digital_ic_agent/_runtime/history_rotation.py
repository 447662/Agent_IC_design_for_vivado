import gzip
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_ACTIVE_RECORD_LIMIT = 200


def normalize_active_record_limit(active_limit: int | None) -> int | None:
    if active_limit is None:
        return None
    if (
        isinstance(active_limit, bool)
        or not isinstance(active_limit, int)
        or active_limit < 1
    ):
        raise ValueError(
            "active record limit must be a positive integer or None"
        )
    return active_limit


def archive_path_for(active_path: Path) -> Path:
    active_path = Path(active_path)
    name = active_path.name
    if name.endswith(".jsonl"):
        stem = name[:-len(".jsonl")]
    elif name.endswith(".json"):
        stem = name[:-len(".json")]
    else:
        stem = active_path.stem
    return active_path.with_name("{}.archive.jsonl.gz".format(stem))


def _append_archived_records(
    archive_path: Path,
    records: Sequence[Mapping[str, Any]],
) -> None:
    if not records:
        return
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(
        archive_path,
        "at",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        for record in records:
            stream.write(
                json.dumps(dict(record), ensure_ascii=False) + "\n"
            )


def rotate_json_records(
    records: Sequence[Mapping[str, Any]],
    active_path: Path,
    *,
    active_limit: int | None = DEFAULT_ACTIVE_RECORD_LIMIT,
) -> tuple[list[dict[str, Any]], Path, int]:
    normalized_limit = normalize_active_record_limit(active_limit)
    normalized_records = [dict(record) for record in records]
    archive_path = archive_path_for(active_path)
    if (
        normalized_limit is None
        or len(normalized_records) <= normalized_limit
    ):
        return normalized_records, archive_path, 0

    archive_count = len(normalized_records) - normalized_limit
    archived_records = normalized_records[:archive_count]
    active_records = normalized_records[archive_count:]
    _append_archived_records(archive_path, archived_records)
    return active_records, archive_path, archive_count


def build_rotation_metadata(
    existing: Mapping[str, Any] | None,
    *,
    active_limit: int | None,
    archive_path: Path,
    newly_archived: int,
    count_key: str,
) -> dict[str, Any] | None:
    normalized_limit = normalize_active_record_limit(active_limit)
    existing = dict(existing or {})
    previous_count = existing.get(count_key, 0)
    if (
        isinstance(previous_count, bool)
        or not isinstance(previous_count, int)
        or previous_count < 0
    ):
        previous_count = 0
    archived_count = previous_count + newly_archived
    if normalized_limit is None and archived_count == 0:
        return None
    return {
        "active_limit": normalized_limit,
        "archive_path": archive_path.name,
        count_key: archived_count,
    }
