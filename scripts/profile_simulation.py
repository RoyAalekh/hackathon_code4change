"""Profile simulation to identify performance bottlenecks."""
import cProfile
import pstats
from pathlib import Path
from io import StringIO

from scheduler.data.case_generator import CaseGenerator
from scheduler.simulation.engine import CourtSim, CourtSimConfig


def run_simulation():
    """Run a small simulation for profiling."""
    cases = CaseGenerator.from_csv(Path("data/generated/cases_small.csv"))
    print(f"Loaded {len(cases)} cases")
    
    config = CourtSimConfig(
        start=cases[0].filed_date if cases else None,
        days=30,
        seed=42,
        courtrooms=5,
        daily_capacity=151,
        policy="readiness",
    )
    
    sim = CourtSim(config, cases)
    result = sim.run()
    
    print(f"Completed: {result.hearings_total} hearings, {result.disposals} disposals")


if __name__ == "__main__":
    # Profile the simulation
    profiler = cProfile.Profile()
    profiler.enable()
    
    run_simulation()
    
    profiler.disable()
    
    # Print stats
    s = StringIO()
    stats = pstats.Stats(profiler, stream=s)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    stats.print_stats(30)  # Top 30 functions
    
    print("\n" + "="*80)
    print("TOP 30 CUMULATIVE TIME CONSUMERS")
    print("="*80)
    print(s.getvalue())
    
    # Also sort by total time
    s2 = StringIO()
    stats2 = pstats.Stats(profiler, stream=s2)
    stats2.strip_dirs()
    stats2.sort_stats('tottime')
    stats2.print_stats(20)
    
    print("\n" + "="*80)
    print("TOP 20 TOTAL TIME CONSUMERS")
    print("="*80)
    print(s2.getvalue())
