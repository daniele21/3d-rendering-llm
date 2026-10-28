"""Append-only private JSONL cost ledger + deterministic reconciliation report.

Every live call writes a 'started' event *before* network I/O and a 'settled'
event on completion/failure. Unsettled calls remain UNKNOWN, never free.
No prompts, responses, keys, credential paths or raw exception bodies logged.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import stat
from uuid import uuid4


class LedgerError(RuntimeError):
    pass


def event_id():
    return uuid4().hex


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def default_ledger_path():
    return Path(os.environ.get("GEOMETRY_COST_LEDGER", "runs/costs/events.jsonl")).resolve()


def append_event(path, record: dict):
    """Fail closed if append fails; lock to avoid concurrent line interleaving."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise LedgerError("Cost ledger must not be a symlink")
    flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise LedgerError("Cost ledger is not a regular file")
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.fchmod(fd, 0o600)
            payload = (json.dumps(record, sort_keys=True, ensure_ascii=True,
                                  separators=(",", ":")) + "\n").encode("utf-8")
            with os.fdopen(os.dup(fd), "ab", buffering=0) as stream:
                stream.write(payload)
                os.fsync(stream.fileno())
        finally:
            os.close(fd)
    except OSError as exc:
        raise LedgerError("Unable to durably append cost record") from exc


def load_events(path):
    path = Path(path)
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def reconcile(events: list[dict]) -> dict:
    by_call = {}
    for ev in events:
        cid = ev.get("call_id")
        if not cid or ev.get("event") not in {"started", "settled"}:
            raise LedgerError("Invalid cost ledger event")
        if cid not in by_call:
            by_call[cid] = {}
        state = by_call[cid]
        if ev["event"] in state:
            raise LedgerError(f"Duplicate {ev['event']} for call")
        state[ev["event"]] = ev
    groups = defaultdict(lambda: {"calls": 0, "priced_calls": 0, "unpriced_calls": 0,
                                  "input_total": 0, "input_uncached": 0,
                                  "input_cache_read": 0, "input_cache_write_30m": 0,
                                  "input_cache_write_12h": 0, "output_total": 0,
                                  "output_reasoning_known": 0, "usd_priced": Decimal("0")})
    pending = []
    for call_id, states in sorted(by_call.items()):
        if "started" not in states:
            raise LedgerError("Settled cost call without corresponding start")
        first = states["started"]
        final = states.get("settled")
        # If provider resolved a different model than requested, group by the
        # actual model used for tariffing. A missing response retains requested.
        reported_model = (final or {}).get("model_returned")
        key = (reported_model or first.get("model_requested", "unknown"),
               first.get("stage", "unknown"))
        g = groups[key]
        g["calls"] += 1
        priced = (final or {}).get("pricing") or {}
        if final is None or priced.get("status") != "PRICED":
            g["unpriced_calls"] += 1
            observed = (final or {}).get("usage_observed") or {}
            pending.append({"call_id": call_id, "model": key[0], "stage": key[1],
                            "reason": ("not_settled" if final is None else
                                       priced.get("reason") or final.get("outcome", "unpriced")),
                            "observed_input_tokens": observed.get("input_total"),
                            "observed_cached_read_tokens": observed.get("input_cache_read"),
                            "observed_cached_write_tokens": observed.get("input_cache_write"),
                            "observed_output_tokens": observed.get("output_total")})
            continue
        tok = priced["tokens"]
        g["priced_calls"] += 1
        for name in ("input_total", "input_uncached", "input_cache_read", "input_cache_write_30m",
                     "input_cache_write_12h", "output_total"):
            g[name] += tok[name]
        g["output_reasoning_known"] += tok["output_reasoning_subset"] or 0
        g["usd_priced"] += Decimal(priced["estimated_usd"])
    rows = []
    for (model, stage), g in sorted(groups.items()):
        row = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in g.items()}
        row.update({"model": model, "stage": stage,
                    "cost_completeness": "COMPLETE" if not g["unpriced_calls"] else "INCOMPLETE"})
        rows.append(row)
    priced_total = sum((Decimal(r["usd_priced"]) for r in rows), Decimal("0"))
    return {"schema_version": 1, "currency": "USD", "recorded_calls": len(by_call),
            "priced_subtotal_usd": str(priced_total),
            "grand_total_status": "COMPLETE" if not pending else "INCOMPLETE_UNKNOWN_COST",
            "by_model_stage": rows, "unpriced_calls": pending,
            "note": "Usage-based estimate for model tokens only; provider invoice, tools, compute and tax are separate."}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, default=default_ledger_path())
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    result = reconcile(load_events(args.ledger))
    data = json.dumps(result, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            p.error("Do not overwrite a prior cost report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
