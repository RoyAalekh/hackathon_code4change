"""Centralized output directory management.

Provides clean, hierarchical output structure for all pipeline artifacts.
No scattered files, no duplicate saves, single source of truth per run.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
import json
from dataclasses import asdict


class OutputManager:
    """Manages all output paths for a pipeline run.
    
    Design principles:
    - Single run directory contains ALL artifacts
    - No copying/moving files between directories
    - Clear hierarchy: eda/ training/ simulation/ reports/
    - Run ID is timestamp-based for sorting
    - Config saved at root for reproducibility
    """
    
    def __init__(self, run_id: Optional[str] = None, base_dir: Optional[Path] = None):
        """Initialize output manager for a pipeline run.
        
        Args:
            run_id: Unique run identifier (default: timestamp)
            base_dir: Base directory for all outputs (default: outputs/runs)
        """
        self.run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Base paths
        project_root = Path(__file__).parent.parent.parent
        self.base_dir = base_dir or (project_root / "outputs" / "runs")
        self.run_dir = self.base_dir / self.run_id
        
        # Primary output directories
        self.eda_dir = self.run_dir / "eda"
        self.training_dir = self.run_dir / "training"
        self.simulation_dir = self.run_dir / "simulation"
        self.reports_dir = self.run_dir / "reports"
        
        # EDA subdirectories
        self.eda_figures = self.eda_dir / "figures"
        self.eda_params = self.eda_dir / "params"
        self.eda_data = self.eda_dir / "data"
        
        # Reports subdirectories
        self.visualizations_dir = self.reports_dir / "visualizations"
        
    def create_structure(self):
        """Create all output directories."""
        for dir_path in [
            self.run_dir,
            self.eda_dir,
            self.eda_figures,
            self.eda_params,
            self.eda_data,
            self.training_dir,
            self.simulation_dir,
            self.reports_dir,
            self.visualizations_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def save_config(self, config):
        """Save pipeline configuration to run directory.
        
        Args:
            config: PipelineConfig or any dataclass
        """
        config_path = self.run_dir / "config.json"
        with open(config_path, 'w') as f:
            # Handle nested dataclasses (like rl_training)
            config_dict = asdict(config) if hasattr(config, '__dataclass_fields__') else config
            json.dump(config_dict, f, indent=2, default=str)
    
    def get_policy_dir(self, policy_name: str) -> Path:
        """Get simulation directory for a specific policy.
        
        Args:
            policy_name: Policy name (e.g., 'readiness', 'rl')
            
        Returns:
            Path to policy simulation directory
        """
        policy_dir = self.simulation_dir / policy_name
        policy_dir.mkdir(parents=True, exist_ok=True)
        return policy_dir
    
    def get_cause_list_dir(self, policy_name: str) -> Path:
        """Get cause list directory for a policy.
        
        Args:
            policy_name: Policy name
            
        Returns:
            Path to cause list directory
        """
        cause_list_dir = self.get_policy_dir(policy_name) / "cause_lists"
        cause_list_dir.mkdir(parents=True, exist_ok=True)
        return cause_list_dir
    
    @property
    def training_cases_file(self) -> Path:
        """Path to generated training cases CSV."""
        return self.training_dir / "cases.csv"
    
    @property
    def trained_model_file(self) -> Path:
        """Path to trained RL agent model."""
        return self.training_dir / "agent.pkl"
    
    @property
    def training_stats_file(self) -> Path:
        """Path to training statistics JSON."""
        return self.training_dir / "stats.json"
    
    @property
    def executive_summary_file(self) -> Path:
        """Path to executive summary markdown."""
        return self.reports_dir / "EXECUTIVE_SUMMARY.md"
    
    @property
    def comparison_report_file(self) -> Path:
        """Path to comparison report markdown."""
        return self.reports_dir / "COMPARISON_REPORT.md"
    
    def create_model_symlink(self, alias: str = "latest"):
        """Create symlink in models/ directory pointing to trained model.
        
        Args:
            alias: Symlink name (e.g., 'latest', 'v1.0')
        """
        project_root = self.run_dir.parent.parent.parent
        models_dir = project_root / "models"
        models_dir.mkdir(exist_ok=True)
        
        symlink_path = models_dir / f"{alias}.pkl"
        target = self.trained_model_file
        
        # Remove existing symlink if present
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        
        # Create symlink (use absolute path for cross-directory links)
        try:
            symlink_path.symlink_to(target.resolve())
        except (OSError, NotImplementedError):
            # Fallback: copy file if symlinks not supported (Windows without dev mode)
            import shutil
            shutil.copy2(target, symlink_path)
    
    def __str__(self) -> str:
        return f"OutputManager(run_id='{self.run_id}', run_dir='{self.run_dir}')"
    
    def __repr__(self) -> str:
        return self.__str__()
