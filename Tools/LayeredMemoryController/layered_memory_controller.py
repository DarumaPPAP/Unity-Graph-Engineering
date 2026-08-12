#!/usr/bin/env python3
"""Evidence-preserving layered memory controller for Unity Graph Engineering.

Non-personal profiles use a safe-only index and never scan unindexed memory
records. Unindexed/legacy records therefore fail closed as project-internal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.2"
MAX_RAW_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_ITEMS = 8
DEFAULT_MAX_CHARS = 6000
MAX_ITEMS = 20
MAX_CHARS = 12000

LAYERS = ("L0_raw_evidence", "L1_atom", "L2_scenario", "L3_reusable_candidate")
LAYER_DIR = dict(zip(LAYERS, ("L0", "L1", "L2", "L3")))
LAYER_WEIGHT = dict(zip(LAYERS, (1.0, 2.0, 3.0, 4.0)))
PROFILES = {"generic_planning", "personal_full_control", "team_safe_import"}
SAFE_SCOPES = {"portable_artifact", "public_reference"}
SCOPE_RANK = {"public_reference": 0, "portable_artifact": 1, "project_internal": 2}
CONFIDENCE = {"verified", "probable", "unverified"}
REVIEW = {"not_required", "pending", "approved", "rejected"}
PROMOTION = {"none", "execution_reference", "unityagent_knowledge", "user_policy_candidate"}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TOKEN_RE = re.compile(r"[A-Za-z0-9_./:+-]{2,}")
SECRET_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)\b"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9+/=_\-.]{12,}"
        ),
    ),
)


class MemoryErrorContract(Exception):
    def __init__(self, code: str, message: str, status: str = "invalid_request") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: Any, field: str = "id") -> str:
    text = str(value or "").strip()
    if not ID_RE.fullmatch(text):
        raise MemoryErrorContract("invalid_id", f"{field} must match {ID_RE.pattern}")
    return text


def _list(value: Any, field: str, required: bool = False) -> list[str]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise MemoryErrorContract("invalid_request", f"{field} must be an array")
    result = [str(item).strip() for item in value]
    if any(not item for item in result):
        raise MemoryErrorContract("invalid_request", f"{field} contains an empty value")
    if required and not result:
        raise MemoryErrorContract("invalid_request", f"{field} must not be empty")
    return result


def _profile(request: dict[str, Any]) -> str:
    profile = str(request.get("execution_profile", "generic_planning"))
    if profile not in PROFILES:
        raise MemoryErrorContract("invalid_profile", f"unsupported execution_profile: {profile}")
    return profile


def _scope(value: Any, field: str = "scope_class") -> str:
    scope = str(value or "portable_artifact").strip()
    if scope not in SCOPE_RANK:
        raise MemoryErrorContract("invalid_scope", f"{field} must be one of {sorted(SCOPE_RANK)}")
    return scope


def _scope_allowed(profile: str, scope: str) -> bool:
    return profile == "personal_full_control" or scope in SAFE_SCOPES


def _guard_scope(profile: str, scope: str, action: str) -> None:
    if not _scope_allowed(profile, scope):
        raise MemoryErrorContract(
            "memory_scope_forbidden",
            f"{profile} may not {action} {scope} memory",
            "blocked",
        )


def _memory_root(workspace: Path) -> Path:
    return workspace / "STATE" / "memory"


def _record_path(workspace: Path, layer: str, memory_id: str) -> Path:
    return _memory_root(workspace) / LAYER_DIR[layer] / f"{memory_id}.json"


def _raw_path(workspace: Path, evidence_id: str) -> Path:
    return workspace / "Evidence" / "raw" / f"{evidence_id}.txt"


def _event_path(workspace: Path) -> Path:
    return _memory_root(workspace) / "events.jsonl"


def _safe_index_path(workspace: Path) -> Path:
    return _memory_root(workspace) / "safe-index.jsonl"


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def _append_event(workspace: Path, value: dict[str, Any]) -> None:
    _append_jsonl(_event_path(workspace), value)


def _envelope(operation: str, status: str, data: Any = None, diagnostics=None, mutated=False) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "controller": "layered_memory",
        "operation": operation,
        "status": status,
        "mutated": mutated,
        "data": data,
        "diagnostics": diagnostics or [],
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MemoryErrorContract("memory_not_found", f"memory record not found: {path.stem}") from exc
    except json.JSONDecodeError as exc:
        raise MemoryErrorContract("memory_corrupt", f"invalid JSON in {path}: {exc}", "blocked") from exc
    if not isinstance(value, dict):
        raise MemoryErrorContract("memory_corrupt", f"record must be an object: {path}", "blocked")
    return value


def _safe_index_entries(workspace: Path) -> dict[str, dict[str, str]]:
    """Read only non-sensitive routing metadata; project_internal is never indexed."""
    path = _safe_index_path(workspace)
    if not path.is_file():
        return {}
    entries: dict[str, dict[str, str]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MemoryErrorContract("safe_index_unreadable", str(exc), "blocked") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MemoryErrorContract("safe_index_corrupt", f"safe index line {line_number} is invalid JSON", "blocked") from exc
        if not isinstance(value, dict):
            raise MemoryErrorContract("safe_index_corrupt", f"safe index line {line_number} must be an object", "blocked")
        memory_id = _safe_id(value.get("memory_id"), "safe_index.memory_id")
        layer = str(value.get("layer", ""))
        scope = str(value.get("scope_class", ""))
        if layer not in LAYERS or scope not in SAFE_SCOPES:
            raise MemoryErrorContract("safe_index_corrupt", "safe index may contain only safe scopes and known layers", "blocked")
        entry = {"memory_id": memory_id, "layer": layer, "scope_class": scope}
        previous = entries.get(memory_id)
        if previous is not None and previous != entry:
            raise MemoryErrorContract("safe_index_corrupt", f"conflicting safe index entry: {memory_id}", "blocked")
        entries[memory_id] = entry
    return entries


def _ensure_safe_index(workspace: Path, record: dict[str, Any]) -> None:
    scope = _record_scope(record)
    if scope not in SAFE_SCOPES:
        return
    memory_id = _safe_id(record.get("memory_id"), "memory_id")
    layer = str(record.get("layer", ""))
    expected = {"memory_id": memory_id, "layer": layer, "scope_class": scope}
    existing = _safe_index_entries(workspace).get(memory_id)
    if existing is not None:
        if existing != expected:
            raise MemoryErrorContract("safe_index_conflict", f"safe index conflicts for {memory_id}", "blocked")
        return
    _append_jsonl(_safe_index_path(workspace), expected)


def _load_record(workspace: Path, memory_id: str) -> dict[str, Any]:
    memory_id = _safe_id(memory_id, "memory_id")
    for layer in LAYERS:
        path = _record_path(workspace, layer, memory_id)
        if path.is_file():
            return _read_json(path)
    raise MemoryErrorContract("memory_not_found", f"memory record not found: {memory_id}")


def _record_scope(record: dict[str, Any]) -> str:
    # Legacy records without an explicit scope are treated as project-internal.
    if "scope_class" not in record:
        return "project_internal"
    return _scope(record.get("scope_class"))


def _load_accessible_record(workspace: Path, memory_id: str, profile: str, action: str) -> dict[str, Any]:
    memory_id = _safe_id(memory_id, "memory_id")
    if profile != "personal_full_control":
        entry = _safe_index_entries(workspace).get(memory_id)
        if entry is None:
            raise MemoryErrorContract(
                "memory_scope_forbidden",
                f"{profile} may not {action} unindexed/project-internal memory",
                "blocked",
            )
        record = _read_json(_record_path(workspace, entry["layer"], memory_id))
        if _record_scope(record) != entry["scope_class"] or record.get("layer") != entry["layer"]:
            raise MemoryErrorContract("safe_index_mismatch", f"safe index mismatch: {memory_id}", "blocked")
        return record
    record = _load_record(workspace, memory_id)
    _guard_scope(profile, _record_scope(record), action)
    return record


def _guard_secret(text: str, sensitivity: str) -> None:
    if sensitivity.lower() == "secret":
        raise MemoryErrorContract("secret_capture_forbidden", "secret-classified raw evidence must not be stored", "blocked")
    findings = [code for code, pattern in SECRET_PATTERNS if pattern.search(text)]
    if findings:
        raise MemoryErrorContract(
            "secret_capture_forbidden",
            f"raw evidence matched secret patterns: {', '.join(findings)}",
            "blocked",
        )


def _derive_scope(records: Iterable[dict[str, Any]], requested: Any = None) -> str:
    inherited_rank = max((SCOPE_RANK[_record_scope(record)] for record in records), default=0)
    inherited = next(name for name, rank in SCOPE_RANK.items() if rank == inherited_rank)
    if requested is None:
        return inherited
    requested_scope = _scope(requested)
    if SCOPE_RANK[requested_scope] < inherited_rank:
        raise MemoryErrorContract(
            "scope_downgrade_forbidden",
            f"requested scope {requested_scope} is less restrictive than inherited scope {inherited}",
            "blocked",
        )
    return requested_scope


def _validate_refs(
    workspace: Path,
    refs: list[str],
    expected_layer: str,
    field: str,
    profile: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    normalized = [_safe_id(ref, field) for ref in refs]
    records = []
    for ref in normalized:
        record = _load_accessible_record(workspace, ref, profile, "derive from")
        if record.get("layer") != expected_layer:
            raise MemoryErrorContract(
                "invalid_reference_layer",
                f"{field} {ref} must reference {expected_layer}, got {record.get('layer')}",
            )
        records.append(record)
    return normalized, records


def _relation_refs(workspace: Path, request: dict[str, Any], field: str, profile: str) -> list[str]:
    refs = [_safe_id(ref, field) for ref in _list(request.get(field), field)]
    for ref in refs:
        _load_accessible_record(workspace, ref, profile, "relate to")
    return refs


def capture_raw(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    evidence_id = _safe_id(request.get("evidence_id"), "evidence_id")
    profile = _profile(request)
    scope = _scope(request.get("scope_class", "portable_artifact"))
    _guard_scope(profile, scope, "capture")

    # Scope is checked before touching source_file. Critical for team_safe/generic.
    source = Path(str(request.get("source_file", ""))).expanduser().resolve()
    if not source.is_file():
        raise MemoryErrorContract("source_file_not_found", f"source_file does not exist: {source}")
    max_bytes = int(request.get("max_raw_bytes", MAX_RAW_BYTES))
    if not 1 <= max_bytes <= MAX_RAW_BYTES:
        raise MemoryErrorContract("invalid_max_raw_bytes", f"max_raw_bytes must be 1..{MAX_RAW_BYTES}")
    raw = source.read_bytes()
    if len(raw) > max_bytes:
        raise MemoryErrorContract("raw_evidence_too_large", f"raw evidence exceeds {max_bytes} bytes", "blocked")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MemoryErrorContract("raw_evidence_not_utf8", "raw evidence must be UTF-8 text", "blocked") from exc
    _guard_secret(text, str(request.get("sensitivity", "internal")))

    digest = hashlib.sha256(raw).hexdigest()
    raw_path = _raw_path(workspace, evidence_id)
    meta_path = _record_path(workspace, "L0_raw_evidence", evidence_id)
    if raw_path.exists():
        if hashlib.sha256(raw_path.read_bytes()).hexdigest() != digest:
            raise MemoryErrorContract("id_conflict", f"raw evidence {evidence_id} already has different content", "blocked")
        if meta_path.exists():
            existing = _read_json(meta_path)
            if existing.get("sha256") != digest or _record_scope(existing) != scope:
                raise MemoryErrorContract("id_conflict", f"metadata for {evidence_id} differs", "blocked")
            _ensure_safe_index(workspace, existing)
            return _envelope("capture_raw", "ok", existing, mutated=False)

    metadata = {
        "memory_id": evidence_id,
        "layer": "L0_raw_evidence",
        "created_at": str(request.get("created_at") or _now()),
        "statement": str(request.get("statement") or f"Raw evidence: {request.get('source_type', 'tool_output')}"),
        "raw_refs": [f"Evidence/raw/{evidence_id}.txt"],
        "atom_refs": [],
        "scenario_refs": [],
        "applicability": _list(request.get("applicability"), "applicability"),
        "limits": _list(request.get("limits"), "limits"),
        "confidence": "verified",
        "provenance": _list(request.get("provenance"), "provenance"),
        "promotion_target": "none",
        "review_status": "not_required",
        "supersedes": [],
        "conflicts_with": [],
        "source_type": str(request.get("source_type", "tool_output")),
        "sha256": digest,
        "byte_count": len(raw),
        "execution_profile": profile,
        "scope_class": scope,
        "sensitivity": str(request.get("sensitivity", "internal")),
        "repository": request.get("repository"),
        "unity_version": request.get("unity_version"),
        "platform": request.get("platform"),
        "run_id": request.get("run_id"),
        "tags": _list(request.get("tags"), "tags"),
    }
    if meta_path.exists():
        existing = _read_json(meta_path)
        if existing.get("sha256") != digest or _record_scope(existing) != scope:
            raise MemoryErrorContract("id_conflict", f"metadata for {evidence_id} differs", "blocked")
        metadata = existing

    mutated = False
    if not raw_path.exists():
        _atomic_text(raw_path, text)
        mutated = True
    if not meta_path.exists():
        _write_json(meta_path, metadata)
        mutated = True
    _ensure_safe_index(workspace, metadata)
    if mutated:
        _append_event(workspace, {
            "event": "memory_created", "memory_id": evidence_id, "layer": "L0_raw_evidence",
            "captured_at": _now(), "sha256": digest, "scope_class": scope,
        })
    return _envelope("capture_raw", "ok", metadata, mutated=mutated)


def _new_record(
    workspace: Path,
    request: dict[str, Any],
    layer: str,
    ref_field: str,
    ref_layer: str,
) -> dict[str, Any]:
    profile = _profile(request)
    memory_id = _safe_id(request.get("memory_id"), "memory_id")
    statement = str(request.get("statement", "")).strip()
    if not statement:
        raise MemoryErrorContract("missing_statement", "statement must not be empty")
    confidence = str(request.get("confidence", "unverified"))
    if confidence not in CONFIDENCE:
        raise MemoryErrorContract("invalid_confidence", f"unsupported confidence: {confidence}")
    review = str(request.get("review_status", "pending" if layer == "L3_reusable_candidate" else "not_required"))
    if review not in REVIEW:
        raise MemoryErrorContract("invalid_review_status", f"unsupported review_status: {review}")
    promotion = str(request.get("promotion_target", "none"))
    if promotion not in PROMOTION:
        raise MemoryErrorContract("invalid_promotion_target", f"unsupported promotion_target: {promotion}")

    refs, parents = _validate_refs(
        workspace,
        _list(request.get(ref_field), ref_field, required=True),
        ref_layer,
        ref_field,
        profile,
    )
    scope = _derive_scope(parents, request.get("scope_class"))
    _guard_scope(profile, scope, "create")
    supersedes = _relation_refs(workspace, request, "supersedes", profile)
    conflicts = _relation_refs(workspace, request, "conflicts_with", profile)
    if memory_id in supersedes or memory_id in conflicts:
        raise MemoryErrorContract("self_reference", "memory record cannot reference itself")
    return {
        "memory_id": memory_id,
        "layer": layer,
        "created_at": str(request.get("created_at") or _now()),
        "statement": statement,
        "raw_refs": refs if ref_field == "raw_refs" else [],
        "atom_refs": refs if ref_field == "atom_refs" else [],
        "scenario_refs": refs if ref_field == "scenario_refs" else [],
        "applicability": _list(request.get("applicability"), "applicability"),
        "limits": _list(request.get("limits"), "limits"),
        "confidence": confidence,
        "provenance": _list(request.get("provenance"), "provenance"),
        "promotion_target": promotion,
        "review_status": review,
        "supersedes": supersedes,
        "conflicts_with": conflicts,
        "repository": request.get("repository"),
        "unity_version": request.get("unity_version"),
        "platform": request.get("platform"),
        "tags": _list(request.get("tags"), "tags"),
        "execution_profile": profile,
        "scope_class": scope,
    }


def _store_record(workspace: Path, record: dict[str, Any], operation: str) -> dict[str, Any]:
    path = _record_path(workspace, record["layer"], record["memory_id"])
    if path.exists():
        existing = _read_json(path)
        if existing == record:
            _ensure_safe_index(workspace, existing)
            return _envelope(operation, "ok", existing, mutated=False)
        raise MemoryErrorContract(
            "id_conflict",
            f"{record['memory_id']} already exists; use supersedes/conflicts_with",
            "blocked",
        )
    _write_json(path, record)
    _ensure_safe_index(workspace, record)
    _append_event(workspace, {
        "event": "memory_created", "memory_id": record["memory_id"], "layer": record["layer"],
        "captured_at": _now(), "scope_class": record["scope_class"],
        "supersedes": record["supersedes"], "conflicts_with": record["conflicts_with"],
    })
    return _envelope(operation, "ok", record, mutated=True)


def create_atom(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    return _store_record(
        workspace,
        _new_record(workspace, request, "L1_atom", "raw_refs", "L0_raw_evidence"),
        "create_atom",
    )


def create_scenario(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    record = _new_record(workspace, request, "L2_scenario", "atom_refs", "L1_atom")
    if not record["applicability"]:
        raise MemoryErrorContract("missing_applicability", "L2 scenario requires applicability")
    if not record["limits"]:
        raise MemoryErrorContract("missing_limits", "L2 scenario requires limits")
    return _store_record(workspace, record, "create_scenario")


def create_candidate(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    record = _new_record(workspace, request, "L3_reusable_candidate", "scenario_refs", "L2_scenario")
    if not record["provenance"]:
        raise MemoryErrorContract("missing_provenance", "L3 reusable candidate requires provenance")
    if record["promotion_target"] == "none":
        raise MemoryErrorContract("missing_promotion_target", "L3 reusable candidate requires a promotion_target")
    return _store_record(workspace, record, "create_candidate")


def _records(workspace: Path, profile: str) -> list[dict[str, Any]]:
    if profile != "personal_full_control":
        records = []
        for memory_id, entry in sorted(_safe_index_entries(workspace).items()):
            record = _read_json(_record_path(workspace, entry["layer"], memory_id))
            if _record_scope(record) != entry["scope_class"] or record.get("layer") != entry["layer"]:
                raise MemoryErrorContract("safe_index_mismatch", f"safe index mismatch: {memory_id}", "blocked")
            records.append(record)
        return records
    result = []
    for layer in LAYERS:
        folder = _memory_root(workspace) / LAYER_DIR[layer]
        if folder.is_dir():
            result.extend(_read_json(path) for path in sorted(folder.glob("*.json")))
    return result


def _tokens(value: Any) -> set[str]:
    text = " ".join(map(str, value)) if isinstance(value, list) else str(value or "")
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _score(record: dict[str, Any], query: set[str], context: dict[str, Any]) -> float:
    searchable = set()
    for field in ("statement", "applicability", "limits", "provenance", "tags", "repository", "unity_version", "platform"):
        searchable |= _tokens(record.get(field))
    score = len(query & searchable) * 10.0 + LAYER_WEIGHT.get(record.get("layer"), 0.0)
    for field, bonus in (("repository", 4.0), ("unity_version", 2.0), ("platform", 2.0)):
        wanted = str(context.get(field) or "").lower()
        actual = str(record.get(field) or "").lower()
        if wanted and actual and wanted == actual:
            score += bonus
    if record.get("confidence") == "verified":
        score += 1.0
    return score


def _compact(record: dict[str, Any]) -> dict[str, Any]:
    list_fields = {"applicability", "limits", "provenance", "supersedes", "conflicts_with"}
    return {
        key: record.get(key, [] if key in list_fields else None)
        for key in (
            "memory_id", "layer", "statement", "confidence", "applicability", "limits", "provenance",
            "supersedes", "conflicts_with", "repository", "unity_version", "platform", "scope_class",
        )
    }


def retrieve(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(request)
    query_text = str(request.get("query", "")).strip()
    query = _tokens(query_text)
    max_items = int(request.get("max_items", DEFAULT_MAX_ITEMS))
    max_chars = int(request.get("max_chars", DEFAULT_MAX_CHARS))
    if not 1 <= max_items <= MAX_ITEMS:
        raise MemoryErrorContract("invalid_max_items", f"max_items must be 1..{MAX_ITEMS}")
    if not 256 <= max_chars <= MAX_CHARS:
        raise MemoryErrorContract("invalid_max_chars", f"max_chars must be 256..{MAX_CHARS}")
    requested_layers = request.get("layers")
    allowed = set(LAYERS) if requested_layers is None else set(_list(requested_layers, "layers"))
    unknown = allowed - set(LAYERS)
    if unknown:
        raise MemoryErrorContract("invalid_layer", f"unsupported layers: {sorted(unknown)}")

    context = {field: request.get(field) for field in ("repository", "unity_version", "platform")}
    ranked = []
    for record in _records(workspace, profile):
        if record.get("layer") not in allowed:
            continue
        # Personal scan still enforces record scope. Non-personal input came from the safe-only index.
        if not _scope_allowed(profile, _record_scope(record)):
            continue
        score = _score(record, query, context)
        base = LAYER_WEIGHT.get(record.get("layer"), 0.0) + (1.0 if record.get("confidence") == "verified" else 0.0)
        if query and score <= base:
            continue
        ranked.append((score, record))
    ranked.sort(
        key=lambda item: (item[0], LAYER_WEIGHT.get(item[1].get("layer"), 0.0), item[1].get("created_at", "")),
        reverse=True,
    )

    items, used, truncated = [], 0, False
    for score, record in ranked:
        if len(items) >= max_items:
            truncated = True
            break
        item = _compact(record)
        item["score"] = round(score, 3)
        size = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        if items and used + size > max_chars:
            truncated = True
            break
        if not items and size > max_chars:
            item["statement"] = str(item.get("statement") or "")[: max(64, max_chars // 2)]
            size = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
            truncated = True
        items.append(item)
        used += size

    diagnostics = []
    if profile != "personal_full_control":
        diagnostics.append({
            "code": "memory_scope_filtered",
            "message": "Non-personal retrieval uses the safe-only index; unindexed records are not inspected.",
        })
    return _envelope(
        "retrieve",
        "ok",
        {
            "query": query_text,
            "execution_profile": profile,
            "items": items,
            "item_count": len(items),
            "characters": used,
            "truncated": truncated,
            "raw_content_included": False,
            "retrieval_policy": "safe_index_then_layer_weighted_lexical_context_affinity",
        },
        diagnostics=diagnostics,
    )


def _children(record: dict[str, Any]) -> list[str]:
    field = {"L3_reusable_candidate": "scenario_refs", "L2_scenario": "atom_refs", "L1_atom": "raw_refs"}.get(record.get("layer"))
    return list(record.get(field, [])) if field else []


def drilldown(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(request)
    root_id = _safe_id(request.get("memory_id"), "memory_id")
    include_raw = bool(request.get("include_raw_content", False))
    max_chars = int(request.get("max_chars", DEFAULT_MAX_CHARS))
    if not 256 <= max_chars <= MAX_CHARS:
        raise MemoryErrorContract("invalid_max_chars", f"max_chars must be 256..{MAX_CHARS}")
    visited, ordered = set(), []

    def walk(memory_id: str) -> None:
        if memory_id in visited:
            return
        visited.add(memory_id)
        record = _load_accessible_record(workspace, memory_id, profile, "drill down into")
        ordered.append(record)
        for child in _children(record):
            walk(child)

    walk(root_id)
    output, used, truncated = [], 0, False
    for record in ordered:
        item = _compact(record)
        for field in ("raw_refs", "atom_refs", "scenario_refs"):
            item[field] = record.get(field, [])
        if include_raw and record.get("layer") == "L0_raw_evidence" and record.get("raw_refs"):
            relative = str(record["raw_refs"][0])
            if not relative.startswith("Evidence/raw/"):
                raise MemoryErrorContract("invalid_raw_path", "raw evidence path is outside Evidence/raw", "blocked")
            raw_path = (workspace / relative).resolve()
            if workspace != raw_path and workspace not in raw_path.parents:
                raise MemoryErrorContract("invalid_raw_path", "raw evidence path escapes workspace", "blocked")
            item["raw_content"] = raw_path.read_text(encoding="utf-8") if raw_path.is_file() else None
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        remaining = max_chars - used
        if remaining <= 0:
            truncated = True
            break
        if len(encoded) > remaining:
            if item.get("raw_content"):
                overhead = len(encoded) - len(item["raw_content"])
                item["raw_content"] = item["raw_content"][: max(0, remaining - overhead - 32)]
                item["raw_content_truncated"] = True
                encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                truncated = True
            else:
                truncated = True
                break
        output.append(item)
        used += len(encoded)
    return _envelope(
        "drilldown",
        "ok",
        {
            "root_memory_id": root_id,
            "execution_profile": profile,
            "records": output,
            "characters": used,
            "truncated": truncated,
            "raw_content_included": include_raw,
        },
    )


def project(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    result = retrieve(workspace, request)
    items = result["data"]["items"]
    result["operation"] = "project"
    result["data"] = {
        "projection_id": str(request.get("projection_id") or f"projection-{hashlib.sha256(str(request.get('query','')).encode()).hexdigest()[:12]}"),
        "execution_profile": result["data"]["execution_profile"],
        "highest_layer": items[0]["layer"] if items else None,
        "items": items,
        "raw_evidence_refs": sorted({
            ref
            for item in items
            for ref in (_load_record(workspace, item["memory_id"]).get("raw_refs", []) if item["layer"] == "L0_raw_evidence" else [])
        }),
        "raw_content_included": False,
        "source_of_truth": "STATE/current.yaml + Evidence/raw + STATE/memory",
        "characters": result["data"]["characters"],
        "truncated": result["data"]["truncated"],
    }
    return result


def promote(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(request)
    memory_id = _safe_id(request.get("memory_id"), "memory_id")
    record = _load_accessible_record(workspace, memory_id, profile, "promote")
    if record.get("layer") != "L3_reusable_candidate":
        raise MemoryErrorContract("promotion_requires_l3", "only L3 reusable candidates may be promoted")
    target = str(request.get("target") or record.get("promotion_target") or "none")
    if target not in {"execution_reference", "unityagent_knowledge", "user_policy_candidate"}:
        raise MemoryErrorContract("invalid_promotion_target", f"unsupported promotion target: {target}")
    reasons = []
    if record.get("review_status") != "approved":
        reasons.append("candidate review_status must be approved")
    if not record.get("provenance"):
        reasons.append("candidate provenance is required")
    if target in {"unityagent_knowledge", "user_policy_candidate"} and record.get("confidence") != "verified":
        reasons.append(f"{target} requires verified confidence")
    if target == "user_policy_candidate" and request.get("human_gate_approved") is not True:
        reasons.append("user_policy_candidate requires explicit Human Gate approval")
    approved = not reasons
    return _envelope(
        "promote",
        "ok" if approved else "blocked",
        {
            "memory_id": memory_id,
            "target": target,
            "approved": approved,
            "writes_external_authority": False,
            "promotion_projection": _compact(record) if approved else None,
            "required_next_action": "caller_may_submit_to_target_authority" if approved else "resolve_promotion_gate",
        },
        [{"code": "promotion_gate", "message": reason} for reason in reasons],
        mutated=False,
    )


OPERATIONS = {
    "capture_raw": capture_raw,
    "create_atom": create_atom,
    "create_scenario": create_scenario,
    "create_candidate": create_candidate,
    "retrieve": retrieve,
    "drilldown": drilldown,
    "project": project,
    "promote": promote,
}


def execute(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation", "")).strip()
    handler = OPERATIONS.get(operation)
    if not handler:
        raise MemoryErrorContract("unsupported_operation", f"operation must be one of {sorted(OPERATIONS)}")
    return handler(workspace, request)


def _read_request(path_value: str) -> dict[str, Any]:
    text = sys.stdin.read() if path_value == "-" else Path(path_value).expanduser().resolve().read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise MemoryErrorContract("invalid_request", "request must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-preserving layered memory controller.")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--request", required=True, help="Request JSON path or '-' for stdin.")
    args = parser.parse_args(argv)
    operation = "unknown"
    try:
        workspace = Path(args.workspace_root).expanduser().resolve()
        if not workspace.is_dir():
            raise MemoryErrorContract("workspace_not_found", f"workspace root does not exist: {workspace}")
        request = _read_request(args.request)
        operation = str(request.get("operation", "unknown"))
        result = execute(workspace, request)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        result = _envelope(operation, "invalid_request", diagnostics=[{"code": "invalid_request_file", "message": str(exc)}])
    except MemoryErrorContract as exc:
        result = _envelope(operation, exc.status, diagnostics=[{"code": exc.code, "message": exc.message}])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 3 if result["status"] == "blocked" else 4


if __name__ == "__main__":
    sys.exit(main())
