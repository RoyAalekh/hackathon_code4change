"""RL-based scheduling policy using tabular Q-learning for case prioritization.

Implements hybrid approach from RL_EXPLORATION_PLAN.md:
- Uses RL agent for case priority scoring
- Maintains rule-based filtering for fairness and constraints
- Integrates with existing simulation framework
"""

from typing import List, Dict, Any
from datetime import date
from pathlib import Path

from scheduler.core.case import Case
from scheduler.core.policy import SchedulerPolicy

try:
    from rl.config import PolicyConfig, DEFAULT_POLICY_CONFIG
except ImportError:
    # Fallback if rl module not available
    from dataclasses import dataclass
    @dataclass
    class PolicyConfig:
        min_gap_days: int = 7
        old_case_threshold_days: int = 180
    DEFAULT_POLICY_CONFIG = PolicyConfig()
from scheduler.simulation.policies.readiness import ReadinessPolicy

try:
    import sys
    from pathlib import Path
    # Add rl module to path
    rl_path = Path(__file__).parent.parent.parent.parent / "rl"
    if rl_path.exists():
        sys.path.insert(0, str(rl_path.parent))
    from rl.simple_agent import TabularQAgent
    RL_AVAILABLE = True
except ImportError as e:
    RL_AVAILABLE = False
    print(f"[DEBUG] RL import failed: {e}")


class RLPolicy(SchedulerPolicy):
    """RL-enhanced scheduling policy with hybrid rule-based + RL approach."""
    
    def __init__(self, agent_path: Path, policy_config: PolicyConfig = None):
        """Initialize RL policy.
        
        Args:
            agent_path: Path to trained RL agent file (REQUIRED)
        
        Raises:
            ImportError: If RL module not available
            FileNotFoundError: If agent model file doesn't exist
            RuntimeError: If agent fails to load
        """
        super().__init__()
        
        # Use provided config or default
        self.config = policy_config if policy_config is not None else DEFAULT_POLICY_CONFIG
        
        if not RL_AVAILABLE:
            raise ImportError("RL module not available. Install required dependencies.")
        
        # Ensure agent_path is Path object
        if not isinstance(agent_path, Path):
            agent_path = Path(agent_path)
        
        # Validate model file exists
        if not agent_path.exists():
            raise FileNotFoundError(
                f"RL agent model not found at {agent_path}. "
                "Train the agent first or provide correct path."
            )
        
        # Load agent
        try:
            self.agent = TabularQAgent.load(agent_path)
            print(f"[INFO] Loaded RL agent from {agent_path}")
            print(f"[INFO] Agent stats: {self.agent.get_stats()}")
        except Exception as e:
            raise RuntimeError(f"Failed to load RL agent from {agent_path}: {e}")
    
    def sort_cases(self, cases: List[Case], current_date: date, **kwargs) -> List[Case]:
        """Sort cases by RL-based priority scores with rule-based filtering.
        
        Following hybrid approach:
        1. Apply rule-based filtering (fairness, ripeness) 
        2. Use RL agent for priority scoring
        3. Fall back to readiness policy if needed
        """
        if not cases:
            return []
        
        # Agent is guaranteed to be loaded (checked in __init__)
        
        try:
            # Apply rule-based filtering first (like readiness policy does)
            filtered_cases = self._apply_rule_based_filtering(cases, current_date)
            
            # Get RL priority scores for filtered cases
            case_scores = []
            for case in filtered_cases:
                try:
                    priority_score = self.agent.get_priority_score(case, current_date)
                    case_scores.append((case, priority_score))
                except Exception as e:
                    print(f"[WARN] Failed to get RL score for case {case.case_id}: {e}")
                    # Assign neutral score
                    case_scores.append((case, 0.0))
            
            # Sort by RL priority score (highest first)
            case_scores.sort(key=lambda x: x[1], reverse=True)
            sorted_cases = [case for case, _ in case_scores]
            
            return sorted_cases
            
        except Exception as e:
            # This should never happen - agent is validated in __init__
            raise RuntimeError(f"RL policy failed unexpectedly: {e}")
    
    def _apply_rule_based_filtering(self, cases: List[Case], current_date: date) -> List[Case]:
        """Apply rule-based filtering similar to ReadinessPolicy.
        
        This maintains fairness and basic judicial constraints while letting
        RL handle prioritization within the filtered set.
        """
        # Filter for basic scheduling eligibility
        eligible_cases = []
        
        for case in cases:
            # Skip if already disposed
            if case.is_disposed:
                continue
                
            # Skip if too soon since last hearing (basic fairness)
            if case.last_hearing_date:
                days_since = (current_date - case.last_hearing_date).days
                if days_since < self.config.min_gap_days:
                    continue
            
            # Include urgent cases regardless of other filters
            if case.is_urgent:
                eligible_cases.append(case)
                continue
            
            # Apply ripeness filter if available
            if hasattr(case, 'ripeness_status'):
                if case.ripeness_status == "RIPE":
                    eligible_cases.append(case)
                # Skip UNRIPE cases unless they're very old
                elif (self.config.allow_old_unripe_cases and 
                      case.age_days and case.age_days > self.config.old_case_threshold_days):
                    eligible_cases.append(case)
            else:
                # No ripeness info, include case
                eligible_cases.append(case)
        
        return eligible_cases
    
    def get_explanation(self, case: Case, current_date: date) -> str:
        """Get explanation for why a case was prioritized."""
        if not RL_AVAILABLE or not self.agent:
            return "RL not available, using fallback policy"
        
        try:
            priority_score = self.agent.get_priority_score(case, current_date)
            state = self.agent.extract_state(case, current_date)
            
            explanation_parts = [
                f"RL Priority Score: {priority_score:.3f}",
                f"Case State: Stage={case.current_stage}, Age={case.age_days}d, Urgent={case.is_urgent}"
            ]
            
            # Add specific reasoning based on state
            if case.is_urgent:
                explanation_parts.append("HIGH: Urgent case")
            
            if case.age_days and case.age_days > 365:
                explanation_parts.append("HIGH: Long pending case (>1 year)")
                
            if hasattr(case, 'ripeness_status'):
                explanation_parts.append(f"Ripeness: {case.ripeness_status}")
            
            return " | ".join(explanation_parts)
            
        except Exception as e:
            return f"RL explanation failed: {e}"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get policy statistics."""
        stats = {"policy_type": "RL-based"}
        
        if self.agent:
            stats.update(self.agent.get_stats())
            stats["agent_loaded"] = self.agent_loaded
        else:
            stats["agent_available"] = False
            
        return stats
    
    def prioritize(self, cases: List[Case], current_date: date) -> List[Case]:
        """Prioritize cases for scheduling (required by SchedulerPolicy interface)."""
        return self.sort_cases(cases, current_date)
    
    def get_name(self) -> str:
        """Get the policy name for logging/reporting."""
        return "RL-based Priority Scoring"
    
    def requires_readiness_score(self) -> bool:
        """Return True if this policy requires readiness score computation."""
        return True  # We use ripeness filtering
