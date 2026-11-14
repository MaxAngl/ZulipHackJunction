"""Les trois réseaux de docs/modele.md : l'autoencodeur, le réseau A et le réseau B.

- `features` : passage des relevés bruts θ aux entrées des réseaux (numpy seul).
- `models` : les trois réseaux et la forme de la zone.
- `runtime` : charge des poids et répond en numpy. C'est ce que l'app utilise.
- `train` : entraîne les trois réseaux sur un jeu simulé.
- `policy` et `evaluate` : fait tourner B en boucle fermée contre des références.

Les réseaux sont entraînés sur des données simulées : ils apprennent ce que le simulateur
contient, rien de plus.
"""
