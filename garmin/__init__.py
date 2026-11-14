"""Montre Garmin : lire les signaux de θ, en tirer un état et le pousser à la vraie app.

Voie choisie pour le hackathon (issue #24) : la montre se synchronise en Bluetooth avec le
téléphone, et on lit le compte Garmin Connect avec la bibliothèque non officielle `garminconnect`.
Une montre simulée (`ml/simulation`) prend le relais si la connexion échoue.

Lancement : `uv run python -m garmin --help`.
"""
