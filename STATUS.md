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

## Max (Claude Code)

- **En cours :** #1, boucle IA de bout en bout (PR ouverte).
- **Bloqué :** pas de clé Gemini sur la machine, donc la connexion à Gemini n'est pas testée en réel. Mettre la clé dans `.env`, puis `uv run python -m ml.check_gemini`.
- **Notes pour la suite :**
  - Le modèle de zone (`ml/model.py`) et le capteur θ (`backend/sensor.py`) sont simulés. Garder leurs signatures en les remplaçant.
  - Si Gemini donne des λ tassés ou incohérents, regarder `lambda_position` dans `ml/pipeline.py` et les trois phrases de référence de `ml/check_gemini.py`.
  - Démo sur deux téléphones : `?view=helper` et `?view=patient`, avec `npm --prefix frontend run dev -- --host`.
  - Le serveur garde l'état en mémoire : un redémarrage remet la démo à zéro.

## _<prénom B>_

- **En cours :** —
- **Bloqué :** —
- **Notes pour la suite :** —

## _<prénom C>_

- **En cours :** —
- **Bloqué :** —
- **Notes pour la suite :** —
