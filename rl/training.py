"""Training pipeline for tabular Q-learning agent.

Implements episodic training on generated case data to learn optimal
case prioritization policies through simulation-based rewards.
"""

import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict
from datetime import date, timedelta
import random

from scheduler.data.case_generator import CaseGenerator
from scheduler.simulation.engine import CourtSim, CourtSimConfig
from scheduler.core.case import Case, CaseStatus
from .simple_agent import TabularQAgent, CaseState


class RLTrainingEnvironment:
    """Training environment for RL agent using court simulation."""
    
    def __init__(self, cases: List[Case], start_date: date, horizon_days: int = 90):
        """Initialize training environment.
        
        Args:
            cases: List of cases to simulate
            start_date: Simulation start date
            horizon_days: Training episode length in days
        """
        self.cases = cases
        self.start_date = start_date
        self.horizon_days = horizon_days
        self.current_date = start_date
        self.episode_rewards = []
        
    def reset(self) -> List[Case]:
        """Reset environment for new training episode.
        
        Note: In practice, train_agent() generates fresh cases per episode,
        so case state doesn't need resetting. This method just resets
        environment state (date, rewards).
        """
        self.current_date = self.start_date
        self.episode_rewards = []
        return self.cases.copy()
    
    def step(self, agent_decisions: Dict[str, int]) -> Tuple[List[Case], Dict[str, float], bool]:
        """Execute one day of simulation with agent decisions.
        
        Args:
            agent_decisions: Dict mapping case_id to action (0=skip, 1=schedule)
            
        Returns:
            (updated_cases, rewards, episode_done)
        """
        # Simulate one day with agent decisions
        rewards = {}
        
        # For each case that agent decided to schedule
        scheduled_cases = [case for case in self.cases 
                          if case.case_id in agent_decisions and agent_decisions[case.case_id] == 1]
        
        # Simulate hearing outcomes for scheduled cases
        for case in scheduled_cases:
            if case.is_disposed:
                continue
                
            # Simulate hearing outcome based on stage transition probabilities
            outcome = self._simulate_hearing_outcome(case)
            was_heard = "heard" in outcome.lower()
            
            # Always record the hearing
            case.record_hearing(self.current_date, was_heard=was_heard, outcome=outcome)
            
            if was_heard:
                # Check if case progressed to terminal stage
                if outcome in ["FINAL DISPOSAL", "SETTLEMENT", "NA"]:
                    case.status = CaseStatus.DISPOSED
                    case.disposal_date = self.current_date
                elif outcome != "ADJOURNED":
                    # Advance to next stage
                    case.current_stage = outcome
            # If adjourned, case stays in same stage
            
            # Compute reward for this case
            rewards[case.case_id] = self._compute_reward(case, outcome)
        
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
    
    def _compute_reward(self, case: Case, outcome: str) -> float:
        """Compute reward based on case and outcome."""
        agent = TabularQAgent()  # Use for reward computation
        return agent.compute_reward(case, was_scheduled=True, hearing_outcome=outcome)


def train_agent(agent: TabularQAgent, episodes: int = 100, 
                cases_per_episode: int = 1000, 
                episode_length: int = 60,
                verbose: bool = True) -> Dict:
    """Train RL agent using episodic simulation.
    
    Args:
        agent: TabularQAgent to train
        episodes: Number of training episodes
        cases_per_episode: Number of cases per episode
        episode_length: Episode length in days
        verbose: Print training progress
        
    Returns:
        Training statistics
    """
    training_stats = {
        "episodes": [],
        "total_rewards": [],
        "disposal_rates": [],
        "states_explored": [],
        "q_updates": []
    }
    
    if verbose:
        print(f"Training RL agent for {episodes} episodes...")
    
    for episode in range(episodes):
        # Generate fresh cases for this episode
        start_date = date(2024, 1, 1) + timedelta(days=episode * 10)
        end_date = start_date + timedelta(days=30)
        
        generator = CaseGenerator(start=start_date, end=end_date, seed=42 + episode)
        cases = generator.generate(cases_per_episode, stage_mix_auto=True)
        
        # Initialize training environment
        env = RLTrainingEnvironment(cases, start_date, episode_length)
        
        # Reset environment
        episode_cases = env.reset()
        episode_reward = 0.0
        
        # Run episode
        for day in range(episode_length):
            # Get eligible cases (not disposed, basic filtering)
            eligible_cases = [c for c in episode_cases if not c.is_disposed]
            if not eligible_cases:
                break
            
            # Agent makes decisions for each case
            agent_decisions = {}
            case_states = {}
            
            for case in eligible_cases[:100]:  # Limit to 100 cases per day for efficiency
                state = agent.extract_state(case, env.current_date)
                action = agent.get_action(state, training=True)
                agent_decisions[case.case_id] = action
                case_states[case.case_id] = state
            
            # Environment step
            updated_cases, rewards, done = env.step(agent_decisions)
            
            # Update Q-values based on rewards
            for case_id, reward in rewards.items():
                if case_id in case_states:
                    state = case_states[case_id]
                    action = agent_decisions[case_id]
                    
                    # Simple Q-update (could be improved with next state)
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
        if episode > 0 and episode % 20 == 0:
            agent.epsilon = max(0.01, agent.epsilon * 0.9)
        
        if verbose and (episode + 1) % 10 == 0:
            print(f"Episode {episode + 1}/{episodes}: "
                  f"Reward={episode_reward:.1f}, "
                  f"Disposal={disposal_rate:.1%}, "
                  f"States={len(agent.states_visited)}, "
                  f"Epsilon={agent.epsilon:.3f}")
    
    if verbose:
        final_stats = agent.get_stats()
        print(f"\nTraining complete!")
        print(f"States explored: {final_stats['states_visited']}")
        print(f"Q-table size: {final_stats['q_table_size']}")
        print(f"Total updates: {final_stats['total_updates']}")
    
    return training_stats


def evaluate_agent(agent: TabularQAgent, test_cases: List[Case], 
                  episodes: int = 10, episode_length: int = 90) -> Dict:
    """Evaluate trained agent performance.
    
    Args:
        agent: Trained TabularQAgent
        test_cases: Test cases for evaluation
        episodes: Number of evaluation episodes
        episode_length: Episode length in days
        
    Returns:
        Evaluation metrics
    """
    # Set agent to evaluation mode (no exploration)
    original_epsilon = agent.epsilon
    agent.epsilon = 0.0
    
    evaluation_stats = {
        "disposal_rates": [],
        "total_hearings": [],
        "avg_hearing_to_disposal": [],
        "utilization": []
    }
    
    print(f"Evaluating agent on {episodes} test episodes...")
    
    for episode in range(episodes):
        start_date = date(2024, 6, 1) + timedelta(days=episode * 10)
        env = RLTrainingEnvironment(test_cases.copy(), start_date, episode_length)
        
        episode_cases = env.reset()
        total_hearings = 0
        
        # Run evaluation episode
        for day in range(episode_length):
            eligible_cases = [c for c in episode_cases if not c.is_disposed]
            if not eligible_cases:
                break
            
            # Agent makes decisions (no exploration)
            agent_decisions = {}
            for case in eligible_cases[:100]:
                state = agent.extract_state(case, env.current_date)
                action = agent.get_action(state, training=False)
                agent_decisions[case.case_id] = action
            
            # Environment step
            updated_cases, rewards, done = env.step(agent_decisions)
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
        evaluation_stats["utilization"].append(total_hearings / (episode_length * 151 * 5))  # 151 capacity, 5 courts
    
    # Restore original epsilon
    agent.epsilon = original_epsilon
    
    # Compute summary statistics
    summary = {
        "mean_disposal_rate": np.mean(evaluation_stats["disposal_rates"]),
        "std_disposal_rate": np.std(evaluation_stats["disposal_rates"]),
        "mean_utilization": np.mean(evaluation_stats["utilization"]),
        "mean_hearings_to_disposal": np.mean(evaluation_stats["avg_hearing_to_disposal"])
    }
    
    print(f"Evaluation complete:")
    print(f"Mean disposal rate: {summary['mean_disposal_rate']:.1%} ± {summary['std_disposal_rate']:.1%}")
    print(f"Mean utilization: {summary['mean_utilization']:.1%}")
    print(f"Avg hearings to disposal: {summary['mean_hearings_to_disposal']:.1f}")
    
    return summary