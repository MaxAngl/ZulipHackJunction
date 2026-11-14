# Mode d'emploi de l'équipe

Tu pilotes, ton agent tape. GitHub dit qui fait quoi, la CI dit si c'est bon.
Ce guide te dit, pour chaque moment de la journée, **ce que tu fais toi-même** et **la phrase exacte à donner à ton agent**. Les règles détaillées, que ton agent lit tout seul, sont dans [AGENTS.md](AGENTS.md).

Dans ce guide, chaque étape indique qui agit :

- **Toi** : tu décides et tu vérifies.
- **Ton agent** : il tape les commandes et le code.
- **Automatique** : les hooks et la CI, sans que tu aies rien à faire.

## Les 4 règles

1. **Pas d'issue assignée, pas de code.** S'assigner une issue GitHub, c'est réserver la tâche. Une issue prise par quelqu'un d'autre ne se touche pas.
2. **Jamais de push sur `main`.** Tout passe par une pull request. `main` doit toujours pouvoir servir pour la démo.
3. **Le contrat d'API ne change pas en silence.** On régénère les fichiers générés, on commite tout ensemble et on prévient l'équipe.
4. **Une décision = une ligne dans `AGENTS.md`.** C'est la mémoire de tous les agents. Un fichier périmé, ce sont des agents qui codent sur des hypothèses différentes.

## 1. Avant de commencer, une seule fois (environ 15 min)

- [ ] **Accepter l'invitation GitHub** au repo, par mail ou sur github.com/notifications.
- [ ] **Installer les outils** (tableau ci-dessous). Après une installation sous Windows, ouvre un nouveau terminal pour que la commande soit trouvée.
- [ ] **Connecter GitHub** avec `gh auth login` : GitHub.com, HTTPS, **Y** à « Authenticate Git », puis connexion par le navigateur.
- [ ] **Ouvrir ton agent** dans un dossier **hors OneDrive, iCloud ou Dropbox** (par exemple `C:\dev` ou `~/dev`), et lui coller le prompt d'installation ci-dessous.
- [ ] *(Facultatif)* Copier `.env.example` en `.env` et y mettre une clé `GEMINI_API_KEY`. Sans clé, l'app tourne en mode simulé.
- [ ] **Relancer ton agent depuis la racine du repo**, puis accepter la confiance dans le dossier, et le serveur `context7` pour Claude.

| Outil | Windows | macOS | Vérifier |
|---|---|---|---|
| git | `winget install --id Git.Git` | `brew install git` | `git --version` |
| uv (Python) | `winget install --id astral-sh.uv` | `brew install uv` | `uv --version` |
| Node.js 22+ | `winget install --id OpenJS.NodeJS.LTS` | `brew install node` | `node --version` |
| npm 11.19+ | `npm install -g npm@latest` | idem | `npm --version` |
| GitHub CLI | `winget install --id GitHub.cli` | `brew install gh` | `gh --version` |
| Claude Code | `claude update` (v2.1.277 ou plus) | idem | `claude --version` |
| Gemini CLI | `npm install -g @google/gemini-cli@latest` | idem | `gemini --version` |

**Prompt d'installation**, à coller dans ton agent :

```text
Tu vas installer pour moi le repo de notre hackathon, puis m'expliquer comment on travaille.

1. Vérifie les prérequis, sans rien installer sans mon accord : git, uv, Node.js 22+, npm 11.19+,
   et GitHub CLI connecté (gh auth status). S'il manque quelque chose, donne-moi la commande pour
   mon système et attends que je confirme. C'est moi qui fais gh auth login.
2. Choisis avec moi un dossier hors OneDrive, iCloud ou Dropbox, et clone dedans
   https://github.com/MaxAngl/ZulipHackJunction.git
3. Dans le repo, lance : uv sync, puis npm --prefix frontend ci, puis uv run pre-commit install.
4. Lance uv run pre-commit run --all-files : tout doit être « Passed ».
   Sinon, explique-moi pourquoi avant de corriger quoi que ce soit.
5. Lis en entier AGENTS.md, ONBOARDING.md et STATUS.md, puis résume-moi en 10 lignes maximum
   la boucle issue → branche → PR → merge, les règles d'or et ce qui est interdit.
6. Montre-moi les issues libres (gh issue list --search "no:assignee") et les PR ouvertes.
7. Dis-moi de te relancer depuis la racine du repo, pour que tu charges AGENTS.md automatiquement.

Ne modifie aucun fichier du repo et ne fais aucun commit pendant cette installation.
```

**Vérifier que ton agent a bien chargé le repo :**

- **Claude Code** : `/memory` doit lister AGENTS.md, et `/mcp` doit montrer `context7` connecté.
- **Gemini CLI** : `/memory show` et `/mcp`. S'il ignore AGENTS.md, il ne fait pas confiance au dossier.
- Ne crée **jamais** de `CLAUDE.md` ni de `GEMINI.md` : ils remplaceraient AGENTS.md.

## 2. Une tâche, du début à la fin

```
issue  →  branche  →  code  →  test  →  PR  →  relecture  →  merge
```

La même boucle pour chaque tâche. Vise une PR mergée toutes les 2 à 3 heures : plus une branche vit longtemps, plus les conflits font mal.

### Étape 1 · Se mettre à jour — *Ton agent*

À chaque début de session, pour partir de la dernière version et voir ce que font les autres.

```text
Mets-toi à jour : passe sur main et fais git pull, lis STATUS.md, puis montre-moi
mes issues assignées, les issues libres et les PR ouvertes.
```

### Étape 2 · Prendre une tâche — *Toi, puis ton agent*

Tu choisis quoi faire. Vérifie que personne n'a déjà l'issue : si c'est le cas, parlez-vous d'abord.

Pour une nouvelle tâche :

```text
Crée une issue avec le modèle « Tâche » pour : <ce que tu veux faire>.
Remplis l'objectif, la zone touchée et « fini quand », puis assigne-la-moi.
```

Pour démarrer :

```text
Prends l'issue #12 : assigne-la-moi, crée la branche <prénom>/12-<sujet> depuis main à jour,
lis les fichiers concernés et propose-moi un plan court avant de coder.
```

### Étape 3 · Valider le plan — *Toi*

Lis le plan de ton agent : 30 secondes qui évitent une heure dans la mauvaise direction. Vérifie qu'il reste dans la zone de l'issue et qu'il signale tout changement du contrat d'API. Puis : « OK, vas-y », ou « Non, plutôt comme ça… ».

### Étape 4 · Coder — *Ton agent, plus l'automatique*

Ton agent code et fait de petits commits. À chaque commit, les hooks mettent en forme le code, vérifient les types et lancent les tests. S'ils corrigent un fichier, ton agent le ré-ajoute et recommite.

### Étape 5 · Tester toi-même — *Toi*

Ton agent ne voit pas l'écran de la démo. Lance l'app et clique sur ce que tu viens de faire. La vraie app est sur `#/`, la console de démo sur `#/demo`.

```text
Lance le backend et le front pour que je teste, et donne-moi l'adresse à ouvrir.
```

### Étape 6 · Ouvrir la PR — *Ton agent, plus l'automatique*

Ton agent fait une dernière vérification, met à jour ton bloc de `STATUS.md` et ouvre la PR. La CI se lance toute seule sur GitHub.

```text
On a fini l'issue #12. Récupère les derniers changements de main (git pull --rebase origin main),
lance uv run pre-commit run --all-files et corrige ce qui casse, mets à jour mon bloc de STATUS.md,
commit, push, puis ouvre la PR avec « Closes #12 » en remplissant le modèle de PR.
```

### Étape 7 · Faire relire — *Toi, et l'agent d'un coéquipier*

Il n'y a pas de relecture automatique. Demande à un coéquipier de faire relire ta PR par son agent. C'est encore mieux s'il utilise l'autre modèle (Claude ↔ Gemini), car ils ne ratent pas les mêmes choses.

Le coéquipier dit à son agent :

```text
Relis la PR #15 comme un relecteur exigeant : lis le diff (gh pr diff 15) et AGENTS.md,
puis liste seulement les vrais problèmes (bugs, contrat d'API, règles d'AGENTS.md),
avec fichier et ligne. Ne modifie rien, et poste ta relecture en commentaire (gh pr comment 15).
```

Puis l'auteur dit à son agent :

```text
Lis la CI (gh pr checks) et les commentaires de la PR #15.
Corrige ce qui est justifié, et dis-moi ce que tu ignores et pourquoi.
```

### Étape 8 · Merger — *Toi, puis ton agent*

Tu décides quand merger : la CI est verte, la relecture est traitée, et tu as testé. Le merge ferme l'issue tout seul.

```text
Si la CI de la PR #15 est verte, merge-la en squash, supprime la branche,
puis reviens sur main à jour.
```

### Étape 9 · Prévenir si ça touche les autres — *Toi*

Nouvelle route d'API, champ renommé, nouvelle dépendance : dis-le à voix haute à l'équipe, en plus de la ligne dans « À lire par tous » de `STATUS.md`. Puis on recommence à l'étape 1.

## 3. Deux situations à connaître

**Changer le contrat d'API.** Ajouter une route ou un champ, en renommer un : le front et le back doivent rester d'accord.

```text
J'ai besoin de <nouvelle route ou nouveau champ>. Suis à la lettre la procédure
« Contrat d'API » d'AGENTS.md (schemas.py, export, gen:api, les trois fichiers commités ensemble)
et annonce-le dans STATUS.md.
```

**Avant de couper.** Pause, fin de journée, ou tâche passée à quelqu'un d'autre : la prochaine session doit reprendre sans contexte.

```text
Mets à jour mon bloc de STATUS.md avec où j'en suis, ce qui reste et les pièges rencontrés,
pour que la prochaine session ou un coéquipier reprenne sans contexte.
```

## 4. Ce qui est automatique

| Quand | Quoi |
|---|---|
| Chaque commit | Hook pre-commit : format (ruff, prettier), lint (ruff, oxlint), types (tsc), tests du contrat API et ML, refus des fichiers de plus de 5 Mo |
| Chaque PR et chaque push sur `main` | CI GitHub : les mêmes vérifications, sur une machine propre. **Une PR rouge ne se merge pas.** |

## 5. Quand ça coince

| Ce que tu vois | Quoi faire |
|---|---|
| Commit refusé : « files were modified by this hook » | Les hooks ont corrigé des fichiers. Dis : « Ajoute les fichiers modifiés par les hooks et recommite. » Jamais `--no-verify`. |
| La CI est rouge | « Lis l'erreur de la CI de la PR #15 (gh run view --log-failed) et corrige-la. » |
| Le test de contrat échoue | Quelqu'un a changé l'API sans régénérer les fichiers. « Le test de contrat casse : explique-moi pourquoi avant de régénérer quoi que ce soit. » |
| Conflit sur `contract/openapi.json` ou `schema.d.ts` | Ne pas fusionner à la main. « Résous le conflit dans backend/schemas.py, puis régénère les fichiers du contrat. » |
| CI : « Missing: … from lock file » | Ton npm est trop vieux. Lance `npm install -g npm@latest`, puis demande à ton agent de réinstaller le front et de commiter le lockfile. |
| Un job « Claude Code Review » ou « Gemini Review » est rouge | Il vient d'une branche créée avant le retrait des relectures automatiques. Ignore-le : seule la CI compte. Il disparaît dès que la branche récupère `main` (`gh pr update-branch`). |
| L'agent ignore les règles du repo | Claude : `claude update`, puis nouvelle session. Gemini : vérifier qu'il fait confiance au dossier. |
| Context7 répond 429 | Quota atteint (on l'utilise sans clé) : le signaler dans `STATUS.md`. |
| Quelqu'un travaille sur les mêmes fichiers | Celui qui n'a pas l'issue assignée s'arrête. Parlez-vous. |

## 6. À trois

**Jamais**

- Coder sans issue assignée.
- Pousser directement sur `main`.
- Contourner les hooks avec `--no-verify`.
- Modifier à la main `contract/openapi.json` ou `frontend/src/api/schema.d.ts`.
- Commiter une clé : le `.env` reste sur ta machine.
- Créer un `CLAUDE.md` ou un `GEMINI.md`.
- Mettre le repo dans OneDrive, iCloud ou Dropbox.

**Rituels**

- **Toutes les 2 à 3 heures**, un point de 5 minutes : ce que j'ai mergé, ce que je prends, ce qui me bloque.
- **`main` est toujours démontrable** : on doit pouvoir lancer la démo à tout moment.
- **Une décision prise** = une ligne dans « Décisions » d'`AGENTS.md`, dans la PR qui l'applique.
