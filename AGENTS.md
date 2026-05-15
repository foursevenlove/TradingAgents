# Repository Guidelines

## Project Structure & Module Organization

`tradingagents/` contains the core package: agent roles live under `agents/`, graph orchestration under `graph/`, data providers under `dataflows/`, LLM adapters under `llm_clients/`, and A-share rules under `market_rules/`. `cli/` provides the Typer entry point. The web app is split into `web/backend/` for FastAPI and `web/frontend/` for Vue 3, Vite, and Tailwind. Root-level `test_*.py` files are the current test suite. Docs and images live in `docs/` and `assets/`.

## Build, Test, and Development Commands

- Use the `tradingagents` conda environment for Python work, e.g. `conda run -n tradingagents python test_news_pipeline.py`.
- `conda run -n tradingagents python -m pip install -r requirements.txt`: install Python dependencies.
- `conda run -n tradingagents python -m cli.main`: start the CLI.
- `conda run -n tradingagents pytest test_news_analyst.py` or `conda run -n tradingagents pytest test_*.py`: run focused or full tests.
- `./scripts/start_web.sh`: build/start the FastAPI + Vue web UI at `http://localhost:8000`.
- `uvicorn web.backend.app:app --reload --port 8000`: run only the backend.
- `cd web/frontend && npm install && npm run dev`: run the frontend dev server.
- `cd web/frontend && npm run build`: produce the frontend production bundle.

## Coding Style & Naming Conventions

Use Python 3.10+ syntax and follow PEP 8 with 4-space indentation. Keep module and function names `snake_case`, classes `PascalCase`, and constants `UPPER_SNAKE_CASE`. Prefer typed Pydantic models in `web/backend/models.py` for API contracts, and keep provider-specific logic in the matching `dataflows/` or `llm_clients/` module. Vue components use `PascalCase.vue`.

## Testing Guidelines

Add or update `test_*.py` files near the repository root unless introducing a dedicated package-level test area. Use `pytest` assertions and keep network/API-key-dependent checks isolated behind clear skips or mocks. For web changes, verify backend routes where practical and run `npm run build` for frontend regressions.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit prefixes such as `feat:`, `fix(deps):`, and `docs(agent):`. Keep messages imperative and scoped when useful, for example `feat(web): add holdings summary`. Pull requests should explain the user-facing change, list verification commands, note required environment variables, and include screenshots or short recordings for UI changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local secrets. Never commit API keys, personal tokens, generated logs, local databases, or bulky report outputs. Document new configuration in README or `.env.example` when adding environment variables.

## Agent-Specific Instructions

Use Chinese when communicating with the repository owner unless they explicitly request another language.
