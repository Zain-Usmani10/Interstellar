"""Smoke test against a running backend:  python app/scripts/smoke_test.py <operator-token>

Runs health, planet info, one mouse selection and one full mission (upload, arm, start) and
prints what the controller reported. Start the backend with SIM_SPEED=100 to finish in ~2 s.
"""
import sys
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def main(token: str) -> None:
    op = {"X-Operator-Token": token}
    with httpx.Client(base_url=BASE, timeout=20) as c:
        health = c.get("/health").json()
        print("controller:", health["transport"]["controller_label"], "| data:", health["data_mode"])
        print("mars weather:", c.get("/planets/499/info").json()["conditions"]["availability"])

        session = c.post("/input/sessions", json={"source": "mouse", "adapter": {"name": "smoke"}}).json()
        ctx = session["context"]
        result = c.post("/input/intents", headers={"X-Input-Token": session["token"]}, json={
            "schema_version": 1, "event_id": str(uuid.uuid4()), "input_session_id": session["input_session_id"],
            "context_id": ctx["context_id"], "context_revision": ctx["revision"],
            "target_id": "planet.499", "source": "mouse"}).json()
        print("select planet.499:", result["reason"])

        plan_id = c.get("/plans").json()["plans"][0]["plan_id"]
        mission = c.post("/missions", json={"plan_id": plan_id}, headers=op).json()["mission_id"]
        for name in ("upload", "arm", "start"):
            r = c.post(f"/missions/{mission}/commands", json={"command": name}, headers=op).json()
            print(f"{name}: applied={r['applied']} detail={r['detail']}")
        deadline = time.monotonic() + 140
        last = None
        while time.monotonic() < deadline:
            snap = c.get(f"/missions/{mission}").json()
            line = (snap["state"], snap["executed_mask"], snap["spacecraft"]["phase"], snap["outcome"])
            if line != last:
                print("tick", snap["tick"], *line)
                last = line
            if snap["state"] in ("COMPLETE", "SAFE", "ABORTED"):
                break
            time.sleep(0.1)
        ok = snap["state"] == "COMPLETE" and snap["outcome"] == "captured"
        print("RESULT:", "PASS" if ok else "FAIL", f"({snap['controller_label']})")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1])
