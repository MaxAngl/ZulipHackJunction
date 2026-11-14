"""Génère les données simulées.

Usage : uv run python -m ml.simulation --people 600 --days 56 --seed 0 --out ml/data/sim
"""

import argparse
from pathlib import Path

from ml.simulation.generate import generate, save, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère les données simulées (docs/modele.md).")
    parser.add_argument("--people", type=int, default=600, help="nombre de personnes")
    parser.add_argument("--days", type=int, default=56, help="nombre de jours simulés")
    parser.add_argument("--healthy", type=float, default=0.4, help="part de personnes saines")
    parser.add_argument("--seed", type=int, default=0, help="graine : même graine, mêmes données")
    parser.add_argument("--out", type=Path, default=Path("ml/data/sim"), help="dossier de sortie")
    args = parser.parse_args()

    dataset = generate(args.people, args.days, args.healthy, args.seed)
    save(dataset, args.out)
    print(summary(dataset))
    print(f"Écrit dans {args.out} : people.npz, episodes.npz, meta.json")


if __name__ == "__main__":
    main()
