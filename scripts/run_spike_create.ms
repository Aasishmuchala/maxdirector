-- P0-T3 runner: execute the headless-create spike via 3dsmaxbatch.
-- Usage:
--   "C:\Program Files\Autodesk\3ds Max 2026\3dsmaxbatch.exe" -mxs "%~dp0run_spike_create.ms"
-- Set the repo path if it isn't the default.
global MAXDIRECTOR_REPO = (getEnvVariable "MAXDIRECTOR")
if MAXDIRECTOR_REPO == undefined do (
    messageBox "Set the MAXDIRECTOR environment variable to your clone folder first."
    throw "MAXDIRECTOR not set"
)
python.Execute ("import sys; sys.path.insert(0, r'" + MAXDIRECTOR_REPO + "')")
python.ExecuteFile (MAXDIRECTOR_REPO + "\\scripts\\spike_headless_create.py")
