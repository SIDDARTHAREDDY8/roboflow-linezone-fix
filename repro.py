"""Verbatim minimal reproduction from roboflow/supervision#2578.

Bug: LineZone.trigger() keys its crossing state by tracker_id and treats
every detection with tracker_id = -1 as one shared track. roboflow/trackers
(e.g. ByteTrackTracker) returns -1 for tracks it has not confirmed yet
(minimum_consecutive_frames), so on a busy frame many distinct unconfirmed
objects all carry -1 and their independent motion makes the single phantom
track cross the line over and over — counts inflate silently.

Run: PYTHONPATH=/path/to/supervision/src python3 repro.py
Expected on buggy main: prints "2 3" (wrong) then "0 0" (control, correct).
"""
import numpy as np
import supervision as sv


def box(tid, y):
    return sv.Detections(
        xyxy=np.array([[80.0, y, 120.0, y + 40]]),
        confidence=np.array([0.9]),
        class_id=np.array([0]),
        tracker_id=np.array([tid]),
    )


# two different unconfirmed objects, both id -1, on opposite sides of the line
lz = sv.LineZone(start=sv.Point(0, 100), end=sv.Point(200, 100))
for tid, y in [(-1, 20), (-1, 160), (-1, 20), (-1, 160), (-1, 20), (-1, 160)]:
    lz.trigger(box(tid, y))
print(lz.in_count, lz.out_count)  # 2 3 on buggy main (should be 0 0)

# identical motion with real ids is correctly quiet
lz2 = sv.LineZone(start=sv.Point(0, 100), end=sv.Point(200, 100))
for tid, y in [(1, 20), (2, 160), (1, 20), (2, 160), (1, 20), (2, 160)]:
    lz2.trigger(box(tid, y))
print(lz2.in_count, lz2.out_count)  # 0 0
