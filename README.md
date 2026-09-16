# LineZone unconfirmed-track fix — roboflow/supervision#2578

A working reproduction + fix for a real, still-open bug in
[roboflow/supervision](https://github.com/roboflow/supervision) (issue
[#2578](https://github.com/roboflow/supervision/issues/2578), maintainer-labeled
`bug` + `help wanted`, reported 2026-09-15).

## The bug

`LineZone.trigger()` keys its crossing state by `tracker_id` and treats every
detection with `tracker_id = -1` as one shared track. Roboflow's own
`roboflow/trackers` library (e.g. `ByteTrackTracker`) returns `-1` for tracks
it has not confirmed yet (`minimum_consecutive_frames`), so on a busy frame
many distinct unconfirmed objects all carry `-1`. Their independent motion
makes that single phantom track cross the line over and over — counts inflate
**silently**. The issue reporter saw a working pipeline go from ~7/9 to 97/95
on the same footage after migrating off the deprecated `sv.ByteTrack`.

## What's here

- `repro.py` — the issue's minimal reproduction, verbatim. Run against a
  supervision checkout:
  `PYTHONPATH=/path/to/supervision/src python3 repro.py`
- `fix.patch` — the fix: a ~10-line change to
  `src/supervision/detection/line_zone.py`. In `trigger()`, skip detections
  whose `tracker_id` is `None` or negative before updating crossing state,
  plus a docstring note that `trigger()` expects confirmed tracks.
- `eval_fix.py` — applies `fix.patch` to a pristine checkout in a temp dir
  and runs three scenarios against the patched tree, asserting every number:
  `python3 eval_fix.py --src /path/to/pristine/supervision`

## Verified results (run 2026-09-16, supervision @ `19649ac2`)

| scenario | before | after | expected |
|---|---|---|---|
| issue verbatim repro | (2, 3) | (0, 0) | (0, 0) |
| stress: 6 unconfirmed objects zigzagging, 60 frames | — | (0, 0) | (0, 0) |
| mixed: 2 confirmed tracks crossing once each + 4 unconfirmed noise objects | — | (1, 1) | (1, 1) |

Regression check: all **56 tests** in supervision's own
`tests/detection/test_line_counter.py` pass with the patch applied.

## Honest scope

- The bug was reproduced on supervision main @ `19649ac2` (2026-09-16) before
  fixing; the "before" numbers above are from that run.
- There is a community fix PR (#2579) but it is stalled on CLA + merge
  conflicts, not merged — the bug is still live on main. This fix was written
  independently and is not affiliated with that PR.
- No maintainer has reviewed this fix; it is a demo of the defect and a
  minimal, tested remedy, not an upstream contribution.
