"""Données simulées pour entraîner l'autoencodeur, puis les réseaux A et B.

Voir docs/modele.md, sections 6 (générateurs) et 11 (θ, L et la récompense en détail).
Tout ce que ces données « savent » vient des règles écrites ici : elles servent à mettre au
point la machinerie d'apprentissage, pas à prouver quoi que ce soit sur de vrais patients.
"""

from ml.simulation.generate import Dataset, generate, population, save, subset

__all__ = ["Dataset", "generate", "population", "save", "subset"]
