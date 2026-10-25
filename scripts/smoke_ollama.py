"""One real Gemma call against the labeled demo assignment. Not part of pytest."""

from datetime import datetime, timezone

from studyguardian.ai import OllamaClient, generate_weekly_plan
from studyguardian.config import load_settings
from studyguardian.demo import demo_records


def main() -> None:
    settings = load_settings()
    client = OllamaClient(settings.ollama_host, settings.ollama_model, timeout=180)
    ok, message = client.status()
    print(message)
    if not ok:
        raise SystemExit(1)
    now = datetime.now(timezone.utc)
    _courses, assignments = demo_records(now, timezone.utc)
    plan = generate_weekly_plan(
        assignments,
        client,
        now=now,
        tz=timezone.utc,
        source_scope="demo",
    )
    print(f"model={plan.model} items={len(plan.items)} sessions={len(plan.study_sessions)}")
    for item in plan.ordered_items():
        print(f"- {item.order} {item.priority} {item.assignment_id} model={item.model_generated}")
        print(f"  {item.reason}")
    if plan.missing_information:
        print("missing:")
        for line in plan.missing_information:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
