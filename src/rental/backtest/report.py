"""Backtest report renderer.

Produces a self-contained HTML file with:

  - score-vs-realized-return per snapshot (table)
  - quintile means per snapshot (table + simple inline SVG line chart)
  - bootstrap CI on top-minus-bottom for each snapshot
  - walk-forward stability summary (train vs. validate mean Spearman)
  - recommended weights
  - baseline comparisons

If the top quintile doesn't beat the bottom quintile with statistical
significance on the primary target (mean top-minus-bottom > 0 AND
bootstrap CI lower bound > 0 across snapshots), we slap a "NOT READY"
banner on the report. The scorecard isn't trusted to ship until the
banner is gone.

Charts: deliberately no plotly/matplotlib. Hand-rolled SVG so the
report renders in any browser with zero dependencies beyond Jinja2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import jinja2

from rental.backtest.run import (
    BacktestResult,
    SnapshotResult,
    bootstrap_top_minus_bottom_ci,
)
from rental.backtest.tune import WeightTuneResult

_TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class ReportContext:
    """Pre-computed numbers handed straight to the Jinja template."""

    snapshots: list[dict] = field(default_factory=list)
    overall_mean_spearman: float = float("nan")
    overall_mean_top_minus_bottom: float = float("nan")
    ready: bool = False
    tune: dict | None = None
    generated_at: str = ""


def _svg_line_chart(values: list[float], width: int = 300, height: int = 100) -> str:
    """Inline SVG of quintile means as a line chart.

    Empty / all-NaN -> empty SVG (so the template renders something).
    """
    clean = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    if not clean:
        return f'<svg width="{width}" height="{height}"></svg>'
    lo, hi = min(clean), max(clean)
    span = (hi - lo) or 1.0
    pad = 8
    plot_h = height - 2 * pad
    plot_w = width - 2 * pad
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        if isinstance(v, float) and math.isnan(v):
            continue
        x = pad + (plot_w * i / max(1, n - 1))
        y = pad + plot_h - (plot_h * (v - lo) / span)
        pts.append(f"{x:.1f},{y:.1f}")
    polyline = (
        f'<polyline fill="none" stroke="#3366cc" stroke-width="2" '
        f'points="{" ".join(pts)}"/>'
    )
    dots = "".join(
        f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3" fill="#3366cc"/>'
        for p in pts
    )
    baseline = (
        f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" '
        f'stroke="#ccc" stroke-width="1"/>'
    )
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"{baseline}{polyline}{dots}</svg>"
    )


def _format_snapshot(snap: SnapshotResult) -> dict:
    ci_lo, ci_mid, ci_hi = bootstrap_top_minus_bottom_ci(
        snap.universe, n_bootstrap=500, seed=snap.snapshot_date.toordinal(),
    )
    return {
        "snapshot_date": snap.snapshot_date.isoformat(),
        "n_zips": snap.n_zips,
        "spearman": snap.spearman,
        "quintile_means": snap.quintile_means,
        "quintile_svg": _svg_line_chart(snap.quintile_means),
        "top_minus_bottom": snap.top_minus_bottom,
        "ci_low": ci_lo,
        "ci_mid": ci_mid,
        "ci_high": ci_hi,
        "significant": (
            not math.isnan(ci_lo) and ci_lo > 0
        ),
        "baselines": snap.baselines,
    }


def build_context(
    result: BacktestResult,
    tune: WeightTuneResult | None = None,
) -> ReportContext:
    snaps = [_format_snapshot(s) for s in result.snapshots]
    mean_spearman = (
        sum(s["spearman"] for s in snaps if not math.isnan(s["spearman"]))
        / max(1, sum(1 for s in snaps if not math.isnan(s["spearman"])))
        if snaps else float("nan")
    )
    mean_tmb = (
        sum(s["top_minus_bottom"] for s in snaps if not math.isnan(s["top_minus_bottom"]))
        / max(1, sum(1 for s in snaps if not math.isnan(s["top_minus_bottom"])))
        if snaps else float("nan")
    )

    # "Ready" = at least 75% of snapshots show CI lower bound > 0 AND mean
    # top-minus-bottom is positive overall. Tight enough to flag the
    # easy fails; loose enough to not trip on a single noisy snapshot.
    sig_count = sum(1 for s in snaps if s["significant"])
    ready = (
        bool(snaps)
        and sig_count / len(snaps) >= 0.75
        and not math.isnan(mean_tmb)
        and mean_tmb > 0
    )

    tune_dict = None
    if tune is not None:
        tune_dict = {
            "best_weights": tune.best_weights,
            "train_mean_spearman": tune.train_mean_spearman,
            "validate_mean_spearman": tune.validate_mean_spearman,
            "grid_size": tune.grid_size,
        }

    return ReportContext(
        snapshots=snaps,
        overall_mean_spearman=mean_spearman,
        overall_mean_top_minus_bottom=mean_tmb,
        ready=ready,
        tune=tune_dict,
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


def _format_float(v: float, decimals: int = 4) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.{decimals}f}"


def render_report(
    result: BacktestResult,
    output_path: Path,
    tune: WeightTuneResult | None = None,
    template_dir: Path | None = None,
) -> Path:
    """Render the report to ``output_path``; return the path written."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir or _TEMPLATE_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    env.filters["fmt"] = _format_float
    template = env.get_template("backtest_report.html.j2")
    ctx = build_context(result, tune)
    html = template.render(ctx=ctx)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    return output_path
