"""Tabular Q-learning agent for court case priority scoring.

Implements the simplified RL approach described in RL_EXPLORATION_PLAN.md:
- 6D state space per case
- Binary action space (schedule/skip)
- Tabular Q-learning with epsilon-greedy exploration
"""

import numpy as np
import pickle
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from collections import defaultdict

from scheduler.core.case import Case


@dataclass
class CaseState:
    """6-dimensional state representation for a case."""
    stage_encoded: int      # 0-7 for different stages
    age_days: float        # normalized 0-1
    days_since_last: float # normalized 0-1  
    urgency: int           # 0 or 1
    ripe: int              # 0 or 1
    hearing_count: float   # normalized 0-1
    
    def to_tuple(self) -> Tuple[int, int, int, int, int, int]:
        """Convert to tuple for use as dict key."""
        return (
            self.stage_encoded,
            min(9, int(self.age_days * 20)),  # discretize to 20 bins, cap at 9
            min(9, int(self.days_since_last * 20)),  # discretize to 20 bins, cap at 9
            self.urgency,
            self.ripe,
            min(9, int(self.hearing_count * 20))  # discretize to 20 bins, cap at 9
        )


class TabularQAgent:
    """Tabular Q-learning agent for case priority scoring."""
    
    # Stage mapping based on config.py
    STAGE_TO_ID = {
        "PRE-ADMISSION": 0,
        "ADMISSION": 1, 
        "FRAMING OF CHARGES": 2,
        "EVIDENCE": 3,
        "ARGUMENTS": 4,
        "INTERLOCUTORY APPLICATION": 5,
        "SETTLEMENT": 6,
        "ORDERS / JUDGMENT": 7,
        "FINAL DISPOSAL": 8,
        "OTHER": 9,
        "NA": 10
    }
    
    def __init__(self, learning_rate: float = 0.1, epsilon: float = 0.1, 
                 discount: float = 0.95):
        """Initialize tabular Q-learning agent.
        
        Args:
            learning_rate: Q-learning step size
            epsilon: Exploration probability
            discount: Discount factor for future rewards
        """
        self.learning_rate = learning_rate
        self.epsilon = epsilon
        self.discount = discount
        
        # Q-table: state -> action -> Q-value
        # Actions: 0 = skip, 1 = schedule
        self.q_table: Dict[Tuple, Dict[int, float]] = defaultdict(lambda: {0: 0.0, 1: 0.0})
        
        # Statistics
        self.states_visited = set()
        self.total_updates = 0
        
    def extract_state(self, case: Case, current_date) -> CaseState:
        """Extract 6D state representation from a case.
        
        Args:
            case: Case object
            current_date: Current simulation date
            
        Returns:
            CaseState representation
        """
        # Stage encoding
        stage_id = self.STAGE_TO_ID.get(case.current_stage, 9)  # Default to "OTHER"
        
        # Age in days (normalized by max reasonable age of 2 years)
        actual_age = max(0, case.age_days) if case.age_days is not None else max(0, (current_date - case.filed_date).days)
        age_days = min(actual_age / (365 * 2), 1.0)
        
        # Days since last hearing (normalized by max reasonable gap of 180 days)
        days_since = 0.0
        if case.last_hearing_date:
            days_gap = max(0, (current_date - case.last_hearing_date).days)
            days_since = min(days_gap / 180, 1.0)
        else:
            # No previous hearing - use age as days since "last" hearing
            days_since = min(actual_age / 180, 1.0)
        
        # Urgency flag
        urgency = 1 if case.is_urgent else 0
        
        # Ripeness (assuming we have ripeness status)
        ripe = 1 if hasattr(case, 'ripeness_status') and case.ripeness_status == "RIPE" else 0
        
        # Hearing count (normalized by reasonable max of 20 hearings)
        hearing_count = min(case.hearing_count / 20, 1.0) if case.hearing_count else 0.0
        
        return CaseState(
            stage_encoded=stage_id,
            age_days=age_days,
            days_since_last=days_since,
            urgency=urgency,
            ripe=ripe,
            hearing_count=hearing_count
        )
    
    def get_action(self, state: CaseState, training: bool = False) -> int:
        """Select action using epsilon-greedy policy.
        
        Args:
            state: Current case state
            training: Whether in training mode (enables exploration)
            
        Returns:
            Action: 0 = skip, 1 = schedule
        """
        state_key = state.to_tuple()
        self.states_visited.add(state_key)
        
        # Epsilon-greedy exploration during training
        if training and np.random.random() < self.epsilon:
            return np.random.choice([0, 1])
        
        # Greedy action selection
        q_values = self.q_table[state_key]
        if q_values[0] == q_values[1]:  # If tied, prefer scheduling (action 1)
            return 1
        return max(q_values, key=q_values.get)
    
    def get_priority_score(self, case: Case, current_date) -> float:
        """Get priority score for a case (Q-value for schedule action).
        
        Args:
            case: Case object
            current_date: Current simulation date
            
        Returns:
            Priority score (Q-value for action=1)
        """
        state = self.extract_state(case, current_date)
        state_key = state.to_tuple()
        return self.q_table[state_key][1]  # Q-value for schedule action
    
    def update_q_value(self, state: CaseState, action: int, reward: float, 
                      next_state: Optional[CaseState] = None):
        """Update Q-table using Q-learning rule.
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state (optional, for terminal states)
        """
        state_key = state.to_tuple()
        
        # Q-learning update
        old_q = self.q_table[state_key][action]
        
        if next_state is not None:
            next_key = next_state.to_tuple()
            max_next_q = max(self.q_table[next_key].values())
            target = reward + self.discount * max_next_q
        else:
            # Terminal state
            target = reward
            
        new_q = old_q + self.learning_rate * (target - old_q)
        self.q_table[state_key][action] = new_q
        self.total_updates += 1
    
    def compute_reward(self, case: Case, was_scheduled: bool, hearing_outcome: str) -> float:
        """Compute reward based on the outcome as per RL plan.
        
        Reward function:
        +2 if case progresses
        -1 if adjourned  
        +3 if urgent & scheduled
        -2 if unripe & scheduled
        +1 if long pending & scheduled
        
        Args:
            case: Case object
            was_scheduled: Whether case was scheduled
            hearing_outcome: Outcome of the hearing
            
        Returns:
            Reward value
        """
        reward = 0.0
        
        if was_scheduled:
            # Base scheduling reward (small positive for taking action)
            reward += 0.5
            
            # Hearing outcome rewards
            if "disposal" in hearing_outcome.lower() or "judgment" in hearing_outcome.lower() or "settlement" in hearing_outcome.lower():
                reward += 10.0  # Major positive for disposal
            elif "progress" in hearing_outcome.lower() and "adjourn" not in hearing_outcome.lower():
                reward += 3.0  # Progress without disposal
            elif "adjourn" in hearing_outcome.lower():
                reward -= 3.0  # Negative for adjournment
            
            # Urgency bonus
            if case.is_urgent:
                reward += 2.0
                
            # Ripeness penalty  
            if hasattr(case, 'ripeness_status') and case.ripeness_status not in ["RIPE", "UNKNOWN"]:
                reward -= 4.0
                
            # Long pending bonus (>365 days)
            if case.age_days and case.age_days > 365:
                reward += 2.0
        
        return reward
    
    def get_stats(self) -> Dict:
        """Get agent statistics."""
        return {
            "states_visited": len(self.states_visited),
            "total_updates": self.total_updates,
            "q_table_size": len(self.q_table),
            "epsilon": self.epsilon,
            "learning_rate": self.learning_rate
        }
    
    def save(self, path: Path):
        """Save agent to file."""
        agent_data = {
            'q_table': dict(self.q_table),
            'learning_rate': self.learning_rate,
            'epsilon': self.epsilon,
            'discount': self.discount,
            'states_visited': self.states_visited,
            'total_updates': self.total_updates
        }
        with open(path, 'wb') as f:
            pickle.dump(agent_data, f)
    
    @classmethod
    def load(cls, path: Path) -> 'TabularQAgent':
        """Load agent from file."""
        with open(path, 'rb') as f:
            agent_data = pickle.load(f)
        
        agent = cls(
            learning_rate=agent_data['learning_rate'],
            epsilon=agent_data['epsilon'],
            discount=agent_data['discount']
        )
        agent.q_table = defaultdict(lambda: {0: 0.0, 1: 0.0})
        agent.q_table.update(agent_data['q_table'])
        agent.states_visited = agent_data['states_visited']
        agent.total_updates = agent_data['total_updates']
        
        return agent