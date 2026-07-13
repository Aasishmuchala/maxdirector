"""The ONLY layer that imports pymxs — the boundary to the 3ds Max host.

Nothing here runs off a 3ds Max session; these modules are complete, review-ready source
that executes on the Windows + Max 2026 box. Pure logic lives in ``maxdirector.core`` and
is exercised by the macOS test suite with these services mocked.
"""
