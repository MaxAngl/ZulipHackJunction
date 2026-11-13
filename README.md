# Hackathon

_Sujet à compléter._

Toutes les règles, commandes et conventions sont dans **[AGENTS.md](AGENTS.md)** (lu aussi par les agents IA).
L'avancement de chacun est dans **[STATUS.md](STATUS.md)**.

## Démarrage rapide

Prérequis : [uv](https://docs.astral.sh/uv/) et Node.js 22 ou plus.

```bash
uv sync
npm --prefix frontend install
uv run pre-commit install
```

Puis, dans deux terminaux :

```bash
uv run uvicorn backend.main:app --reload --port 8000
npm --prefix frontend run dev
```

Ouvrir http://localhost:5173.

## Agents IA

- **Claude Code** : `claude update` (v2.1.277 ou plus), puis lancer `claude` à la racine. Il lit `AGENTS.md` tout seul.
- **Gemini CLI** : lancer `gemini` à la racine. `.gemini/settings.json` lui fait lire `AGENTS.md`.
- Ne pas créer de `CLAUDE.md` ni de `GEMINI.md`.
