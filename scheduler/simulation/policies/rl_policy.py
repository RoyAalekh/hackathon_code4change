"""RL-based scheduling policy using tabular Q-learning for case prioritization.

Implements hybrid approach from RL_EXPLORATION_PLAN.md:
- Uses RL agent for case priority scoring
- Maintains rule-based filtering for fairness and constraints
- Integrates with existing simulation framework
"""

from typing import List, Optional, Dict, Any
from datetime import date
from pathlib import Path

from scheduler.core.case import Case
from scheduler.core.policy import SchedulerPolicy
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
    
    def __init__(self, agent_path: Optional[Path] = None, fallback_to_readiness: bool = True):
        """Initialize RL policy.
        
        Args:
            agent_path: Path to trained RL agent file
            fallback_to_readiness: Whether to fall back to readiness policy if RL fails
        """
        super().__init__()
        
        self.fallback_to_readiness = fallback_to_readiness
        self.readiness_policy = ReadinessPolicy() if fallback_to_readiness else None
        
        # Initialize RL agent
        self.agent: Optional[TabularQAgent] = None
        self.agent_loaded = False
        
        if not RL_AVAILABLE:
            print("[WARN] RL module not available, falling back to readiness policy")
            return
            
        # Try to load RL agent from various locations
        search_paths = [
            Path("models/intensive_trained_rl_agent.pkl"),  # Intensive training
            Path("models/trained_rl_agent.pkl"),  # Standard training
            agent_path if agent_path else None  # Custom path
        ]
        
        for check_path in search_paths:
            if check_path and check_path.exists():
                try:
                    self.agent = TabularQAgent.load(check_path)
                    self.agent_loaded = True
                    print(f"[INFO] Loaded RL agent from {check_path}")
                    print(f"[INFO] Agent stats: {self.agent.get_stats()}")
                    break
                except Exception as e:
                    print(f"[WARN] Failed to load agent from {check_path}: {e}")
        
        if not self.agent_loaded and agent_path and agent_path.exists():
            try:
                self.agent = TabularQAgent.load(agent_path)
                self.agent_loaded = True
                print(f"[INFO] Loaded RL agent from {agent_path}")
                print(f"[INFO] Agent stats: {self.agent.get_stats()}")
            except Exception as e:
                print(f"[WARN] Failed to load RL agent from {agent_path}: {e}")
        
        if not self.agent_loaded:
            # Create new untrained agent
            self.agent = TabularQAgent(learning_rate=0.1, epsilon=0.0)  # No exploration in production
            print("[INFO] Using untrained RL agent (will behave randomly initially)")
    
    def sort_cases(self, cases: List[Case], current_date: date, **kwargs) -> List[Case]:
        """Sort cases by RL-based priority scores with rule-based filtering.
        
        Following hybrid approach:
        1. Apply rule-based filtering (fairness, ripeness) 
        2. Use RL agent for priority scoring
        3. Fall back to readiness policy if needed
        """
        if not cases:
            return []
        
        # If RL is not available or agent not loaded, use fallback
        if not RL_AVAILABLE or not self.agent:
            if self.readiness_policy:
                return self.readiness_policy.prioritize(cases, current_date)
            else:
                # Simple age-based fallback
                return sorted(cases, key=lambda c: c.age_days or 0, reverse=True)
        
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
            print(f"[ERROR] RL policy failed: {e}")
            # Fall back to readiness policy
            if self.readiness_policy:
                return self.readiness_policy.prioritize(cases, current_date)
            else:
                return cases  # Return unsorted
    
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
                if days_since < 7:  # Min 7 days gap
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
                elif case.age_days and case.age_days > 180:  # Old cases get priority
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
