"""Vérifie en une commande que la clé Gemini fonctionne et que la mesure λ est plausible.

Usage : uv run python -m ml.check_gemini
À lancer après avoir mis GEMINI_API_KEY dans `.env`, avant une démo.
"""

from ml import gemini
from ml.model import InterestPair, generate_candidates, load_env_file, measure_message, zone_for

PAIRS = [InterestPair("gardening", "cooking"), InterestPair("jazz", "cycling")]
REFERENCES = (
    ("tout côté patient", "Which herb is the easiest to grow on a small balcony?"),
    ("mélange", "I'm cooking dinner for six. Which herbs from your garden would you use?"),
    ("tout côté aidant", "Soup or pasta for Saturday's dinner menu, what would you cook?"),
)


def main() -> None:
    load_env_file()
    if not gemini.is_configured():
        print("ÉCHEC : GEMINI_API_KEY absente. Ajoutez-la dans .env à la racine du repo.")
        return
    print(f"Clé trouvée. Génération : {gemini.generation_model()}")
    print(f"             Embeddings : {gemini.embedding_model()}")

    try:
        vectors = gemini.embed(["gardening", "cooking"])
        print(f"OK embeddings : {len(vectors)} vecteurs de dimension {len(vectors[0])}")
    except gemini.GeminiError as exc:
        print(f"ÉCHEC embeddings : {exc}")
        print("  -> essayez GEMINI_EMBED_MODEL=gemini-embedding-2 dans .env")
        return

    print("Mesure λ sur trois phrases de référence (attendu : haut, moyen, bas) :")
    for label, text in REFERENCES:
        measured, _ = measure_message(text, PAIRS[:1])
        print(f"  λ = {measured.lam:.2f}  [{measured.provider}]  {label}")

    zone = zone_for(0.5)
    candidates = generate_candidates(PAIRS, zone, "Mikko", "Aino", avoid=[], seed=1)
    live = [candidate for candidate in candidates if candidate.provider == "gemini"]
    if not live:
        print("ÉCHEC génération : la banque hors ligne a pris le relais (voir les logs).")
        print("  -> essayez un autre modèle avec GEMINI_MODEL=... dans .env")
        return
    inside = [c for c in live if zone.contains(c.lam, c.effort)]
    print(f"OK génération : {len(live)} demandes, dont {len(inside)} dans la zone")
    print(f"  zone : λ de {zone.low:.2f} à {zone.high:.2f}, effort max {zone.effort_max:.2f}")
    for candidate in live[:5]:
        aim = f"{candidate.intended:.2f}" if candidate.intended is not None else " ?  "
        print(f"  visé {aim} mesuré {candidate.lam:.2f}  {candidate.format:8} {candidate.text}")


if __name__ == "__main__":
    main()
