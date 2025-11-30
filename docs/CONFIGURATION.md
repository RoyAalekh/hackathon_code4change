# Configuration Guide (Consolidated)

This configuration reference has been intentionally simplified for the hackathon to keep the repository focused for judges and evaluators.

For the end-to-end demo and instructions, see:
- `docs/HACKATHON_SUBMISSION.md`

Advanced usage help is available via the CLI:

```bash
uv run court-scheduler --help
uv run court-scheduler generate --help
uv run court-scheduler simulate --help
uv run court-scheduler workflow --help
```

Note: uv is required for all commands.

### Deprecating Parameters
1. Move to config class first (keep old path working)
2. Add deprecation warning
3. Remove old path after one release cycle

## Validation Rules

All config classes validate in `__post_init__`:
- Value ranges (0 < learning_rate <= 1)
- Type consistency (convert strings to Path)
- Cross-parameter constraints (max_gap >= min_gap)
- Required file existence (rl_agent_path must exist)

## Anti-Patterns

**DON'T**:
- Hardcode magic numbers in algorithms
- Use module-level mutable globals
- Mix domain constants with tunable parameters
- Create "god config" with everything in one class

**DO**:
- Separate by lifecycle and ownership
- Validate early (constructor time)
- Use dataclasses for immutability
- Provide sensible defaults with named presets
