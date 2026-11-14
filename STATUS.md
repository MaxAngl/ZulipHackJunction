# STATUS

**Qui fait quoi : ce sont les issues GitHub** (s'assigner = réserver, PR mergée = fait).
Ce fichier sert à ce que les issues ne disent pas : les annonces, les blocages et les notes de passation d'une session d'agent à la suivante.

Chacun n'édite que **son bloc** (ça évite les conflits git), et le met à jour dans la PR de sa tâche. Une ligne par point, court. Format : `- [JJ/MM HH:MM] texte`.

## À lire par tous

Changements qui touchent les autres (contrat, dépendance, convention, fichier sensible). Ajouter en bas.

- [13/11 12:50] Repo initialisé : squelette `frontend/`, `backend/`, `ml/`, contrat d'API, pre-commit. Compléter l'équipe (prénoms + agent) dans `AGENTS.md`.
- [13/11 14:00] Tâches dans les issues GitHub, tout passe par des PR, CI sur chaque PR. Installer `gh` et faire `gh auth login`.
- [14/11 06:00] **Contrat d'API changé** (issue #1) : `/api/predict` est supprimé, la boucle est sous `/api/loop/*`. `contract/openapi.json` et `schema.d.ts` sont régénérés.
- [14/11 06:00] **Contrat ML changé** (issue #1) : `ml.model.predict` est supprimé. Le backend importe la zone et la chaîne de demandes depuis `ml.model` (voir `__all__`).
- [14/11 06:00] Nouvelle variable `GEMINI_API_KEY` dans `.env` (modèle dans `.env.example`). Sans elle, l'app tourne hors ligne. Aucune dépendance ajoutée.
- [14/11 06:00] Lire `HYPOTHESES.md` : tout ce qui a été décidé sans validation de l'équipe, et ce qui est simulé.
- [14/11 06:00] Interface et messages d'erreur en anglais (voir « Décisions » d'`AGENTS.md`).
- [14/11 07:00] **Contrat d'API étendu** (issue #3) : nouvelles routes `/api/app/*` pour la vraie app (inscription, aidant, patient). L'en-tête `X-Needed-Token` identifie l'appareil. Rien n'est retiré.
- [14/11 09:00] Relectures automatiques des PR retirées (issue #7) : faire relire sa PR par l'agent d'un coéquipier, prompt dans `ONBOARDING.md`. Ignorer les anciens jobs Claude ou Gemini rouges.
- [14/11 07:00] La console de démo est maintenant sur `#/demo`. L'accueil `#/` mène à la vraie app. Base locale dans `data/` (ignorée par git), aucune dépendance ajoutée.
- [14/11 12:30] **Modèle cible fixé dans `docs/modele.md`** (issue #12) : objets, axes d'une demande, trois réseaux, entraînement, évaluation. `AGENTS.md` est modifié : un lien et cinq décisions. Aucun code ni contrat touché. À lire avant tout travail dans `ml/`.
- [14/11 13:30] **Nouvelle dépendance `numpy`** (issue #15) : relancer `uv sync` après le prochain `git pull`. Nouveau paquet `ml/simulation` qui génère les données d'entraînement. `pyproject.toml`, `uv.lock` et `AGENTS.md` sont modifiés. Aucun contrat touché, rien n'est branché sur l'app.
- [14/11 12:51] `.pre-commit-config.yaml` : les hooks de `pre-commit-hooks` passent par `python -m` (Smart App Control de Windows 11 bloquait leurs .exe, WinError 4551). Mêmes vérifications, aucune dépendance ajoutée.
- [14/11 13:46] **Contrat ML étendu** (issue #19) : `ml.model` exporte `InterestProfile`, `build_profile` et `stable_match` (`ml/matching.py`). Dans la vraie app, l'aidant reçoit le patient qui lui est apparié par centres d'intérêt et temps d'attente. Nouvelle table SQLite `profiles`, créée toute seule. Rien n'est retiré, contrat d'API inchangé, aucune dépendance ajoutée.

## Max (Claude Code)

- **En cours :** #15, les données simulées (PR ouverte, à faire relire).
- **Bloqué :** pas de clé Gemini sur la machine, donc la connexion à Gemini n'est pas testée en réel. Mettre la clé dans `.env`, puis `uv run python -m ml.check_gemini`.
- **Notes pour la suite :**
  - Données simulées : `uv run python -m ml.simulation` écrit `ml/data/sim` (hors git). Le sens de chaque colonne est dans `meta.json`, les règles dans `docs/modele.md`, section 12.
  - Prochaine étape : l'autoencodeur (section 6, étape 1). Il lit `people.npz` : `theta` et `mask` en entrée, `state` comme cible de la tête supervisée. Il demandera une nouvelle dépendance pour les réseaux, à annoncer.
  - Les choix de θ, de L et de la récompense sont délégués à Claude et attendent une relecture de l'équipe (section 11).
  - Changement décidé le 14/11 : la partie personnelle est un vecteur de 8 nombres par patient, lu par A et par B, et non plus une dernière couche par patient. B ne reçoit pas le texte des centres d'intérêt. Tailles et quantité de données : section 13.
  - Pour entraîner, générer plus gros que le réglage par défaut : `uv run python -m ml.simulation --people 5000 --days 84`, puis séparer par personne.
  - La récompense simulée est bruitée (écart-type 14,8 pour des écarts de quelques points) : c'est voulu, l'état bouge tout seul d'un jour à l'autre. Le journal contient aussi `reward_counterfactual`, plus net, pour comparer.
  - Le modèle cible n'est pas codé. Le code actuel est décrit par `HYPOTHESES.md` ; les écarts sont en section 8 de `docs/modele.md`. Le coder changera les deux contrats (API et ML).
  - #13 reste ouverte : `docs/modele.md` en couvre l'essentiel, sauf les définitions encore ouvertes de la section 10.
  - Le modèle de zone (`ml/model.py`) et le capteur θ (`backend/sensor.py`) sont simulés. Garder leurs signatures en les remplaçant.
  - Si Gemini donne des λ tassés ou incohérents, regarder `lambda_position` dans `ml/pipeline.py` et les trois phrases de référence de `ml/check_gemini.py`.
  - Démo sur deux téléphones : `?view=helper` et `?view=patient`, avec `npm --prefix frontend run dev -- --host`.
  - La console de démo garde son état en mémoire : un redémarrage la remet à zéro. La vraie app, elle, garde tout dans `data/needed.db` ; supprimer ce fichier repart de zéro.
  - Vraie app sur deux téléphones : `npm --prefix frontend run dev -- --host`, puis `#/helper` sur l'un et `#/patient` sur l'autre. Sur une seule machine, les deux comptes cohabitent dans le même navigateur.
  - La vraie app n'a ni mot de passe ni chiffrement : pas de vrais patients en l'état.

## Adel (Claude Code)

- **En cours :** #19, l'appariement patient–aidant par centres d'intérêt (PR ouverte). #5 et #23 sont mergées.
- **Bloqué :** —
- **Notes pour la suite :**
  - Le commentaire libre de l'inscription n'est pas encore dans l'API. Quand il arrive, le passer à `build_profile(tags, comment)` : chaque phrase devient un élément d'intérêt, comparé à tous ceux de l'autre personne.
  - Le bonus d'attente (`WAIT_WEIGHT`, `WAIT_FULL_DAYS` dans `ml/matching.py`) est un premier réglage, à ajuster avec l'équipe.
  - Le repli hors ligne (trigrammes de lettres) ne comprend pas le sens : « ski » et « montagne » n'y sont pas proches. Il ne sert qu'à ne jamais casser sans clé Gemini.
  - Un profil enregistré n'est pas recalculé si les intérêts changent : supprimer sa ligne dans la table `profiles` pour le recalculer.

## Rami (Antigravity)

- **En cours :** #31 (évolutions et finitions UI/UX de la page aidant) et #33 (branchage et validation de l'API Gemini).
- **Bloqué :** —
- **Notes pour la suite :**
  - #11 est mergée dans main.
  - Page aidant : sélection de profil interactive, affichage des hobbies, propositions IA dédiées, bouton « Send mine » centré et suppression de « Not now ».
  - L'inscription applique les contraintes de Max (max 40 car., max 8 intérêts).
  - #33 validée avec `check_gemini` : embeddings (gemini-embedding-001, dim 768), calcul de l'axe λ et génération de demandes JSON (gemini-flash-lite-latest) opérationnels de bout en bout avec mécanismes de repli automatique.
