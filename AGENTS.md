# Repository Guidelines

## Project Structure & Module Organization

This repository contains a small Python/Pygame multiplayer game:

- `server.py`: authoritative game state, player movement, collisions, missions, routers, and Karma effects.
- `client.py`: Pygame window, input handling, menus, HUD, and rendering.
- `network.py`: shared TCP/IPv4 JSON framing and client connection helpers.
- `test_server.py`: unit tests for gameplay and server state.
- `test_network.py`: unit tests for serialization, framing, and connection errors.
- `README.md`: setup, controls, networking, and gameplay documentation.

Keep game rules on the server. The client may display predictions or effects, but it must not decide whether movement, repairs, mission progress, or victory are valid.

## Build, Test, and Development Commands

Use Python 3.10 or newer. On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
.\.venv\Scripts\python.exe client.py --name "Jugador UNI"
```

Run the complete test suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Check syntax before submitting changes:

```powershell
.\.venv\Scripts\python.exe -m py_compile network.py server.py client.py
```

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation. Use `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Add type hints to public functions and data structures where practical. Prefer small methods and descriptive gameplay names such as `time_remaining` or `target_router`.

No formatter or linter is currently enforced. Keep imports grouped as standard library, third-party, then local modules. Preserve JSON-compatible network payloads and avoid sending Python-specific objects.

## Testing Guidelines

Tests use the standard-library `unittest` framework. Name files `test_*.py`, classes `*Tests`, and methods `test_*`. Add tests for server-authoritative behavior, protocol edge cases, mission transitions, and regressions. Use seeded `random.Random(...)` instances when randomness must be reproducible.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Spanish summaries, for example: `Mejora ruta aleatoria y tabla de Karma`. Keep each commit focused on one coherent change.

Pull requests should explain gameplay and protocol changes, list tests run, and include screenshots for visible Pygame interface updates. Mention any new message types or state fields so client and server compatibility can be reviewed together.

## Security & Configuration Tips

Do not commit virtual environments, local tools, credentials, or tunnel tokens. Treat all client messages as untrusted: validate message types, payloads, sizes, player ownership, and coordinates on the server.
