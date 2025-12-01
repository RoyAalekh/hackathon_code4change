"""Unified CLI for Court Scheduling System.

This module provides a single entry point for key court scheduling operations:
- EDA pipeline execution
- Case generation
- Simulation runs
- Full workflow orchestration
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cli import __version__

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Initialize Typer app and console
app = typer.Typer(
    name="court-scheduler",
    help="Court Scheduling System for Karnataka High Court",
    add_completion=False,
)
# Use force_terminal=False to avoid legacy Windows rendering issues with Unicode
console = Console(legacy_windows=False)


@app.command()
def eda(
    skip_clean: bool = typer.Option(
        False, "--skip-clean", help="Skip data loading and cleaning"
    ),
    skip_viz: bool = typer.Option(
        False, "--skip-viz", help="Skip visualization generation"
    ),
    skip_params: bool = typer.Option(
        False, "--skip-params", help="Skip parameter extraction"
    ),
) -> None:
    """Run the EDA pipeline (load, explore, extract parameters)."""
    console.print("[bold blue]Running EDA Pipeline[/bold blue]")

    try:
        # Import here to avoid loading heavy dependencies if not needed
        from eda.exploration import run_exploration
        from eda.load_clean import run_load_and_clean
        from eda.parameters import run_parameter_export

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if not skip_clean:
                task = progress.add_task("Step 1/3: Load and clean data...", total=None)
                run_load_and_clean()
                progress.update(task, completed=True)
                console.print("Data loaded and cleaned")

            if not skip_viz:
                task = progress.add_task(
                    "Step 2/3: Generate visualizations...", total=None
                )
                run_exploration()
                progress.update(task, completed=True)
                console.print("Visualizations generated")

            if not skip_params:
                task = progress.add_task("Step 3/3: Extract parameters...", total=None)
                run_parameter_export()
                progress.update(task, completed=True)
                console.print("Parameters extracted")

        console.print("\n[bold]EDA Pipeline Complete[/bold]")
        console.print("Outputs: reports/figures/")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def generate(
    config: Path = typer.Option(  # noqa: B008
        None,
        "--config",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to config (.toml or .json)",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt for parameters interactively"
    ),
    n_cases: int = typer.Option(
        10000, "--cases", "-n", help="Number of cases to generate"
    ),
    start_date: str = typer.Option(
        "2022-01-01", "--start", help="Start date (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option("2023-12-31", "--end", help="End date (YYYY-MM-DD)"),
    output: str = typer.Option(
        "data/generated/cases.csv", "--output", "-o", help="Output CSV file"
    ),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility"),
    case_type_dist: str = typer.Option(
        None,
        "--case-type-dist",
        help=(
            'Custom case type distribution. Accepts JSON (e.g., \'{"Writ":0.6,"Civil":0.4}\') '
            "or comma-separated pairs 'Writ:0.6,Civil:0.4'. Defaults to historical distribution."
        ),
    ),
) -> None:
    """Generate synthetic test cases for simulation."""
    console.print(f"[bold blue]Generating {n_cases:,} test cases[/bold blue]")

    try:
        from datetime import date as date_cls

        from cli.config import GenerateConfig, load_generate_config
        from scheduler.data.case_generator import CaseGenerator

        # Resolve parameters: config -> interactive -> flags
        if config:
            cfg = load_generate_config(config)
        else:
            if interactive:
                n_cases = typer.prompt("Number of cases", default=n_cases)
                start_date = typer.prompt("Start date (YYYY-MM-DD)", default=start_date)
                end_date = typer.prompt("End date (YYYY-MM-DD)", default=end_date)
                output = typer.prompt("Output CSV path", default=output)
                seed = typer.prompt("Random seed", default=seed)
            cfg = GenerateConfig(
                n_cases=n_cases,
                start=date_cls.fromisoformat(start_date),
                end=date_cls.fromisoformat(end_date),
                output=Path(output),
                seed=seed,
            )

        start = cfg.start
        end = cfg.end
        output_path = cfg.output
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating cases...", total=None)

            # Parse optional custom case type distribution
            def _parse_case_type_dist(s: str | None) -> dict | None:
                if not s:
                    return None
                s = s.strip()
                try:
                    import json

                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass
                # Try comma-separated pairs format
                parts = [p.strip() for p in s.split(",") if p.strip()]
                dist: dict[str, float] = {}
                for part in parts:
                    if ":" not in part:
                        continue
                    k, v = part.split(":", 1)
                    k = k.strip()
                    try:
                        val = float(v)
                    except ValueError:
                        continue
                    if k:
                        dist[k] = val
                return dist or None

            user_dist = _parse_case_type_dist(case_type_dist)

            gen = CaseGenerator(start=start, end=end, seed=seed)
            cases = gen.generate(
                n_cases, stage_mix_auto=True, case_type_distribution=user_dist
            )
            # Write primary cases file
            CaseGenerator.to_csv(cases, output_path)
            # Also write detailed hearings history alongside, for the dashboard/classifier
            hearings_path = output_path.parent / "hearings.csv"
            CaseGenerator.to_hearings_csv(cases, hearings_path)

            progress.update(task, completed=True)

        console.print(f"Generated {len(cases):,} cases")
        console.print(f"Saved to: {output_path}")
        console.print(f"Hearings history: {hearings_path}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def simulate(
    config: Path = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to config (.toml or .json)",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", help="Prompt for parameters interactively"
    ),
    cases_csv: str = typer.Option(
        "data/generated/cases.csv", "--cases", help="Input cases CSV"
    ),
    days: int = typer.Option(
        384, "--days", "-d", help="Number of working days to simulate"
    ),
    start_date: str = typer.Option(
        None, "--start", help="Simulation start date (YYYY-MM-DD)"
    ),
    policy: str = typer.Option(
        "readiness", "--policy", "-p", help="Scheduling policy (fifo/age/readiness)"
    ),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    log_dir: str = typer.Option(
        None, "--log-dir", "-o", help="Output directory for logs"
    ),
) -> None:
    """Run court scheduling simulation."""
    console.print(f"[bold blue]Running {days}-day simulation[/bold blue]")

    try:
        from datetime import date as date_cls

        from cli.config import SimulateConfig, load_simulate_config
        from scheduler.core.case import CaseStatus
        from scheduler.data.case_generator import CaseGenerator
        from scheduler.metrics.basic import gini
        from scheduler.simulation.engine import CourtSim, CourtSimConfig

        # Resolve parameters: config -> interactive -> flags
        if config:
            scfg = load_simulate_config(config)
            # CLI flags override config if provided
            scfg = scfg.model_copy(
                update={
                    "cases": Path(cases_csv) if cases_csv else scfg.cases,
                    "days": days if days else scfg.days,
                    "start": (
                        date_cls.fromisoformat(start_date) if start_date else scfg.start
                    ),
                    "policy": policy if policy else scfg.policy,
                    "seed": seed if seed else scfg.seed,
                    "log_dir": (Path(log_dir) if log_dir else scfg.log_dir),
                }
            )
        else:
            if interactive:
                cases_csv = typer.prompt("Cases CSV", default=cases_csv)
                days = typer.prompt("Days to simulate", default=days)
                start_date = (
                    typer.prompt(
                        "Start date (YYYY-MM-DD) or blank", default=start_date or ""
                    )
                    or None
                )
                policy = typer.prompt("Policy [readiness|fifo|age]", default=policy)
                seed = typer.prompt("Random seed", default=seed)
                log_dir = (
                    typer.prompt("Log dir (or blank)", default=log_dir or "") or None
                )
            scfg = SimulateConfig(
                cases=Path(cases_csv),
                days=days,
                start=(date_cls.fromisoformat(start_date) if start_date else None),
                policy=policy,
                seed=seed,
                log_dir=(Path(log_dir) if log_dir else None),
            )

        # Load cases
        path = scfg.cases
        if path.exists():
            cases = CaseGenerator.from_csv(path)
            start = scfg.start or (
                max(c.filed_date for c in cases) if cases else date_cls.today()
            )
        else:
            console.print(
                f"[yellow]Warning:[/yellow] {path} not found. Generating test cases..."
            )
            start = scfg.start or date_cls.today().replace(day=1)
            gen = CaseGenerator(start=start, end=start.replace(day=28), seed=scfg.seed)
            cases = gen.generate(n_cases=5 * 151)

        # Run simulation
        cfg = CourtSimConfig(
            start=start,
            days=scfg.days,
            seed=scfg.seed,
            policy=scfg.policy,
            duration_percentile="median",
            log_dir=scfg.log_dir,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Simulating {days} days...", total=None)
            sim = CourtSim(cfg, cases)
            res = sim.run()
            progress.update(task, completed=True)

        # Display results
        console.print("\n[bold green]Simulation Complete![/bold green]")
        console.print(f"\nHorizon: {cfg.start} -> {res.end_date} ({days} days)")
        console.print("\n[bold]Hearing Metrics:[/bold]")
        console.print(f"  Total: {res.hearings_total:,}")
        console.print(
            f"  Heard: {res.hearings_heard:,} ({res.hearings_heard / max(1, res.hearings_total):.1%})"
        )
        console.print(
            f"  Adjourned: {res.hearings_adjourned:,} ({res.hearings_adjourned / max(1, res.hearings_total):.1%})"
        )

        disp_times = [
            (c.disposal_date - c.filed_date).days
            for c in cases
            if c.disposal_date is not None and c.status == CaseStatus.DISPOSED
        ]
        gini_disp = gini(disp_times) if disp_times else 0.0

        console.print("\n[bold]Disposal Metrics:[/bold]")
        console.print(
            f"  Cases disposed: {res.disposals:,} ({res.disposals / len(cases):.1%})"
        )
        console.print(f"  Gini coefficient: {gini_disp:.3f}")

        console.print("\n[bold]Efficiency:[/bold]")
        console.print(f"  Utilization: {res.utilization:.1%}")
        console.print(f"  Avg hearings/day: {res.hearings_total / days:.1f}")

        if log_dir:
            console.print("\n[bold cyan]Output Files:[/bold cyan]")
            console.print(f"  - {log_dir}/report.txt")
            console.print(f"  - {log_dir}/metrics.csv")
            console.print(f"  - {log_dir}/events.csv")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def workflow(
    n_cases: int = typer.Option(
        10000, "--cases", "-n", help="Number of cases to generate"
    ),
    sim_days: int = typer.Option(384, "--days", "-d", help="Simulation days"),
    output_dir: str = typer.Option(
        "data/workflow_run", "--output", "-o", help="Output directory"
    ),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
) -> None:
    """Run full workflow: EDA -> Generate -> Simulate -> Report."""
    console.print("[bold blue]Running Full Workflow[/bold blue]\n")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: EDA (skip if already done recently)
        console.print("[bold]Step 1/3:[/bold] EDA Pipeline")
        console.print("  Skipping (use 'court-scheduler eda' to regenerate)\n")

        # Step 2: Generate cases
        console.print("[bold]Step 2/3:[/bold] Generate Cases")
        cases_file = output_path / "cases.csv"
        from datetime import date as date_cls

        from scheduler.data.case_generator import CaseGenerator

        start = date_cls(2022, 1, 1)
        end = date_cls(2023, 12, 31)

        gen = CaseGenerator(start=start, end=end, seed=seed)
        cases = gen.generate(n_cases, stage_mix_auto=True)
        CaseGenerator.to_csv(cases, cases_file)
        console.print(f"  Generated {len(cases):,} cases\n")

        # Step 3: Run simulation
        console.print("[bold]Step 3/3:[/bold] Run Simulation")
        from scheduler.simulation.engine import CourtSim, CourtSimConfig

        sim_start = max(c.filed_date for c in cases)
        cfg = CourtSimConfig(
            start=sim_start,
            days=sim_days,
            seed=seed,
            policy="readiness",
            log_dir=output_path,
        )

        sim = CourtSim(cfg, cases)
        sim.run()
        console.print("  Simulation complete\n")

        # Summary
        console.print("[bold]Workflow Complete[/bold]")
        console.print(f"\nResults: {output_path}/")
        console.print(f"  - cases.csv ({len(cases):,} cases)")
        console.print("  - report.txt (simulation summary)")
        console.print("  - metrics.csv (daily metrics)")
        console.print("  - events.csv (event log)")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def dashboard(
    port: int = typer.Option(8501, "--port", "-p", help="Port to run dashboard on"),
    host: str = typer.Option("localhost", "--host", help="Host address to bind to"),
) -> None:
    """Launch interactive dashboard."""
    console.print("[bold blue]Launching Interactive Dashboard[/bold blue]")
    console.print(f"Dashboard will be available at: http://{host}:{port}")
    console.print("Press Ctrl+C to stop the dashboard\n")

    try:
        import subprocess
        import sys

        # Get path to dashboard app
        app_path = Path(__file__).parent.parent / "scheduler" / "dashboard" / "app.py"

        if not app_path.exists():
            console.print(
                f"[bold red]Error:[/bold red] Dashboard app not found at {app_path}"
            )
            raise typer.Exit(code=1)

        # Run streamlit
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.port",
            str(port),
            "--server.address",
            host,
            "--browser.gatherUsageStats",
            "false",
        ]

        subprocess.run(cmd)

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"Court Scheduler CLI v{__version__}")
    console.print("Court Scheduling System for Karnataka High Court")


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
