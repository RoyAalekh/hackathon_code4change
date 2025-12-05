### Utils Module — Calendar Utilities

Directory: `scheduler/utils/`

Utility functions that support scheduling and simulation. Currently focused on court calendar handling.

#### Files overview

- `calendar.py`
  - Purpose: Calendar/date helpers used by the scheduler and simulation.
  - Typical responsibilities: business day calculations, holiday/weekend handling, date ranges for scheduling windows, and formatting for outputs.
  - Interactions: Imported where date arithmetic and calendar rules are required (e.g., selecting valid hearing days).

- `__init__.py`
  - Purpose: Package initialization.
