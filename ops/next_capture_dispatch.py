#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))
TARGET_MINUTES = (30, 15, 10, 5, 2)


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(JST)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return dt.astimezone(JST)


def next_dispatch(
    *,
    data_dir: Path,
    now: datetime | None = None,
    relay_max_seconds: int = 5400,
    dispatch_lead_seconds: int = 480,
    max_late_seconds: int = 120,
) -> dict[str, Any]:
    schedules = sorted(data_dir.glob("all_schedule_*.csv"))
    if not schedules:
        return {
            "status": "no_schedule",
            "delay_seconds": None,
            "next_target": None,
        }

    schedule = schedules[-1]
    now = (now or datetime.now(JST)).astimezone(JST)
    targets: list[datetime] = []

    with schedule.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            start = datetime.strptime(
                f"{row['race_date']} {row['start_time']}",
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=JST)
            track = row["track"].strip()
            race_no = int(row["race_no"])

            for minutes_before in TARGET_MINUTES:
                pattern = (
                    data_dir
                    / f"{track}_{race_no}R_m{minutes_before}_*_odds.csv"
                )
                if glob.glob(str(pattern)):
                    continue
                target = start - timedelta(minutes=minutes_before)
                if target < now - timedelta(seconds=max_late_seconds):
                    continue
                targets.append(target)

    if not targets:
        return {
            "status": "no_future_targets",
            "delay_seconds": None,
            "next_target": None,
        }

    next_target = min(targets)
    dispatch_at = next_target - timedelta(seconds=dispatch_lead_seconds)
    delay = max(0, int((dispatch_at - now).total_seconds()))
    delay = min(delay, relay_max_seconds)
    return {
        "status": "dispatch",
        "delay_seconds": delay,
        "next_target": next_target.isoformat(),
        "dispatch_at": dispatch_at.isoformat(),
        "schedule": schedule.name,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--now")
    ap.add_argument("--relay-max-seconds", type=int, default=5400)
    ap.add_argument("--dispatch-lead-seconds", type=int, default=480)
    ap.add_argument("--max-late-seconds", type=int, default=120)
    ap.add_argument("--delay-only", action="store_true")
    args = ap.parse_args()

    out = next_dispatch(
        data_dir=Path(args.data_dir),
        now=parse_now(args.now),
        relay_max_seconds=args.relay_max_seconds,
        dispatch_lead_seconds=args.dispatch_lead_seconds,
        max_late_seconds=args.max_late_seconds,
    )
    if args.delay_only:
        value = out["delay_seconds"]
        print("none" if value is None else value)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
