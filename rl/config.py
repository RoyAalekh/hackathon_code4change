"""RL training configuration and hyperparameters.

This module contains all configurable parameters for RL agent training,
separate from domain constants and simulation settings.
"""

from dataclasses import dataclass


@dataclass
class RLTrainingConfig:
    """Configuration for RL agent training.
    
    Hyperparameters that affect learning behavior and convergence.
    """
    # Training episodes
    episodes: int = 100
    cases_per_episode: int = 1000
    episode_length_days: int = 60

    # Courtroom + allocation constraints
    courtrooms: int = 5
    daily_capacity_per_courtroom: int = 151
    cap_daily_allocations: bool = True
    max_daily_allocations: int | None = None  # Optional hard cap (overrides computed capacity)
    enforce_min_gap: bool = True
    apply_judge_preferences: bool = True
    
    # Q-learning hyperparameters
    learning_rate: float = 0.15
    discount_factor: float = 0.95
    
    # Exploration strategy
    initial_epsilon: float = 0.4
    epsilon_decay: float = 0.99
    min_epsilon: float = 0.05
    
    # Training data generation
    training_seed: int = 42
    stage_mix_auto: bool = True  # Use EDA-derived stage distribution
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if not (0.0 < self.learning_rate <= 1.0):
            raise ValueError(f"learning_rate must be in (0, 1], got {self.learning_rate}")
        
        if not (0.0 <= self.discount_factor <= 1.0):
            raise ValueError(f"discount_factor must be in [0, 1], got {self.discount_factor}")
        
        if not (0.0 <= self.initial_epsilon <= 1.0):
            raise ValueError(f"initial_epsilon must be in [0, 1], got {self.initial_epsilon}")
        
        if self.episodes < 1:
            raise ValueError(f"episodes must be >= 1, got {self.episodes}")
        
        if self.cases_per_episode < 1:
            raise ValueError(f"cases_per_episode must be >= 1, got {self.cases_per_episode}")

        if self.courtrooms < 1:
            raise ValueError(f"courtrooms must be >= 1, got {self.courtrooms}")

        if self.daily_capacity_per_courtroom < 1:
            raise ValueError(
                f"daily_capacity_per_courtroom must be >= 1, got {self.daily_capacity_per_courtroom}"
            )

        if self.max_daily_allocations is not None and self.max_daily_allocations < 1:
            raise ValueError(
                f"max_daily_allocations must be >= 1 when provided, got {self.max_daily_allocations}"
            )


@dataclass
class PolicyConfig:
    """Configuration for scheduling policy behavior.
    
    Settings that affect how policies prioritize and filter cases.
    """
    # Minimum gap between hearings (days)
    min_gap_days: int = 7  # From MIN_GAP_BETWEEN_HEARINGS in config.py
    
    # Maximum gap before alert (days)
    max_gap_alert_days: int = 90  # From MAX_GAP_WITHOUT_ALERT
    
    # Old case threshold for priority boost (days)
    old_case_threshold_days: int = 180
    
    # Ripeness filtering
    skip_unripe_cases: bool = True
    allow_old_unripe_cases: bool = True  # Allow scheduling if age > old_case_threshold
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.min_gap_days < 0:
            raise ValueError(f"min_gap_days must be >= 0, got {self.min_gap_days}")
        
        if self.max_gap_alert_days < self.min_gap_days:
            raise ValueError(
                f"max_gap_alert_days ({self.max_gap_alert_days}) must be >= "
                f"min_gap_days ({self.min_gap_days})"
            )


# Default configurations
DEFAULT_RL_TRAINING_CONFIG = RLTrainingConfig()
DEFAULT_POLICY_CONFIG = PolicyConfig()

# Quick demo configuration (for testing)
QUICK_DEMO_RL_CONFIG = RLTrainingConfig(
    episodes=20,
    cases_per_episode=1000,
    episode_length_days=45,
    learning_rate=0.15,
    initial_epsilon=0.4,
)
