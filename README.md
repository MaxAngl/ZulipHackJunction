# Needed

Une communauté où ce sont les patients en rémission qui rendent service. Projet Junction 2026, challenge du maintien à domicile après un traitement de la dépression par TMS.

Une IA mesure l'état du patient, en déduit la zone des demandes qui lui conviennent, fait écrire ces demandes par Gemini, les mesure, et en propose trois à un membre de la communauté. Le patient reçoit la demande d'une personne, pas d'une app, et sa réaction ajuste la zone.

Ce qui est simulé et ce qui a été décidé sans validation de l'équipe : **[HYPOTHESES.md](HYPOTHESES.md)**.

Toutes les règles, commandes et conventions sont dans **[AGENTS.md](AGENTS.md)** (lu aussi par les agents IA).
L'avancement de chacun est dans **[STATUS.md](STATUS.md)**.
**Nouveau dans l'équipe ?** Commence par **[ONBOARDING.md](ONBOARDING.md)** : installation, boucle de travail et prompts à donner à ton agent.

## Démarrage rapide

Prérequis : [uv](https://docs.astral.sh/uv/), Node.js 22 ou plus avec npm 11.19 ou plus (`npm install -g npm@latest`), et [GitHub CLI](https://cli.github.com/) (`gh auth login`).

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

Ouvrir http://localhost:5173 :

- `#/` : l'accueil de la vraie app. `#/helper` pour demander un service, `#/patient` pour y répondre. Les comptes et les échanges sont gardés dans `data/needed.db`.
- `#/demo` : la console de démo, avec un patient simulé, où l'on voit toute la boucle sur un écran.

Pour essayer sur deux téléphones du même réseau : `npm --prefix frontend run dev -- --host`.

Pour brancher Gemini, copier `.env.example` en `.env`, y mettre `GEMINI_API_KEY`, puis vérifier :

```bash
uv run python -m ml.check_gemini
```

Sans clé, l'app tourne avec une banque de demandes hors ligne.

## Agents IA

- **Claude Code** : `claude update` (v2.1.277 ou plus), puis lancer `claude` à la racine. Il lit `AGENTS.md` tout seul.
- **Gemini CLI** : lancer `gemini` à la racine. `.gemini/settings.json` lui fait lire `AGENTS.md`.
- Ne pas créer de `CLAUDE.md` ni de `GEMINI.md`.
