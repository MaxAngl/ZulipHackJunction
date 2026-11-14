# Hypothèses prises pendant la nuit du 13 au 14 novembre

Ce que Claude a décidé seul pour faire tourner la boucle, sans validation de l'équipe.
Chaque ligne dit où le changer. Ce qui avait été validé en discussion n'est pas repris ici.

> **Mise à jour du 14 novembre, après-midi.** Le modèle que l'équipe a arrêté (données brutes θ, vecteur d'état L(θ), zone sur six axes, trois réseaux) est codé, entraîné et branché dans l'app : voir [docs/modele.md](docs/modele.md), dont la section 8 dit ce qui reste simulé. Dans ce fichier, tout ce qui parle de la règle `zone_for`, de `learn`, du capteur `backend/sensor.py` ou d'un état θ à un seul nombre décrit **l'ancienne version** : ces morceaux ne servent plus à l'app. Le reste (produit, génération des demandes, vraie app) est toujours vrai.
>
> Hypothèses nouvelles, prises par Claude en branchant les réseaux :
>
> - **La position d'un format sur les axes** (concret, durée, échange, exposition, démarrage) est posée à la main, format par format, dans `ml/formats.py`. Aucun modèle ne note encore une vraie demande axe par axe.
> - **Le patient virtuel** (`ml/virtual.py`) tient lieu de montre : même simulateur que les données d'entraînement, une graine par patient. Dans la console, le curseur règle son niveau caché.
> - **La frappe relevée par l'app** remplace les signaux simulés correspondants dans le relevé du lendemain. Le délai d'ouverture n'est pas encore mesuré par les écrans.
> - **Rien du corps virtuel n'est enregistré** : au redémarrage, il se reconstruit en rejouant les demandes traitées. Un niveau poussé par `/api/app/patient/state` est donc perdu au redémarrage.

## À faire en premier

1. **Mettre une clé Gemini** dans `.env` à la racine (`GEMINI_API_KEY=...`), puis lancer `uv run python -m ml.check_gemini`. **La connexion à Gemini n'a jamais été testée en réel** : il n'y avait pas de clé sur la machine. Sans clé, l'app tourne avec une banque de secours.
2. Lancer : `uv run uvicorn backend.main:app --port 8000` et `npm --prefix frontend run dev`, puis ouvrir http://localhost:5173. L'accueil mène à la **vraie app** (`#/helper`, `#/patient`) ; la **console de démo** est sur `#/demo`.
3. Trancher les trois premières lignes du tableau « Produit ».
4. **Ne pas y mettre de vrais patients en l'état** : la vraie app n'a ni mot de passe, ni chiffrement, ni recueil de consentement (voir « La vraie app »).

## Produit et démo

| Décision | Où |
|---|---|
| Nom provisoire : **Needed** | `frontend/index.html`, `frontend/src/App.tsx`, `backend/main.py` |
| **Interface en anglais**, pour un jury international. Cela déroge à la convention « messages en français » | Textes dans `frontend/src/components/` |
| Logo : poignée de main au trait, une main encre, une main cyan. Le tracé vient de l'icône « handshake » de Lucide (licence ISC), il n'est pas original | `frontend/src/components/Logo.tsx`, `frontend/public/favicon.svg` |
| Charte minimaliste : noir sur blanc, traits fins, sans ombres, un seul accent cyan vif `#00D8FF` (`#00E0FF` en mode sombre), police système sans empattement | `frontend/src/index.css` |
| Personas : Aino, patiente (gardening, jazz, baking) ; Mikko (cooking, cycling), Sara (photography, hiking) et Leo (woodworking, board games), aidants | `backend/loop.py` |
| Un écran à trois panneaux : aidant, console, patient. `?view=helper` et `?view=patient` affichent un seul téléphone, pour une démo sur deux appareils | `frontend/src/App.tsx` |
| Un seul patient, état en mémoire, ni comptes ni base de données | `backend/loop.py` |

## Zone et mesure

| Décision | Où |
|---|---|
| Règle de départ : centre = 1 − 0,6·θ, plafond d'effort = 0,25 + 0,75·θ | `ml/model.py` |
| Largeur de la zone : ±0,18 au départ, divisée par √(1 + n/2) après n réponses, jamais sous ±0,07 | `ml/model.py` |
| Grille des formats et de leur effort : opinion 0,15 · memory 0,25 · explain 0,40 · review 0,50 · make 0,70 · call 0,85 | `ml/formats.py` |
| **Mesure λ modifiée** : λ = 0,5 + (a·p − a·h) / (2·(1 − p·h)), c'est-à-dire la projection du message sur l'axe aidant → patient. La formule validée, a·p / (a·p + a·h), donne presque toujours 0,5 avec de vrais embeddings, parce que deux textes se ressemblent toujours un peu | `ml/pipeline.py`, `lambda_position` |
| **Avec Gemini, l'échelle est recalée sur chaque lot** : une droite relie les positions mesurées aux positions annoncées par le générateur. Chaque demande garde sa propre mesure | `ml/pipeline.py`, `_calibrate` |
| Un message sans lien avec aucun des deux centres d'intérêt reçoit λ = 0, donc il est retenu. **Ce test ne marche que hors ligne** : avec Gemini, le seuil est à 0 et reste à calibrer | `ml/pipeline.py`, `MIN_RELEVANCE` |
| Effort d'un message écrit par l'aidant : format reconnu par Gemini, sinon par mots-clés | `ml/pipeline.py`, `ml/formats.py` |
| Un message jugé dangereux (argent, données personnelles, avis médical) est **refusé** à l'aidant. C'est la seule exception à « retardé, pas refusé » | `ml/pipeline.py` |

## Boucle

| Décision | Où |
|---|---|
| Étape 3 : l'aidant et les paires de centres d'intérêt **tournent** à chaque manche, rien n'est appris. Deux paires par manche | `backend/loop.py` |
| Les trois propositions : la plus proche du centre, la meilleure d'une autre paire, puis un format pas encore essayé (sinon le bord de la zone) | `ml/pipeline.py` |
| Moins de trois demandes dans la zone : une seconde génération, puis on en propose moins. On ne complète jamais avec une demande hors zone | `backend/loop.py` |
| Bouger θ refiltre les demandes déjà mesurées, sans regénérer | `backend/loop.py` |
| Un message retenu part dès que la zone le contient. Il n'expire jamais | `backend/loop.py` |
| « Pas maintenant » côté aidant : rien n'est enregistré | `backend/loop.py` |
| Le patient a deux boutons : aider, ou pas maintenant | `frontend/src/components/PatientPhone.tsx` |

## La vraie app (ajoutée le 14 novembre au matin)

De vraies personnes, sur leur téléphone, avec une base de données. La même boucle tourne derrière.

| Décision | Où |
|---|---|
| Deux rôles : « Join the community » (l'aidant) et « My clinic invited me » (le patient). Inscription avec un prénom et des centres d'intérêt, rien d'autre | `frontend/src/screens/` |
| **Pas de mot de passe** : un jeton par appareil, gardé dans le navigateur. Suffisant pour une démo, pas pour de vraies données de santé | `backend/community.py`, `frontend/src/session.ts` |
| Base **SQLite** dans `data/needed.db` (ignoré par git), sans dépendance ajoutée. Le journal des demandes garde l'état avant et après, la position, l'effort et la récompense : c'est le futur jeu d'entraînement | `backend/store.py` |
| **L'état θ n'est plus simulé ici** : il est estimé d'après le comportement. Réponse = score 0,6, +0,2 si elle arrive en moins d'une heure, +0,2 si elle fait au moins 80 caractères ; « pas maintenant » = 0,3. θ fait 30 % du chemin vers ce score. Règle non validée | `backend/community.py` |
| θ de départ = 0,6 à l'inscription, faute de mesure faite à la clinique. θ attendu = θ avant (pas de dérive modélisée) | `backend/community.py` |
| Un capteur externe peut pousser θ : `POST /api/app/patient/state` | `backend/main.py` |
| **Un patient n'a jamais plus d'une demande à la fois.** Les suivantes attendent leur tour, et l'aidant ne voit aucune différence | `backend/community.py` |
| Choix du patient pour un aidant : celui qui est libre et sollicité depuis le plus longtemps. Rien n'est appris | `backend/community.py`, `_pick_patient` |
| L'aidant voit le prénom du patient, jamais son état, sa zone ni la difficulté d'une demande | `backend/schemas.py`, `AppProposal` |
| Le patient répond par écrit. L'aidant peut dire ce qu'il a fait de la réponse : c'est la preuve d'utilité, affichée chez le patient | `frontend/src/screens/PatientScreen.tsx` |
| Pas de notifications : chaque écran se rafraîchit toutes les 4 secondes | `frontend/src/screens/useHome.ts` |
| `learn` reste la règle simulée, réglée pour le capteur de la démo : avec l'estimation par comportement, ses seuils sont à revoir | `ml/model.py` |

## Ce qui est faux ou simulé

| Quoi | Comment |
|---|---|
| **Modèle de zone** (`ml/model.py`, `learn`) | Règle écrite à la main, aucun entraînement. Signal = (récompense − 0,04) / 0,03, borné à ±1. Le centre se décale de 0,6 × signal × (λ envoyé − centre), dans la limite de ±0,3. Il n'y a pas de modèle commun appris |
| **Capteur θ** (`backend/sensor.py`) | Un curseur, plus une simulation sans hasard. θ attendu = retour de 10 % vers 0,55. Demande rendue : +0,01 à +0,07 selon la distance à un point idéal caché (règle commune − 0,12). Demande ignorée : −0,04. Mesure immédiate, sans fenêtre |
| **Générateur de secours** (`ml/lexicon.py`) | Phrases composées à partir d'une banque, mesurées par mots-clés. Il sert sans clé Gemini, ou si Gemini échoue |

## Challenge technique : Best Use of Gemini API

- **Pourquoi lui** : vous vouliez déjà « un modèle type Gemini », et Gemini est au cœur de la boucle à trois endroits. Il écrit les demandes pour la zone, ses embeddings mesurent où chacune tombe, et il relit les messages écrits par l'aidant. L'argument à présenter : Gemini propose, une mesure indépendante dispose.
- **Écartés** : Gemma, ElevenLabs et Nemotron demandaient un second branchement ; les autres sont de l'infrastructure.
- **Appels REST directs**, sans SDK : aucune dépendance ajoutée (`ml/gemini.py`).
- **Modèles par défaut** : `gemini-flash-latest` et `gemini-embedding-001`, modifiables avec `GEMINI_MODEL` et `GEMINI_EMBED_MODEL` dans `.env`.
- Les noms de champs viennent de la documentation lue cette nuit. En cas de refus de l'API, le client réessaie avec une requête plus simple, puis bascule sur la banque de secours.
- Le chemin Gemini est couvert par des tests avec une **fausse API** (`ml/tests/test_gemini_path.py`). Ils vérifient notre code, pas le comportement de la vraie API.

## Repo

- Branche `max/1-boucle-ia` et bloc « Max » dans `STATUS.md` : prénom déduit du pseudo GitHub.
- `ONBOARDING.md`, resté indexé en local, est commité dans la même PR.
- Les contrats d'API et ML ont changé : `/api/predict` et `ml.model.predict` n'existent plus.

## Points ouverts repérés

- **Un vrai besoin sans lien avec les intérêts du patient n'est jamais transmis** : le centre de la zone ne descend pas sous 0,4. Il faut soit une zone qui descend plus bas quand le patient va bien, soit une règle à part pour les vrais besoins.
- Hors ligne, à θ très bas, la zone ne contient parfois que deux demandes.
- Le choix de l'aidant parmi les trois n'est pas enregistré.
- Non construits : la vue clinicien, l'alerte de dérive, les notifications, la modération humaine.
- Avant tout usage réel : comptes protégés, consentement, hébergement et chiffrement adaptés à des données de santé.
- La page des challenges affichait un compte à rebours qui tombe vers 11 h le 14 novembre : à vérifier.
