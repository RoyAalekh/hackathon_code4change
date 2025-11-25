"""Configuration-driven RL agent training and evaluation.

Modular training pipeline for reinforcement learning in court scheduling.
"""

import argparse
import json
import numpy as np
from pathlib import Path
from datetime import date
from dataclasses import dataclass
from typing import Dict, Any

from rl.simple_agent import TabularQAgent
from rl.training import train_agent, evaluate_agent
from scheduler.data.case_generator import CaseGenerator


@dataclass
class TrainingConfig:
    """Training configuration parameters."""
    episodes: int = 50
    cases_per_episode: int = 500
    episode_length: int = 30
    learning_rate: float = 0.1
    initial_epsilon: float = 0.3
    discount: float = 0.95
    model_name: str = "trained_rl_agent.pkl"
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'TrainingConfig':
        """Create config from dictionary."""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__annotations__})
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'TrainingConfig':
        """Load config from JSON file."""
        with open(config_path) as f:
            return cls.from_dict(json.load(f))


def run_training_experiment(config: TrainingConfig = None):
    """Run configurable RL training experiment.
    
    Args:
        config: Training configuration. If None, uses defaults.
    """
    if config is None:
        config = TrainingConfig()
        
    print("=" * 70)
    print("RL AGENT TRAINING EXPERIMENT")
    print("=" * 70)
    
    print(f"Training Parameters:")
    print(f"  Episodes: {config.episodes}")
    print(f"  Cases per episode: {config.cases_per_episode}")
    print(f"  Episode length: {config.episode_length} days")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Initial exploration: {config.initial_epsilon}")
    
    # Initialize agent
    agent = TabularQAgent(
        learning_rate=config.learning_rate,
        epsilon=config.initial_epsilon,
        discount=config.discount
    )
    
    print(f"\nInitial agent state: {agent.get_stats()}")
    
    # Training phase
    print("\n" + "=" * 50)
    print("TRAINING PHASE")
    print("=" * 50)
    
    training_stats = train_agent(
        agent=agent,
        episodes=config.episodes,
        cases_per_episode=config.cases_per_episode,
        episode_length=config.episode_length,
        verbose=True
    )
    
    # Save trained agent
    model_path = Path("models")
    model_path.mkdir(exist_ok=True)
    agent_file = model_path / config.model_name
    agent.save(agent_file)
    print(f"\nTrained agent saved to: {agent_file}")
    
    # Generate test cases for evaluation
    print("\n" + "=" * 50)
    print("EVALUATION PHASE")
    print("=" * 50)
    
    test_start = date(2024, 7, 1)
    test_end = date(2024, 8, 1)
    test_generator = CaseGenerator(start=test_start, end=test_end, seed=999)
    test_cases = test_generator.generate(1000, stage_mix_auto=True)
    
    print(f"Generated {len(test_cases)} test cases")
    
    # Evaluate trained agent
    evaluation_results = evaluate_agent(
        agent=agent,
        test_cases=test_cases,
        episodes=5,
        episode_length=60
    )
    
    # Print final analysis
    print("\n" + "=" * 50)
    print("TRAINING ANALYSIS")
    print("=" * 50)
    
    final_stats = agent.get_stats()
    print(f"Final agent statistics:")
    print(f"  States explored: {final_stats['states_visited']:,}")
    print(f"  Q-table size: {final_stats['q_table_size']:,}")
    print(f"  Total Q-updates: {final_stats['total_updates']:,}")
    print(f"  Final epsilon: {final_stats['epsilon']:.3f}")
    
    # Training progression analysis
    if len(training_stats["disposal_rates"]) >= 10:
        early_performance = np.mean(training_stats["disposal_rates"][:10])
        late_performance = np.mean(training_stats["disposal_rates"][-10:])
        improvement = late_performance - early_performance
        
        print(f"\nLearning progression:")
        print(f"  Early episodes (1-10): {early_performance:.1%} disposal rate")
        print(f"  Late episodes (-10 to end): {late_performance:.1%} disposal rate")
        print(f"  Improvement: {improvement:.1%}")
        
        if improvement > 0.01:  # 1% improvement threshold
            print("  STATUS: Agent showed learning progress")
        else:
            print("  STATUS: Limited learning detected")
    
    # State space coverage analysis
    theoretical_states = 11 * 10 * 10 * 2 * 2 * 10  # 6D discretized state space
    coverage = final_stats['states_visited'] / theoretical_states
    print(f"\nState space analysis:")
    print(f"  Theoretical max states: {theoretical_states:,}")
    print(f"  States actually visited: {final_stats['states_visited']:,}")
    print(f"  Coverage: {coverage:.1%}")
    
    if coverage < 0.01:
        print("  WARNING: Very low state space exploration")
    elif coverage < 0.1:
        print("  NOTE: Limited state space exploration (expected)")
    else:
        print("  GOOD: Reasonable state space exploration")
    
    print("\n" + "=" * 50)
    print("PERFORMANCE SUMMARY")
    print("=" * 50)
    
    print(f"Trained RL Agent Performance:")
    print(f"  Mean disposal rate: {evaluation_results['mean_disposal_rate']:.1%}")
    print(f"  Standard deviation: {evaluation_results['std_disposal_rate']:.1%}")
    print(f"  Mean utilization: {evaluation_results['mean_utilization']:.1%}")
    print(f"  Avg hearings to disposal: {evaluation_results['mean_hearings_to_disposal']:.1f}")
    
    # Compare with baseline from previous runs (known values)
    baseline_disposal = 0.107  # 10.7% from readiness policy
    rl_disposal = evaluation_results['mean_disposal_rate']
    
    print(f"\nComparison with Baseline:")
    print(f"  Baseline (Readiness): {baseline_disposal:.1%}")
    print(f"  RL Agent: {rl_disposal:.1%}")
    print(f"  Difference: {(rl_disposal - baseline_disposal):.1%}")
    
    if rl_disposal > baseline_disposal + 0.01:  # 1% improvement threshold
        print("  RESULT: RL agent outperforms baseline")
    elif rl_disposal > baseline_disposal - 0.01:
        print("  RESULT: RL agent performs comparably to baseline") 
    else:
        print("  RESULT: RL agent underperforms baseline")
    
    # Recommendations
    print("\n" + "=" * 50)
    print("RECOMMENDATIONS")
    print("=" * 50)
    
    if coverage < 0.01:
        print("1. Increase training episodes for better state exploration")
        print("2. Consider state space dimensionality reduction")
        
    if final_stats['total_updates'] < 10000:
        print("3. Extend training duration for more Q-value updates")
        
    if evaluation_results['std_disposal_rate'] > 0.05:
        print("4. High variance detected - consider ensemble methods")
    
    if rl_disposal <= baseline_disposal:
        print("5. Reward function may need tuning")
        print("6. Consider different exploration strategies")
        print("7. Baseline policy is already quite effective")
    
    print("\nExperiment complete.")
    return agent, training_stats, evaluation_results


def main():
    """CLI interface for RL training."""
    parser = argparse.ArgumentParser(description="Train RL agent for court scheduling")
    parser.add_argument("--config", type=Path, help="Training configuration file (JSON)")
    parser.add_argument("--episodes", type=int, help="Number of training episodes")
    parser.add_argument("--learning-rate", type=float, help="Learning rate")
    parser.add_argument("--epsilon", type=float, help="Initial exploration rate")
    parser.add_argument("--model-name", help="Output model filename")
    
    args = parser.parse_args()
    
    # Load config
    if args.config and args.config.exists():
        config = TrainingConfig.from_file(args.config)
        print(f"Loaded configuration from {args.config}")
    else:
        config = TrainingConfig()
        print("Using default configuration")
    
    # Override config with CLI args
    if args.episodes:
        config.episodes = args.episodes
    if args.learning_rate:
        config.learning_rate = args.learning_rate
    if args.epsilon:
        config.initial_epsilon = args.epsilon
    if args.model_name:
        config.model_name = args.model_name
    
    # Run training
    return run_training_experiment(config)


if __name__ == "__main__":
    main()
