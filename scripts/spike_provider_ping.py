"""P0-T2 SPIKE — model routing. Confirm the Omega gateway is reachable for BOTH models and
which wire path GPT-5.5 needs. Run anywhere with Python + requests + your oc_ key:

    OC_KEY=oc_xxx python scripts/spike_provider_ping.py
    # or: python scripts/spike_provider_ping.py oc_xxx

PASS = opus-4.8 pings OK. GPT-5.5 OK confirms the openai-chat path; a 404/500 there means it
needs a different route (defer gpt-5.5, keep opus-4.8 default).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from maxdirector.core import provider  # noqa: E402


def main():
    key = os.environ.get("OC_KEY") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not key:
        print("no key — set OC_KEY or pass it as argv[1]")
        return 2
    ok = True
    for model in ("claude-opus-4-8", "gpt-5.5"):
        try:
            print("OK  ", provider.ping(key, model))
        except Exception as e:  # noqa: BLE001
            print("FAIL", model, "->", e)
            if model == "claude-opus-4-8":
                ok = False
    print("\nCheckpoint-0 model routing:", "GO (opus reachable)" if ok else "BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
