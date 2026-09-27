"""Command line entry point: ``mqute run module:app``."""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
from collections.abc import Sequence

from .app import BROKER_URL_ENV, MQute


def load_app(target: str) -> MQute:
    """Import ``module:attribute`` and return the :class:`MQute` instance it names."""
    module_name, _, attribute = target.partition(":")
    if not module_name or not attribute:
        raise ValueError(f"Expected 'module:attribute', got {target!r}")
    module = importlib.import_module(module_name)
    app = getattr(module, attribute, None)
    if not isinstance(app, MQute):
        raise ValueError(f"{target!r} is not an MQute application")
    return app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mqute", description="Run MQute applications.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run an application, e.g. `mqute run main:app`")
    run.add_argument("app", help="import path of the application, as module:attribute")
    run.add_argument("--broker", help=f"broker URL (sets {BROKER_URL_ENV} before import)")
    run.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.broker:
        os.environ[BROKER_URL_ENV] = args.broker
    sys.path.insert(0, os.getcwd())
    try:
        app = load_app(args.app)
    except (ImportError, ValueError) as exc:
        parser.error(str(exc))
    app.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
