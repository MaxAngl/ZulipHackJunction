"""Les trois réseaux (docs/modele.md, sections 4 et 13) et la forme de la zone.

- `StateAutoencoder` : θ → L(θ). Un encodeur par modalité, une fusion, un décodeur.
- `RewardNet`, le réseau A : (contexte, demande, vecteur du patient) → récompense attendue.
- `ZoneNet`, le réseau B : (28 états, comportement en direct, vecteur du patient) → zone.

A ne sert qu'à l'entraînement. B décide seul.
"""

import torch
from torch import nn

from ml.nets.features import CONTEXT_SIZE, LIVE_SIZE
from ml.simulation.spec import AXES, COMPONENTS, CONTEXT_LENGTH, INTERVAL_AXES

LATENT = len(COMPONENTS)
VECTOR_SIZE = 8  # le vecteur personnel d'un patient
TIME_SIZE = 4

# La zone. Demi-largeur d'un intervalle : jamais un point, jamais tout l'axe.
HALF_MIN, HALF_MAX = 0.08, 0.25
# Plafonds de sécurité, fixes et hors de tout apprentissage : quoi que dise B, la borne haute
# d'un axe de coût ne les dépasse pas. Ordre : intérêts, concret, durée, échange, exposition.
CEILING = (1.0, 1.0, 0.85, 0.85, 0.75)
STARTUP_CEILING = 0.80
STARTUP_FLOOR = 0.05
ZONE_OUTPUTS = 2 * INTERVAL_AXES + 1  # cinq centres, cinq demi-largeurs, un plafond


def _mlp(sizes: list[int]) -> nn.Sequential:
    layers: list[nn.Module] = []
    for index in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[index], sizes[index + 1]))
        if index < len(sizes) - 2:
            layers.append(nn.GELU())
    return nn.Sequential(*layers)


class StateAutoencoder(nn.Module):
    """θ → L(θ) → θ. Un petit encodeur par modalité, dont les sorties s'additionnent.

    Une modalité absente (montre non portée, aucune frappe ce jour-là) est remplacée par un
    vecteur appris. Ajouter une modalité revient à ajouter un encodeur et une tête de décodeur
    (`add_modality`) : ils partent de zéro, donc L ne change pas tant qu'ils ne sont pas
    entraînés, et les réseaux A et B, qui ne lisent que L, n'ont pas à bouger.
    """

    def __init__(self, columns: dict[str, list[int]], width: int = 32) -> None:
        super().__init__()
        self.width = width
        self.columns: dict[str, list[int]] = {}
        self.encoders = nn.ModuleDict()
        self.heads = nn.ModuleDict()
        self.absent = nn.ParameterDict()
        self.fuse = _mlp([width + TIME_SIZE, 32, LATENT])
        self.trunk = nn.Sequential(
            nn.Linear(LATENT + TIME_SIZE, 32), nn.GELU(), nn.Linear(32, 64), nn.GELU()
        )
        for name, signal_columns in columns.items():
            self._add(name, signal_columns, start_at_zero=False)

    @property
    def n_signals(self) -> int:
        return sum(len(signal_columns) for signal_columns in self.columns.values())

    def _add(self, name: str, signal_columns: list[int], start_at_zero: bool) -> None:
        hidden = 48 if len(signal_columns) > 8 else 16
        encoder = _mlp([3 * len(signal_columns), hidden, self.width])
        if start_at_zero:
            nn.init.zeros_(encoder[-1].weight)
            nn.init.zeros_(encoder[-1].bias)
        self.columns[name] = list(signal_columns)
        self.encoders[name] = encoder
        self.heads[name] = nn.Linear(64, len(signal_columns))
        self.absent[name] = nn.Parameter(torch.zeros(self.width))

    def add_modality(self, name: str, signal_columns: list[int]) -> list[nn.Parameter]:
        """Ajoute une modalité et renvoie ses paramètres, les seuls à entraîner ensuite."""
        if name in self.columns:
            raise ValueError(f"La modalité {name} existe déjà.")
        self._add(name, signal_columns, start_at_zero=True)
        return [
            *self.encoders[name].parameters(),
            *self.heads[name].parameters(),
            self.absent[name],
        ]

    def encode(
        self, g: torch.Tensor, p: torch.Tensor, m: torch.Tensor, time: torch.Tensor
    ) -> torch.Tensor:
        """L(θ) : six composantes entre 0 et 1. Entrées : [..., signaux] et [..., 4]."""
        total = torch.zeros(*g.shape[:-1], self.width, dtype=g.dtype, device=g.device)
        for name, signal_columns in self.columns.items():
            presence = m[..., signal_columns]
            views = [g[..., signal_columns], p[..., signal_columns], presence]
            token = self.encoders[name](torch.cat(views, dim=-1))
            present = presence.amax(dim=-1, keepdim=True)
            total = total + present * token + (1.0 - present) * self.absent[name]
        return torch.sigmoid(self.fuse(torch.cat([total, time], dim=-1)))

    def decode(self, state: torch.Tensor, time: torch.Tensor) -> torch.Tensor:
        """Reconstruit chaque signal, par rapport à la normale de la personne."""
        hidden = self.trunk(torch.cat([state, time], dim=-1))
        out = torch.zeros(*hidden.shape[:-1], self.n_signals, dtype=hidden.dtype)
        for name, signal_columns in self.columns.items():
            out[..., signal_columns] = self.heads[name](hidden)
        return out


BUMPS = 6  # nombre de bosses par axe
BUMP_WIDTH = 0.15


def axis_features(axes: torch.Tensor) -> torch.Tensor:
    """La position d'une demande, donnée à A sous une forme qui laisse voir un optimum.

    Ce qui convient à un patient est souvent au milieu d'un axe : ni tout près de ses intérêts,
    ni trop loin ; ni trop léger, ni trop lourd. Un petit réseau qui reçoit la position brute
    n'apprend, sur des récompenses bruitées, que des tendances droites. On lui donne donc aussi
    six « bosses » par axe, chacune maximale autour d'une position : un optimum au milieu devient
    simple à représenter.
    """
    centers = torch.linspace(0.0, 1.0, BUMPS, dtype=axes.dtype, device=axes.device)
    bumps = torch.exp(-((axes.unsqueeze(-1) - centers) ** 2) / (2.0 * BUMP_WIDTH**2))
    return torch.cat([axes, bumps.flatten(start_dim=-2)], dim=-1)


class RewardNet(nn.Module):
    """Le réseau A : un comité de petits réseaux denses, deux couches de 64 chacun.

    Chaque membre prédit deux choses pour une demande : la récompense, et si le patient
    répondra. La réponse est un signal bien plus net que la récompense : c'est surtout elle
    qui permet de régler le vecteur d'un patient avec peu de réactions.

    Pourquoi un comité : là où les membres ne sont pas d'accord, A ne sait pas. Le réseau B est
    entraîné sur leur avis prudent (moyenne moins désaccord), ce qui l'empêche d'aller chercher
    de bonnes notes là où A n'a jamais vu de données.
    """

    def __init__(self, members: int = 5) -> None:
        super().__init__()
        request = len(AXES) * (1 + BUMPS)
        sizes = [CONTEXT_SIZE + request + VECTOR_SIZE, 64, 64, 2]
        self.members = nn.ModuleList(_mlp(sizes) for _ in range(members))

    def opinions(
        self, context: torch.Tensor, axes: torch.Tensor, vector: torch.Tensor
    ) -> torch.Tensor:
        """L'avis de chaque membre : [membres, ..., 2] = (récompense / 100, logit de réponse)."""
        inputs = torch.cat([context, axis_features(axes), vector], dim=-1)
        return torch.stack([member(inputs) for member in self.members])

    def forward(
        self, context: torch.Tensor, axes: torch.Tensor, vector: torch.Tensor
    ) -> torch.Tensor:
        """Récompense attendue, divisée par 100 : la moyenne du comité."""
        return self.opinions(context, axes, vector)[..., 0].mean(dim=0)

    def cautious(
        self, context: torch.Tensor, axes: torch.Tensor, vector: torch.Tensor, caution: float
    ) -> torch.Tensor:
        """L'avis prudent : la moyenne du comité, moins `caution` fois son désaccord."""
        rewards = self.opinions(context, axes, vector)[..., 0]
        return rewards.mean(dim=0) - caution * rewards.std(dim=0)


class ZoneNet(nn.Module):
    """Le réseau B : un Transformer sur les 28 derniers relevés, puis une tête dense."""

    def __init__(self, width: int = 32, layers: int = 2, heads: int = 4) -> None:
        super().__init__()
        self.width = width
        self.embed = nn.Linear(LATENT + TIME_SIZE, width)
        self.position = nn.Parameter(torch.randn(CONTEXT_LENGTH, width) * 0.02)
        layer = nn.TransformerEncoderLayer(
            width, heads, 2 * width, dropout=0.0, batch_first=True, norm_first=True
        )
        self.body = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(width)
        self.head = _mlp([2 * width + LIVE_SIZE + VECTOR_SIZE, 48, ZONE_OUTPUTS])

    def forward(
        self, sequence: torch.Tensor, live: torch.Tensor, vector: torch.Tensor
    ) -> torch.Tensor:
        """Sorties brutes ; `to_zone` en fait une zone. `sequence` : [n, 28, 6 + 4]."""
        hidden = self.norm(self.body(self.embed(sequence) + self.position))
        pooled = torch.cat([hidden.mean(dim=1), hidden[:, -1]], dim=-1)
        return self.head(torch.cat([pooled, live, vector], dim=-1))


def to_zone(raw: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Des 11 sorties de B à la zone : bas [n, 5], haut [n, 5], plafond de démarrage [n]."""
    ceiling = torch.tensor(CEILING, dtype=raw.dtype, device=raw.device)
    center = torch.sigmoid(raw[..., :INTERVAL_AXES])
    half = HALF_MIN + (HALF_MAX - HALF_MIN) * torch.sigmoid(raw[..., INTERVAL_AXES:-1])
    # Le centre est ramené dans l'axe, pour que l'intervalle garde toute sa largeur.
    center = torch.minimum(torch.maximum(center, half), ceiling - half)
    startup = STARTUP_FLOOR + (STARTUP_CEILING - STARTUP_FLOOR) * torch.sigmoid(raw[..., -1])
    return center - half, center + half, startup


def draw_requests(
    low: torch.Tensor, high: torch.Tensor, startup: torch.Tensor, samples: int
) -> torch.Tensor:
    """Tire `samples` demandes dans chaque zone : [samples, n, 6]. Le tirage reste dérivable."""
    spread = torch.rand(samples, *low.shape, dtype=low.dtype, device=low.device)
    inside = low + spread * (high - low)
    cost = torch.rand(samples, *startup.shape, 1, dtype=low.dtype) * startup.unsqueeze(-1)
    return torch.cat([inside, cost], dim=-1)
