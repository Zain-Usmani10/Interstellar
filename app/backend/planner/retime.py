"""Offline catalogue migration: python -m app.backend.planner.retime.

Validate every replacement before writing; retain one file per immutable plan,
and update the objective references in the catalogue and Earth/Mars index.
"""
import json
from dataclasses import asdict

from .demo import PLANS_DIR, SEARCH_DIR
from .plan import TickMap, presentation_plan, verify_plan
from ..runtime.stores import load_validators


def retime_catalog(plans_dir=PLANS_DIR, search_dir=SEARCH_DIR):
    validator = load_validators()["mission_plan"]
    replacements, ids, filenames, unique = {}, {}, {}, {}
    # Prefer the legacy Earth/Mars filenames used by the demo index.
    paths = sorted(plans_dir.glob("*.json"), key=lambda p: ("presentation" in p.name, p.name))
    for path in paths:
        old = json.loads(path.read_text(encoding="utf-8"))
        new = presentation_plan(old)
        validator.validate(new)
        errors = verify_plan(new)
        if errors:
            raise ValueError(errors)
        ids[old["plan_id"]] = new["plan_id"]
        winner = unique.setdefault(new["plan_id"], path)
        filenames[path.name] = winner.name
        if winner == path:
            replacements[path] = new

    catalog_path = search_dir / "planet_pairs.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for key in ("pairs", "demo_pairs"):
        for row in catalog.get(key, []):
            if "objectives" in row:
                row["objectives"] = {k: ids[v] for k, v in row["objectives"].items()}
    catalog["presentation_max_seconds"] = TickMap().end_tick / 100
    index_path = search_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["objectives"] = {k: filenames[v] for k, v in index["objectives"].items()}
    index["built_from"]["ticks"] = asdict(TickMap())
    referenced = {value for key in ("pairs", "demo_pairs") for row in catalog.get(key, [])
                  for value in row.get("objectives", {}).values()}
    replacements = {path: plan for path, plan in replacements.items()
                    if plan["plan_id"] in referenced or path.name in index["objectives"].values()}
    for path, value in {**replacements, catalog_path: catalog, index_path: index}.items():
        path.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
    for path in paths:
        if path not in replacements:
            path.unlink()
    return {"before": len(paths), "after": len(replacements), "changed_ids": ids}


if __name__ == "__main__":
    result = retime_catalog()
    print(json.dumps(result, indent=2))
