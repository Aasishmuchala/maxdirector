"""MaxDirector — an LLM cinematographer-director for 3ds Max 2026 + V-Ray 7.

Hexagonal architecture (mirrors LightMatch native + MaxOptimizer):
  * ``maxdirector.core``     — PURE python, ZERO pymxs. Unit-testable without 3ds Max.
  * ``maxdirector.maxbridge`` — the ONLY layer that imports pymxs (the host boundary).
  * ``maxdirector.ui``       — PySide6 dock.

The Director is a staged pipeline: UNDERSTAND -> BRIEF -> (REFERENCE GATE) -> DIRECT
-> RESOLVE GAPS -> COMPILE -> BUILD/VERIFY/RENDER. The LLM (via the Omega gateway)
plans; the plugin executes. See SPEC.md.
"""

__version__ = "0.0.1"
