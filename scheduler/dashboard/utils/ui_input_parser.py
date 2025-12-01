from pathlib import Path
from cli.config import GenerateConfig


def merge_with_default_config(
    default_cfg: GenerateConfig,
    n_cases: int,
    start_date,
    end_date,
    output_dir: str,
    seed: int,
) -> GenerateConfig:
    """Merge UI values with the repo's default generate config."""
    return GenerateConfig(
        n_cases=n_cases or default_cfg.n_cases,
        start=start_date or default_cfg.start,
        end=end_date or default_cfg.end,
        output=Path(output_dir) / "cases.csv" if output_dir else default_cfg.output,
        seed=seed if seed is not None else default_cfg.seed,
    )


def build_case_type_distribution(
    rsa_pct: int,
    rfa_pct: int,
    crp_pct: int,
    ca_pct: int,
    ccc_pct: int,
    cp_pct: int,
    cmp_pct: int,
) -> dict[str, float]:
    """Convert percentage inputs into a probability distribution."""
    total = rsa_pct + rfa_pct + crp_pct + ca_pct + ccc_pct + cp_pct + cmp_pct
    if total == 0:
        return {}

    return {
        "RSA": rsa_pct / total,
        "RFA": rfa_pct / total,
        "CRP": crp_pct / total,
        "CA": ca_pct / total,
        "CCC": ccc_pct / total,
        "CP": cp_pct / total,
        "CMP": cmp_pct / total,
    }
