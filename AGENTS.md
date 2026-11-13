# AGENTS.md

Fichier d'instructions **unique**, lu par tous les agents (Claude Code, Gemini CLI, Codex…) et par les humains.
C'est la mémoire commune de l'équipe : **mettez-le à jour dès qu'une décision est prise.**

> Ne créez jamais de `CLAUDE.md` ni de `GEMINI.md` : Claude Code lirait le `CLAUDE.md` à la place de ce fichier, et les deux IA divergeraient.

## Projet

**Sujet :** _à compléter (une phrase : quoi, pour qui)._
**Démo attendue :** _à compléter._

## Règles d'or (pour chaque agent, à chaque tâche)

1. **Avant de commencer**, lire `STATUS.md`.
2. **Réserver sa zone avant de coder.** Personne n'a de dossier attitré : tout le monde peut toucher à tout. Avant de commencer, écris dans ton bloc de `STATUS.md` la tâche et les fichiers ou dossiers que tu vas modifier. Si quelqu'un est déjà dessus, coordonnez-vous d'abord. Reste dans le périmètre de ta tâche : pas de refacto opportuniste ailleurs.
3. **Ne jamais changer le contrat d'API en silence** (voir « Contrat d'API »).
4. **Aucune nouvelle dépendance sans le dire** : l'ajouter dans « Décisions » ci-dessous et dans `STATUS.md`.
5. **En fin de tâche**, mettre à jour son bloc dans `STATUS.md` (fait / en cours / bloqué).
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
- **Réserver** sa tâche et ses fichiers dans `STATUS.md` avant de commencer (règle 2).
- **Une branche par tâche, mergée vite** (quelques heures au plus) : plus une branche vit longtemps, plus les conflits sont gros.
- **Fichiers sensibles**, partagés par tout le monde : `backend/schemas.py`, `ml/model.py`, `AGENTS.md` et les configs à la racine. Annoncer dans `STATUS.md` (« À lire par tous ») **avant** de les modifier.

## Stack

- **Backend** : Python 3.12, FastAPI, Pydantic v2, uvicorn. Gestionnaire : **uv** (jamais `pip install`).
- **ML** : Python 3.12, dans le même environnement uv que le backend.
- **Frontend** : React 19, TypeScript 7, Vite 8. Gestionnaire : **npm**.
- **Qualité** : ruff (lint + format Python), prettier (format front), oxlint (lint front), pytest, pre-commit.

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
- `main` doit toujours fonctionner. Une branche par tâche : `prenom/tache`, mergée dans la journée.
- `git pull --rebase` souvent. Petits commits au message clair (« backend: ajoute /api/items »).
- Conflit sur `contract/openapi.json` ou `frontend/src/api/schema.d.ts` : ne **jamais** fusionner ces fichiers à la main. Résoudre le conflit dans `backend/schemas.py`, puis les régénérer avec les deux commandes du contrat.

## Décisions

Le plus récent en haut. Format : `AAAA-MM-JJ — décision — pourquoi`.

- 2026-11-13 — Pas de rôle ni de dossier attitré : chacun prend des tâches de bout en bout et réserve sa zone dans `STATUS.md` — les rôles ne sont pas définis à l'avance.
- 2026-11-13 — Stack FastAPI + React/Vite + module `ml/` Python — Python pour le ML, front et back séparés par un contrat d'API.
- 2026-11-13 — Contrat d'API généré depuis Pydantic (`openapi.json` commité, types TS générés) — une seule source de vérité.
- 2026-11-13 — `openapi-typescript` lancé via `npx` en version figée (7.13.0) — il exige TypeScript 5, le front est en TypeScript 7.
- 2026-11-13 — Un seul fichier d'instructions (`AGENTS.md`) : Claude Code le lit nativement (v2.1.277+), Gemini CLI via `.gemini/settings.json`.

## Notes agents

- **Claude Code** : lit ce fichier automatiquement s'il n'existe aucun `CLAUDE.md` (v2.1.277 ou plus ; `claude update`). Après une mise à jour, la toute première session peut ne pas le lire : relancer une session. Vérifier avec `/memory`.
- **Gemini CLI** : `.gemini/settings.json` pointe vers `AGENTS.md`. Vérifier avec `/memory show`.
- Les deux : en fin de tâche, lancer `uv run pre-commit run --all-files` et mettre à jour `STATUS.md`.
