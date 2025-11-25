"""Unified CLI for Court Scheduling System.

This module provides a single entry point for all court scheduling operations:
- EDA pipeline execution
- Case generation
- Simulation runs
- Full workflow orchestration
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Initialize Typer app and console
app = typer.Typer(
    name="court-scheduler",
    help="Court Scheduling System for Karnataka High Court",
    add_completion=False,
)
console = Console()


@app.command()
def eda(
    skip_clean: bool = typer.Option(False, "--skip-clean", help="Skip data loading and cleaning"),
    skip_viz: bool = typer.Option(False, "--skip-viz", help="Skip visualization generation"),
    skip_params: bool = typer.Option(False, "--skip-params", help="Skip parameter extraction"),
) -> None:
    """Run the EDA pipeline (load, explore, extract parameters)."""
    console.print("[bold blue]Running EDA Pipeline[/bold blue]")
    
    try:
        # Import here to avoid loading heavy dependencies if not needed
        from src.eda_load_clean import run_load_and_clean
        from src.eda_exploration import run_exploration
        from src.eda_parameters import run_parameter_export
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if not skip_clean:
                task = progress.add_task("Step 1/3: Load and clean data...", total=None)
                run_load_and_clean()
                progress.update(task, completed=True)
                console.print("[green]\u2713[/green] Data loaded and cleaned")
            
            if not skip_viz:
                task = progress.add_task("Step 2/3: Generate visualizations...", total=None)
                run_exploration()
                progress.update(task, completed=True)
                console.print("[green]\u2713[/green] Visualizations generated")
            
            if not skip_params:
                task = progress.add_task("Step 3/3: Extract parameters...", total=None)
                run_parameter_export()
                progress.update(task, completed=True)
                console.print("[green]\u2713[/green] Parameters extracted")
        
        console.print("\n[bold green]\u2713 EDA Pipeline Complete![/bold green]")
        console.print("Outputs: reports/figures/")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def generate(
    config: Path = typer.Option(None, "--config", exists=True, dir_okay=False, readable=True, help="Path to config (.toml or .json)"),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt for parameters interactively"),
    n_cases: int = typer.Option(10000, "--cases", "-n", help="Number of cases to generate"),
    start_date: str = typer.Option("2022-01-01", "--start", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option("2023-12-31", "--end", help="End date (YYYY-MM-DD)"),
    output: str = typer.Option("data/generated/cases.csv", "--output", "-o", help="Output CSV file"),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility"),
) -> None:
    """Generate synthetic test cases for simulation."""
    console.print(f"[bold blue]Generating {n_cases:,} test cases[/bold blue]")
    
    try:
        from datetime import date as date_cls
        from scheduler.data.case_generator import CaseGenerator
        from .config_loader import load_generate_config
        from .config_models import GenerateConfig

        # Resolve parameters: config -> interactive -> flags
        if config:
            cfg = load_generate_config(config)
            # Note: in this first iteration, flags do not override config for generate
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
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating cases...", total=None)
            
            gen = CaseGenerator(start=start, end=end, seed=seed)
            cases = gen.generate(n_cases, stage_mix_auto=True)
            CaseGenerator.to_csv(cases, output_path)
            
            progress.update(task, completed=True)
        
        console.print(f"[green]\u2713[/green] Generated {len(cases):,} cases")
        console.print(f"[green]\u2713[/green] Saved to: {output_path}")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def simulate(
    config: Path = typer.Option(None, "--config", exists=True, dir_okay=False, readable=True, help="Path to config (.toml or .json)"),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt for parameters interactively"),
    cases_csv: str = typer.Option("data/generated/cases.csv", "--cases", help="Input cases CSV"),
    days: int = typer.Option(384, "--days", "-d", help="Number of working days to simulate"),
    start_date: str = typer.Option(None, "--start", help="Simulation start date (YYYY-MM-DD)"),
    policy: str = typer.Option("readiness", "--policy", "-p", help="Scheduling policy (fifo/age/readiness)"),
    seed: int = typer.Option(42, "--seed", help="Random seed"),
    log_dir: str = typer.Option(None, "--log-dir", "-o", help="Output directory for logs"),
) -> None:
    """Run court scheduling simulation."""
    console.print(f"[bold blue]Running {days}-day simulation[/bold blue]")
    
    try:
        from datetime import date as date_cls
        from scheduler.core.case import CaseStatus
        from scheduler.data.case_generator import CaseGenerator
        from scheduler.metrics.basic import gini
        from scheduler.simulation.engine import CourtSim, CourtSimConfig
        from .config_loader import load_simulate_config
        from .config_models import SimulateConfig
        
        # Resolve parameters: config -> interactive -> flags
        if config:
            scfg = load_simulate_config(config)
            # CLI flags override config if provided (best-effort)
            scfg = scfg.model_copy(update={
                "cases": Path(cases_csv) if cases_csv else scfg.cases,
                "days": days if days else scfg.days,
                "start": (date_cls.fromisoformat(start_date) if start_date else scfg.start),
                "policy": policy if policy else scfg.policy,
                "seed": seed if seed else scfg.seed,
                "log_dir": (Path(log_dir) if log_dir else scfg.log_dir),
            })
        else:
            if interactive:
                cases_csv = typer.prompt("Cases CSV", default=cases_csv)
                days = typer.prompt("Days to simulate", default=days)
                start_date = typer.prompt("Start date (YYYY-MM-DD) or blank", default=start_date or "") or None
                policy = typer.prompt("Policy [readiness|fifo|age]", default=policy)
                seed = typer.prompt("Random seed", default=seed)
                log_dir = typer.prompt("Log dir (or blank)", default=log_dir or "") or None
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
            start = scfg.start or (max(c.filed_date for c in cases) if cases else date_cls.today())
        else:
            console.print(f"[yellow]Warning:[/yellow] {path} not found. Generating test cases...")
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
        
        # Calculate additional metrics for report
        allocator_stats = sim.allocator.get_utilization_stats()
        disp_times = [(c.disposal_date - c.filed_date).days for c in cases 
                      if c.disposal_date is not None and c.status == CaseStatus.DISPOSED]
        gini_disp = gini(disp_times) if disp_times else 0.0
        
        # Disposal rates by case type
        case_type_stats = {}
        for c in cases:
            if c.case_type not in case_type_stats:
                case_type_stats[c.case_type] = {"total": 0, "disposed": 0}
            case_type_stats[c.case_type]["total"] += 1
            if c.is_disposed:
                case_type_stats[c.case_type]["disposed"] += 1
        
        # Ripeness distribution
        active_cases = [c for c in cases if not c.is_disposed]
        ripeness_dist = {}
        for c in active_cases:
            status = c.ripeness_status
            ripeness_dist[status] = ripeness_dist.get(status, 0) + 1
        
        # Generate report.txt if log_dir specified
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            report_path = Path(log_dir) / "report.txt"
            with report_path.open("w", encoding="utf-8") as rf:
                rf.write("=" * 80 + "\n")
                rf.write("SIMULATION REPORT\n")
                rf.write("=" * 80 + "\n\n")
                
                rf.write(f"Configuration:\n")
                rf.write(f"  Cases: {len(cases)}\n")
                rf.write(f"  Days simulated: {days}\n")
                rf.write(f"  Policy: {policy}\n")
                rf.write(f"  Horizon end: {res.end_date}\n\n")
                
                rf.write(f"Hearing Metrics:\n")
                rf.write(f"  Total hearings: {res.hearings_total:,}\n")
                rf.write(f"  Heard: {res.hearings_heard:,} ({res.hearings_heard/max(1,res.hearings_total):.1%})\n")
                rf.write(f"  Adjourned: {res.hearings_adjourned:,} ({res.hearings_adjourned/max(1,res.hearings_total):.1%})\n\n")
                
                rf.write(f"Disposal Metrics:\n")
                rf.write(f"  Cases disposed: {res.disposals:,}\n")
                rf.write(f"  Disposal rate: {res.disposals/len(cases):.1%}\n")
                rf.write(f"  Gini coefficient: {gini_disp:.3f}\n\n")
                
                rf.write(f"Disposal Rates by Case Type:\n")
                for ct in sorted(case_type_stats.keys()):
                    stats = case_type_stats[ct]
                    rate = (stats["disposed"] / stats["total"] * 100) if stats["total"] > 0 else 0
                    rf.write(f"  {ct:4s}: {stats['disposed']:4d}/{stats['total']:4d} ({rate:5.1f}%)\n")
                rf.write("\n")
                
                rf.write(f"Efficiency Metrics:\n")
                rf.write(f"  Court utilization: {res.utilization:.1%}\n")
                rf.write(f"  Avg hearings/day: {res.hearings_total/days:.1f}\n\n")
                
                rf.write(f"Ripeness Impact:\n")
                rf.write(f"  Transitions: {res.ripeness_transitions:,}\n")
                rf.write(f"  Cases filtered (unripe): {res.unripe_filtered:,}\n")
                if res.hearings_total + res.unripe_filtered > 0:
                    rf.write(f"  Filter rate: {res.unripe_filtered/(res.hearings_total + res.unripe_filtered):.1%}\n")
                rf.write("\nFinal Ripeness Distribution:\n")
                for status in sorted(ripeness_dist.keys()):
                    count = ripeness_dist[status]
                    pct = (count / len(active_cases) * 100) if active_cases else 0
                    rf.write(f"  {status}: {count} ({pct:.1f}%)\n")
                
                # Courtroom allocation metrics
                if allocator_stats:
                    rf.write("\nCourtroom Allocation:\n")
                    rf.write(f"  Strategy: load_balanced\n")
                    rf.write(f"  Load balance fairness (Gini): {allocator_stats['load_balance_gini']:.3f}\n")
                    rf.write(f"  Avg daily load: {allocator_stats['avg_daily_load']:.1f} cases\n")
                    rf.write(f"  Allocation changes: {allocator_stats['allocation_changes']:,}\n")
                    rf.write(f"  Capacity rejections: {allocator_stats['capacity_rejections']:,}\n\n")
                    rf.write("  Courtroom-wise totals:\n")
                    for cid in range(1, sim.cfg.courtrooms + 1):
                        total = allocator_stats['courtroom_totals'][cid]
                        avg = allocator_stats['courtroom_averages'][cid]
                        rf.write(f"    Courtroom {cid}: {total:,} cases ({avg:.1f}/day)\n")
    
        # Display results to console
        console.print("\n[bold green]Simulation Complete![/bold green]")
        console.print(f"\nHorizon: {cfg.start} \u2192 {res.end_date} ({days} days)")
        console.print(f"\n[bold]Hearing Metrics:[/bold]")
        console.print(f"  Total: {res.hearings_total:,}")
        console.print(f"  Heard: {res.hearings_heard:,} ({res.hearings_heard/max(1,res.hearings_total):.1%})")
        console.print(f"  Adjourned: {res.hearings_adjourned:,} ({res.hearings_adjourned/max(1,res.hearings_total):.1%})")
        
        console.print(f"\n[bold]Disposal Metrics:[/bold]")
        console.print(f"  Cases disposed: {res.disposals:,} ({res.disposals/len(cases):.1%})")
        console.print(f"  Gini coefficient: {gini_disp:.3f}")
        
        console.print(f"\n[bold]Efficiency:[/bold]")
        console.print(f"  Utilization: {res.utilization:.1%}")
        console.print(f"  Avg hearings/day: {res.hearings_total/days:.1f}")
        
        if log_dir:
            console.print(f"\n[bold cyan]Output Files:[/bold cyan]")
            console.print(f"  - {log_dir}/report.txt (comprehensive report)")
            console.print(f"  - {log_dir}/metrics.csv (daily metrics)")
            console.print(f"  - {log_dir}/events.csv (event log)")
            
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def workflow(
    n_cases: int = typer.Option(10000, "--cases", "-n", help="Number of cases to generate"),
    sim_days: int = typer.Option(384, "--days", "-d", help="Simulation days"),
    output_dir: str = typer.Option("data/workflow_run", "--output", "-o", help="Output directory"),
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
        console.print(f"  [green]\u2713[/green] Generated {len(cases):,} cases\n")
        
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
        res = sim.run()
        console.print(f"  [green]\u2713[/green] Simulation complete\n")
        
        # Summary
        console.print("[bold green]\u2713 Workflow Complete![/bold green]")
        console.print(f"\nResults: {output_path}/")
        console.print(f"  - cases.csv ({len(cases):,} cases)")
        console.print(f"  - report.txt (simulation summary)")
        console.print(f"  - metrics.csv (daily metrics)")
        console.print(f"  - events.csv (event log)")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information."""
    from court_scheduler import __version__
    console.print(f"Court Scheduler CLI v{__version__}")
    console.print("Court Scheduling System for Karnataka High Court")


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
