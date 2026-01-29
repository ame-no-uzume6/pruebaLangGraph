import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_case(input_path: Path, output_path: Path) -> None:
    command = [
        sys.executable,
        "run.py",
        "--input",
        str(input_path),
        "--debug",
        "--debug-out",
        str(output_path),
    ]
    subprocess.run(command, cwd=str(ROOT), check=True)


def main() -> None:
    cases = [
        (
            ROOT / "langgraph_agent" / "data" / "batch_debug" / "sqs_event_1.json",
            ROOT / "langgraph_agent" / "data" / "state_debug_1.json",
        ),
        (
            ROOT / "langgraph_agent" / "data" / "batch_debug" / "sqs_event_2.json",
            ROOT / "langgraph_agent" / "data" / "state_debug_2.json",
        ),
        (
            ROOT / "langgraph_agent" / "data" / "batch_debug" / "sqs_event_3.json",
            ROOT / "langgraph_agent" / "data" / "state_debug_3.json",
        ),
    ]

    for input_path, output_path in cases:
        run_case(input_path, output_path)

    print("Debug JSON generados:")
    for _, output_path in cases:
        print(f"- {output_path}")


if __name__ == "__main__":
    main()
