#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE / "general_factory.py"

with tempfile.TemporaryDirectory(prefix="research_factory_smoke_") as d:
    root = Path(d) / "project"
    subprocess.run([
        sys.executable, str(CLI), "init", str(root),
        "--question", "Can a computational method support a scholarly claim?",
        "--field", "digital humanities",
        "--subfield", "historical NLP",
        "--venue", "Mock Venue",
        "--backend", "mock",
        "--offline",
    ], check=True)
    subprocess.run([sys.executable, str(CLI), "run", str(root), "--backend", "mock"], check=True)
    state = json.loads((root / "state.json").read_text())
    assert state["status"] == "awaiting_human_review", state
    assert (root / "venue" / "venue_profile.json").exists()
    assert (root / "profiles" / "research_contract.json").exists()
    assert (root / "paper" / "paper.md").exists()
    print("OK: general Research Factory smoke test passed.")
