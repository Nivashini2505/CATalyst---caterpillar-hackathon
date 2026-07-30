"""
reduce_dataset.py — shrink usage_logs.csv so it fits under GitHub's 100 MB
(committing a lightweight <20 MB version) while preserving the statistical
characteristics the anomaly-detection model needs.

Why this file exists
---------------------
The full `usage_logs.csv` produced by `generate_dataset.py` is ~1.27M rows
(~192 MB) — too big for GitHub. This script produces a REPRESENTATIVE subset,
not a truncation, using **stratified sampling by `anomaly_type`**:

  * Sampling the SAME fraction from every anomaly_type stratum keeps the class
    balance exact (overall anomaly rate AND each type's share are preserved).
  * Because equipment_type / region / customer_segment are roughly independent
    of anomaly_type, proportional sampling within each stratum also preserves
    those marginal distributions (verified at the end of this script).
  * With ~114K rows retained, every equipment unit (220), operator (60) and
    site (30) still appears many times, and every anomaly type keeps >900 rows
    — plenty for training + a hackathon demo.
  * Output is re-sorted by (rental_id, log_date) so each rental's daily
    sequence stays in chronological order (thinned, but ordered).

Usage
-----
    cd ml
    python reduce_dataset.py                      # reads data/usage_logs_full.csv
                                                  # writes data/usage_logs.csv
    python reduce_dataset.py --in X --out Y --target-mb 17

Called automatically at the end of generate_dataset.py too.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"
DEFAULT_IN = DATA / "usage_logs_full.csv"
DEFAULT_OUT = DATA / "usage_logs.csv"
STRATIFY_COL = "anomaly_type"
SORT_COLS = ["rental_id", "log_date"]
SEED = 42


def reduce_usage_logs(in_path: Path, out_path: Path, target_mb: float = 17.0,
                      verbose: bool = True) -> Path:
    if verbose:
        print(f"Reading {in_path} ...")
    df = pd.read_csv(in_path)
    n_full = len(df)
    src_mb = in_path.stat().st_size / 1e6

    # Fraction that lands us at ~target_mb (bytes/row is ~constant).
    frac = min(1.0, target_mb / src_mb)
    if verbose:
        print(f"  full: {n_full:,} rows, {src_mb:.0f} MB  ->  target ~{target_mb:.0f} MB "
              f"(frac={frac:.4f})")

    # Stratified sample by anomaly_type — preserves class balance exactly.
    reduced = (
        df.groupby(STRATIFY_COL, group_keys=False)
          .apply(lambda g: g.sample(frac=frac, random_state=SEED), include_groups=True)
    )
    # Keep each rental's daily logs in chronological order.
    reduced = reduced.sort_values(SORT_COLS).reset_index(drop=True)

    reduced.to_csv(out_path, index=False)
    out_mb = out_path.stat().st_size / 1e6

    if verbose:
        _verify(df, reduced, out_mb)
    return out_path


def _verify(full: pd.DataFrame, red: pd.DataFrame, out_mb: float):
    print("\n" + "=" * 66)
    print("VERIFICATION — reduced vs full")
    print("=" * 66)
    print(f"rows:            {len(full):>12,}  ->  {len(red):>10,} "
          f"({len(red)/len(full)*100:.1f}%)")
    print(f"output size:     {out_mb:.2f} MB  ({'OK <20MB' if out_mb < 20 else 'STILL TOO BIG'})")

    print(f"\nclass balance (is_anomaly):")
    print(f"  full    anomaly rate: {full.is_anomaly.mean()*100:6.2f}%")
    print(f"  reduced anomaly rate: {red.is_anomaly.mean()*100:6.2f}%")

    print(f"\nanomaly_type share (full% -> reduced%):")
    f_at = full.anomaly_type.value_counts(normalize=True) * 100
    r_at = red.anomaly_type.value_counts(normalize=True) * 100
    for t in f_at.index:
        print(f"  {t:18s} {f_at[t]:6.2f}%  ->  {r_at.get(t,0):6.2f}%   "
              f"(n={int(red.anomaly_type.eq(t).sum()):>6,})")

    for col in ["equipment_type", "region", "customer_segment"]:
        print(f"\n{col} — max share drift:")
        f_s = full[col].value_counts(normalize=True) * 100
        r_s = red[col].value_counts(normalize=True) * 100
        drift = (f_s - r_s).abs().max()
        print(f"  categories full={full[col].nunique()} reduced={red[col].nunique()} "
              f"| max share drift = {drift:.2f} pts")

    print(f"\ncoverage of entities (full -> reduced, must match):")
    for col in ["equipment_id", "operator_id", "site_id", "rental_id"]:
        print(f"  {col:14s} {full[col].nunique():>7,}  ->  {red[col].nunique():>7,}")

    print(f"\nnumeric feature means (full -> reduced):")
    for col in ["engine_hours", "idle_hours", "fuel_consumed_liters",
                "utilization_rate", "last_ping_gap_hours"]:
        print(f"  {col:22s} {full[col].mean():8.3f}  ->  {red[col].mean():8.3f}")

    print(f"\ntemporal coverage:")
    print(f"  full    {full.log_date.min()} -> {full.log_date.max()} "
          f"({full.log_date.nunique():,} distinct days)")
    print(f"  reduced {red.log_date.min()} -> {red.log_date.max()} "
          f"({red.log_date.nunique():,} distinct days)")
    print("=" * 66)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default=str(DEFAULT_IN))
    ap.add_argument("--out", dest="out_path", default=str(DEFAULT_OUT))
    ap.add_argument("--target-mb", type=float, default=17.0)
    args = ap.parse_args()
    reduce_usage_logs(Path(args.in_path), Path(args.out_path), args.target_mb)
