"""Training pipeline for tabular Q-learning agent.

Implements episodic training on generated case data to learn optimal
case prioritization policies through simulation-based rewards.
"""

import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import date, timedelta
import random

from scheduler.data.case_generator import CaseGenerator
from scheduler.core.case import Case, CaseStatus
from scheduler.core.algorithm import SchedulingAlgorithm
from scheduler.core.courtroom import Courtroom
from scheduler.core.policy import SchedulerPolicy
from scheduler.simulation.policies.readiness import ReadinessPolicy
from scheduler.simulation.allocator import CourtroomAllocator, AllocationStrategy
from scheduler.control.overrides import Override, OverrideType, JudgePreferences
from .simple_agent import TabularQAgent, CaseState
from .rewards import EpisodeRewardHelper
from .config import (
    RLTrainingConfig,
    PolicyConfig,
    DEFAULT_RL_TRAINING_CONFIG,
    DEFAULT_POLICY_CONFIG,
)


class RLTrainingEnvironment:
    """Training environment for RL agent using court simulation."""

    def __init__(
        self,
        cases: List[Case],
        start_date: date,
        horizon_days: int = 90,
        rl_config: RLTrainingConfig | None = None,
        policy_config: PolicyConfig | None = None,
    ):
        """Initialize training environment.

        Args:
            cases: List of cases to simulate
            start_date: Simulation start date
            horizon_days: Training episode length in days
            rl_config: RL-specific training constraints
            policy_config: Policy knobs for ripeness/gap rules
        """
        self.cases = cases
        self.start_date = start_date
        self.horizon_days = horizon_days
        self.current_date = start_date
        self.episode_rewards = []
        self.rl_config = rl_config or DEFAULT_RL_TRAINING_CONFIG
        self.policy_config = policy_config or DEFAULT_POLICY_CONFIG
        self.reward_helper = EpisodeRewardHelper(total_cases=len(cases))

        # Resources mirroring production defaults
        self.courtrooms = [
            Courtroom(
                courtroom_id=i + 1,
                judge_id=f"J{i+1:03d}",
                daily_capacity=self.rl_config.daily_capacity_per_courtroom,
            )
            for i in range(self.rl_config.courtrooms)
        ]
        self.allocator = CourtroomAllocator(
            num_courtrooms=self.rl_config.courtrooms,
            per_courtroom_capacity=self.rl_config.daily_capacity_per_courtroom,
            strategy=AllocationStrategy.LOAD_BALANCED,
        )
        self.policy: SchedulerPolicy = ReadinessPolicy()
        self.algorithm = SchedulingAlgorithm(
            policy=self.policy,
            allocator=self.allocator,
            min_gap_days=self.policy_config.min_gap_days if self.rl_config.enforce_min_gap else 0,
        )
        self.preferences = self._build_preferences()

    def _build_preferences(self) -> Optional[JudgePreferences]:
        """Synthetic judge preferences for training context."""
        if not self.rl_config.apply_judge_preferences:
            return None

        capacity_overrides = {room.courtroom_id: room.daily_capacity for room in self.courtrooms}
        return JudgePreferences(
            judge_id="RL-JUDGE",
            capacity_overrides=capacity_overrides,
            case_type_preferences={
                "Monday": ["RSA"],
                "Tuesday": ["CCC"],
                "Wednesday": ["NI ACT"],
            },
        )
    def reset(self) -> List[Case]:
        """Reset environment for new training episode.

        Note: In practice, train_agent() generates fresh cases per episode,
        so case state doesn't need resetting. This method just resets
        environment state (date, rewards).
        """
        self.current_date = self.start_date
        self.episode_rewards = []
        self.reward_helper = EpisodeRewardHelper(total_cases=len(self.cases))
        return self.cases.copy()

    def capacity_ratio(self, remaining_slots: int) -> float:
        """Proportion of courtroom capacity still available for the day."""
        total_capacity = self.rl_config.courtrooms * self.rl_config.daily_capacity_per_courtroom
        return max(0.0, min(1.0, remaining_slots / total_capacity)) if total_capacity else 0.0

    def preference_score(self, case: Case) -> float:
        """Return 1.0 when case_type aligns with day-of-week preference, else 0."""
        if not self.preferences:
            return 0.0

        day_name = self.current_date.strftime("%A")
        preferred_types = self.preferences.case_type_preferences.get(day_name, [])
        return 1.0 if case.case_type in preferred_types else 0.0

    def step(self, agent_decisions: Dict[str, int]) -> Tuple[List[Case], Dict[str, float], bool]:
        """Execute one day of simulation with agent decisions via SchedulingAlgorithm."""
        rewards: Dict[str, float] = {}

        # Convert agent schedule actions into priority overrides
        overrides: List[Override] = []
        priority_boost = 1.0
        for case in self.cases:
            if agent_decisions.get(case.case_id) == 1:
                overrides.append(
                    Override(
                        override_id=f"rl-{case.case_id}-{self.current_date.isoformat()}",
                        override_type=OverrideType.PRIORITY,
                        case_id=case.case_id,
                        judge_id="RL-JUDGE",
                        timestamp=self.current_date,
                        new_priority=case.get_priority_score() + priority_boost,
                    )
                )
                priority_boost += 0.1  # keep relative ordering stable

        # Run scheduling algorithm (capacity, ripeness, min-gap enforced)
        result = self.algorithm.schedule_day(
            cases=self.cases,
            courtrooms=self.courtrooms,
            current_date=self.current_date,
            overrides=overrides or None,
            preferences=self.preferences,
        )

        # Flatten scheduled cases
        scheduled_cases = [c for cases in result.scheduled_cases.values() for c in cases]
        # Simulate hearing outcomes for scheduled cases
        for case in scheduled_cases:
            if case.is_disposed:
                continue

            outcome = self._simulate_hearing_outcome(case)
            was_heard = "heard" in outcome.lower()

            # Track gap relative to previous hearing for reward shaping
            previous_gap = None
            if case.last_hearing_date:
                previous_gap = max(0, (self.current_date - case.last_hearing_date).days)

            case.record_hearing(self.current_date, was_heard=was_heard, outcome=outcome)

            if was_heard:
                if outcome in ["FINAL DISPOSAL", "SETTLEMENT", "NA"]:
                    case.status = CaseStatus.DISPOSED
                    case.disposal_date = self.current_date
                elif outcome != "ADJOURNED":
                    case.current_stage = outcome

            # Compute reward using shared reward helper
            rewards[case.case_id] = self.reward_helper.compute_case_reward(
                case,
                was_scheduled=True,
                hearing_outcome=outcome,
                current_date=self.current_date,
                previous_gap_days=previous_gap,
            )
        # Update case ages
        for case in self.cases:
            case.update_age(self.current_date)

        # Move to next day
        self.current_date += timedelta(days=1)
        episode_done = (self.current_date - self.start_date).days >= self.horizon_days

        return self.cases, rewards, episode_done

    def _simulate_hearing_outcome(self, case: Case) -> str:
        """Simulate hearing outcome based on stage and case characteristics."""
        # Simplified outcome simulation
        current_stage = case.current_stage

        # Terminal stages - high disposal probability
        if current_stage in ["ORDERS / JUDGMENT", "FINAL DISPOSAL"]:
            if random.random() < 0.7:  # 70% chance of disposal
                return "FINAL DISPOSAL"
            else:
                return "ADJOURNED"

        # Early stages more likely to adjourn
        if current_stage in ["PRE-ADMISSION", "ADMISSION"]:
            if random.random() < 0.6:  # 60% adjournment rate
                return "ADJOURNED"
            else:
                # Progress to next logical stage
                if current_stage == "PRE-ADMISSION":
                    return "ADMISSION"
                else:
                    return "EVIDENCE"

        # Mid-stages
        if current_stage in ["EVIDENCE", "ARGUMENTS"]:
            if random.random() < 0.4:  # 40% adjournment rate
                return "ADJOURNED"
            else:
                if current_stage == "EVIDENCE":
                    return "ARGUMENTS"
                else:
                    return "ORDERS / JUDGMENT"

        # Default progression
        return "ARGUMENTS"


def train_agent(
    agent: TabularQAgent,
    rl_config: RLTrainingConfig = DEFAULT_RL_TRAINING_CONFIG,
    policy_config: PolicyConfig = DEFAULT_POLICY_CONFIG,
    verbose: bool = True,
) -> Dict:
    """Train RL agent using episodic simulation with courtroom constraints."""
    config = rl_config or DEFAULT_RL_TRAINING_CONFIG
    policy_cfg = policy_config or DEFAULT_POLICY_CONFIG

    # Align agent hyperparameters with config
    agent.discount = config.discount_factor
    agent.epsilon = config.initial_epsilon

>>>>>>> origin/codex/modify-training-for-schedulingalgorithm-integration
    training_stats = {
        "episodes": [],
        "total_rewards": [],
        "disposal_rates": [],
        "states_explored": [],
        "q_updates": [],
    }

    if verbose:
        print(f"Training RL agent for {config.episodes} episodes...")

    for episode in range(config.episodes):
        # Generate fresh cases for this episode
        start_date = date(2024, 1, 1) + timedelta(days=episode * 10)
        end_date = start_date + timedelta(days=30)

        generator = CaseGenerator(
            start=start_date,
            end=end_date,
            seed=config.training_seed + episode,
        )
        cases = generator.generate(config.cases_per_episode, stage_mix_auto=config.stage_mix_auto)

        # Initialize training environment
        env = RLTrainingEnvironment(
            cases,
            start_date,
            config.episode_length_days,
            rl_config=config,
            policy_config=policy_cfg,
        )

        # Reset environment
        episode_cases = env.reset()
        episode_reward = 0.0

        total_capacity = config.courtrooms * config.daily_capacity_per_courtroom

        # Run episode
        for _ in range(config.episode_length_days):
            # Get eligible cases (not disposed, basic filtering)
            eligible_cases = [c for c in episode_cases if not c.is_disposed]
            if not eligible_cases:
                break

            # Agent makes decisions for each case
            agent_decisions = {}
            case_states = {}

            daily_cap = config.max_daily_allocations or total_capacity
            if not config.cap_daily_allocations:
                daily_cap = len(eligible_cases)
            remaining_slots = min(daily_cap, total_capacity) if config.cap_daily_allocations else daily_cap

            for case in eligible_cases[:daily_cap]:
                cap_ratio = env.capacity_ratio(remaining_slots if remaining_slots else total_capacity)
                pref_score = env.preference_score(case)
                state = agent.extract_state(
                    case,
                    env.current_date,
                    capacity_ratio=cap_ratio,
                    min_gap_days=policy_cfg.min_gap_days if config.enforce_min_gap else 0,
                    preference_score=pref_score,
                )
                action = agent.get_action(state, training=True)

                if config.cap_daily_allocations and action == 1 and remaining_slots <= 0:
                    action = 0
                elif action == 1 and config.cap_daily_allocations:
                    remaining_slots = max(0, remaining_slots - 1)

                agent_decisions[case.case_id] = action
                case_states[case.case_id] = state

            # Environment step
            _, rewards, done = env.step(agent_decisions)

            # Update Q-values based on rewards
            for case_id, reward in rewards.items():
                if case_id in case_states:
                    state = case_states[case_id]
                    action = agent_decisions.get(case_id, 0)

                    agent.update_q_value(state, action, reward)
                    episode_reward += reward

            if done:
                break

        # Compute episode statistics
        disposed_count = sum(1 for c in episode_cases if c.is_disposed)
        disposal_rate = disposed_count / len(episode_cases) if episode_cases else 0.0

        # Record statistics
        training_stats["episodes"].append(episode)
        training_stats["total_rewards"].append(episode_reward)
        training_stats["disposal_rates"].append(disposal_rate)
        training_stats["states_explored"].append(len(agent.states_visited))
        training_stats["q_updates"].append(agent.total_updates)

        # Decay exploration
        agent.epsilon = max(config.min_epsilon, agent.epsilon * config.epsilon_decay)

        if verbose and (episode + 1) % 10 == 0:
            print(
                f"Episode {episode + 1}/{config.episodes}: "
                f"Reward={episode_reward:.1f}, "
                f"Disposal={disposal_rate:.1%}, "
                f"States={len(agent.states_visited)}, "
                f"Epsilon={agent.epsilon:.3f}"
            )

    if verbose:
        final_stats = agent.get_stats()
        print(f"\nTraining complete!")
        print(f"States explored: {final_stats['states_visited']}")
        print(f"Q-table size: {final_stats['q_table_size']}")
        print(f"Total updates: {final_stats['total_updates']}")

    return training_stats


def evaluate_agent(
    agent: TabularQAgent,
    test_cases: List[Case],
    episodes: Optional[int] = None,
    episode_length: Optional[int] = None,
    rl_config: RLTrainingConfig = DEFAULT_RL_TRAINING_CONFIG,
    policy_config: PolicyConfig = DEFAULT_POLICY_CONFIG,
) -> Dict:
    """Evaluate trained agent performance."""
    # Set agent to evaluation mode (no exploration)
    original_epsilon = agent.epsilon
    agent.epsilon = 0.0

    config = rl_config or DEFAULT_RL_TRAINING_CONFIG
    policy_cfg = policy_config or DEFAULT_POLICY_CONFIG

    evaluation_stats = {
        "disposal_rates": [],
        "total_hearings": [],
        "avg_hearing_to_disposal": [],
        "utilization": [],
    }

    eval_episodes = episodes if episodes is not None else 10
    eval_length = episode_length if episode_length is not None else config.episode_length_days

    print(f"Evaluating agent on {eval_episodes} test episodes...")

    total_capacity = config.courtrooms * config.daily_capacity_per_courtroom

    for episode in range(eval_episodes):
        start_date = date(2024, 6, 1) + timedelta(days=episode * 10)
        env = RLTrainingEnvironment(
            test_cases.copy(),
            start_date,
            eval_length,
            rl_config=config,
            policy_config=policy_cfg,
        )

        episode_cases = env.reset()
        total_hearings = 0

        # Run evaluation episode
        for _ in range(eval_length):
            eligible_cases = [c for c in episode_cases if not c.is_disposed]
            if not eligible_cases:
                break

            daily_cap = config.max_daily_allocations or total_capacity
            remaining_slots = min(daily_cap, total_capacity) if config.cap_daily_allocations else len(eligible_cases)

            # Agent makes decisions (no exploration)
            agent_decisions = {}
            for case in eligible_cases[:daily_cap]:
                cap_ratio = env.capacity_ratio(remaining_slots if remaining_slots else total_capacity)
                pref_score = env.preference_score(case)
                state = agent.extract_state(
                    case,
                    env.current_date,
                    capacity_ratio=cap_ratio,
                    min_gap_days=policy_cfg.min_gap_days if config.enforce_min_gap else 0,
                    preference_score=pref_score,
                )
                action = agent.get_action(state, training=False)
                if config.cap_daily_allocations and action == 1 and remaining_slots <= 0:
                    action = 0
                elif action == 1 and config.cap_daily_allocations:
                    remaining_slots = max(0, remaining_slots - 1)

                agent_decisions[case.case_id] = action

            # Environment step
            _, rewards, done = env.step(agent_decisions)
            total_hearings += len([r for r in rewards.values() if r != 0])

            if done:
                break

        # Compute metrics
        disposed_count = sum(1 for c in episode_cases if c.is_disposed)
        disposal_rate = disposed_count / len(episode_cases)

        disposed_cases = [c for c in episode_cases if c.is_disposed]
        avg_hearings = np.mean([c.hearing_count for c in disposed_cases]) if disposed_cases else 0

        evaluation_stats["disposal_rates"].append(disposal_rate)
        evaluation_stats["total_hearings"].append(total_hearings)
        evaluation_stats["avg_hearing_to_disposal"].append(avg_hearings)
        evaluation_stats["utilization"].append(total_hearings / (eval_length * total_capacity))

    # Restore original epsilon
    agent.epsilon = original_epsilon

    # Compute summary statistics
    summary = {
        "mean_disposal_rate": np.mean(evaluation_stats["disposal_rates"]),
        "std_disposal_rate": np.std(evaluation_stats["disposal_rates"]),
        "mean_utilization": np.mean(evaluation_stats["utilization"]),
        "mean_hearings_to_disposal": np.mean(evaluation_stats["avg_hearing_to_disposal"]),
    }

    print("Evaluation complete:")
    print(f"Mean disposal rate: {summary['mean_disposal_rate']:.1%} ± {summary['std_disposal_rate']:.1%}")
    print(f"Mean utilization: {summary['mean_utilization']:.1%}")
    print(f"Avg hearings to disposal: {summary['mean_hearings_to_disposal']:.1f}")

    return summary
