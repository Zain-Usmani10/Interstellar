"""Earth->Mars route search and the immutable, validated MissionPlan."""


def run_search(params, progress=lambda fraction: None, cancelled=lambda: False):
    """Backend hook; see planner.demo.run_search. Imported lazily so the numeric stack loads on first use."""
    from .demo import run_search as _run_search
    return _run_search(params, progress, cancelled)
