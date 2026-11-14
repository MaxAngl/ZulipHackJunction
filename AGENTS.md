# AGENTS.md

Fichier d'instructions **unique**, lu par tous les agents (Claude Code, Gemini CLI, Codex…) et par les humains.
C'est la mémoire commune de l'équipe : **mettez-le à jour dès qu'une décision est prise.**
Le guide pratique pour les humains (installation, boucle de travail, prompts types) est [ONBOARDING.md](ONBOARDING.md).

> Ne créez jamais de `CLAUDE.md` ni de `GEMINI.md` : Claude Code lirait le `CLAUDE.md` à la place de ce fichier, et les deux IA divergeraient.

## Projet

**Sujet :** Needed (nom provisoire), pour le challenge Junction sur le maintien à domicile après un traitement de la dépression par TMS. Une communauté où ce sont les patients en rémission qui rendent service : une IA décide quoi leur demander, quand et de la part de qui, selon leur état.
**Démo attendue :** deux choses. La **vraie app** (`#/helper`, `#/patient`) : deux personnes s'inscrivent sur leur téléphone, l'une demande un service, l'autre répond, la première remercie. Et la **console** (`#/demo`) : la boucle fermée pour un patient simulé, où l'on voit l'état θ bouger, la zone λ(θ) se déplacer, les demandes générées, mesurées et filtrées, puis la zone s'ajuster.
**À lire :** [HYPOTHESES.md](HYPOTHESES.md) liste ce qui a été décidé sans validation de l'équipe et ce qui est simulé dans le code actuel.
**Modèle cible :** [docs/modele.md](docs/modele.md) définit les objets, les axes d'une demande, les trois réseaux, leur entraînement et leur évaluation. Il n'est pas encore codé : avant de toucher à `ml/`, lire ce document et sa section « Écarts avec le code actuel ».

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
- **On merge soi-même** sa PR dès que la CI est verte et que la relecture d'un coéquipier est traitée.
- **Fichiers sensibles**, partagés par tout le monde : `backend/schemas.py`, `ml/model.py`, `AGENTS.md` et les configs à la racine. Annoncer dans `STATUS.md` (« À lire par tous ») **avant** de les modifier.

## Stack

- **Backend** : Python 3.12, FastAPI, Pydantic v2, uvicorn. Gestionnaire : **uv** (jamais `pip install`).
- **ML** : Python 3.12, dans le même environnement uv que le backend. `numpy` pour les données simulées.
- **IA générative** : API Gemini appelée en REST avec la bibliothèque standard (`ml/gemini.py`), sans SDK. Clé dans `.env` (`GEMINI_API_KEY`). Sans clé, ou si Gemini échoue, `ml/lexicon.py` prend le relais.
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

uv run python -m ml.check_gemini           # vérifie la clé Gemini et la mesure λ
uv run python -m ml.simulation             # génère les données simulées dans ml/data/sim (hors git)

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
  loop.py            # console de démo : la boucle en 12 étapes, un patient simulé, état en mémoire
  sensor.py          # capteur d'état θ SIMULÉ (console de démo seulement)
  community.py       # vraie app : comptes, demandes, réponses, θ estimé d'après le comportement
  store.py           # vraie app : stockage SQLite (data/needed.db, ignoré par git)
  errors.py          # ApiError + format d'erreur unique
  export_openapi.py  # schemas -> contract/openapi.json
  tests/             # tests du contrat d'API
ml/
  model.py           # CONTRAT : zone_for, learn (modèle de zone SIMULÉ) et tout ce que le backend importe
  pipeline.py        # générer -> mesurer λ -> filtrer -> choisir trois demandes
  gemini.py          # client REST Gemini (génération JSON, embeddings)
  lexicon.py         # mode hors ligne : banque de demandes et mesure par mots-clés
  formats.py         # grille fixe des formats et de leur effort
  check_gemini.py    # vérification de la clé Gemini
  simulation/        # données simulées : θ, état caché, patient simulé, journal d'épisodes (docs/modele.md, 11 et 12)
  tests/             # tests du contrat ML et des données simulées
  data/, models/     # données et poids : ignorés par git (trop lourds)
docs/
  modele.md          # le modèle cible : objets, axes, réseaux, entraînement (pas encore codé)
contract/
  openapi.json       # GÉNÉRÉ, commité : la référence partagée front/back
frontend/
  src/api/schema.d.ts  # GÉNÉRÉ depuis contract/openapi.json, ne pas éditer
  src/api/client.ts    # seul endroit qui appelle fetch()
  src/components/      # console de démo : un composant par fichier (téléphones, plan des demandes)
  src/screens/         # vraie app (accueil, inscription, aidant, patient) et écran de la console
  src/session.ts       # jeton de l'appareil, par rôle
  src/App.tsx          # routes : #/ accueil, #/helper, #/patient, #/demo
```

## Contrat d'API

Chaîne de vérité, dans un seul sens :

```
backend/schemas.py  ──export──▶  contract/openapi.json  ──gen:api──▶  frontend/src/api/schema.d.ts
```

- **Front ↔ back** : `backend/schemas.py` est la source de vérité. Le front n'écrit **jamais** de types d'API à la main : il importe ceux de `schema.d.ts` via `src/api/client.ts`.
- **Back ↔ ML** : le backend n'importe que depuis `ml.model`. Le contrat est la liste `__all__` de ce fichier : la zone (`zone_for`, `learn`), la chaîne de demandes (`generate_candidates`, `measure_message`, `select_three`) et leurs types. L'intérieur est libre.
- **Garde-fou** : `backend/tests/test_api_contract.py` échoue si l'API ne correspond plus à `contract/openapi.json`. `ml/tests/` vérifie le comportement attendu de `ml.model`. Les tests coupent Gemini (`conftest.py`) : ils ne touchent jamais le réseau.

**Pour changer le contrat** (et seulement si c'est voulu) :
1. Modifier `backend/schemas.py` (ou `ml/model.py` pour le contrat ML).
2. `uv run python -m backend.export_openapi` puis `npm --prefix frontend run gen:api`.
3. Commiter les trois fichiers **ensemble**.
4. Annoncer le changement dans `STATUS.md` (« À lire par tous ») : quelqu'un code peut-être en ce moment contre l'ancien schéma.

Ne jamais « réparer » le test de contrat en régénérant `openapi.json` sans avoir compris pourquoi il casse.

## Outils branchés

- **CI** (`.github/workflows/ci.yml`) : relance tous les hooks pre-commit sur chaque PR et chaque push sur `main`. On ne merge jamais une PR dont la CI est rouge.
- **Context7** : serveur MCP `context7` qui donne la documentation à jour des librairies. Il est configuré dans `.mcp.json` (Claude) et `.gemini/settings.json` (Gemini). **Agents : avant d'écrire du code qui utilise l'API d'une librairie (FastAPI, Pydantic, React, Vite…), consultez Context7.** La stack est plus récente que vos connaissances. Il est utilisé sans clé API, donc avec des quotas bas : en cas d'erreur 429, le signaler dans `STATUS.md`.
- **Relecture croisée par les agents** (pas de relecture automatique sur GitHub) : l'auteur d'une PR demande à un coéquipier de la faire relire par son agent, idéalement l'autre modèle (Claude ↔ Gemini). **Agents relecteurs :** lisez le diff (`gh pr diff N`) et ce fichier, listez seulement les vrais problèmes (bugs, contrat d'API, règles de ce fichier) avec fichier et ligne, ne modifiez rien, et postez la relecture en commentaire (`gh pr comment N`).

## Conventions

**Général**
- Identifiants de code en anglais, commentaires en français. **Textes de l'interface et messages d'erreur de l'API en anglais** : le jury est international.
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

- 2026-11-14 — Hooks `pre-commit-hooks` lancés via `python -m` (champ `entry`) — Smart App Control de Windows 11 bloque les .exe non signés que pip génère, ce qui rendait tout commit impossible.
- 2026-11-14 — La partie personnelle se réduit à un vecteur de 8 nombres par patient, lu par A et par B. **Cela remplace la dernière couche par patient décidée plus bas** — 715 nombres pour B, c'était trop pour une trentaine de réactions par mois.
- 2026-11-14 — B ne reçoit pas le texte des centres d'intérêt — sa sortie sur cet axe est une position entre les deux sujets, quels qu'ils soient ; le texte sert au choix de la paire, à Gemini et à la mesure.
- 2026-11-14 — Les réseaux restent petits, environ 45 000 paramètres au total, et la taille de B se choisit par un essai de capacité — peu d'entrées, un générateur simple ; un petit modèle s'explique et tourne sur un téléphone.
- 2026-11-14 — Nouvelle dépendance `numpy` — générer et enregistrer les données simulées ; les réseaux en auront besoin de toute façon.
- 2026-11-14 — θ compte 22 signaux : ceux d'une montre Garmin Forerunner 965 utiles au suivi, plus le comportement dans l'app. L a 6 composantes : sommeil, rythme, énergie, calme, activité, engagement — choix délégués à Claude, à relire (`docs/modele.md`, section 11).
- 2026-11-14 — Récompense = 50 + 150 × l'amélioration relative de la distance à L_ref, entre 0 et 100, mesurée 24 heures après la demande — L_ref est une moyenne et une dispersion des personnes saines, donc une région.
- 2026-11-14 — Les données d'entraînement sont simulées par `ml/simulation` et restent hors git — aucune donnée réelle ; toutes les règles du générateur sont listées en section 12 de `docs/modele.md`.
- 2026-11-14 — Le modèle cible est fixé dans `docs/modele.md` et remplacera la règle écrite à la main — le code actuel tient l'état en un seul nombre ; la cible sépare les données brutes θ du vecteur d'état L(θ).
- 2026-11-14 — Trois réseaux : un autoencodeur pour L(θ), B (un Transformer) qui sort la zone, A (petit réseau dense) qui prédit la récompense. **A ne sert qu'à l'entraînement, B décide seul** — la décision tient en un réseau, et la réalité corrige A, qui corrige B.
- 2026-11-14 — Poids généraux partagés, plus une dernière couche par patient dans A et dans B — un réseau entier par patient n'aurait pas assez de données.
- 2026-11-14 — Une demande se décrit sur 8 axes (6 en phase 1) et la zone donne un intervalle par axe, avec un plafond seul pour le coût de démarrage et la compétence exigée — l'ancien « effort » mélangeait durée, échange et passage à l'action.
- 2026-11-14 — L_ref est l'état d'une personne saine, et la récompense va de 0 à 100 en comparant L avant et après la demande — une cible lisible pour mesurer une amélioration.
- 2026-11-14 — Vraie app à côté de la console de démo : comptes par jeton d'appareil, sans mot de passe — assez pour une démo sur deux téléphones ; à remplacer avant tout usage avec de vrais patients.
- 2026-11-14 — Stockage SQLite avec la bibliothèque standard (`data/needed.db`, ignoré par git) — persistance sans dépendance ni service à installer.
- 2026-11-14 — Dans la vraie app, θ est estimé d'après le comportement du patient, et un capteur externe peut le pousser par l'API — pas de capteur réel disponible ; la règle n'est pas validée.
- 2026-11-14 — Charte minimaliste : noir sur blanc, traits fins, un seul accent cyan vif `#00D8FF` — demande de l'équipe.
- 2026-11-14 — Challenge technique visé : Best Use of Gemini API — Gemini écrit les demandes, ses embeddings les mesurent, et il relit les messages de l'aidant.
- 2026-11-14 — Gemini appelé en REST avec la bibliothèque standard, sans SDK — aucune dépendance à ajouter, et un repli hors ligne si l'API échoue.
- 2026-11-14 — Modèle de zone et capteur d'état simulés derrière `ml/model.py` et `backend/sensor.py` — pas de données pour entraîner ; les signatures resteront quand le vrai modèle arrivera.
- 2026-11-14 — Interface et messages d'erreur en anglais — jury international ; les commentaires restent en français.
- 2026-11-14 — Mesure λ = 0,5 + (a·p − a·h) / (2·(1 − p·h)), recalée sur chaque lot avec Gemini — le rapport a·p / (a·p + a·h) tasse tout autour de 0,5 avec de vrais embeddings.
- 2026-11-14 — État de la démo en mémoire, un seul patient — pas de base de données tant que la boucle n'est pas validée.
- 2026-11-14 — Pas de relecture automatique des PR : relecture croisée par l'agent d'un coéquipier, idéalement l'autre modèle — aucune clé API branchée sur GitHub, et deux modèles différents ne ratent pas les mêmes bugs.
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
