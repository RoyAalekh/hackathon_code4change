# Interactive Dashboard - Living Documentation

**Last Updated**: 2025-11-27
**Status**: Initial Implementation Complete
**Version**: 0.1.0

## Overview

This document tracks the design decisions, architecture, usage patterns, and evolution of the Interactive Multi-Page Dashboard for the Court Scheduling System.

## Purpose and Goals

The dashboard provides three key functionalities:
1. **EDA Analysis** - Visualize and explore court case data patterns
2. **Ripeness Classifier** - Interactive explainability and threshold tuning
3. **RL Training** - Train and visualize reinforcement learning agents

### Design Philosophy
- Transparency: Every algorithm decision should be explainable
- Interactivity: Users can adjust parameters and see immediate impact
- Efficiency: Data caching to minimize load times
- Integration: Seamless integration with existing CLI and modules

## Architecture

### Technology Stack

**Framework**: Streamlit 1.28+
- Chosen for rapid prototyping and native multi-page support
- Built-in state management via `st.session_state`
- Excellent integration with Plotly and Pandas/Polars

**Visualization**: Plotly
- Interactive charts (zoom, pan, hover)
- Better aesthetics than Matplotlib for dashboards
- Native Streamlit support

**Data Processing**:
- Polars for fast CSV loading
- Pandas for compatibility with existing code
- Caching with `@st.cache_data` decorator

### Directory Structure

```
scheduler/
  dashboard/
    __init__.py           # Package initialization
    app.py                # Main entry point (home page)
    utils/
      __init__.py
      data_loader.py      # Cached data loading functions
    pages/
      1_EDA_Analysis.py           # EDA visualizations
      2_Ripeness_Classifier.py    # Ripeness explainability
      3_RL_Training.py            # RL training interface
```

### Module Reuse Strategy

The dashboard reuses existing components without duplication:
- `scheduler.data.param_loader.ParameterLoader` - Load EDA-derived parameters
- `scheduler.data.case_generator.CaseGenerator` - Load generated cases
- `scheduler.core.ripeness.RipenessClassifier` - Classification logic
- `scheduler.core.case.Case` - Case data structure
- `rl.training.train_agent()` - RL training (future integration)

## Page Implementations

### Page 1: EDA Analysis

**Features**:
- Key metrics dashboard (total cases, adjournment rates, stages)
- Interactive filters (case type, stage)
- Multiple visualizations:
  - Case distribution by type (bar chart + pie chart)
  - Stage analysis (bar chart + pie chart)
  - Adjournment patterns (bar charts by type and stage)
  - Adjournment probability heatmap (stage × case type)
- Raw data viewer with download capability

**Data Sources**:
- `Data/processed/cleaned_cases.csv` - Cleaned case data from EDA pipeline
- `configs/parameters/` - Pre-computed parameters from ParameterLoader

**Design Decisions**:
- Use tabs instead of separate sections for better organization
- Show top 10/15 items in charts to avoid clutter
- Provide download button for filtered data
- Cache data with 1-hour TTL to balance freshness and performance

### Page 2: Ripeness Classifier

**Features**:
- **Tab 1: Configuration**
  - Display current thresholds
  - Stage-specific rules table
  - Decision tree logic explanation
- **Tab 2: Interactive Testing**
  - Synthetic case creation
  - Real-time classification with explanations
  - Feature importance visualization
  - Criteria pass/fail breakdown
- **Tab 3: Batch Classification**
  - Load generated test cases
  - Classify all with current thresholds
  - Show distribution (RIPE/UNRIPE/UNKNOWN)

**State Management**:
- Thresholds stored in `st.session_state`
- Sidebar sliders for real-time adjustment
- Reset button to restore defaults
- Session-based (not persisted to disk)

**Explainability Approach**:
- Clear criteria breakdown (service hearings, case age, stage days, keywords)
- Visual indicators (✓/✗) for pass/fail
- Feature importance bar chart
- Before/after comparison capability

**Design Decisions**:
- Simplified classification logic for demo (uses basic criteria)
- Future: Integrate actual RipenessClassifier.classify_case()
- Stage-specific rules hardcoded for now (future: load from config)
- Color coding: green (RIPE), orange (UNKNOWN), red (UNRIPE)

### Page 3: RL Training

**Features**:
- **Tab 1: Train Agent**
  - Configuration form (episodes, learning rate, epsilon, etc.)
  - Training progress visualization (demo mode)
  - Multiple live charts (disposal rate, rewards, states, epsilon decay)
  - Command generation for CLI training
- **Tab 2: Training History**
  - Load and display previous training runs
  - Plot historical performance
- **Tab 3: Model Comparison**
  - Load saved models from models/ directory
  - Compare Q-table sizes and hyperparameters
  - Visualization of model differences

**Demo Mode**:
- Current implementation simulates training results
- Generates synthetic stats for visualization
- Shows CLI command for actual training
- Future: Integrate real-time training with rl.training.train_agent()

**Design Decisions**:
- Demo mode chosen for initial release (no blocking UI during training)
- Future: Add async training with progress updates
- Hyperparameter guide in expander for educational value
- Model persistence via pickle (existing pattern)

## CLI Integration

### Command
```bash
uv run court-scheduler dashboard [--port PORT] [--host HOST]
```

**Default**: `http://localhost:8501`

**Implementation**:
- Added to `cli/main.py` as `@app.command()`
- Uses subprocess to launch Streamlit
- Validates dashboard app.py exists before launching
- Handles KeyboardInterrupt gracefully

**Usage Example**:
```bash
# Launch on default port
uv run court-scheduler dashboard

# Custom port
uv run court-scheduler dashboard --port 8080

# Bind to all interfaces
uv run court-scheduler dashboard --host 0.0.0.0 --port 8080
```

## Data Flow

### Loading Sequence
1. User launches dashboard via CLI
2. `app.py` loads, displays home page and system status
3. User navigates to a page (e.g., EDA Analysis)
4. Page imports data_loader utilities
5. `@st.cache_data` checks cache for data
6. If not cached, load from disk and cache
7. Data processed and visualized
8. User interactions trigger re-renders (cached data reused)

### Caching Strategy
- **TTL**: 3600 seconds (1 hour) for data files
- **No TTL**: For computed statistics (invalidates on data change)
- **Session State**: For UI state (thresholds, training configs)

### Performance Considerations
- Polars for fast CSV loading
- Limit DataFrame display to first 100 rows
- Top N filtering for visualizations (top 10/15)
- Lazy loading (pages only load data when accessed)

## Usage Patterns

### Typical Workflow 1: EDA Exploration
1. Run EDA pipeline: `uv run court-scheduler eda`
2. Launch dashboard: `uv run court-scheduler dashboard`
3. Navigate to EDA Analysis page
4. Apply filters (case type, stage)
5. Explore visualizations
6. Download filtered data if needed

### Typical Workflow 2: Threshold Tuning
1. Generate test cases: `uv run court-scheduler generate`
2. Launch dashboard: `uv run court-scheduler dashboard`
3. Navigate to Ripeness Classifier page
4. Adjust thresholds in sidebar
5. Test with synthetic case (Tab 2)
6. Run batch classification (Tab 3)
7. Analyze impact on RIPE/UNRIPE distribution

### Typical Workflow 3: RL Training
1. Launch dashboard: `uv run court-scheduler dashboard`
2. Navigate to RL Training page
3. Configure hyperparameters (Tab 1)
4. Copy CLI command and run separately (or use demo)
5. Return to dashboard, view history (Tab 2)
6. Compare models (Tab 3)

## Future Enhancements

### Planned Features
- [ ] Real-time RL training integration (non-blocking)
- [ ] RipenessCalibrator integration (auto-suggest thresholds)
- [ ] RipenessMetrics tracking (false positive/negative rates)
- [ ] Actual RipenessClassifier integration (not simplified logic)
- [ ] EDA plot regeneration option
- [ ] Export threshold configurations
- [ ] Simulation runner from dashboard
- [ ] Authentication (if deployed externally)

### Technical Improvements
- [ ] Async data loading for large datasets
- [ ] WebSocket support for real-time training updates
- [ ] Plotly Dash migration (if more customization needed)
- [ ] Unit tests for dashboard components
- [ ] Playwright automated UI tests

### UX Improvements
- [ ] Dark mode support
- [ ] Custom color themes
- [ ] Keyboard shortcuts
- [ ] Save/load dashboard state
- [ ] Export visualizations as PNG/PDF
- [ ] Guided tour for new users

## Testing Strategy

### Manual Testing Checklist
- [ ] Dashboard launches without errors
- [ ] All pages load correctly
- [ ] EDA page: filters work, visualizations render
- [ ] Ripeness page: sliders adjust thresholds, classification updates
- [ ] RL page: form submission works, charts render
- [ ] CLI command generation correct
- [ ] System status checks work

### Integration Testing
- [ ] Load actual cleaned data
- [ ] Load generated test cases
- [ ] Load parameters from configs/
- [ ] Verify caching behavior
- [ ] Test with missing data files

### Performance Testing
- [ ] Large dataset loading (100K+ rows)
- [ ] Batch classification (10K+ cases)
- [ ] Multiple concurrent users (if deployed)

## Troubleshooting

### Common Issues

**Issue**: Dashboard won't launch
- **Check**: Is Streamlit installed? `pip list | grep streamlit`
- **Solution**: Ensure venv is activated, run `uv sync`

**Issue**: "Data file not found" warnings
- **Check**: Has EDA pipeline been run?
- **Solution**: Run `uv run court-scheduler eda`

**Issue**: Empty visualizations
- **Check**: Is `Data/processed/cleaned_cases.csv` empty?
- **Solution**: Verify EDA pipeline completed successfully

**Issue**: Ripeness batch classification fails
- **Check**: Are test cases generated?
- **Solution**: Run `uv run court-scheduler generate`

**Issue**: Slow page loads
- **Check**: Is data being cached?
- **Solution**: Check Streamlit cache, reduce data size

## Design Decisions Log

### Decision 1: Streamlit over Dash/Gradio
**Date**: 2025-11-27
**Rationale**: 
- Already in dependencies (no new install)
- Simpler multi-page support
- Better for data science workflows
- Faster development time

**Alternatives Considered**:
- Dash: More customizable but more boilerplate
- Gradio: Better for ML demos, less flexible

### Decision 2: Plotly over Matplotlib
**Date**: 2025-11-27
**Rationale**:
- Interactive by default (zoom, pan, hover)
- Better aesthetics for dashboards
- Native Streamlit integration
- Users expect interactivity in modern dashboards

**Note**: Matplotlib still used for static EDA plots already generated

### Decision 3: Session State for Thresholds
**Date**: 2025-11-27
**Rationale**:
- Ephemeral experimentation (users can reset easily)
- No need to persist to disk
- Simpler implementation
- Users can export configs separately if needed

**Future**: May add "save configuration" feature

### Decision 4: Demo Mode for RL Training
**Date**: 2025-11-27
**Rationale**:
- Avoid blocking UI during long training runs
- Show visualization capabilities
- Guide users to use CLI for actual training
- Simpler initial implementation

**Future**: Add async training with WebSocket updates

### Decision 5: Simplified Ripeness Logic
**Date**: 2025-11-27
**Rationale**:
- Demonstrate explainability concept
- Avoid tight coupling with RipenessClassifier implementation
- Easier to understand for users
- Placeholder for full integration

**Future**: Integrate actual RipenessClassifier.classify_case()

## Maintenance Notes

### Dependencies
- Streamlit: Keep updated for security fixes
- Plotly: Monitor for breaking changes
- Polars: Ensure compatibility with Pandas conversion

### Code Quality
- Follow project ruff/black style
- Add docstrings to new functions
- Keep pages under 350 lines if possible
- Extract reusable components to utils/

### Performance Monitoring
- Monitor cache hit rates
- Track page load times
- Watch for memory leaks with large datasets

## Educational Value

The dashboard serves an educational purpose:
- **Transparency**: Shows how algorithms work (ripeness classifier)
- **Interactivity**: Lets users experiment (threshold tuning)
- **Visualization**: Makes complex data accessible (EDA plots)
- **Learning**: Explains RL concepts (hyperparameter guide)

This aligns with the "explainability" goal of the Code4Change project.

## Conclusion

The dashboard successfully provides:
1. Comprehensive EDA visualization
2. Full ripeness classifier explainability
3. RL training interface (demo mode)
4. CLI integration
5. Cached data loading
6. Interactive threshold tuning

Next steps focus on integrating real RL training and enhancing the ripeness classifier with actual implementation.

---

**Contributors**: Roy Aalekh (Initial Implementation)
**Project**: Code4Change Court Scheduling System
**Target**: Karnataka High Court Scheduling Optimization
