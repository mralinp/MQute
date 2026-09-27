# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## What this project is

MQute is a FastAPI-style framework for MQTT services, published on PyPI as
`mqute`. Users decorate functions with topic patterns; MQute subscribes,
decodes payloads from type annotations, injects dependencies, runs middleware,
calls the handler and publishes the return value as the reply. It must work
with any MQTT 3.1.1/5 broker (Mosquitto, EMQX, HiveMQ, AWS IoT, ...) over
TCP, TLS or WebSockets.

Design goals, in priority order: correct MQTT semantics, a small and
predictable API that mirrors FastAPI, minimal dependencies (runtime:
`paho-mqtt` only), clean readable code.

## Layout

```
src/mqute/
  app.py           MQute: lifecycle, hooks, exception handlers, message pipeline (process → middleware → handler → reply)
  routing.py       Router, Route, Subscription; prefixes, include_router, router-level middleware
  topics.py        TopicPattern: "{name}"/"{name:path}" patterns → MQTT filters, matching, validation
  dependencies.py  Depends and Dependant: signature analysis at registration, parameter resolution per message
  encoding.py      encode() values → bytes; decode() bytes → annotated type (pydantic via duck typing)
  message.py       Message (immutable; used for incoming and outgoing messages)
  response.py      Response (explicit reply options)
  broker.py        Broker / TLS / Will settings, Broker.from_url
  providers.py     Presets: hivemq_cloud, hivemq_public, emqx_cloud, aws_iot, mosquitto
  transport.py     Transport ABC + PahoTransport (the only module importing paho)
  testing.py       MemoryTransport + TestClient
  cli.py           `mqute run module:app`
tests/             unit tests (one file per module); tests/integration needs a real broker
scripts/release.py stdlib-only: PR-title check and next-version computation used by CI
examples/          runnable examples referenced from the README
.github/           CI, release workflow, issue/PR templates, dependabot
```

## Architecture rules

- `transport.py` is the only place that touches paho. Everything else talks to
  the `Transport` interface; keep it that way so other clients can be plugged in.
- Transport callbacks come from paho's network thread; they must be handed to
  the event loop with `loop.call_soon_threadsafe`. App code runs on the loop only.
- Handler signatures are analysed once at registration (`Dependant`). Fail fast
  with `TypeError`/`TopicError` there rather than at message time.
- Each incoming message is processed in its own task; sync handlers run via
  `asyncio.to_thread`. Shutdown drains tasks (`shutdown_timeout`) before disconnecting.
- `MQute.process(message)` is the single pipeline entry; it raises unhandled
  errors (TestClient relies on this), while the transport path logs them.
- Pydantic is optional: never import it in `src/`; detect models by
  `model_validate_json` / `model_dump_json`.
- Keep MQTT correctness: `+`/`#` never match `$`-topics at the first level,
  `#` must be last, publish topics must not contain wildcards.

## Commands

```bash
python -m pip install -e . --group dev   # setup (pip >= 25.1)
ruff check . && ruff format --check .    # lint + format check (ruff format . to fix)
mypy                                     # strict typing on src/
pytest --cov                             # tests, coverage gate 90%
MQUTE_TEST_BROKER_URL=mqtt://localhost:1883 pytest   # include broker integration tests
python -m build                          # sdist + wheel (version from git tags via hatch-vcs)
```

A local broker for integration tests: `mosquitto -p 1883` or
`docker run -d -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf`.

Always run lint, mypy and the full test suite before committing.

## Standard workflow

1. Work starts from a GitHub **issue**, assigned to whoever does it.
2. Each issue gets its own **branch** named `<issue-number>-<short-slug>`
   (e.g. `42-shared-subscriptions`). Never commit directly to `main`.
3. Changes land through a **pull request** into `main` whose title is a
   **Conventional Commit** (`feat(scope): ...`, `fix: ...`, `type!: ...` for
   breaking) and whose body contains `Closes #<issue>`. Follow
   `.github/pull_request_template.md`.
4. PRs are **squash-merged**, so the PR title becomes the commit on `main`.
5. Every merge to `main` triggers `.github/workflows/release.yml`: CI → next
   version from `scripts/release.py next-version` → build → tag `vX.Y.Z` →
   GitHub release → PyPI (trusted publishing). Never edit version numbers by
   hand: the version comes from git tags (`hatch-vcs`), and `mqute.__version__`
   reads installed metadata.

Version bumps: `feat` → minor, anything else → patch, `!`/`BREAKING CHANGE:` →
major (minor while the version is 0.x).

## Coding conventions

- Python ≥ 3.10, `from __future__ import annotations` in library modules, full
  type hints, `mypy --strict` clean, ruff (line length 120) clean.
- Clean code: small focused functions, descriptive names, no dead code, no
  `print` (use `logging.getLogger("mqute")`), no speculative abstractions.
- Public API is exported from `mqute/__init__.py` and listed in `__all__`;
  anything else is private. Changing public API means updating `README.md`.
- Docstrings: short, say *what* and *why*; comments only for non-obvious reasons.
- No new runtime dependency without an issue discussing it; optional features
  go behind extras (like `mqute[pydantic]`).
- Tests: pytest, `asyncio_mode = auto`, warnings are errors. App behaviour is
  tested through `mqute.testing.TestClient`; pure logic with plain unit tests.
  Add a test for every bug fix and feature. Keep coverage ≥ 90%.
