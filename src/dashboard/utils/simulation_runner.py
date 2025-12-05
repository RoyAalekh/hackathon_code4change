from __future__ import annotations
from pathlib import Path
from datetime import date

from cli.config import SimulateConfig
from src.data.case_generator import CaseGenerator
from src.simulation.engine import CourtSim, CourtSimConfig
from src.core.case import CaseStatus
from src.metrics.basic import gini


def merge_simulation_config(
    default_cfg: SimulateConfig,
    cases_path: str,
    days: int,
    start_date: date | None,
    policy: str,
    seed: int,
    log_dir: str,
) -> SimulateConfig:
    """Merge UI inputs with default simulation config."""
    return SimulateConfig(
        cases=Path(cases_path) if cases_path else default_cfg.cases,
        days=days or default_cfg.days,
        start=start_date or default_cfg.start,
        policy=policy or default_cfg.policy,
        seed=seed if seed is not None else default_cfg.seed,
        log_dir=Path(log_dir) if log_dir else default_cfg.log_dir,
    )


def run_simulation_dashboard(scfg: SimulateConfig, run_dir: Path):
    """
    Execute simulation based on the provided Streamlit configuration.
    """

    # ------------------------------------------------------------------
    # Load case data
    # ------------------------------------------------------------------
    path = scfg.cases
    if path.exists():
        cases = CaseGenerator.from_csv(path)
        start = scfg.start or (
            max(c.filed_date for c in cases) if cases else date.today()
        )
    else:
        # Fallback (CLI fallback behaviour)
        start = scfg.start or date.today().replace(day=1)
        gen = CaseGenerator(start=start, end=start.replace(day=28), seed=scfg.seed)
        cases = gen.generate(n_cases=5 * 151)

    # ------------------------------------------------------------------
    # Build CourtSimConfig
    # ------------------------------------------------------------------
    cfg = CourtSimConfig(
        start=start,
        days=scfg.days,
        seed=scfg.seed,
        policy=scfg.policy,
        duration_percentile=scfg.duration_percentile,
        log_dir=run_dir,
    )

    # ------------------------------------------------------------------
    # Run simulation
    # ------------------------------------------------------------------
    sim = CourtSim(cfg, cases)
    res = sim.run()

    # ------------------------------------------------------------------
    # Collect metrics exactly like CLI
    # ------------------------------------------------------------------
    disp_times = [
        (c.disposal_date - c.filed_date).days
        for c in cases
        if c.disposal_date is not None and c.status == CaseStatus.DISPOSED
    ]
    gini_disp = gini(disp_times) if disp_times else 0.0

    summary_text = f"""
Simulation Complete!
Horizon: {cfg.start} -> {res.end_date} ({cfg.days} days)

Hearing Metrics:
  Total: {res.hearings_total}
  Heard: {res.hearings_heard} ({res.hearings_heard / max(1, res.hearings_total):.1%})
  Adjourned: {res.hearings_adjourned} ({res.hearings_adjourned / max(1, res.hearings_total):.1%})

Disposal Metrics:
  Disposed: {res.disposals} ({res.disposals / len(cases):.1%})
  Gini coefficient: {gini_disp:.3f}

Efficiency:
  Utilization: {res.utilization:.2%}
  Avg hearings/day: {res.hearings_total / max(1, cfg.days):.2f}
"""
    # Merge engine insights into report.txt
    insights_text = (getattr(res, "insights_text", "") or "").strip()
    if insights_text:
        full_report = summary_text.rstrip() + "\n\n" + insights_text + "\n"
    else:
        full_report = summary_text
    (run_dir / "report.txt").write_text(full_report, encoding="utf-8")

    # -------------------------------------------------------
    # Locate generated CSVs (if they exist)
    # -------------------------------------------------------
    metrics_path = run_dir / "metrics.csv"
    events_path = run_dir / "events.csv"

    return {
        "summary": summary_text,
        "insights": insights_text,
        "end_date": res.end_date,
        "metrics_path": metrics_path if metrics_path.exists() else None,
        "events_path": events_path if events_path.exists() else None,
    }
