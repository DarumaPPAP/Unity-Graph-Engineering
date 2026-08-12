#!/usr/bin/env python3
"""Native layered-memory controller for Unity Graph Engineering.

The controller stores source-faithful raw evidence separately from compact
memory records. It intentionally does not write UnityAgent knowledge or user
policy; promotion operations only return a gated projection.
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

SCHEMA_VERSION = "1.0"
DEFAULT_MAX_RAW_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_ITEMS = 8
DEFAULT_MAX_CHARS = 6000
MAX_RETRIEVAL_ITEMS = 20
MAX_RETRIEVAL_CHARS = 12000

LAYERS = ("L0_raw_evidence", "L1_atom", "L2_scenario", "L3_reusable_candidate")
LAYER_DIR = {
    "L0_raw_evidence": "L0",
    "L1_atom": "L1",
    "L2_scenario": "L2",
    "L3_reusable_candidate": "L3",
}
LAYER_WEIGHT = {
    "L3_reusable_candidate": 4.0,
    "L2_scenario": 3.0,
    "L1_atom": 2.0,
    "L0_raw_evidence": 1.0,
}
EXECUTION_PROFILES = {"generic_planning", "personal_full_control", "team_safe_import"}
SAFE_TEAM_SCOPES = {"portable_artifact", "public_reference"}
CONFIDENCE = {"verified", "probable", "unverified"}
REVIEW_STATUS = {"not_required", "pending", "approved", "rejected"}
PROMOTION_TARGETS = {"none", "execution_reference", "unityagent_knowledge", "user_policy_candidate"}

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
    """Typed controller error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, *, status: str = "invalid_request") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: Any, field: str = "id") -> str:
    text = str(value or "").strip()
    if not ID_RE.fullmatch(text):
        raise MemoryErrorContract(
            "invalid_id",
            f"{field} must match {ID_RE.pattern}",
        )
    return text


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MemoryErrorContract("invalid_request", f"{field} must be an array")
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            raise MemoryErrorContract("invalid_request", f"{field} contains an empty value")
        result.append(text)
    if not allow_empty and not result:
        raise MemoryErrorContract("invalid_request", f"{field} must not be empty")
    return result


def _workspace_root(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise MemoryErrorContract("workspace_not_found", f"workspace root does not exist: {path}")
    return path


def _memory_root(workspace: Path) -> Path:
    return workspace / "STATE" / "memory"


def _record_path(workspace: Path, layer: str, memory_id: str) -> Path:
    return _memory_root(workspace) / LAYER_DIR[layer] / f"{memory_id}.json"


def _raw_path(workspace: Path, evidence_id: str) -> Path:
    return workspace / "Evidence" / "raw" / f"{evidence_id}.txt"


def _event_path(workspace: Path) -> Path:
    return _memory_root(workspace) / "events.jsonl"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _append_event(workspace: Path, event: dict[str, Any]) -> None:
    path = _event_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def _envelope(
    operation: str,
    status: str,
    *,
    data: Any = None,
    diagnostics: list[dict[str, Any]] | None = None,
    mutated: bool = False,
) -> dict[str, Any]:
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
        raise MemoryErrorContract("memory_corrupt", f"invalid JSON in {path}: {exc}", status="blocked") from exc
    if not isinstance(value, dict):
        raise MemoryErrorContract("memory_corrupt", f"record must be a JSON object: {path}", status="blocked")
    return value


def _load_record(workspace: Path, memory_id: str) -> dict[str, Any]:
    memory_id = _safe_id(memory_id, "memory_id")
    for layer in LAYERS:
        path = _record_path(workspace, layer, memory_id)
        if path.is_file():
            return _read_json(path)
    raise MemoryErrorContract("memory_not_found", f"memory record not found: {memory_id}")


def _secret_findings(text: str) -> list[str]:
    findings = []
    for code, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(code)
    return findings


def _request_profile(request: dict[str, Any]) -> str:
    profile = str(request.get("execution_profile", "generic_planning"))
    if profile not in EXECUTION_PROFILES:
        raise MemoryErrorContract("invalid_profile", f"unsupported execution_profile: {profile}")
    return profile


def _assert_capture_scope(request: dict[str, Any], text: str) -> tuple[str, str]:
    profile = _request_profile(request)
    scope_class = str(request.get("scope_class", "portable_artifact")).strip()
    sensitivity = str(request.get("sensitivity", "internal")).strip().lower()
    if sensitivity == "secret":
        raise MemoryErrorContract(
            "secret_capture_forbidden",
            "secret-classified raw evidence must not be stored",
            status="blocked",
        )
    findings = _secret_findings(text)
    if findings:
        raise MemoryErrorContract(
            "secret_capture_forbidden",
            f"raw evidence matched secret patterns: {', '.join(findings)}",
            status="blocked",
        )
    if profile == "team_safe_import" and scope_class not in SAFE_TEAM_SCOPES:
        raise MemoryErrorContract(
            "team_safe_scope_forbidden",
            f"team_safe_import may capture only {sorted(SAFE_TEAM_SCOPES)}",
            status="blocked",
        )
    return profile, scope_class


def _ensure_new_or_identical(path: Path, payload: dict[str, Any]) -> bool:
    if not path.exists():
        return True
    existing = _read_json(path)
    if existing == payload:
        return False
    raise MemoryErrorContract(
        "id_conflict",
        f"{path.stem} already exists with different content; use supersedes/conflicts_with instead of overwrite",
        status="blocked",
    )


def _validate_refs(workspace: Path, refs: Iterable[str], required_layer: str, field: str) -> list[str]:
    normalized = [_safe_id(ref, field) for ref in refs]
    for ref in normalized:
        record = _load_record(workspace, ref)
        if record.get("layer") != required_layer:
            raise MemoryErrorContract(
                "invalid_reference_layer",
                f"{field} {ref} must reference {required_layer}, got {record.get('layer')}",
            )
    return normalized


def _validate_relation_refs(workspace: Path, refs: Iterable[str], field: str) -> list[str]:
    normalized = [_safe_id(ref, field) for ref in refs]
    for ref in normalized:
        _load_record(workspace, ref)
    return normalized


def capture_raw(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    evidence_id = _safe_id(request.get("evidence_id"), "evidence_id")
    source_file = Path(str(request.get("source_file", ""))).expanduser().resolve()
    if not source_file.is_file():
        raise MemoryErrorContract("source_file_not_found", f"source_file does not exist: {source_file}")
    max_bytes = int(request.get("max_raw_bytes", DEFAULT_MAX_RAW_BYTES))
    if max_bytes <= 0 or max_bytes > DEFAULT_MAX_RAW_BYTES:
        raise MemoryErrorContract(
            "invalid_max_raw_bytes",
            f"max_raw_bytes must be 1..{DEFAULT_MAX_RAW_BYTES}",
        )
    raw = source_file.read_bytes()
    if len(raw) > max_bytes:
        raise MemoryErrorContract(
            "raw_evidence_too_large",
            f"raw evidence is {len(raw)} bytes; maximum is {max_bytes}",
            status="blocked",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MemoryErrorContract(
            "raw_evidence_not_utf8",
            "raw evidence must be UTF-8 text for this native controller",
            status="blocked",
        ) from exc

    profile, scope_class = _assert_capture_scope(request, text)
    digest = hashlib.sha256(raw).hexdigest()
    raw_path = _raw_path(workspace, evidence_id)
    metadata_path = _record_path(workspace, "L0_raw_evidence", evidence_id)

    metadata = {
        "memory_id": evidence_id,
        "layer": "L0_raw_evidence",
        "created_at": str(request.get("created_at") or _utc_now()),
        "statement": str(request.get("statement") or f"Raw evidence: {request.get('source_type', 'tool_output')}"),
        "raw_refs": [f"Evidence/raw/{evidence_id}.txt"],
        "atom_refs": [],
        "scenario_refs": [],
        "applicability": _string_list(request.get("applicability"), "applicability"),
        "limits": _string_list(request.get("limits"), "limits"),
        "confidence": "verified",
        "provenance": _string_list(request.get("provenance"), "provenance"),
        "promotion_target": "none",
        "review_status": "not_required",
        "supersedes": [],
        "conflicts_with": [],
        "source_type": str(request.get("source_type", "tool_output")),
        "sha256": digest,
        "byte_count": len(raw),
        "execution_profile": profile,
        "scope_class": scope_class,
        "sensitivity": str(request.get("sensitivity", "internal")),
        "repository": request.get("repository"),
        "run_id": request.get("run_id"),
    }

    if raw_path.exists():
        existing_raw = raw_path.read_bytes()
        if hashlib.sha256(existing_raw).hexdigest() != digest:
            raise MemoryErrorContract(
                "id_conflict",
                f"raw evidence {evidence_id} already exists with different content",
                status="blocked",
            )
    should_write_meta = _ensure_new_or_identical(metadata_path, metadata)
    mutated = False
    if not raw_path.exists():
        _atomic_write_text(raw_path, text)
        mutated = True
    if should_write_meta:
        _write_json(metadata_path, metadata)
        mutated = True
    if mutated:
        _append_event(
            workspace,
            {
                "event": "memory_created",
                "memory_id": evidence_id,
                "layer": "L0_raw_evidence",
                "captured_at": _utc_now(),
                "sha256": digest,
            },
        )
    return _envelope("capture_raw", "ok", data=metadata, mutated=mutated)


def _base_record(
    workspace: Path,
    request: dict[str, Any],
    *,
    layer: str,
    required_ref_field: str,
    required_ref_layer: str,
) -> dict[str, Any]:
    memory_id = _safe_id(request.get("memory_id"), "memory_id")
    statement = str(request.get("statement", "")).strip()
    if not statement:
        raise MemoryErrorContract("missing_statement", "statement must not be empty")
    confidence = str(request.get("confidence", "unverified"))
    if confidence not in CONFIDENCE:
        raise MemoryErrorContract("invalid_confidence", f"unsupported confidence: {confidence}")
    review_status = str(request.get("review_status", "pending" if layer == "L3_reusable_candidate" else "not_required"))
    if review_status not in REVIEW_STATUS:
        raise MemoryErrorContract("invalid_review_status", f"unsupported review_status: {review_status}")
    promotion_target = str(request.get("promotion_target", "none"))
    if promotion_target not in PROMOTION_TARGETS:
        raise MemoryErrorContract("invalid_promotion_target", f"unsupported promotion_target: {promotion_target}")

    refs = _string_list(request.get(required_ref_field), required_ref_field, allow_empty=False)
    refs = _validate_refs(workspace, refs, required_ref_layer, required_ref_field)
    supersedes = _validate_relation_refs(
        workspace,
        _string_list(request.get("supersedes"), "supersedes"),
        "supersedes",
    )
    conflicts = _validate_relation_refs(
        workspace,
        _string_list(request.get("conflicts_with"), "conflicts_with"),
        "conflicts_with",
    )
    if memory_id in supersedes or memory_id in conflicts:
        raise MemoryErrorContract("self_reference", "memory record cannot supersede or conflict with itself")

    record = {
        "memory_id": memory_id,
        "layer": layer,
        "created_at": str(request.get("created_at") or _utc_now()),
        "statement": statement,
        "raw_refs": refs if required_ref_field == "raw_refs" else [],
        "atom_refs": refs if required_ref_field == "atom_refs" else [],
        "scenario_refs": refs if required_ref_field == "scenario_refs" else [],
        "applicability": _string_list(request.get("applicability"), "applicability"),
        "limits": _string_list(request.get("limits"), "limits"),
        "confidence": confidence,
        "provenance": _string_list(request.get("provenance"), "provenance"),
        "promotion_target": promotion_target,
        "review_status": review_status,
        "supersedes": supersedes,
        "conflicts_with": conflicts,
        "repository": request.get("repository"),
        "unity_version": request.get("unity_version"),
        "platform": request.get("platform"),
        "tags": _string_list(request.get("tags"), "tags"),
    }
    return record


def _write_record(workspace: Path, record: dict[str, Any], operation: str) -> dict[str, Any]:
    path = _record_path(workspace, str(record["layer"]), str(record["memory_id"]))
    should_write = _ensure_new_or_identical(path, record)
    if should_write:
        _write_json(path, record)
        _append_event(
            workspace,
            {
                "event": "memory_created",
                "memory_id": record["memory_id"],
                "layer": record["layer"],
                "captured_at": _utc_now(),
                "supersedes": record.get("supersedes", []),
                "conflicts_with": record.get("conflicts_with", []),
            },
        )
    return _envelope(operation, "ok", data=record, mutated=should_write)


def create_atom(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    record = _base_record(
        workspace,
        request,
        layer="L1_atom",
        required_ref_field="raw_refs",
        required_ref_layer="L0_raw_evidence",
    )
    return _write_record(workspace, record, "create_atom")


def create_scenario(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    record = _base_record(
        workspace,
        request,
        layer="L2_scenario",
        required_ref_field="atom_refs",
        required_ref_layer="L1_atom",
    )
    if not record["applicability"]:
        raise MemoryErrorContract("missing_applicability", "L2 scenario requires applicability")
    if not record["limits"]:
        raise MemoryErrorContract("missing_limits", "L2 scenario requires limits")
    return _write_record(workspace, record, "create_scenario")


def create_candidate(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    record = _base_record(
        workspace,
        request,
        layer="L3_reusable_candidate",
        required_ref_field="scenario_refs",
        required_ref_layer="L2_scenario",
    )
    if not record["provenance"]:
        raise MemoryErrorContract("missing_provenance", "L3 reusable candidate requires provenance")
    if record["promotion_target"] == "none":
        raise MemoryErrorContract("missing_promotion_target", "L3 reusable candidate requires a promotion_target")
    return _write_record(workspace, record, "create_candidate")


def _all_records(workspace: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for layer in LAYERS:
        folder = _memory_root(workspace) / LAYER_DIR[layer]
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            records.append(_read_json(path))
    return records


def _tokens(value: Any) -> set[str]:
    text = " ".join(str(x) for x in value) if isinstance(value, list) else str(value or "")
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _score_record(record: dict[str, Any], query_tokens: set[str], context: dict[str, Any]) -> float:
    haystack = set()
    for field in ("statement", "applicability", "limits", "provenance", "tags", "repository", "unity_version", "platform"):
        haystack |= _tokens(record.get(field))
    lexical = len(query_tokens & haystack)
    score = float(lexical) * 10.0 + LAYER_WEIGHT.get(str(record.get("layer")), 0.0)

    for field, bonus in (("repository", 4.0), ("unity_version", 2.0), ("platform", 2.0)):
        wanted = str(context.get(field) or "").strip().lower()
        actual = str(record.get(field) or "").strip().lower()
        if wanted and actual and wanted == actual:
            score += bonus
    if record.get("confidence") == "verified":
        score += 1.0
    return score


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": record.get("memory_id"),
        "layer": record.get("layer"),
        "statement": record.get("statement"),
        "confidence": record.get("confidence"),
        "applicability": record.get("applicability", []),
        "limits": record.get("limits", []),
        "provenance": record.get("provenance", []),
        "supersedes": record.get("supersedes", []),
        "conflicts_with": record.get("conflicts_with", []),
        "repository": record.get("repository"),
        "unity_version": record.get("unity_version"),
        "platform": record.get("platform"),
    }


def retrieve(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    query = str(request.get("query", "")).strip()
    query_tokens = _tokens(query)
    max_items = int(request.get("max_items", DEFAULT_MAX_ITEMS))
    max_chars = int(request.get("max_chars", DEFAULT_MAX_CHARS))
    if not 1 <= max_items <= MAX_RETRIEVAL_ITEMS:
        raise MemoryErrorContract("invalid_max_items", f"max_items must be 1..{MAX_RETRIEVAL_ITEMS}")
    if not 256 <= max_chars <= MAX_RETRIEVAL_CHARS:
        raise MemoryErrorContract("invalid_max_chars", f"max_chars must be 256..{MAX_RETRIEVAL_CHARS}")

    requested_layers = request.get("layers")
    if requested_layers is None:
        allowed_layers = set(LAYERS)
    else:
        allowed_layers = set(_string_list(requested_layers, "layers"))
        unknown = allowed_layers - set(LAYERS)
        if unknown:
            raise MemoryErrorContract("invalid_layer", f"unsupported layers: {sorted(unknown)}")

    context = {
        "repository": request.get("repository"),
        "unity_version": request.get("unity_version"),
        "platform": request.get("platform"),
    }
    scored = []
    for record in _all_records(workspace):
        if record.get("layer") not in allowed_layers:
            continue
        score = _score_record(record, query_tokens, context)
        if query_tokens and score <= LAYER_WEIGHT.get(str(record.get("layer")), 0.0) + 1.0:
            continue
        scored.append((score, record))

    scored.sort(
        key=lambda item: (
            item[0],
            LAYER_WEIGHT.get(str(item[1].get("layer")), 0.0),
            str(item[1].get("created_at", "")),
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    used_chars = 0
    truncated = False
    for score, record in scored:
        if len(selected) >= max_items:
            truncated = True
            break
        compact = _compact_record(record)
        compact["score"] = round(score, 3)
        encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if selected and used_chars + len(encoded) > max_chars:
            truncated = True
            break
        if not selected and len(encoded) > max_chars:
            compact["statement"] = str(compact.get("statement") or "")[: max(64, max_chars // 2)]
            encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            truncated = True
        selected.append(compact)
        used_chars += len(encoded)

    return _envelope(
        "retrieve",
        "ok",
        data={
            "query": query,
            "items": selected,
            "item_count": len(selected),
            "characters": used_chars,
            "truncated": truncated,
            "raw_content_included": False,
            "retrieval_policy": "layer_weighted_lexical_then_context_affinity",
        },
    )


def _child_refs(record: dict[str, Any]) -> list[str]:
    layer = record.get("layer")
    if layer == "L3_reusable_candidate":
        return list(record.get("scenario_refs", []))
    if layer == "L2_scenario":
        return list(record.get("atom_refs", []))
    if layer == "L1_atom":
        return list(record.get("raw_refs", []))
    return []


def drilldown(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    root_id = _safe_id(request.get("memory_id"), "memory_id")
    include_raw_content = bool(request.get("include_raw_content", False))
    max_chars = int(request.get("max_chars", DEFAULT_MAX_CHARS))
    if not 256 <= max_chars <= MAX_RETRIEVAL_CHARS:
        raise MemoryErrorContract("invalid_max_chars", f"max_chars must be 256..{MAX_RETRIEVAL_CHARS}")

    visited: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def walk(memory_id: str) -> None:
        if memory_id in visited:
            return
        visited.add(memory_id)
        record = _load_record(workspace, memory_id)
        ordered.append(record)
        for child in _child_refs(record):
            walk(child)

    walk(root_id)

    output: list[dict[str, Any]] = []
    used_chars = 0
    truncated = False
    for record in ordered:
        compact = _compact_record(record)
        compact["raw_refs"] = record.get("raw_refs", [])
        compact["atom_refs"] = record.get("atom_refs", [])
        compact["scenario_refs"] = record.get("scenario_refs", [])
        if include_raw_content and record.get("layer") == "L0_raw_evidence":
            raw_refs = record.get("raw_refs", [])
            if raw_refs:
                raw_rel = str(raw_refs[0])
                expected_prefix = "Evidence/raw/"
                if raw_rel.startswith(expected_prefix):
                    raw_path = (workspace / raw_rel).resolve()
                    if workspace not in raw_path.parents:
                        raise MemoryErrorContract("invalid_raw_path", "raw evidence path escapes workspace", status="blocked")
                    compact["raw_content"] = raw_path.read_text(encoding="utf-8") if raw_path.is_file() else None

        encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        remaining = max_chars - used_chars
        if remaining <= 0:
            truncated = True
            break
        if len(encoded) > remaining:
            if "raw_content" in compact and compact["raw_content"]:
                overhead = len(encoded) - len(str(compact["raw_content"]))
                budget = max(0, remaining - overhead - 32)
                compact["raw_content"] = str(compact["raw_content"])[:budget]
                compact["raw_content_truncated"] = True
                encoded = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
                truncated = True
            else:
                truncated = True
                break
        output.append(compact)
        used_chars += len(encoded)

    return _envelope(
        "drilldown",
        "ok",
        data={
            "root_memory_id": root_id,
            "records": output,
            "characters": used_chars,
            "truncated": truncated,
            "raw_content_included": include_raw_content,
        },
    )


def project(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    projected_request = dict(request)
    projected_request["operation"] = "retrieve"
    projected_request.setdefault("max_items", DEFAULT_MAX_ITEMS)
    projected_request.setdefault("max_chars", DEFAULT_MAX_CHARS)
    result = retrieve(workspace, projected_request)
    items = result["data"]["items"]
    highest_layer = items[0]["layer"] if items else None
    raw_evidence_refs: list[str] = []
    for item in items:
        record = _load_record(workspace, str(item["memory_id"]))
        if record.get("layer") == "L0_raw_evidence":
            raw_evidence_refs.extend(record.get("raw_refs", []))
    result["operation"] = "project"
    result["data"] = {
        "projection_id": str(request.get("projection_id") or f"projection-{hashlib.sha256(str(request.get('query','')).encode()).hexdigest()[:12]}"),
        "highest_layer": highest_layer,
        "items": items,
        "raw_evidence_refs": sorted(set(raw_evidence_refs)),
        "raw_content_included": False,
        "source_of_truth": "STATE/current.yaml + Evidence/raw + STATE/memory",
        "characters": result["data"]["characters"],
        "truncated": result["data"]["truncated"],
    }
    return result


def promote(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    memory_id = _safe_id(request.get("memory_id"), "memory_id")
    record = _load_record(workspace, memory_id)
    if record.get("layer") != "L3_reusable_candidate":
        raise MemoryErrorContract("promotion_requires_l3", "only L3 reusable candidates may be promoted")
    target = str(request.get("target") or record.get("promotion_target") or "none")
    if target not in {"execution_reference", "unityagent_knowledge", "user_policy_candidate"}:
        raise MemoryErrorContract("invalid_promotion_target", f"unsupported promotion target: {target}")

    reasons: list[str] = []
    if record.get("review_status") != "approved":
        reasons.append("candidate review_status must be approved")
    if not record.get("provenance"):
        reasons.append("candidate provenance is required")
    if target == "unityagent_knowledge" and record.get("confidence") != "verified":
        reasons.append("unityagent_knowledge requires verified confidence")
    if target == "user_policy_candidate":
        if record.get("confidence") != "verified":
            reasons.append("user_policy_candidate requires verified confidence")
        if request.get("human_gate_approved") is not True:
            reasons.append("user_policy_candidate requires explicit Human Gate approval")

    approved = not reasons
    status = "ok" if approved else "blocked"
    return _envelope(
        "promote",
        status,
        data={
            "memory_id": memory_id,
            "target": target,
            "approved": approved,
            "writes_external_authority": False,
            "promotion_projection": _compact_record(record) if approved else None,
            "required_next_action": (
                "caller_may_submit_to_target_authority"
                if approved
                else "resolve_promotion_gate"
            ),
        },
        diagnostics=[{"code": "promotion_gate", "message": reason} for reason in reasons],
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
    if handler is None:
        raise MemoryErrorContract(
            "unsupported_operation",
            f"operation must be one of {sorted(OPERATIONS)}",
        )
    return handler(workspace, request)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Store and retrieve layered Graph Engineering memory with evidence-preserving drill-down."
    )
    parser.add_argument("--workspace-root", default=".", help="Execution workspace root.")
    parser.add_argument("--request", required=True, help="UTF-8 JSON request file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    operation = "unknown"
    try:
        workspace = _workspace_root(args.workspace_root)
        request_path = Path(args.request).expanduser().resolve()
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise MemoryErrorContract("invalid_request", "request must be a JSON object")
        operation = str(request.get("operation", "unknown"))
        result = execute(workspace, request)
    except FileNotFoundError as exc:
        result = _envelope(operation, "invalid_request", diagnostics=[{"code": "request_not_found", "message": str(exc)}])
    except json.JSONDecodeError as exc:
        result = _envelope(operation, "invalid_request", diagnostics=[{"code": "invalid_json", "message": str(exc)}])
    except MemoryErrorContract as exc:
        result = _envelope(
            operation,
            exc.status,
            diagnostics=[{"code": exc.code, "message": exc.message}],
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "ok":
        return 0
    if result["status"] == "blocked":
        return 3
    return 4


if __name__ == "__main__":
    sys.exit(main())
