# Le modèle : objets, réseaux, entraînement

Ce document fixe le modèle cible, tel que l'équipe l'a arrêté le 14 novembre. **Rien de ce qui suit n'est encore codé** : l'app tourne avec la version précédente, où l'état du patient est un seul nombre et la zone une règle écrite à la main. Les écarts sont listés en section 8.

Chaque élément porte un statut :

- **Décidé** : tranché par l'équipe.
- **Proposé** : suggestion qui n'a pas été confirmée.
- **À définir** : question ouverte.

## 1. Le processus, en neuf étapes

On mesure l'état du patient, on en déduit quel genre de demande lui convient, un humain la lui envoie, on mesure à nouveau, et on apprend de la différence.

1. **Mesurer.** On relève les données brutes du patient à cet instant : θ.
2. **Résumer.** L'autoencodeur transforme θ en un vecteur d'état, L(θ).
3. **Rassembler le contexte.** Plusieurs L(θ) relevés à des moments fixes de la journée et de la semaine, les centres d'intérêt du patient, ceux de l'aidant, et le comportement récent du patient dans l'app.
4. **Définir la zone.** Le réseau B lit ce contexte et sort la zone : pour chaque axe, ce qui est acceptable maintenant.
5. **Générer.** Gemini écrit une dizaine de demandes qui visent cette zone.
6. **Trier.** Chaque demande est mesurée sur les axes. Celles qui sortent de la zone sont écartées. On en garde trois.
7. **L'aidant décide.** Il en choisit une, la modifie ou écrit la sienne. Une demande hors zone est retenue jusqu'au bon moment, jamais refusée.
8. **Le patient réagit.** Il répond, ou non.
9. **Mesurer à nouveau.** Après un délai dt, on relève θ, on recalcule L(θ), et on en tire une récompense de 0 à 100.

## 2. Les objets

| Objet | Symbole | Type et domaine | Définition | Statut |
|---|---|---|---|---|
| Données brutes | θ_t | Vecteur de signaux, à un instant t | Tout ce qu'on relève sur le patient à cet instant, sans rien lui demander | Décidé ; contenu à définir |
| État | L(θ_t) | Vecteur de dimension k | Code latent de l'autoencodeur appliqué à θ_t | Décidé ; k et composantes à définir |
| Référence saine | L_ref | Même espace que L | L d'une personne saine | Décidé ; une région plutôt qu'un point : proposé |
| Centre d'intérêt | p (patient), h (aidant) | Texte, et son vecteur | Ce que la personne aime ou connaît | Décidé |
| Paire | (p, h) | Un centre d'intérêt de chaque côté | Les deux sujets entre lesquels une demande se place | Décidé ; règle de choix à définir |
| Demande | a | Texte, origine, état | Un petit service demandé au patient par un aidant | Décidé |
| Position d'une demande | x(a) | Un nombre entre 0 et 1 par axe | Où la demande se situe sur chacun des axes (section 3) | Décidé ; grilles de notation à définir |
| Zone | Z | Un intervalle ou un plafond par axe | Les demandes acceptables pour ce patient, maintenant | Décidé |
| Propositions | — | Trois demandes de la zone | Ce que l'aidant se voit proposer | Décidé |
| Réaction du patient | — | Répond ou non, délai, longueur | Ce qu'on observe après la demande ; elle fait partie de θ | Décidé |
| Récompense | r | Nombre de 0 à 100 | Amélioration de l'état, en comparant L(θ_t) à L(θ_t+dt) | Décidé ; formule à définir |
| Ligne du journal | — | Un enregistrement par demande | Contexte, positions de la demande, réaction, récompense | Décidé ; champs à définir |

Origines possibles d'une demande : suggérée, modifiée par l'aidant, ou vrai besoin écrit par lui. États possibles : retenue, transmise, répondue, mise de côté.

| Objet | D'où viennent ses données | Qui le voit | Dans le code actuel |
|---|---|---|---|
| θ | Comportement dans l'app, capteurs | Personne | N'existe pas sous forme brute |
| L(θ) | Calculé par l'autoencodeur | Personne | `theta`, un seul nombre (`backend/loop.py`, colonne `theta` de `backend/store.py`) |
| L_ref | Personnes saines, simulées puis réelles | Personne | N'existe pas |
| Centre d'intérêt | Saisi à l'inscription | L'aidant et le patient voient le leur | `interests` (`backend/store.py`) |
| Paire | Choisie par le système | L'aidant, sur la console de démo | `InterestPair` (`ml/types.py`), choisie par rotation |
| Demande | Gemini, ou l'aidant | L'aidant, puis le patient | `Candidate` (`ml/types.py`), table `requests` |
| Position | Mesurée sur le texte | Personne | `lam` et `effort` seulement |
| Zone | Sortie du réseau B | Personne | `Zone` (`ml/types.py`), calculée par `zone_for` |
| Propositions | Tri des demandes générées | L'aidant | `select_three` (`ml/pipeline.py`) |
| Réaction | Observée dans l'app | Le système | `reply`, `answered_at`, `status` (table `requests`) |
| Récompense | Calculée | Personne | `reward`, une différence signée |
| Journal | Enregistré à chaque demande | Personne | Table `requests`, sans les axes |

## 3. Les axes d'une demande

L'ancien « effort » était un seul nombre qui mélangeait la durée, l'échange et le passage à l'action. Il est remplacé par des axes séparés.

| Axe | Ce qu'il mesure | Forme dans la zone | Phase |
|---|---|---|---|
| Position entre les intérêts (λ) | 0 = intérêts de l'aidant, 1 = intérêts du patient | Intervalle | 1 |
| Concret / abstrait | Une chose à faire ou à montrer, ou une idée à discuter | Intervalle | 1 |
| Temps de réalisation | Le temps que la tâche demande | Intervalle | 1 |
| Échange humain | La part d'interaction avec l'aidant | Intervalle | 1 |
| Exposition personnelle | À quel point le patient doit se livrer | Intervalle | 1 |
| Coût de démarrage | Ce qu'il faut pour s'y mettre | Plafond seul | 1 |
| Activation physique | Rester assis, se lever, sortir de chez soi | Intervalle | 2 |
| Compétence exigée | Le niveau de savoir-faire que la tâche demande | Plafond seul | 2 |

Toutes ces lignes sont **décidées**. Trois règles les accompagnent, décidées elles aussi :

- **La borne haute est une sécurité.** Elle n'est jamais dépassée.
- **La borne basse est un objectif.** Elle ne s'applique qu'aux demandes générées, et n'oblige jamais le patient à se confier.
- **Un vrai besoin écrit par l'aidant n'est jamais retenu parce qu'il est trop léger.**

Le réseau B sort donc 11 nombres en phase 1 (cinq intervalles et un plafond), et 14 avec la phase 2.

À trancher : la compétence exigée se mesure sur le texte seul, donc rien n'empêche de la passer en phase 1.

## 4. Les trois réseaux

| Réseau | Rôle | Entrée → sortie | Sert à |
|---|---|---|---|
| **Autoencodeur** | Dire comment va le patient | θ → L(θ) | La décision et l'entraînement |
| **B**, un Transformer | Dire quel genre de demande convient maintenant | Contexte → zone | La décision |
| **A**, un petit réseau dense | Dire ce qu'une demande précise va apporter | (contexte, positions de la demande) → récompense attendue | L'entraînement seulement |

**A n'intervient jamais dans la décision.** B décide seul. A reste en coulisses : il apprend de la réalité, et B apprend de lui.

Pourquoi B a besoin de A : B sort onze nombres, et le patient renvoie une seule note. Avec cette note seule, B ne sait pas lequel de ses nombres corriger. Sans A, il faudrait essayer des zones au hasard sur des centaines de demandes, alors qu'un patient en reçoit une trentaine par mois.

Décidé pour l'autoencodeur : θ est pris à un instant ; une partie de θ est masquée à l'entraînement ; θ est normalisé par personne ; une tête supervisée oriente le code latent.

Décidé pour B : il reçoit un nombre fixe de L(θ), relevés à des moments différents de la journée et de la semaine, les centres d'intérêt du patient et de l'aidant, et le comportement en direct du patient, que L contient déjà mais de façon brouillée.

### Ce qui est général, ce qui est personnel

Un seul jeu de poids général pour tout le monde, et une petite partie par patient. Jamais un réseau entier par patient : il n'aurait pas assez de données.

| Réseau | Partie générale | Partie personnelle |
|---|---|---|
| Autoencodeur | Tous ses poids | Aucun poids : seulement la normale du patient, qui sert à normaliser θ |
| A | Le corps et une dernière couche commune | Une dernière couche par patient |
| B | Le corps et une dernière couche commune | Une dernière couche par patient |

| | Partie générale | Partie personnelle |
|---|---|---|
| Données | Tous les patients, simulés puis réels | Celles du patient seulement |
| Moment | Hors ligne : avant le déploiement, puis chaque nuit ou chaque semaine | Après chaque réaction |
| Ce qu'elle apprend | Ce qui vaut pour tous | L'écart de ce patient par rapport à la moyenne |
| Vérification | Sur des patients jamais vus | Sur les semaines suivantes du même patient |

Un nouveau patient n'a pas de partie personnelle : il reçoit exactement le modèle général.

## 5. La décision : B seul

1. B, avec ses poids généraux et la couche personnelle du patient, sort la zone.
2. Gemini génère dans cette zone.
3. Les demandes sont mesurées sur les axes. Celles hors zone sont écartées.
4. Trois propositions sont choisies par leur position dans la zone : la plus centrale, une autre paire de centres d'intérêt, un bord pour explorer.

L'exploration vient de la largeur de la zone.

## 6. L'entraînement

**0. Deux générateurs de données.**
Le générateur d'états tire un état caché pour des personnes simulées, saines ou malades, et produit leurs données brutes θ, avec du bruit et des trous. Le patient simulé reçoit une demande et produit une réaction, puis un nouvel état.

**1. L'autoencodeur, une fois pour toutes.**
On normalise θ par personne et on en masque une partie. L'encodeur produit L(θ), le décodeur reconstruit θ en entier, et une tête supplémentaire retrouve l'état caché à partir de L. L'encodeur est ensuite figé, et L_ref est calculé sur les personnes saines simulées.

**2. Un journal d'épisodes simulés.**
Pour chaque patient simulé, on choisit des zones au hasard, on tire une demande dedans, le patient simulé réagit, et on calcule la récompense. On enregistre le contexte, les positions de la demande et la note.

**3. Le réseau A.**
Régression sur ce journal : contexte et demande en entrée, note en sortie.

**4. Le réseau B.**
Pour chaque contexte, B propose une zone, on tire des demandes dedans, A les note, et on ajuste B pour faire monter la note moyenne. Les plafonds de sécurité restent fixes.

**5. On recommence les étapes 2 à 4** quelques fois, en laissant B choisir une partie des zones, pour que A voie les régions où B va réellement.

**6. Sur les patients réels.**

Après chaque réaction :

1. On calcule la récompense.
2. La couche personnelle de A est mise à jour.
3. La couche personnelle de B fait quelques pas vers les zones que le A de ce patient note le mieux.

Régulièrement : A général est réentraîné sur tous les patients, puis B général est réajusté contre **A général**, puis les couches personnelles sont recalculées en rejouant l'historique de chaque patient.

B général s'entraîne contre A général, et non contre les A personnels : ceux-ci envoient des signaux qui se contredisent d'un patient à l'autre, et qu'un réseau partagé ne peut que moyenner.

Trois précautions pour la couche personnelle de B :

- la retenir près de la couche générale ;
- ne l'activer qu'après une vingtaine de réactions, quand le A du patient est fiable ;
- laisser les plafonds de sécurité hors de tout apprentissage.

## 7. L'évaluation

En simulation, où la vérité est connue :

1. **Autoencodeur.** Sur des personnes jamais vues : l'erreur de reconstruction des parties masquées, et l'écart entre L et l'état caché.
2. **A.** Sur des patients simulés aux règles jamais vues : l'erreur de prédiction de la note.
3. **B et la boucle entière.** La récompense moyenne obtenue, comparée à trois références : une zone au hasard, la règle fixe du code actuel, et un oracle qui connaît les règles du patient simulé.
4. **Sécurité.** Aucune proposition au-dessus d'un plafond, et une zone qui ne se réduit pas à un point.

Sur patients réels, dans une étude pilote :

5. L'erreur de prédiction de A pour chaque patient, qui doit baisser avec le temps.
6. B contre la règle fixe, en alternant les deux au hasard : récompense moyenne et taux de réponse.
7. L(θ) comparé à des scores cliniques recueillis pendant l'étude.

Les points 1 à 4 montrent que la machinerie apprend. Seuls les points 6 et 7 disent quelque chose sur de vrais patients. **Les réseaux entraînés sur des données générées apprennent ce que les générateurs contiennent, rien de plus.**

## 8. Écarts avec le code actuel

| Dans la cible | Dans le code aujourd'hui | Où |
|---|---|---|
| θ brut, puis L(θ) vecteur | Un seul nombre, appelé `theta`, qui joue le rôle de L | `backend/loop.py`, `backend/community.py`, `backend/store.py` |
| L appris par un autoencodeur | Un curseur et une simulation (console), une règle sur le comportement (vraie app) | `backend/sensor.py`, `backend/community.py` |
| Zone sur 6 à 8 axes | Zone sur 2 axes : un intervalle sur λ, un plafond d'effort | `ml/types.py`, `ml/model.py` |
| Axes mesurés séparément | Une grille de formats avec un seul effort | `ml/formats.py` |
| Zone sortie par le réseau B | Règle `1 − 0,6·θ` et `0,25 + 0,75·θ` | `ml/model.py`, `zone_for` |
| A et B appris, avec une couche par patient | `learn`, une règle écrite à la main, avec un décalage par patient | `ml/model.py` |
| Récompense de 0 à 100 sur des vecteurs | Différence signée de deux nombres | `backend/loop.py`, `backend/community.py` |
| Journal avec les positions sur tous les axes | Table `requests` avec `lam` et `effort` | `backend/store.py` |

Ce qui ne change pas : Gemini génère, chaque demande est mesurée puis filtrée, l'aidant choisit parmi trois, modifie ou écrit la sienne, et une demande hors zone est retenue. La mesure de λ (`lambda_position`, `ml/pipeline.py`) reste celle de l'axe λ.

Passer à la cible changera les deux contrats, API et ML : `theta` et `ZoneState` dans `backend/schemas.py`, `zone_for` et `learn` dans `ml/model.py`.

## 9. Proposé, à confirmer

- Un autoencodeur variationnel, pour que la distance à L_ref ait un sens.
- L_ref comme une région, et une mise à l'échelle par personne.
- Une récompense qui compare L après à l'état attendu sans la demande, et qui mesure si le patient se rapproche de L_ref.
- Les demandes passées et leurs notes ajoutées aux entrées de B.
- Un encodeur commun à A et B.
- Pour A : prédire aussi l'acceptation et le délai de réponse, et fournir une incertitude.
- Une famille de générateurs aux règles tirées au hasard, plutôt qu'un seul.
- Figer la normale de chaque patient sur une période de référence, pour qu'une dégradation lente ne devienne pas sa nouvelle normale.
- À grande échelle : un Transformer sur l'historique du patient en entrée de A.

## 10. À définir

- Le contenu de θ, signal par signal.
- Les composantes de L : leur nombre, et la source de chacune.
- La grille de temps de la séquence donnée à B, et la durée dt.
- La formule exacte de la récompense.
- Les deux générateurs : leurs composantes, leurs règles, leur bruit. **C'est la prochaine étape**, et tout ce que les réseaux sauront en découle.
- La grille de notation de chaque axe.
- La règle de choix de la paire de centres d'intérêt.
- Le cas d'un vrai besoin sans lien avec les centres d'intérêt du patient.
