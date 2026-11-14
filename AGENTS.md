# AGENTS.md

Fichier d'instructions **unique**, lu par tous les agents (Claude Code, Gemini CLI, Codex…) et par les humains.
C'est la mémoire commune de l'équipe : **mettez-le à jour dès qu'une décision est prise.**
Le guide pratique pour les humains (installation, boucle de travail, prompts types) est [ONBOARDING.md](ONBOARDING.md).

> Ne créez jamais de `CLAUDE.md` ni de `GEMINI.md` : Claude Code lirait le `CLAUDE.md` à la place de ce fichier, et les deux IA divergeraient.

## Projet

**Sujet :** _à compléter (une phrase : quoi, pour qui)._
**Démo attendue :** _à compléter._

## Règles d'or (pour chaque agent, à chaque tâche)

1. **Avant de commencer**, lire `STATUS.md` et les issues ouvertes (`gh issue list`).
2. **Réserver sa tâche avant de coder.** Une tâche = une issue GitHub, et **s'assigner l'issue = la réserver** (la créer si elle n'existe pas). Écrire dans l'issue les fichiers ou dossiers touchés. Une issue déjà assignée à quelqu'un d'autre ne se prend pas : on se coordonne. Personne n'a de dossier attitré, mais on reste dans le périmètre de sa tâche : pas de refacto opportuniste ailleurs.
3. **Ne jamais changer le contrat d'API en silence** (voir « Contrat d'API »).
4. **Aucune nouvelle dépendance sans le dire** : l'ajouter dans « Décisions » ci-dessous et dans `STATUS.md`.
5. **En fin de tâche**, ouvrir une PR qui ferme l'issue (`Closes #N`), puis mettre à jour son bloc dans `STATUS.md` (en cours, bloqué, notes pour la suite).
6. **Ne jamais contourner les hooks** (`--no-verify` interdit). Si un hook échoue, corriger.
7. **Aucun secret dans git** : clés et tokens vont dans `.env` (ignoré), modèle dans `.env.example`.

## Équipe et organisation

Pas de rôle fixe : chacun prend des tâches, de préférence **de bout en bout** (une fonctionnalité = front + back + ml si besoin). On n'attend pas les autres pour avancer.

| Personne      | Agent IA             |
| ------------- | -------------------- |
| _<prénom A>_  | _<Claude / Gemini>_  |
| _<prénom B>_  | _<Claude / Gemini>_  |
| _<prénom C>_  | _<Claude / Gemini>_  |

Pour ne pas se marcher dessus :
- **Réserver** sa tâche en s'assignant l'issue GitHub avant de commencer (règle 2). C'est visible tout de suite par les autres, sans push ni pull.
- **Une branche par tâche, mergée vite** (quelques heures au plus) : plus une branche vit longtemps, plus les conflits sont gros.
- **On merge soi-même** sa PR dès que la CI est verte et qu'on a lu les relectures automatiques.
- **Fichiers sensibles**, partagés par tout le monde : `backend/schemas.py`, `ml/model.py`, `AGENTS.md` et les configs à la racine. Annoncer dans `STATUS.md` (« À lire par tous ») **avant** de les modifier.

## Stack

- **Backend** : Python 3.12, FastAPI, Pydantic v2, uvicorn. Gestionnaire : **uv** (jamais `pip install`).
- **ML** : Python 3.12, dans le même environnement uv que le backend.
- **Frontend** : React 19, TypeScript 7, Vite 8. Gestionnaire : **npm 11.19 ou plus** (comme la CI). Un npm plus ancien écrit un `package-lock.json` incomplet que la CI refuse (« Missing: … from lock file »). Mise à jour : `npm install -g npm@latest`.
- **Qualité** : ruff (lint + format Python), prettier (format front), oxlint (lint front), pytest, pre-commit, CI GitHub Actions.

## Commandes

Toutes les commandes se lancent **depuis la racine du repo**.

```bash
# Installation (une fois, après le clone)
uv sync
npm --prefix frontend install
uv run pre-commit install

# Lancer en dev (2 terminaux)
uv run uvicorn backend.main:app --reload --port 8000   # API sur http://localhost:8000 (doc : /docs)
npm --prefix frontend run dev                           # UI sur http://localhost:5173 (proxy /api -> 8000)

# Tester / vérifier
uv run pytest                              # tests contrat API + ML
npm --prefix frontend run typecheck        # types TS
uv run pre-commit run --all-files          # tous les hooks (format, lint, tests)

# Contrat d'API (voir plus bas)
uv run python -m backend.export_openapi    # régénère contract/openapi.json
npm --prefix frontend run gen:api          # régénère frontend/src/api/schema.d.ts

# Tâches et PR (GitHub CLI : gh)
gh issue list                              # tâches ouvertes
gh issue list --search "no:assignee"       # tâches libres
gh issue create --title "..." --body "..." # nouvelle tâche
gh issue edit 12 --add-assignee @me        # réserver la tâche 12
git switch -c prenom/12-sujet              # branche de la tâche 12
gh pr create --title "..." --body "Closes #12"
gh pr checks                               # état de la CI de la PR
gh pr merge --squash --delete-branch       # merger quand la CI est verte
```

**Déploiement** : _à décider. Noter ici la commande dès que c'est fait._

## Arborescence

```
backend/
  main.py            # routes FastAPI (toutes sous /api)
  schemas.py         # CONTRAT : modèles Pydantic requête/réponse
  errors.py          # ApiError + format d'erreur unique
  export_openapi.py  # schemas -> contract/openapi.json
  tests/             # tests du contrat d'API
ml/
  model.py           # CONTRAT : predict(text) -> Prediction
  tests/             # tests du contrat ML
  data/, models/     # données et poids : ignorés par git (trop lourds)
contract/
  openapi.json       # GÉNÉRÉ, commité : la référence partagée front/back
frontend/
  src/api/schema.d.ts  # GÉNÉRÉ depuis contract/openapi.json, ne pas éditer
  src/api/client.ts    # seul endroit qui appelle fetch()
  src/App.tsx
```

## Contrat d'API

Chaîne de vérité, dans un seul sens :

```
backend/schemas.py  ──export──▶  contract/openapi.json  ──gen:api──▶  frontend/src/api/schema.d.ts
```

- **Front ↔ back** : `backend/schemas.py` est la source de vérité. Le front n'écrit **jamais** de types d'API à la main : il importe ceux de `schema.d.ts` via `src/api/client.ts`.
- **Back ↔ ML** : la signature de `ml.model.predict` et la dataclass `Prediction`. L'intérieur est libre.
- **Garde-fou** : `backend/tests/test_api_contract.py` échoue si l'API ne correspond plus à `contract/openapi.json`. `ml/tests/` vérifie la signature de `predict`.

**Pour changer le contrat** (et seulement si c'est voulu) :
1. Modifier `backend/schemas.py` (ou `ml/model.py` pour le contrat ML).
2. `uv run python -m backend.export_openapi` puis `npm --prefix frontend run gen:api`.
3. Commiter les trois fichiers **ensemble**.
4. Annoncer le changement dans `STATUS.md` (« À lire par tous ») : quelqu'un code peut-être en ce moment contre l'ancien schéma.

Ne jamais « réparer » le test de contrat en régénérant `openapi.json` sans avoir compris pourquoi il casse.

## Outils branchés

- **CI** (`.github/workflows/ci.yml`) : relance tous les hooks pre-commit sur chaque PR et chaque push sur `main`. On ne merge jamais une PR dont la CI est rouge.
- **Context7** : serveur MCP `context7` qui donne la documentation à jour des librairies. Il est configuré dans `.mcp.json` (Claude) et `.gemini/settings.json` (Gemini). **Agents : avant d'écrire du code qui utilise l'API d'une librairie (FastAPI, Pydantic, React, Vite…), consultez Context7.** La stack est plus récente que vos connaissances. Il est utilisé sans clé API, donc avec des quotas bas : en cas d'erreur 429, le signaler dans `STATUS.md`.
- **Relecture automatique des PR** : Claude (`claude-code-review.yml`, commentaires dans le code) et Gemini (`gemini-review.yml`, un commentaire de synthèse) relisent chaque PR à son ouverture. Lire ces relectures avant de merger. Si un job de relecture est rouge, c'est un souci de quota ou de clé, pas de code : seule la CI bloque le merge.
  - Question ou deuxième passe par Claude : écrire `@claude …` dans un commentaire de la PR.
  - Deuxième passe par Gemini : relancer le job « Gemini Review » depuis l'onglet Actions.

## Conventions

**Général**
- Identifiants de code en anglais, commentaires et messages utilisateur en français.
- Petites fonctions, pas de code mort, pas de `TODO` sans nom : `TODO(prénom): …`.

**Python** (`backend/`, `ml/`)
- `snake_case` pour fonctions et variables, `PascalCase` pour les classes. Type hints partout.
- Imports absolus depuis la racine : `from backend.schemas import …`, `from ml.model import …`.
- Pas de `print` dans le backend : utiliser `logging`.
- ML : charger le modèle **une seule fois** (au niveau du module ou avec `functools.cache`), jamais à chaque requête.

**TypeScript** (`frontend/`)
- `camelCase` pour variables et fonctions, `PascalCase` pour composants et types. Un composant par fichier.
- Tous les appels réseau passent par `src/api/client.ts`. URLs relatives (`/api/...`), jamais `http://localhost:8000` en dur.
- Style imposé par prettier : pas de point-virgule, guillemets simples.

**Erreurs**
- Toutes les erreurs de l'API ont le même format : `{"error": {"code": "snake_case", "message": "texte"}}` (`ErrorResponse`).
- Backend : `raise ApiError(404, "item_not_found", "…")`. Ne pas lever `HTTPException` avec un format maison.
- Frontend : attraper `ApiError` (qui expose `status`, `code` et `message`) et afficher `message`.

**Dépendances**
- Python : `uv add <paquet>` (ou `uv add --dev`). Front : `npm --prefix frontend install <paquet>`.
- Toujours commiter le lockfile (`uv.lock`, `frontend/package-lock.json`) avec le changement.
- Annoncer la dépendance dans « Décisions » (une ligne : quoi, pourquoi).

**Git**
- `main` doit toujours fonctionner : on n'y pousse jamais directement, tout passe par une PR.
- Une branche par tâche : `prenom/N-sujet` (N = numéro de l'issue), mergée dans la journée.
- `git pull --rebase` souvent. Petits commits au message clair (« backend: ajoute /api/items »).
- Conflit sur `contract/openapi.json` ou `frontend/src/api/schema.d.ts` : ne **jamais** fusionner ces fichiers à la main. Résoudre le conflit dans `backend/schemas.py`, puis les régénérer avec les deux commandes du contrat.

## Décisions

Le plus récent en haut. Format : `AAAA-MM-JJ — décision — pourquoi`.

- 2026-11-13 — Relecture automatique des PR par Claude et par Gemini — deux modèles différents ne ratent pas les mêmes bugs.
- 2026-11-13 — Context7 (MCP, sans clé) branché sur Claude et Gemini — la stack est plus récente que les connaissances des modèles.
- 2026-11-13 — CI GitHub Actions qui relance les hooks pre-commit — filet de sécurité si les hooks locaux ne sont pas installés.
- 2026-11-13 — Tâches dans GitHub Issues (s'assigner = réserver) et tout passe par des PR ; `STATUS.md` garde les annonces, blocages et notes de passation — visible en temps réel, sans attendre un push.
- 2026-11-13 — Pas de rôle ni de dossier attitré : chacun prend des tâches de bout en bout — les rôles ne sont pas définis à l'avance.
- 2026-11-13 — Stack FastAPI + React/Vite + module `ml/` Python — Python pour le ML, front et back séparés par un contrat d'API.
- 2026-11-13 — Contrat d'API généré depuis Pydantic (`openapi.json` commité, types TS générés) — une seule source de vérité.
- 2026-11-13 — `openapi-typescript` lancé via `npx` en version figée (7.13.0) — il exige TypeScript 5, le front est en TypeScript 7.
- 2026-11-13 — Un seul fichier d'instructions (`AGENTS.md`) : Claude Code le lit nativement (v2.1.277+), Gemini CLI via `.gemini/settings.json`.

## Notes agents

- **Claude Code** : lit ce fichier automatiquement s'il n'existe aucun `CLAUDE.md` (v2.1.277 ou plus ; `claude update`). Après une mise à jour, la toute première session peut ne pas le lire : relancer une session. Vérifier avec `/memory`. Au premier lancement, accepter le serveur MCP `context7` proposé par `.mcp.json` (vérifier avec `/mcp`).
- **Gemini CLI** : `.gemini/settings.json` pointe vers `AGENTS.md` et déclare `context7`. Vérifier avec `/memory show` et `/mcp`.
- Les deux : en fin de tâche, lancer `uv run pre-commit run --all-files`, mettre à jour `STATUS.md`, puis ouvrir la PR (`gh pr create`).
