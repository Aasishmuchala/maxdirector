"""MaxDirector CV sidecar — a separate torch+CUDA HTTP service (never Max's Python).

Commercial-safe default stack: GeoCalib, Depth Anything V2-Small, OpenCLIP, MUSIQ/NIMA,
MegaSaM/RAFT. Runs in STUB mode with only the stdlib so the pipeline works before the heavy
models are installed. See README.md.
"""
