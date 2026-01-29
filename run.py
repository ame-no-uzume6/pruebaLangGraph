import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "langgraph_agent" / "src"
sys.path.insert(0, str(SRC_PATH))

from graph import run_graph  # noqa: E402
from dotenv import load_dotenv  # noqa: E402


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Ejecuta el grafo LangGraph con un evento SQS mock."
    )
    parser.add_argument(
        "--input",
        required=True,
        help=(
            "Ruta al archivo JSON con el evento SQS "
            "(ej: langgraph_agent/data/debug/sqs_event.json)."
        ),
    )
    parser.add_argument(
        "--api-key",
        help="API key de Anthropic (si no usas variable de entorno).",
    )
    parser.add_argument(
        "--model",
        help="Modelo Anthropic (sobrescribe ANTHROPIC_MODEL).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Imprime el estado completo del grafo por nodo.",
    )
    parser.add_argument(
        "--debug-out",
        help="Ruta del JSON de debug (sobrescribe el default).",
    )
    args = parser.parse_args()

    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    if args.model:
        os.environ["ANTHROPIC_MODEL"] = args.model

    result = run_graph(args.input, debug=args.debug, debug_output=args.debug_out)
    print(result)


if __name__ == "__main__":
    main()
