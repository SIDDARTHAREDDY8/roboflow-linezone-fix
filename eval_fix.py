"""Before/after evaluation of the fix.patch for roboflow/supervision#2578.

What it does:
  1. Copies a pristine supervision checkout to a temp dir.
  2. Applies fix.patch (git apply).
  3. Runs three scenarios against the PATCHED tree (subprocess, PYTHONPATH),
     plus scenario 1 against the PRISTINE tree for the "before" number.
  4. Asserts every expected count. All numbers come from running code.

Scenarios:
  A. The issue's verbatim repro (2 unconfirmed objects, opposite sides).
  B. Stress: 6 unconfirmed objects zigzagging across the line for 60 frames.
  C. Mixed: 2 confirmed tracks genuinely crossing once each + 4 unconfirmed
     noise objects zigzagging for 60 frames (confirmed counts must survive).

Usage: python3 eval_fix.py --src /path/to/pristine/supervision/checkout
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

SCENARIO = r'''
import sys
import numpy as np
import supervision as sv

MODE = sys.argv[1]  # repro | zigzag | mixed

def box(tid, y, x=80.0):
    return sv.Detections(
        xyxy=np.array([[x, y, x + 40, y + 40]]),
        confidence=np.array([0.9]),
        class_id=np.array([0]),
        tracker_id=np.array([tid]),
    )

lz = sv.LineZone(start=sv.Point(0, 100), end=sv.Point(200, 100))

if MODE == "repro":
    for tid, y in [(-1, 20), (-1, 160), (-1, 20), (-1, 160), (-1, 20), (-1, 160)]:
        lz.trigger(box(tid, y))
elif MODE == "zigzag":
    # 6 unconfirmed objects, none ever crosses; they just alternate sides.
    for _ in range(60):
        for k in range(6):
            y = 20.0 if (k % 2 == 0) else 160.0
            lz.trigger(box(-1, y, x=40.0 + 10 * k))
elif MODE == "mixed":
    # 2 confirmed tracks genuinely cross once each (id 1: down->up = in,
    # id 2: up->down = out); 4 unconfirmed objects zigzag as noise.
    frames = []
    for f in range(60):
        dets = []
        # confirmed crosser 1: y 160 -> 20 (crosses line once, upward)
        y1 = 160.0 - (140.0 * f / 59)
        dets.append((1, y1, 10.0))
        # confirmed crosser 2: y 20 -> 160 (crosses line once, downward)
        y2 = 20.0 + (140.0 * f / 59)
        dets.append((2, y2, 60.0))
        # 4 unconfirmed zigzaggers
        for k in range(4):
            y = 20.0 if ((f + k) % 2 == 0) else 160.0
            dets.append((-1, y, 110.0 + 10 * k))
        frames.append(dets)
    for dets in frames:
        xyxy = np.array([[x, y, x + 40, y + 40] for _, y, x in dets])
        lz.trigger(sv.Detections(
            xyxy=xyxy,
            confidence=np.full(len(dets), 0.9),
            class_id=np.zeros(len(dets), dtype=int),
            tracker_id=np.array([t for t, _, _ in dets]),
        ))

print(f"{lz.in_count} {lz.out_count}")
'''


def run(src_dir, mode):
    env = dict(os.environ, PYTHONPATH=os.path.join(src_dir, "src"))
    p = subprocess.run(
        [sys.executable, "-c", SCENARIO, mode],
        capture_output=True, text=True, env=env,
    )
    if p.returncode != 0:
        sys.exit(f"scenario {mode} failed on {src_dir}:\n{p.stderr[-2000:]}")
    return tuple(int(x) for x in p.stdout.strip().split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="pristine supervision checkout")
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="sv-fixed-", dir=os.path.expanduser("~"))
    shutil.copytree(args.src, os.path.join(work, "sv"),
                    ignore=shutil.ignore_patterns(".git"))
    fixed = os.path.join(work, "sv")
    patch = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fix.patch")
    r = subprocess.run(["git", "apply", patch], cwd=fixed,
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git apply failed:\n{r.stderr}")

    before = run(args.src, "repro")
    after_repro = run(fixed, "repro")
    after_zig = run(fixed, "zigzag")
    after_mix = run(fixed, "mixed")

    print(f"{'scenario':10s} {'before':>10s} {'after':>10s}  expected-after")
    print(f"{'repro':10s} {str(before):>10s} {str(after_repro):>10s}  (0, 0)")
    print(f"{'zigzag':10s} {'n/a':>10s} {str(after_zig):>10s}  (0, 0)")
    print(f"{'mixed':10s} {'n/a':>10s} {str(after_mix):>10s}  (1, 1)")

    assert before == (2, 3), f"before-fix repro changed: {before}"
    assert after_repro == (0, 0), f"repro not fixed: {after_repro}"
    assert after_zig == (0, 0), f"zigzag not fixed: {after_zig}"
    assert after_mix == (1, 1), f"mixed broke confirmed tracks: {after_mix}"
    print("\nAll assertions passed: unconfirmed tracks no longer inflate "
          "counts, confirmed crossings still counted.")

    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
