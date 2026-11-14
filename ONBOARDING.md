# Guide de l'équipe

Comment on travaille à trois avec nos agents IA, sans se marcher dessus.
Les **règles** sont dans [AGENTS.md](AGENTS.md) : ce guide explique **comment s'en servir au quotidien**.

## 1. Installation (une fois, 15 min)

### Prérequis

| Outil | Windows | macOS | Vérifier |
|---|---|---|---|
| git | `winget install --id Git.Git` | `brew install git` | `git --version` |
| uv (Python) | `winget install --id astral-sh.uv` | `brew install uv` | `uv --version` |
| Node.js 22+ | `winget install --id OpenJS.NodeJS.LTS` | `brew install node` | `node --version` |
| npm 11.19+ | `npm install -g npm@latest` | idem | `npm --version` |
| GitHub CLI | `winget install --id GitHub.cli` | `brew install gh` | `gh --version` |
| Claude Code | `claude update` (v2.1.277 ou plus) | idem | `claude --version` |
| Gemini CLI | `npm install -g @google/gemini-cli@latest` | idem | `gemini --version` |

Après une installation sous Windows, **ouvre un nouveau terminal** pour que la commande soit trouvée.

Puis connecte GitHub CLI (choisis GitHub.com, HTTPS, connexion par le navigateur, et réponds **Y** à « Authenticate Git ») :

```bash
gh auth login
```

### Cloner et installer

Mets le repo **hors de OneDrive, iCloud ou Dropbox** (par exemple `C:\dev` ou `~/dev`) : la synchro bloque des fichiers et alourdit tout.

```bash
git clone https://github.com/MaxAngl/ZulipHackJunction.git
cd ZulipHackJunction
uv sync
npm --prefix frontend ci
uv run pre-commit install
uv run pre-commit run --all-files
```

La dernière commande doit afficher uniquement des `Passed`.

### Premier lancement de ton agent

- **Claude Code** : lance `claude` à la racine du repo. Accepte la confiance dans le dossier, puis le serveur MCP `context7`. Vérifie avec `/memory` (AGENTS.md doit apparaître) et `/mcp` (context7 connecté).
- **Gemini CLI** : lance `gemini` à la racine du repo et **fais confiance au dossier**, sinon il ignore `.gemini/settings.json` (donc AGENTS.md et Context7). Vérifie avec `/memory show` et `/mcp`.
- Ne crée **jamais** de `CLAUDE.md` ni de `GEMINI.md`.

## 2. La boucle de travail

```
issue  →  s'assigner  →  branche  →  coder avec l'agent  →  PR  →  CI + relectures  →  merge
```

1. **Choisir une tâche** dans les issues libres, ou en créer une. **S'assigner l'issue = la réserver** : les autres le voient tout de suite.
2. **Créer une branche** depuis `main` à jour : `prenom/12-sujet` (12 = numéro de l'issue).
3. **Coder avec ton agent.** Petits commits. Le hook pre-commit formate, lint, vérifie les types et lance les tests à chaque commit.
4. **Ouvrir une PR** qui contient `Closes #12`. La CI relance toutes les vérifications ; Claude et Gemini relisent la PR automatiquement.
5. **Merger soi-même** dès que la CI est verte et qu'on a lu les relectures. Viser une PR mergée toutes les 2 à 3 heures : plus une branche vit, plus les conflits font mal.

On ne pousse **jamais** directement sur `main`.

## 3. Les prompts à donner à ton agent

Copie-colle et adapte. Ton agent connaît déjà les règles (il lit AGENTS.md), ces prompts déclenchent juste les bonnes étapes.

**En début de session**
```
Mets-toi à jour : passe sur main et fais git pull, lis STATUS.md, puis montre-moi
mes issues assignées, les issues libres et les PR ouvertes.
```

**Créer une tâche**
```
Crée une issue avec le modèle « Tâche » pour : <ce que tu veux faire>.
Remplis l'objectif, la zone touchée et « fini quand ». Assigne-la-moi.
```

**Démarrer une tâche**
```
Prends l'issue #12 : assigne-la-moi, crée la branche <prenom>/12-<sujet> depuis main
à jour, lis les fichiers concernés et propose-moi un plan court avant de coder.
```

**Finir une tâche**
```
On a fini l'issue #12. Lance uv run pre-commit run --all-files et corrige ce qui casse,
mets à jour mon bloc de STATUS.md, commit, push, puis ouvre la PR avec « Closes #12 »
en remplissant le modèle de PR.
```

**Traiter les retours**
```
Lis la CI (gh pr checks) et les commentaires de relecture de la PR #15.
Corrige ce qui est justifié, et dis-moi ce que tu ignores et pourquoi.
```

**Merger**
```
Si la CI de la PR #15 est verte, merge-la en squash, supprime la branche,
puis reviens sur main à jour.
```

**Changer le contrat d'API** (ajouter une route ou un champ)
```
J'ai besoin de <nouvelle route ou nouveau champ>. Suis à la lettre la procédure
« Contrat d'API » d'AGENTS.md (schemas.py, export, gen:api, commit ensemble)
et annonce-le dans STATUS.md.
```

**Avant de couper** (fin de session, pause, relais)
```
Mets à jour mon bloc de STATUS.md avec où j'en suis, ce qui reste et les pièges
rencontrés, pour que la prochaine session (ou un coéquipier) reprenne sans contexte.
```

## 4. Ce qui est automatique

| Quand | Quoi |
|---|---|
| Chaque commit | Hook pre-commit : format (ruff, prettier), lint (ruff, oxlint), types (tsc), tests du contrat API et ML, refus des fichiers de plus de 5 Mo |
| Chaque PR et chaque push sur `main` | CI GitHub : les mêmes vérifications, sur une machine propre |
| Ouverture d'une PR | Relecture par Claude (commentaires dans le code) et par Gemini (un commentaire de synthèse) |
| `@claude …` dans un commentaire | Claude répond ou corrige sur la PR |

Une relecture en rouge = souci de quota ou de clé, pas de code. **Seule la CI bloque un merge.**

## 5. Quand ça coince

| Symptôme | Quoi faire |
|---|---|
| Le commit est refusé, « files were modified by this hook » | Les hooks ont corrigé des fichiers : `git add` puis recommit. Jamais `--no-verify`. |
| `test_openapi_matches_committed_contract` échoue | Quelqu'un a changé `backend/schemas.py`. Si c'est voulu : `uv run python -m backend.export_openapi`, puis `npm --prefix frontend run gen:api`, puis commit et annonce. Sinon, annule le changement. |
| Conflit git sur `contract/openapi.json` ou `schema.d.ts` | Ne pas fusionner à la main : résoudre `backend/schemas.py`, puis régénérer avec les deux commandes ci-dessus. |
| CI : « Missing: … from lock file » | Ton npm est trop vieux : `npm install -g npm@latest`, puis `npm --prefix frontend install` et commit du lockfile. |
| L'agent ignore les règles d'AGENTS.md | Claude : `claude update` puis nouvelle session. Gemini : vérifier qu'il fait confiance au dossier. |
| Context7 répond 429 | Quota atteint (on l'utilise sans clé) : le signaler dans STATUS.md. |
| Deux personnes sur les mêmes fichiers | Celui qui n'a pas l'issue assignée attend ou se coordonne. Dans le doute, on se parle. |

## 6. Rituels d'équipe

- **Point de 5 minutes toutes les 2 à 3 heures** : ce que j'ai mergé, ce que je prends, ce qui me bloque.
- **`main` est toujours démontrable** : à tout moment, on doit pouvoir lancer la démo depuis `main`.
- **Une décision prise = une ligne dans « Décisions » d'AGENTS.md**, dans la PR qui l'applique.
