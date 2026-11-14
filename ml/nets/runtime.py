"""Les réseaux entraînés, prêts à répondre en numpy. C'est la seule porte d'entrée de l'app.

`Networks.load` lit un dossier de poids (par défaut `ml/weights`, versionné dans git).
Tout ce qui est appris est dedans : les trois réseaux, la moyenne et la dispersion de chaque
signal sur tout le monde, et L_ref.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from ml.nets.features import (
    encoder_inputs,
    live_features,
    person_normal,
    time_features,
    transform,
)
from ml.nets.models import VECTOR_SIZE, RewardNet, StateAutoencoder, ZoneNet, to_zone
from ml.simulation.reward import distance, reward
from ml.simulation.spec import SIGNAL_NAMES, modality_indices

DEFAULT_WEIGHTS = Path(__file__).resolve().parent.parent / "weights"
PRIOR = 5.0  # force qui retient le vecteur d'un patient près de zéro
REPLY_WEIGHT = 1.0  # poids de « a-t-il répondu ? » face à l'erreur sur la récompense
CHUNK = 65536


def vector_loss(
    opinions: torch.Tensor, target: torch.Tensor, answered: torch.Tensor
) -> torch.Tensor:
    """Erreur de A sur chaque ligne et pour chaque membre : récompense, et réponse ou non."""
    reward_error = (opinions[..., 0] - target) ** 2
    reply_error = F.binary_cross_entropy_with_logits(
        opinions[..., 1], answered.expand_as(opinions[..., 1]), reduction="none"
    )
    return reward_error + REPLY_WEIGHT * reply_error


def _tensor(array: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.require(array, dtype=np.float32, requirements=["C", "W"]))


@dataclass
class Networks:
    autoencoder: StateAutoencoder
    reward_net: RewardNet
    zone_net: ZoneNet
    global_mean: np.ndarray  # [signaux] moyenne de chaque signal sur tout le monde
    global_spread: np.ndarray  # [signaux]
    reference_mean: np.ndarray  # [6] L_ref : moyenne de L chez les personnes saines
    reference_spread: np.ndarray  # [6]
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        for module in (self.autoencoder, self.reward_net, self.zone_net):
            module.eval()
            for parameter in module.parameters():
                parameter.requires_grad_(False)

    @property
    def prior(self) -> float:
        """Force qui retient le vecteur d'un patient près de zéro, la même qu'à l'entraînement."""
        return float(self.meta.get("trained_on", {}).get("prior", PRIOR))

    # --- Lecture et écriture -----------------------------------------------------------------

    def save(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        torch.save(self.autoencoder.state_dict(), out_dir / "autoencoder.pt")
        torch.save(self.reward_net.state_dict(), out_dir / "reward_net.pt")
        torch.save(self.zone_net.state_dict(), out_dir / "zone_net.pt")
        description = {
            "signals": list(SIGNAL_NAMES),
            "modalities": self.autoencoder.columns,
            "zone_width": self.zone_net.width,
            "global_mean": self.global_mean.tolist(),
            "global_spread": self.global_spread.tolist(),
            "reference_mean": self.reference_mean.tolist(),
            "reference_spread": self.reference_spread.tolist(),
            **self.meta,
        }
        text = json.dumps(description, indent=2, ensure_ascii=False) + "\n"
        (out_dir / "meta.json").write_text(text, encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, weights_dir: Path = DEFAULT_WEIGHTS) -> "Networks":
        description = json.loads((weights_dir / "meta.json").read_text(encoding="utf-8"))
        if description["signals"] != list(SIGNAL_NAMES):
            raise ValueError("Ces poids ont été entraînés avec d'autres signaux : réentraîner.")
        autoencoder = StateAutoencoder(description.get("modalities") or modality_indices())
        reward_net, zone_net = RewardNet(), ZoneNet(description["zone_width"])
        for module, name in (
            (autoencoder, "autoencoder"),
            (reward_net, "reward_net"),
            (zone_net, "zone_net"),
        ):
            module.load_state_dict(torch.load(weights_dir / f"{name}.pt", weights_only=True))
        learned = {
            "signals",
            "modalities",
            "zone_width",
            "global_mean",
            "global_spread",
            "reference_mean",
            "reference_spread",
        }
        return cls(
            autoencoder,
            reward_net,
            zone_net,
            np.array(description["global_mean"], dtype=np.float32),
            np.array(description["global_spread"], dtype=np.float32),
            np.array(description["reference_mean"], dtype=np.float32),
            np.array(description["reference_spread"], dtype=np.float32),
            {key: value for key, value in description.items() if key not in learned},
        )

    # --- L'état : θ → L ----------------------------------------------------------------------

    def normal(self, theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """La normale de chaque personne, à partir de ses relevés bruts [n, relevés, signaux]."""
        return person_normal(transform(theta), self.global_mean, self.global_spread)

    def states(
        self, theta: np.ndarray, normal: tuple[np.ndarray, np.ndarray], index: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """L et comportement en direct de chaque relevé.

        `theta` : relevés bruts [n, t, signaux]. `index` : rang de chaque relevé, [n, t] ou [t],
        qui donne son heure. Renvoie L [n, t, 6] et le comportement en direct [n, t, 12].
        """
        g, p, m = encoder_inputs(transform(theta), self.global_mean, self.global_spread, *normal)
        time = np.broadcast_to(time_features(index), (*g.shape[:-1], 4))
        return self.encode(g, p, m, time), live_features(p, m)

    def encode(self, g: np.ndarray, p: np.ndarray, m: np.ndarray, time: np.ndarray) -> np.ndarray:
        """L à partir des entrées déjà préparées, par morceaux pour ne pas saturer la mémoire."""
        shape = g.shape[:-1]
        flat = [_tensor(array).reshape(-1, array.shape[-1]) for array in (g, p, m, time)]
        parts = []
        with torch.no_grad():
            for start in range(0, len(flat[0]), CHUNK):
                piece = [array[start : start + CHUNK] for array in flat]
                parts.append(self.autoencoder.encode(*piece))
        return torch.cat(parts).numpy().reshape(*shape, -1)

    # --- La récompense -----------------------------------------------------------------------

    def distance(self, state: np.ndarray) -> np.ndarray:
        """Distance d'un état L à L_ref, en largeurs de la dispersion saine."""
        return distance(state, self.reference_mean, self.reference_spread)

    def reward(self, before: np.ndarray, after: np.ndarray) -> np.ndarray:
        """Récompense de 0 à 100 entre deux états L (docs/modele.md, section 11)."""
        return reward(self.distance(before), self.distance(after))

    # --- La zone : le réseau B, seul ---------------------------------------------------------

    def zone(
        self, states: np.ndarray, index: np.ndarray, live: np.ndarray, vectors: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """La zone de chaque patient. `states` : [n, 28, 6], `index` : rang des 28 relevés."""
        time = np.broadcast_to(time_features(index), (*states.shape[:-1], 4))
        sequence = _tensor(np.concatenate([states, time], axis=-1))
        with torch.no_grad():
            low, high, startup = to_zone(self.zone_net(sequence, _tensor(live), _tensor(vectors)))
        return low.numpy(), high.numpy(), startup.numpy()

    # --- Le réseau A : à l'entraînement, et pour régler le vecteur d'un patient --------------

    def predict(self, context: np.ndarray, axes: np.ndarray, vectors: np.ndarray) -> np.ndarray:
        """Récompense attendue (0 à 100) d'une demande. Ne sert jamais à décider."""
        with torch.no_grad():
            out = self.reward_net(_tensor(context), _tensor(axes), _tensor(vectors))
        return 100.0 * out.numpy()

    def reply_chance(
        self, context: np.ndarray, axes: np.ndarray, vectors: np.ndarray
    ) -> np.ndarray:
        """Probabilité que le patient réponde, selon A. Ne sert jamais à décider."""
        with torch.no_grad():
            opinions = self.reward_net.opinions(_tensor(context), _tensor(axes), _tensor(vectors))
        return torch.sigmoid(opinions[..., 1]).mean(dim=0).numpy()

    def fit_vectors(
        self,
        person: np.ndarray,
        context: np.ndarray,
        axes: np.ndarray,
        rewards: np.ndarray,
        replied: np.ndarray,
        n_people: int,
        start: np.ndarray | None = None,
        steps: int = 60,
    ) -> np.ndarray:
        """Règle le vecteur de chaque patient sur ses propres réactions. A et B ne bougent pas.

        Une ligne par demande passée : la personne, le contexte, la demande, la récompense
        (0 à 100) et s'il a répondu. Le vecteur est retenu près de zéro, d'autant plus que le
        patient a peu de réactions : un nouveau patient garde le modèle général.
        """
        vectors = torch.zeros(n_people, VECTOR_SIZE) if start is None else _tensor(start).clone()
        if len(person) == 0:
            return vectors.numpy()
        vectors.requires_grad_(True)
        rows = torch.from_numpy(np.asarray(person, dtype=np.int64))
        context_t, axes_t = _tensor(context), _tensor(axes)
        target = _tensor(np.asarray(rewards) / 100.0)
        answered = _tensor(np.asarray(replied, dtype=np.float32))
        optimizer = torch.optim.Adam([vectors], lr=0.05)
        for _ in range(steps):
            opinions = self.reward_net.opinions(context_t, axes_t, vectors[rows])
            loss = vector_loss(opinions, target, answered).sum() / len(opinions)
            loss = loss + self.prior * (vectors**2).sum()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        return vectors.detach().numpy()
