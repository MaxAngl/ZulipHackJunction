"""Vérifie en une commande que la clé Claude fonctionne, et dit ce qu'a coûté l'essai.

Usage : uv run python -m ml.check_claude
À lancer après avoir mis ANTHROPIC_API_KEY dans `.env`, avant une démo. Un seul appel de
génération (une paire d'intérêts) : quelques centimes avec claude-opus-5-5.
"""

from ml import claude
from ml.embedding import local_available
from ml.model import InterestPair, generate_candidates, load_env_file, provider_info, zone_for

# Prix publics, en dollars par million de tokens (entrée, sortie).
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


def cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


def main() -> None:
    load_env_file()
    if not claude.is_configured():
        print("ÉCHEC : ANTHROPIC_API_KEY absente. Ajoutez-la dans .env à la racine du repo.")
        return
    model = claude.generation_model()
    print(f"Clé trouvée. Modèle : {model}")
    print(f"Mesure de λ : {'modèle local' if local_available() else 'position annoncée'}")

    zone = zone_for(0.5)
    pairs = [InterestPair("gardening", "cooking")]
    candidates = generate_candidates(
        pairs, zone, "Mikko", "Aino", avoid=[], seed=1, patient_bio="I grow tomatoes."
    )
    live = [candidate for candidate in candidates if candidate.provider == "claude"]
    if not live:
        print(f"ÉCHEC génération : la banque a pris le relais ({provider_info().note})")
        return
    inside = [c for c in live if zone.contains(c.lam, c.effort)]
    print(f"OK génération : {len(live)} demandes, dont {len(inside)} dans la zone")
    for candidate in live[:5]:
        body = candidate.text.splitlines()[1] if "\n" in candidate.text else candidate.text
        print(f"  visé {candidate.intended or 0:.2f} mesuré {candidate.lam:.2f}  {body}")
    spent = cost(model, claude.usage["input_tokens"], claude.usage["output_tokens"])
    tokens = f"{claude.usage['input_tokens']} en entrée, {claude.usage['output_tokens']} en sortie"
    price = f" ≈ {spent:.3f} $" if spent is not None else ""
    print(f"Coût de cet essai : {tokens}{price}")


if __name__ == "__main__":
    main()
