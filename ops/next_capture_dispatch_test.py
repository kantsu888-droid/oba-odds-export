import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ops.next_capture_dispatch import next_dispatch


class NextCaptureDispatchTest(unittest.TestCase):
    def write_schedule(self, root: Path, name: str, start_time: str) -> None:
        path = root / name
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "race_date",
                    "track",
                    "track_code",
                    "race_no",
                    "start_time",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "race_date": "2026-10-06",
                    "track": "oi",
                    "track_code": "20",
                    "race_no": "1",
                    "start_time": start_time,
                }
            )

    def test_dispatches_before_next_uncaptured_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_schedule(root, "all_schedule_100000.csv", "18:35")
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-06T17:00:00+09:00"),
            )
            self.assertEqual(out["status"], "dispatch")
            self.assertEqual(out["next_target"], "2026-10-06T18:05:00+09:00")
            self.assertEqual(out["delay_seconds"], 3420)

    def test_relay_delay_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_schedule(root, "all_schedule_100000.csv", "21:00")
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-06T10:00:00+09:00"),
            )
            self.assertEqual(out["delay_seconds"], 5400)

    def test_captured_target_advances_to_next_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_schedule(root, "all_schedule_100000.csv", "18:35")
            (root / "oi_1R_m30_180500_odds.csv").write_text(
                "captured\n",
                encoding="utf-8",
            )
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-06T17:00:00+09:00"),
            )
            self.assertEqual(out["next_target"], "2026-10-06T18:20:00+09:00")

    def test_no_future_targets_stops_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_schedule(root, "all_schedule_100000.csv", "18:35")
            for m, t in [(30, "180500"), (15, "182000"), (10, "182500"), (5, "183000"), (2, "183300")]:
                (root / f"oi_1R_m{m}_{t}_odds.csv").write_text(
                    "captured\n",
                    encoding="utf-8",
                )
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-06T17:00:00+09:00"),
            )
            self.assertEqual(out["status"], "no_future_targets")
            self.assertIsNone(out["delay_seconds"])

    def test_latest_schedule_is_used(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_schedule(root, "all_schedule_100000.csv", "18:35")
            self.write_schedule(root, "all_schedule_120000.csv", "18:45")
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-06T17:00:00+09:00"),
            )
            self.assertEqual(out["next_target"], "2026-10-06T18:15:00+09:00")
            self.assertEqual(out["schedule"], "all_schedule_120000.csv")


    def test_idle_keepalive_relay_after_last_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_schedule(root, "all_schedule_100000.csv", "18:35")
            for m, t in [(30, "180500"), (15, "182000"), (10, "182500"), (5, "183000"), (2, "183300")]:
                (root / f"oi_1R_m{m}_{t}_odds.csv").write_text(
                    "captured\n",
                    encoding="utf-8",
                )
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-06T20:00:00+09:00"),
                keepalive_when_idle=True,
            )
            self.assertEqual(out["status"], "idle_relay")
            self.assertEqual(out["reason"], "no_future_targets")
            self.assertEqual(out["delay_seconds"], 5400)

    def test_idle_keepalive_relay_without_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = next_dispatch(
                data_dir=root,
                now=datetime.fromisoformat("2026-10-07T01:00:00+09:00"),
                keepalive_when_idle=True,
            )
            self.assertEqual(out["status"], "idle_relay")
            self.assertEqual(out["reason"], "no_schedule")
            self.assertEqual(out["delay_seconds"], 5400)

if __name__ == "__main__":
    unittest.main()
