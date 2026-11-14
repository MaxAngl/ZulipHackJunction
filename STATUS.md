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
- [14/11 16:30] **Contrat d'API étendu** (issue #29), sans rien retirer : `LoopState` gagne `state` (L(θ), six composantes), `signals` (θ, 25 signaux), `distance` et `level` ; `ZoneState.axes` donne la zone sur six axes ; `CandidateState.axes`, `MessageState.axes` ; `ModelState.kind` vaut `networks`, avec `parameters` et `vector` ; `HistoryEntry.reward` va maintenant **de 0 à 100** (50 = rien n'a changé). `ReplyRequest` et `RespondRequest` acceptent un champ facultatif `typing`. `contract/openapi.json` et `schema.d.ts` sont régénérés.
- [14/11 16:30] **Contrat ML étendu** (issue #29) : `ml.model` exporte `brain`, `Brain`, `Reading`, `Outcome`, `VirtualPatient`, `ZoneBox`, `request_axes`, `AXIS_KEYS`. `zone_for` et `learn` restent mais ne servent plus à l'app. `backend/sensor.py` est supprimé.
- [14/11 16:30] **Pour relever la frappe dans un écran patient** : `useTypingSignals` dans `frontend/src/typing.ts`, à brancher sur la zone de texte (`onInput`), puis passer `collect()` à `replyToRequest`. Exemple dans `components/PatientPhone.tsx`. Les écrans de la vraie app ne sont pas touchés, pour ne pas gêner #11.
- [14/11 16:30] `frontend/vite.config.ts` lit `NEEDED_API_URL` (par défaut `http://localhost:8000`) : utile pour lancer deux copies de l'app côte à côte.
- [14/11 15:30] **Nouvelle dépendance `torch`, en version CPU** (issue #22) : relancer `uv sync` après le prochain `git pull` (120 Mo à télécharger). Les trois réseaux sont dans `ml/nets`, leurs poids dans `ml/weights` (versionnés : pas besoin de réentraîner). `.gitignore`, `pyproject.toml`, `uv.lock` et `AGENTS.md` sont modifiés. Aucun contrat touché : l'app n'utilise pas encore les réseaux.
- [14/11 13:30] **Nouvelle dépendance `numpy`** (issue #15) : relancer `uv sync` après le prochain `git pull`. Nouveau paquet `ml/simulation` qui génère les données d'entraînement. `pyproject.toml`, `uv.lock` et `AGENTS.md` sont modifiés. Aucun contrat touché, rien n'est branché sur l'app.
- [14/11 12:51] `.pre-commit-config.yaml` : les hooks de `pre-commit-hooks` passent par `python -m` (Smart App Control de Windows 11 bloquait leurs .exe, WinError 4551). Mêmes vérifications, aucune dépendance ajoutée.
- [14/11 13:46] **Contrat ML étendu** (issue #19) : `ml.model` exporte `InterestProfile`, `build_profile` et `stable_match` (`ml/matching.py`). Dans la vraie app, l'aidant reçoit le patient qui lui est apparié par centres d'intérêt et temps d'attente. Nouvelle table SQLite `profiles`, créée toute seule. Rien n'est retiré, contrat d'API inchangé, aucune dépendance ajoutée.
- [14/11 14:45] **Nouvelle dépendance `garminconnect`** (issue #24) : relancer `uv sync` après le prochain `git pull`. Nouveau dossier `garmin/` qui pousse θ sur la route existante `POST /api/app/patient/state`. `pyproject.toml` (dépendance, `testpaths`), `.pre-commit-config.yaml` (pytest sur `garmin/`), `uv.lock`, `.env.example` et `AGENTS.md` sont modifiés. Aucun contrat touché.
- [14/11 15:45] **Contrat d'API étendu** (issue #27) : routes `/api/watch/*` (la montre) et `GET/POST/DELETE /api/app/patient/watch` (l'écran patient). Rien n'est retiré. **Contrat ML étendu** : `ml.model` exporte `theta_from_watch`. Nouvelle app Connect IQ dans `watch/`, nouveau bloc « Your watch » dans l'onglet Profil du patient (composant `WatchLink.tsx`). L'estimation de θ passe de `garmin/state.py` à `ml/watch.py`.

## Max (Claude Code)

- **En cours :** #29, les réseaux branchés dans l'app (PR ouverte, à faire relire). Trois PR à merger dans l'ordre : #20 (θ), #22 (réseaux), #29 (branchement) ; chacune part de la précédente.
- [14/11 16:30] L'app tourne sur les réseaux, console et vraie app. Seul le patient reste simulé (`ml/virtual.py`). Ce qui reste à faire pour sortir de la simulation : `docs/modele.md`, section 8.
- [14/11 15:30] Résultat en boucle fermée sur des patients jamais vus : le réseau B fait nettement mieux que la règle fixe. Chiffres et limites : `docs/modele.md`, section 14. Tout est simulé.
- [14/11 15:30] Pour réentraîner : `uv run python -m ml.simulation --people 5000 --days 84 --out ml/data/sim_big`, puis `uv run python -m ml.nets.train` et `uv run python -m ml.nets.evaluate`. Une dizaine de minutes sur CPU.
- **Bloqué :** —
- [14/11 17:00] Gemini testé en réel dans la console, avec la zone du réseau B (#36) : trois propositions à plusieurs états du patient, message libre retenu, demande d'argent refusée. Le modèle léger par défaut et le repli vers un autre modèle viennent de #33 (Rami) ; #36 ajoute les formats permis dans le prompt et une nouvelle tentative sur les embeddings. La clé va dans `.env` (jamais dans git) ; la demander à Max. Vérifier chez soi : `uv run python -m ml.check_gemini`.
- **Notes pour la suite :**
  - Données simulées : `uv run python -m ml.simulation` écrit `ml/data/sim` (hors git). Le sens de chaque colonne est dans `meta.json`, les règles dans `docs/modele.md`, section 12.
  - Les choix de θ, de L et de la récompense sont délégués à Claude et attendent une relecture de l'équipe (section 11).
  - Changement décidé le 14/11 : la partie personnelle est un vecteur de 8 nombres par patient, lu par A et par B, et non plus une dernière couche par patient. B ne reçoit pas le texte des centres d'intérêt. Tailles et quantité de données : section 13.
  - Pour entraîner, générer plus gros que le réglage par défaut : `uv run python -m ml.simulation --people 5000 --days 84`, puis séparer par personne.
  - La récompense simulée est bruitée (écart-type 14,8 pour des écarts de quelques points) : c'est voulu, l'état bouge tout seul d'un jour à l'autre. Le journal contient aussi `reward_counterfactual`, plus net, pour comparer.
  - #13 reste ouverte : `docs/modele.md` en couvre l'essentiel, sauf les définitions encore ouvertes de la section 10.
  - Montre (#24) : `uv run python -m garmin login` une fois, puis `uv run python -m garmin read --push`. Champs Garmin vérifiés sur une vraie réponse le 14/11 ; SpO2 absente si la mesure est coupée sur la montre. Quand l'autoencodeur existera, remplacer `ml/watch.py` par L(θ).
  - App montre (#27) : voir `watch/README.md`. Testée le 14/11 dans le simulateur et sur une vraie Forerunner 965, installée en beta depuis le compte Garmin de Max. HTTPS obligatoire, même dans le simulateur : tunnel `cloudflared` en dev. La clé qui signe la beta est sur le PC de Max, hors du repo (`C:\dev\garmin-keys`) : la garder, les mises à jour de la beta doivent être signées avec elle.
  - Dans la refonte, la messagerie du patient (`ChatView`) ne lit pas les demandes du backend : une demande d'aidant arrive sur la montre mais pas dans la messagerie web. À brancher pour la démo « dans les deux sens ».
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
