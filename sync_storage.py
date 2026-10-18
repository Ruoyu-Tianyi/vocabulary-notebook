"""Local materialized cache and immutable, mergeable operations.

Drive never receives config, OAuth tokens or a mutable whole-library overwrite.
Keep operations/tombstones: an old offline computer must not resurrect deleted words.
"""
import copy
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fsrs

DEFAULT_BOOK = "default"
VERSION = 1


def atomic_write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    tmp.replace(path)


def _time(value):
    # Python 3.9 accepts an explicit UTC offset, but not the ISO UTC suffix Z.
    if isinstance(value, str) and value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone(timedelta(hours=8))) if parsed.tzinfo is None else parsed


def review_state(base, events):
    state = copy.deepcopy(base)
    for event in sorted(events, key=lambda e: (_time(e["at"]), e["id"])):
        rating = event["rating"]
        now = _time(event["at"])
        if state:
            last = _time(state["last_review_at"])
            now = max(now, last)  # clock skew cannot produce negative elapsed time
            d, s = fsrs.update(float(state["d"]), float(state["s"]), rating,
                               (now - last).total_seconds() / 86400)
            first = state.get("first_review_at", state["last_review_at"])
            reps, lapses = state.get("reps", 0) + 1, state.get("lapses", 0) + (rating == 1)
        else:
            d, s = fsrs.initial_difficulty(rating), fsrs.initial_stability(rating)
            first, reps, lapses = now.isoformat(), 1, int(rating == 1)
        state = {"d": d, "s": s, "first_review_at": first,
                 "last_review_at": now.isoformat(),
                 "due_at": (now + timedelta(days=fsrs.next_interval(s))).isoformat(),
                 "reps": reps, "lapses": lapses}
    return state


def fresh():
    return {"version": VERSION, "device_id": uuid.uuid4().hex, "clock": 0,
            "operations": {}, "uploaded": [], "account": ""}


def _add(meta, entity, entity_id, field, value):
    meta["clock"] += 1
    op = {"id": uuid.uuid4().hex, "clock": meta["clock"], "device": meta["device_id"],
          "entity": entity, "entity_id": entity_id, "field": field, "value": value}
    meta["operations"][op["id"]] = op


def validate_operations(ops):
    if not isinstance(ops, list) or len(ops) > 500000:
        raise ValueError("云端变更格式无效")
    for op in ops:
        if (not isinstance(op, dict) or set(op) != {"id", "clock", "device", "entity", "entity_id", "field", "value"}
                or type(op["clock"]) is not int or not 1 <= op["clock"] < 2**63
                or op["entity"] not in ("word", "notebook")
                or any(not isinstance(op[k], str) or not 1 <= len(op[k]) <= 200
                       for k in ("id", "device", "entity_id", "field"))):
            raise ValueError("云端变更格式无效")
        field, value = op["field"], op["value"]
        allowed = ({"word", "definition", "phonetic", "example", "created_at", "notebook_id", "deleted", "srs_base", "review"}
                   if op["entity"] == "word" else {"name", "description", "created_at"})
        if field not in allowed:
            raise ValueError("不支持的云端字段")
        if field == "review":
            if (not isinstance(value, dict) or set(value) != {"id", "rating", "at"}
                    or not isinstance(value["id"], str) or not value["id"]
                    or type(value["rating"]) is not int or value["rating"] not in (1, 2, 3, 4)):
                raise ValueError("云端复习记录无效")
            _time(value["at"])
        elif field == "srs_base":
            if value is not None:
                if not isinstance(value, dict):
                    raise ValueError("旧复习状态无效")
                d, s = float(value["d"]), float(value["s"])
                if not math.isfinite(d) or not 1 <= d <= 10 or not math.isfinite(s) or not 0 < s < 100000:
                    raise ValueError("旧复习状态无效")
                _time(value["last_review_at"])
                if any(type(value.get(k, 0)) is not int or value.get(k, 0) < 0 for k in ("reps", "lapses")):
                    raise ValueError("旧复习次数无效")
        elif field == "deleted":
            if value is not True:
                raise ValueError("删除标记无效")
        elif not isinstance(value, str) or len(value) > 100000:
            raise ValueError("云端文本字段无效")


def materialize(meta):
    entities, ranks, deleted, reviews, review_ranks = {}, {}, set(), {}, {}
    for op in meta["operations"].values():
        key = (op["entity"], op["entity_id"])
        entity = entities.setdefault(key, {"id": op["entity_id"]})
        field, value = op["field"], op["value"]
        if field == "deleted":
            deleted.add(key)
        elif field == "review":
            rank = (op["clock"], op["device"], op["id"])
            event_key = (key, value["id"])
            if rank > review_ranks.get(event_key, (0, "", "")):
                review_ranks[event_key] = rank
                reviews.setdefault(key, {})[value["id"]] = value
        else:
            rank = (op["clock"], op["device"], op["id"])
            if rank > ranks.get((key, field), (0, "", "")):
                ranks[(key, field)] = rank
                entity[field] = copy.deepcopy(value)
    books, words = [], []
    for key, entity in entities.items():
        if key in deleted:
            continue
        if key[0] == "notebook":
            if key[1] == DEFAULT_BOOK:
                # The implicit default book can have only a description operation.
                # Preserve its fallback fields when materializing that partial state.
                entity.setdefault("name", "默认单词本")
                entity.setdefault("description", "原词库与日常积累")
            books.append(entity)
        elif entity.get("word"):
            entity.setdefault("notebook_id", DEFAULT_BOOK)
            for field in ("definition", "phonetic", "example", "created_at"):
                entity.setdefault(field, "")
            history = sorted(reviews.get(key, {}).values(), key=lambda e: (_time(e["at"]), e["id"]))
            base = entity.pop("srs_base", None)
            if history:
                entity["review_history"] = history
            state = review_state(base, history)
            if state:
                entity["srs"] = state
            words.append(entity)
    if not any(b["id"] == DEFAULT_BOOK for b in books):
        books.append({"id": DEFAULT_BOOK, "name": "默认单词本", "description": "原词库与日常积累"})
    return {"words": sorted(words, key=lambda w: (w["created_at"], w["id"])),
            "notebooks": sorted(books, key=lambda b: (b.get("created_at", ""), b["id"])), "_sync": meta}


def read(path: Path):
    if not path.exists():
        return materialize(fresh())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("words"), list):
            raise ValueError("invalid library")
        if "_sync" not in data:
            backup = path.with_suffix(path.suffix + ".legacy.bak")
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            data = commit(path, data, previous={"words": [], "notebooks": [], "_sync": fresh()})
        if data["_sync"].get("version") != VERSION:
            raise ValueError("不支持的词库版本，请升级应用")
        for book in data.get("notebooks", []):
            if book.get("id") == DEFAULT_BOOK:
                book.setdefault("name", "默认单词本")
                book.setdefault("description", "原词库与日常积累")
        return data
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Fail closed. Never replace a damaged cache with an empty cloud library.
        raise ValueError(f"词库文件损坏，请从 {path}.bak 恢复；原文件已保留") from exc


def commit(path: Path, data: dict, previous=None):
    previous = read(path) if previous is None else previous
    meta = copy.deepcopy(previous["_sync"])
    for entity, collection in (("notebook", "notebooks"), ("word", "words")):
        old = {item["id"]: item for item in previous.get(collection, [])}
        new = {item["id"]: item for item in data.get(collection, previous.get(collection, []))}
        for entity_id, item in new.items():
            prior = old.get(entity_id, {})
            for field, value in item.items():
                if field in ("id", "srs", "review_history"):
                    continue
                if field not in prior or prior[field] != value:
                    _add(meta, entity, entity_id, field, value)
            if entity == "word":
                if not prior and item.get("srs") and not item.get("review_history"):
                    _add(meta, entity, entity_id, "srs_base", item["srs"])
                seen = {e["id"] for e in prior.get("review_history", [])}
                for event in item.get("review_history", []):
                    if event["id"] not in seen:
                        _add(meta, entity, entity_id, "review", event)
        if entity == "word":
            for entity_id in old.keys() - new.keys():
                _add(meta, entity, entity_id, "deleted", True)
    result = materialize(meta)
    atomic_write(path, result)
    return result


def merge(path: Path, operations):
    validate_operations(operations)
    data = read(path)
    meta = data["_sync"]
    count = 0
    for op in operations:
        previous = meta["operations"].get(op["id"])
        if previous is not None and previous != op:
            raise ValueError("云端变更 ID 冲突，已停止同步")
        if previous is None:
            meta["operations"][op["id"]] = op
            meta["clock"] = max(meta["clock"], op["clock"])
            count += 1
    result = materialize(meta)
    atomic_write(path, result)
    return count
