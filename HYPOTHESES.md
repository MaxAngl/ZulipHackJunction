# Hypothèses prises pendant la nuit du 13 au 14 novembre

Ce que Claude a décidé seul pour faire tourner la boucle, sans validation de l'équipe.
Chaque ligne dit où le changer. Ce qui avait été validé en discussion n'est pas repris ici.

## À faire en premier

1. **Mettre une clé Gemini** dans `.env` à la racine (`GEMINI_API_KEY=...`), puis lancer `uv run python -m ml.check_gemini`. **La connexion à Gemini n'a jamais été testée en réel** : il n'y avait pas de clé sur la machine. Sans clé, l'app tourne avec une banque de secours.
2. Lancer la démo : `uv run uvicorn backend.main:app --port 8000` et `npm --prefix frontend run dev`, puis ouvrir http://localhost:5173.
3. Trancher les trois premières lignes du tableau « Produit ».

## Produit et démo

| Décision | Où |
|---|---|
| Nom provisoire : **Needed** | `frontend/index.html`, `frontend/src/App.tsx`, `backend/main.py` |
| **Interface en anglais**, pour un jury international. Cela déroge à la convention « messages en français » | Textes dans `frontend/src/components/` |
| Logo : poignée de main au trait, une main encre, une main cyan. Le tracé vient de l'icône « handshake » de Lucide (licence ISC), il n'est pas original | `frontend/src/components/Logo.tsx`, `frontend/public/favicon.svg` |
| Charte : cyan `#0891B2` (clair) et `#22D3EE` (sombre), gris froids, police système sans empattement | `frontend/src/index.css` |
| Personas : Aino, patiente (gardening, jazz, baking) ; Mikko (cooking, cycling), Sara (photography, hiking) et Leo (woodworking, board games), aidants | `backend/loop.py` |
| Un écran à trois panneaux : aidant, console, patient. `?view=helper` et `?view=patient` affichent un seul téléphone, pour une démo sur deux appareils | `frontend/src/App.tsx` |
| Un seul patient, état en mémoire, ni comptes ni base de données | `backend/loop.py` |

## Zone et mesure

| Décision | Où |
|---|---|
| Règle de départ : centre = 1 − 0,6·θ, plafond d'effort = 0,25 + 0,75·θ | `ml/model.py` |
| Largeur de la zone : ±0,18 au départ, divisée par √(1 + n/2) après n réponses, jamais sous ±0,07 | `ml/model.py` |
| Grille des formats et de leur effort : opinion 0,15 · memory 0,25 · explain 0,40 · review 0,50 · make 0,70 · call 0,85 | `ml/formats.py` |
| **Mesure λ modifiée** : λ = (a·p − s) / ((a·p − s) + (a·h − s)), avec s = p·h. Sans retirer s, de vrais embeddings donnent presque toujours λ ≈ 0,5. Hors ligne, s vaut 0 et on retrouve la formule validée | `ml/pipeline.py` |
| Un message sans lien avec aucun des deux centres d'intérêt reçoit λ = 0, donc il est retenu | `ml/pipeline.py` |
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

## Repo

- Branche `max/1-boucle-ia` et bloc « Max » dans `STATUS.md` : prénom déduit du pseudo GitHub.
- `ONBOARDING.md`, resté indexé en local, est commité dans la même PR.
- Les contrats d'API et ML ont changé : `/api/predict` et `ml.model.predict` n'existent plus.

## Points ouverts repérés

- **Un vrai besoin sans lien avec les intérêts du patient n'est jamais transmis** : le centre de la zone ne descend pas sous 0,4. Il faut soit une zone qui descend plus bas quand le patient va bien, soit une règle à part pour les vrais besoins.
- Hors ligne, à θ très bas, la zone ne contient parfois que deux demandes.
- Le choix de l'aidant parmi les trois n'est pas enregistré.
- Non construits : le retour de l'aidant (preuve d'utilité), la vue clinicien, l'alerte de dérive.
- La page des challenges affichait un compte à rebours qui tombe vers 11 h le 14 novembre : à vérifier.
