# Le modèle : objets, réseaux, entraînement

Ce document fixe le modèle, tel que l'équipe l'a arrêté le 14 novembre. **Les trois réseaux sont codés et entraînés** sur des données simulées (`ml/nets`, poids dans `ml/weights`) : architectures en section 13, résultats en section 14. Tant que leur branchement n'est pas mergé, l'app tourne avec la version précédente, où l'état du patient est un seul nombre et la zone une règle écrite à la main. Les écarts sont listés en section 8.

Chaque élément porte un statut :

- **Décidé** : tranché par l'équipe.
- **Délégué** : choisi par Claude à la demande de l'équipe (« je te laisse faire le mieux »). À relire.
- **Proposé** : suggestion qui n'a pas été confirmée.
- **À définir** : question ouverte.

Ce qui est codé : la génération des données simulées (`ml/simulation/`, sections 11 et 12) et les trois réseaux avec leur entraînement et leur évaluation (`ml/nets/`, sections 13 et 14).

## 1. Le processus, en neuf étapes

On mesure l'état du patient, on en déduit quel genre de demande lui convient, un humain la lui envoie, on mesure à nouveau, et on apprend de la différence.

1. **Mesurer.** On relève les données brutes du patient à cet instant : θ.
2. **Résumer.** L'autoencodeur transforme θ en un vecteur d'état, L(θ).
3. **Rassembler le contexte.** Plusieurs L(θ) relevés à des moments fixes de la journée et de la semaine, le comportement récent du patient dans l'app, et son vecteur personnel.
4. **Définir la zone.** Le réseau B lit ce contexte et sort la zone : pour chaque axe, ce qui est acceptable maintenant.
5. **Générer.** Gemini écrit une dizaine de demandes qui visent cette zone.
6. **Trier.** Chaque demande est mesurée sur les axes. Celles qui sortent de la zone sont écartées. On en garde trois.
7. **L'aidant décide.** Il en choisit une, la modifie ou écrit la sienne. Une demande hors zone est retenue jusqu'au bon moment, jamais refusée.
8. **Le patient réagit.** Il répond, ou non.
9. **Mesurer à nouveau.** Après un délai dt, on relève θ, on recalcule L(θ), et on en tire une récompense de 0 à 100.

## 2. Les objets

| Objet | Symbole | Type et domaine | Définition | Statut |
|---|---|---|---|---|
| Données brutes | θ_t | Vecteur de 25 signaux, à un instant t | Tout ce qu'on relève sur le patient à cet instant, sans rien lui demander | Décidé ; contenu délégué (section 11) |
| État | L(θ_t) | Vecteur de dimension 6 | Code latent de l'autoencodeur appliqué à θ_t | Décidé ; composantes déléguées (section 11) |
| Référence saine | L_ref | Une moyenne et une dispersion par composante | L des personnes saines | Décidé ; forme déléguée (section 11) |
| Centre d'intérêt | p (patient), h (aidant) | Texte, et son vecteur | Ce que la personne aime ou connaît | Décidé |
| Paire | (p, h) | Un centre d'intérêt de chaque côté | Les deux sujets entre lesquels une demande se place | Décidé ; règle de choix à définir |
| Demande | a | Texte, origine, état | Un petit service demandé au patient par un aidant | Décidé |
| Position d'une demande | x(a) | Un nombre entre 0 et 1 par axe | Où la demande se situe sur chacun des axes (section 3) | Décidé ; grilles de notation à définir |
| Zone | Z | Un intervalle ou un plafond par axe | Les demandes acceptables pour ce patient, maintenant | Décidé |
| Propositions | — | Trois demandes de la zone | Ce que l'aidant se voit proposer | Décidé |
| Réaction du patient | — | Répond ou non, délai, longueur | Ce qu'on observe après la demande ; elle fait partie de θ | Décidé |
| Récompense | r | Nombre de 0 à 100 | Amélioration de l'état, en comparant L(θ_t) à L(θ_t+dt) | Décidé ; formule déléguée (section 11) |
| Ligne du journal | — | Un enregistrement par demande | Contexte, positions de la demande, réaction, récompense | Décidé ; champs à définir |

Origines possibles d'une demande : suggérée, modifiée par l'aidant, ou vrai besoin écrit par lui. États possibles : retenue, transmise, répondue, mise de côté.

| Objet | D'où viennent ses données | Qui le voit | Dans le code actuel |
|---|---|---|---|
| θ | Montre Garmin Forerunner 965 et comportement dans l'app | Personne | N'existe pas dans l'app ; simulé par `ml/simulation` |
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

**Plafonds de sécurité** (délégués) : des valeurs fixes, écrites dans le code (`ml/nets/models.py`) et que rien n'apprend. Quoi que sorte le réseau B, la borne haute d'un axe de coût ne les dépasse jamais : 0,85 pour la durée et l'échange, 0,75 pour l'exposition personnelle, 0,80 pour le coût de démarrage. C'est un garde-fou contre un réseau qui se tromperait : même dans ce cas, aucun patient ne reçoit une demande au maximum de l'axe. La demi-largeur d'un intervalle reste entre 0,08 et 0,25 : la zone n'est jamais un point, jamais tout l'axe.

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
| **A**, un comité de petits réseaux denses | Dire ce qu'une demande précise va apporter | (contexte, positions de la demande) → récompense attendue, et chance que le patient réponde | L'entraînement seulement |

**A n'intervient jamais dans la décision.** B décide seul. A reste en coulisses : il apprend de la réalité, et B apprend de lui.

Pourquoi B a besoin de A : B sort onze nombres, et le patient renvoie une seule note. Avec cette note seule, B ne sait pas lequel de ses nombres corriger. Sans A, il faudrait essayer des zones au hasard sur des centaines de demandes. Au rythme supposé d'une demande par jour, cela prendrait des mois, en envoyant exprès de mauvaises demandes à un patient fragile.

Décidé pour l'autoencodeur : θ est pris à un instant ; une partie de θ est masquée à l'entraînement ; θ est normalisé par personne ; une tête supervisée oriente le code latent.

Ce que le code ajoute à ces décisions (délégué, `ml/nets`) :

- **Un encodeur par modalité** (montre, app, frappe), dont les sorties s'additionnent. Une modalité absente est remplacée par un vecteur appris. Une modalité nouvelle part de zéro : L ne change pas tant qu'elle n'est pas entraînée, et A et B, qui ne lisent que L, ne bougent pas (`StateAutoencoder.add_modality`, vérifié par un test).
- **Deux vues de chaque signal** : par rapport à tout le monde, ce qui garde le niveau de la personne, et par rapport à sa propre normale, ce qui efface ses habitudes. Sa normale est calculée sur ses quatorze premiers jours, puis figée.
- **A est un comité de cinq petits réseaux**, et il prédit aussi si le patient répondra. La réponse est un signal bien plus net que la récompense. Là où les cinq ne sont pas d'accord, A ne sait pas.
- **B s'entraîne sur l'avis prudent de A** : la moyenne du comité, moins son désaccord. Cela l'empêche d'aller chercher de bonnes notes là où A n'a jamais vu de données.
- **A reçoit la position d'une demande sous forme de « bosses »** le long de chaque axe. Sans cela, il n'apprend que des tendances droites, et B pousse tout au bout des axes (section 14).

Décidé pour B : il reçoit un nombre fixe de L(θ), relevés à des moments différents de la journée et de la semaine, le comportement en direct du patient, que L contient déjà mais de façon brouillée, et le vecteur personnel du patient.

**B ne reçoit pas le texte des centres d'intérêt** (décidé). Sa sortie sur l'axe des intérêts est une position entre les deux sujets, quels qu'ils soient : il n'a pas besoin de les connaître. Le texte sert ailleurs : au choix de la paire, à Gemini qui écrit la demande, et à la mesure qui vérifie sa position. Si des sujets trop proches posent un jour problème, la distance entre les deux pourra devenir une entrée de B : un seul nombre, pas du texte.

### Ce qui est général, ce qui est personnel

Un seul jeu de poids pour tout le monde, et un petit vecteur par patient. Jamais un réseau entier par patient, ni même une couche entière : un patient fournit une trentaine de réactions par mois, ce qui ne permet de régler qu'une poignée de nombres.

| Élément | Général ou personnel | Taille |
|---|---|---|
| Poids de l'autoencodeur, de A et de B | Général | Environ 45 000 nombres au total (section 13) |
| Vecteur du patient | Personnel | 8 nombres, lus par A et par B comme une entrée de plus |
| Normale du patient | Personnel | La moyenne et la dispersion de chacun de ses 25 signaux, pour normaliser θ. Ce sont des statistiques, pas des poids appris |

Décidé : la partie personnelle est réduite à un petit vecteur partagé par A et B. Sa taille, 8, est déléguée. Ce choix remplace une première version, qui donnait à A et à B une dernière couche par patient : 715 nombres pour B, bien trop pour si peu de réactions.

| | Poids généraux | Vecteur du patient |
|---|---|---|
| Données | Tous les patients, simulés puis réels | Celles du patient seulement |
| Moment | Hors ligne : avant le déploiement, puis chaque nuit ou chaque semaine | Après chaque réaction |
| Ce qu'il apprend | Ce qui vaut pour tous, dont la façon de lire un vecteur | L'écart de ce patient par rapport à la moyenne |
| Appris à partir de | Le journal de tous | L'erreur de prédiction de A sur ce patient |
| Vérification | Sur des patients jamais vus | Sur les semaines suivantes du même patient |

Un nouveau patient part d'un vecteur nul : il reçoit exactement le modèle général.

Le vecteur est appris à travers A, à partir de réactions réelles, et B se contente de le lire. B n'a donc aucune partie personnelle à entraîner, et A reste hors de la décision.

## 5. La décision : B seul

1. B, avec ses poids généraux et le vecteur du patient, sort la zone.
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

**3. Le réseau A, et les vecteurs des patients.**
Régression sur ce journal : contexte, demande et vecteur du patient en entrée ; en sortie, la note, et si le patient a répondu. Les poids de A et le vecteur de chaque patient simulé s'apprennent ensemble. La note que A apprend est calculée sur L(θ), comme elle le sera dans la vraie vie, et non sur l'état caché.

**4. Le réseau B.**
Pour chaque contexte, B lit le vecteur du patient et propose une zone. On tire huit demandes dedans, A les note, et on ajuste B pour faire monter la note prudente. Les plafonds de sécurité restent fixes. Trois fois sur dix, B est entraîné sans vecteur : c'est le cas d'un nouveau patient.

**5. On recommence les étapes 2 à 4**, en laissant B choisir sept zones sur dix, pour que A voie les régions où B va réellement. Le code fait deux passages.

```bash
uv run python -m ml.simulation --people 5000 --days 84 --out ml/data/sim_big
uv run python -m ml.nets.train       # écrit ml/weights
uv run python -m ml.nets.evaluate    # boucle fermée sur les patients de test
```

**6. Sur les patients réels.**

Après chaque réaction :

1. On calcule la récompense.
2. Le vecteur du patient fait quelques pas pour réduire l'erreur de prédiction de A sur tout l'historique de ce patient. Les poids de A et de B ne bougent pas.
3. B lit le nouveau vecteur à la décision suivante.

Régulièrement : A est réentraîné sur le journal de tous, puis B est réajusté contre A, puis le vecteur de chaque patient est recalculé en rejouant son historique.

Deux patients ne se contredisent plus dans B : ils n'ont pas le même vecteur, donc B les distingue.

Trois précautions :

- retenir le vecteur près de zéro, d'autant plus fort que le patient a peu de réactions ;
- pour un patient jamais vu, partir de zéro : c'est aussi ainsi qu'on évalue, en apprenant son vecteur sur ses premières semaines et en mesurant sur les suivantes ;
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
| A et B appris, avec un vecteur de 8 nombres par patient | `learn`, une règle écrite à la main, avec un seul décalage par patient | `ml/model.py` |
| Récompense de 0 à 100 sur des vecteurs | Différence signée de deux nombres | `backend/loop.py`, `backend/community.py` |
| Journal avec les positions sur tous les axes | Table `requests` avec `lam` et `effort` | `backend/store.py` |

Ce qui ne change pas : Gemini génère, chaque demande est mesurée puis filtrée, l'aidant choisit parmi trois, modifie ou écrit la sienne, et une demande hors zone est retenue. La mesure de λ (`lambda_position`, `ml/pipeline.py`) reste celle de l'axe λ.

Passer à la cible changera les deux contrats, API et ML : `theta` et `ZoneState` dans `backend/schemas.py`, `zone_for` et `learn` dans `ml/model.py`.

## 9. Proposé, à confirmer

- Un autoencodeur variationnel, pour que la distance à L_ref ait un sens.
- Une récompense qui compare L après à l'état attendu sans la demande, plutôt qu'à L avant. Les données simulées contiennent les deux (`reward` et `reward_counterfactual`), pour pouvoir comparer. L'équipe a gardé la première pour l'entraînement ; la seconde sert à mesurer les résultats, parce qu'elle isole l'effet de la demande.
- Les demandes passées et leurs notes ajoutées aux entrées de B.
- Un encodeur commun à A et B.
- À grande échelle : un Transformer sur l'historique du patient en entrée de A.

Deux propositions de cette liste sont désormais dans le code, parce que l'entraînement en avait besoin (section 14) :

- Pour A : prédire aussi si le patient répond, et fournir une incertitude (le désaccord du comité). Le délai de réponse n'est pas prédit.
- Figer la normale de chaque patient sur une période de référence : ses quatorze premiers jours.

## 10. À définir

- La grille de notation de chaque axe, pour mesurer une vraie demande écrite par Gemini ou par l'aidant.
- La règle de choix de la paire de centres d'intérêt.
- Le cas d'un vrai besoin sans lien avec les centres d'intérêt du patient.
- Le branchement d'une vraie montre : quelle voie d'accès aux données Garmin, et à quelle cadence.
- L'essai de capacité de B (largeur 16, 32, 64, 128) n'a pas été fait : B est en largeur 32.

## 11. θ, L et la récompense, en détail

Ces choix sont **délégués**. Ils sont appliqués par `ml/simulation/spec.py` et `ml/simulation/reward.py`.

### θ : 25 signaux, trois modalités

θ réunit ce qu'une montre Garmin Forerunner 965 mesure d'utile pour suivre une personne, plus son comportement dans l'app. Un relevé est pris à un instant : les signaux de la nuit et du jour y figurent avec leur dernière valeur connue.

Les signaux sont rangés par **modalité**, c'est-à-dire par source : la montre (19 signaux, blocs Instant, Journée, Nuit et Jour), les réponses dans l'app (3), la frappe (3). L'autoencodeur aura un encodeur par modalité. Ajouter une modalité plus tard revient à déclarer ses signaux dans `ml/simulation/spec.py` et à entraîner son encodeur : les réseaux A et B ne lisent que L, ils ne bougent pas.

Les trois signaux de frappe sont **décidés** par l'équipe le 14 novembre (« le rythme de frappe, la réactivité »). On n'enregistre que des durées et des comptes, jamais les caractères tapés.

| Bloc | Signal | Unité | Composante de l'état qui pèse le plus |
|---|---|---|---|
| Instant | `heart_rate` | bpm | Calme |
| Instant | `stress` | 0 à 100 | Calme |
| Instant | `body_battery` | 0 à 100 | Énergie |
| Instant | `respiration` | respirations par minute | Calme |
| Instant | `steps_last_hour` | pas | Activité |
| Journée | `steps_today` | pas | Activité |
| Journée | `intensity_minutes_today` | minutes | Activité |
| Journée | `floors_today` | étages | Activité |
| Journée | `outdoor_minutes_today` | minutes | Activité |
| Nuit | `sleep_hours` | heures | Sommeil |
| Nuit | `sleep_score` | 0 à 100 | Sommeil |
| Nuit | `deep_sleep_minutes` | minutes | Sommeil |
| Nuit | `rem_sleep_minutes` | minutes | Sommeil |
| Nuit | `awake_minutes` | minutes | Sommeil |
| Nuit | `bedtime_hour` | heures après midi | Rythme |
| Nuit | `wake_hour` | heure | Rythme |
| Nuit | `hrv_overnight_ms` | ms | Calme |
| Nuit | `spo2_sleep` | % | Sommeil |
| Jour | `resting_hr` | bpm | Énergie |
| App | `reply_rate_7d` | 0 à 1 | Engagement |
| App | `reply_delay_hours_7d` | heures | Engagement |
| App | `reply_length_7d` | caractères | Engagement |
| Frappe | `typing_correction_rate` | effacements pour 100 caractères | Sommeil |
| Frappe | `open_delay_minutes` | minutes entre la notification et l'ouverture | Engagement |
| Frappe | `first_key_delay_seconds` | secondes entre l'ouverture et la première touche | Énergie |

À savoir :

- Les signaux de frappe n'existent que les jours où la personne écrit dans l'app. Le reste du temps ils sont absents, comme une montre non portée.

- **La montre n'est pas un dispositif médical**, et Garmin le dit. Ces signaux décrivent un mode de vie, pas un diagnostic.
- Les minutes dehors viennent des activités enregistrées avec le GPS. La montre ne suit pas la position en continu.
- Non retenus : VO2max, charge et statut d'entraînement, score de préparation à l'entraînement. Ce sont des mesures sportives, lentes ou déduites des signaux déjà retenus.
- La mesure de l'oxygène pendant le sommeil est souvent désactivée, car elle vide la batterie. Le générateur la coupe chez une personne sur deux.

### L : 6 composantes

Vingt-cinq signaux, six composantes : une par groupe de signaux qui bougent ensemble. Chaque composante va de 0 à 1, et plus elle est haute, mieux la personne va. L'équipe a décidé de rester à six : la frappe nourrit des composantes existantes (sommeil, calme, engagement, énergie).

| Composante | Ce qu'elle décrit | Signaux qui la portent |
|---|---|---|
| Sommeil (`sleep`) | La qualité des nuits | Durée, score, sommeil profond, paradoxal, éveils, oxygène |
| Rythme (`rhythm`) | La régularité des horaires | Heure du coucher, heure du lever |
| Énergie (`energy`) | Les réserves de la personne | Body Battery, fréquence cardiaque de repos |
| Calme (`calm`) | La tension du système nerveux | Stress, variabilité cardiaque, fréquence cardiaque, respiration |
| Activité (`activity`) | Le mouvement et les sorties | Pas, minutes intensives, étages, minutes dehors |
| Engagement (`engagement`) | Le lien avec les autres dans l'app | Taux, délai et longueur des réponses |

Dans les données simulées, l'état caché a exactement ces six composantes. C'est ce que la tête supervisée de l'autoencodeur devra retrouver.

### Grille de temps et délai

- Quatre relevés par jour : 8 h, 13 h, 18 h et 22 h.
- Le réseau B lit sept jours, soit 28 relevés.
- dt vaut 24 heures : la nouvelle mesure se fait le lendemain, au même moment de la journée.

### Récompense

L_ref est une moyenne et une dispersion par composante, calculées sur les personnes saines. La distance d'un état à L_ref se compte en largeurs de cette dispersion :

```
d(L) = racine de la moyenne, sur les six composantes, de ((L − moyenne saine) / dispersion saine)²
```

Une personne saine typique est à une distance proche de 1. C'est ce qui fait de L_ref une région plutôt qu'un point.

```
gain       = (d_avant − d_après) / (d_avant + 1)
récompense = 50 + 150 · gain, ramenée entre 0 et 100
```

- 50 veut dire que rien n'a changé.
- Le « + 1 » évite qu'un patient déjà proche de L_ref fasse exploser le rapport.
- Une amélioration d'un tiers donne 100.

Dans les données simulées, la récompense est calculée sur l'état caché. Une fois l'autoencodeur entraîné, la même formule s'appliquera à L(θ).

## 12. Les générateurs : toutes les hypothèses

Les réseaux entraînés sur ces données apprendront ces règles, rien de plus. Chacune est une hypothèse, **déléguée**, à défendre ou à corriger.

```bash
uv run python -m ml.simulation --people 600 --days 56 --seed 0 --out ml/data/sim
```

La commande écrit `people.npz` (θ, masque, état caché, groupe, parcours, L_ref), `episodes.npz` (le journal) et `meta.json` (le sens de chaque colonne). Ces fichiers ne sont pas dans git.

### Les personnes et leur état (`ml/simulation/people.py`)

| Hypothèse | Valeur |
|---|---|
| Part de personnes saines | 40 % |
| Niveau moyen de l'état | Saines : 0,78 ± 0,05. Patients : 0,52 ± 0,09 |
| Parcours d'un patient | Stable 50 %, rechute 30 % (−0,22 en trois semaines), rétablissement 20 % (+0,15) |
| État d'un jour | Niveau propre + une part commune aux six composantes + une part propre à chacune, toutes deux corrélées d'un jour à l'autre |
| Habitudes | Besoin de sommeil, heure du coucher, fréquence cardiaque de repos, variabilité cardiaque, pas, longueur des réponses, façon de taper : tirés par personne, **sans lien avec l'état** |
| Signal | Habitude de la personne + effet de l'état + effet de l'heure + bruit |
| Frappe | Habitude de la personne (9 corrections pour 100 caractères, 18 minutes avant d'ouvrir, 8 secondes avant la première touche, en médiane), multipliée par un facteur qui grandit quand l'état baisse. Un patient typique est environ 1,7 fois au-dessus d'une personne saine, avec une forte variation d'un jour à l'autre |
| Ce qui pèse sur la frappe | Corrections : sommeil, puis calme. Délai d'ouverture : engagement. Délai avant la première touche : énergie |
| Données absentes | Montre non portée le jour (1 à 10 % des jours) ou la nuit (2 à 20 %), oxygène coupé chez une personne sur deux, 3 % de mesures instantanées perdues, 8 % des jours sans comportement dans l'app, frappe absente 10 à 50 % des jours selon la personne |

Les habitudes sans lien avec l'état sont ce qui oblige à normaliser θ par personne : deux personnes au même état n'ont pas les mêmes chiffres.

Simplification : le bloc « app » de θ est tiré de la composante d'engagement. Il n'est pas recalculé à partir des réponses du journal.

### Le patient simulé (`ml/simulation/patient.py`)

Chaque patient a ses propres règles, tirées au hasard. Les réseaux ne les voient jamais.

| Hypothèse | Règle |
|---|---|
| Ce qu'il supporte sur un axe de coût | Une base (0,10 à 0,30) plus une part de son état (0,50 à 0,90) |
| D'où vient ce qu'il supporte | Durée : énergie et sommeil. Échange : engagement. Exposition : calme. Démarrage : énergie |
| Ce qui lui convient sur l'axe des intérêts | 1 − pente × état moyen. Plus il va mal, plus c'est proche de ses intérêts |
| Ce qui lui convient sur l'axe concret | 0,95 − pente × état moyen. Plus il va mal, plus c'est concret |
| Dose | Une demande apporte d'autant plus qu'elle mobilise, tant qu'elle reste supportable |
| Surcharge | Au-delà de ce qu'il supporte, il répond bien moins, et la demande lui pèse |
| Sans réponse | Son état baisse légèrement |
| Durée d'un effet | Il en reste 75 % le lendemain |

### Le journal (`ml/simulation/episodes.py`)

- Un patient reçoit une demande 8 jours sur 10, à partir du huitième jour. Les jours sans demande montrent comment son état évolue tout seul.
- La zone est tirée au hasard, puis la demande est tirée dans la zone. C'est voulu : le réseau A doit voir de bonnes et de mauvaises demandes.
- Les personnes saines ne reçoivent pas de demandes.

**Boucle fermée.** `simulate_policy` fait vivre les mêmes patients avec une politique qui choisit les zones à la place du hasard. Chaque jour, on relève θ, puis la politique reçoit les relevés déjà faits et rend une zone par patient ; elle ne voit ni l'état caché ni l'avenir. C'est ce qui servira à comparer le réseau B à une zone au hasard, à la règle fixe et à un oracle (section 7), et à refaire un journal là où B va réellement (section 6, étape 5). L'oracle est la seule politique autorisée à lire la vérité cachée.

```python
from ml.simulation import generate
dataset = generate(n_people=600, n_days=56, seed=0, policy=ma_politique)
```

### Ce que donne le réglage par défaut

Avec 600 personnes, 56 jours et la graine 0 :

| Mesure | Valeur |
|---|---|
| Personnes | 217 saines, 383 patients |
| Relevés | 224 par personne, 25 signaux, 13,8 % de données absentes |
| Distance à L_ref | Saines : 0,93. Patients : 3,20 |
| Demandes | 14 703, dont 54 % reçoivent une réponse |
| Demandes supportables | 46 % du journal, 73 % de réponses |
| Demandes trop lourdes | 15 % de réponses |
| Récompense | Moyenne 49,0, écart-type 14,8 |

Parmi les demandes supportables, la récompense suit bien la qualité du placement :

| Placement de la demande | Réponses | Récompense | Récompense contre l'état attendu |
|---|---|---|---|
| Loin de ce qui convient | 62 % | 46,9 | 48,8 |
| Moyen | 77 % | 50,3 | 53,3 |
| Proche de ce qui convient | 90 % | 56,6 | 59,8 |

L'écart-type de 14,8 est du même ordre que ces différences : l'état d'un patient bouge tout seul d'un jour à l'autre, et une seule récompense dit peu. Le réseau A aura besoin de beaucoup d'épisodes, ce qui est aussi vrai dans la réalité.

## 13. Tailles des réseaux et quantité de données

Rester petit est **décidé** ; le détail est **délégué**. Voici les réseaux tels qu'ils sont codés dans `ml/nets/models.py`.

| Réseau | Architecture | Paramètres |
|---|---|---|
| Autoencodeur | Un encodeur par modalité (montre : 57 → 48 → 32 ; app et frappe : 9 → 16 → 32), somme, puis 36 → 32 → 6. Décodeur : 10 → 32 → 64, puis une tête par modalité | 11 327 |
| B, le Transformer | 28 relevés de 10 valeurs, largeur 32, 2 couches, 4 têtes, puis une tête dense 84 → 48 → 11 | 23 019 |
| A | Comité de 5 réseaux denses, 82 → 64 → 64 → 2 chacun | 48 010 |
| **Total général** | | **82 356** |

- **Entrée d'un encodeur** : pour chaque signal de sa modalité, sa valeur par rapport à tout le monde, sa valeur par rapport à la normale de la personne, et un indicateur de présence. L'heure et le jour (4 valeurs) entrent à la fusion.
- **Entrée de B** : pour chacun des 28 relevés, L (6) et l'heure (4) ; puis le comportement en direct (les 6 signaux de l'app et de la frappe et leur présence, 12 valeurs) et le vecteur du patient (8).
- **Entrée de A** : le contexte (32 valeurs : L maintenant, sa moyenne et sa dispersion sur sept jours, le comportement en direct, l'heure), la demande (6 positions et 36 bosses) et le vecteur du patient (8).
- **Sortie de B** : 11 nombres, transformés en zone par `to_zone`, qui applique les plafonds de sécurité.
- Au moment de décider, seuls l'encodeur et B tournent, soit environ 28 000 paramètres : cela tient sur un téléphone.

Le total dépasse les 45 000 paramètres visés au départ, à cause du comité : un seul réseau A pèse 9 600 paramètres, et il y en a cinq. Ce choix est expliqué en section 14.

Pourquoi rester petit : les entrées sont peu nombreuses et le générateur est simple. Un réseau dix fois plus gros atteindrait la même erreur de validation, le reste étant du bruit.

**Essai de capacité**, pas encore fait : entraîner B en largeur 16, 32, 64 et 128 (`--width`), tracer la récompense obtenue en boucle fermée sur des patients jamais vus, et garder le plus petit réseau à partir duquel elle ne monte plus.

Il faudra grossir si les entrées s'enrichissent : le flux brut de la montre minute par minute, le texte des demandes et des réponses, ou des milliers de patients réels suivis pendant des mois.

### Quantité de données

L'unité qui compte est la personne, pas la ligne : les relevés d'une même personne se ressemblent, et le réseau doit marcher sur des gens qu'il n'a jamais vus.

- **Séparer par personne**, jamais par ligne : 70 % pour l'entraînement, 15 % pour la validation, 15 % pour le test, qui n'est regardé qu'une fois.
- **Le réglage par défaut est trop petit pour A et B** : 383 patients et 14 700 épisodes. Il sert aux essais rapides.
- **Pour entraîner** : 5 000 personnes sur 84 jours, soit 2 994 patients et 181 773 épisodes avec la graine 0. La commande prend une douzaine de secondes et écrit 85 Mo. Puis laisser les courbes dire s'il en faut plus.

```bash
uv run python -m ml.simulation --people 5000 --days 84
```

- **Le plancher de bruit de A** : l'état bouge tout seul, et cette part pèse environ 14 points d'écart-type sur la récompense (mesuré sur le jeu de 5 000 personnes). Même un réseau parfait garde donc une erreur de cet ordre. Un réseau qui descend nettement en dessous sur l'entraînement mémorise du bruit.
- **Plus de données ne règle pas tout** : un réseau peut surapprendre le simulateur lui-même, sa forme et ses liens simples. La parade est de garder un jeu de test produit avec des règles différentes.

## 14. Résultats de l'entraînement

Tout ce qui suit est mesuré **en simulation**, sur des personnes que les réseaux n'ont pas vues à l'entraînement. Ces chiffres disent que la machinerie apprend ce que le simulateur contient. Ils ne disent rien sur de vrais patients.

Le jeu : 5 000 personnes sur 84 jours (graine 0), séparées par personne en 70 % pour entraîner, 15 % pour régler et 15 % pour tester. L'entraînement complet prend 7 minutes sur un portable sans carte graphique. Les mesures brutes sont dans `ml/weights/meta.json`, `evaluation.json` et `evaluation_fresh.json`.

### L'autoencodeur

Écart entre L(θ) et l'état caché, sur les 750 personnes de réglage. Les deux vont de 0 à 1.

| Composante | Erreur |
|---|---|
| Sommeil | 0,062 |
| Rythme | 0,102 |
| Énergie | 0,073 |
| Calme | 0,062 |
| Activité | 0,063 |
| Engagement | 0,059 |
| **Moyenne** | **0,070** |

Une réponse au hasard donnerait 0,199, la dispersion de l'état caché. Le rythme est le plus mal lu : il ne s'exprime que par la régularité du coucher, qu'un seul relevé montre mal.

Ce que chaque modalité apporte, en erreur moyenne :

| Ce que l'autoencodeur voit | Erreur |
|---|---|
| Tout | 0,070 |
| Tout sauf la frappe | 0,070 |
| Tout sauf les réponses dans l'app | 0,080 |
| La montre seule | 0,081 |
| Tout sauf la montre | 0,113 |
| Les réponses dans l'app seules | 0,118 |
| La frappe seule | 0,159 |

- **Quand la montre est là, la frappe n'ajoute presque rien.** Elle ne sert que si le reste manque, et alors elle lit l'état à peine mieux que le hasard.
- **Sans montre, l'état reste lisible** (0,113), surtout grâce aux réponses dans l'app.
- Un signal caché à l'entraînement est reconstruit avec 38 % d'erreur en moins que si l'on supposait la valeur habituelle de la personne.

### La récompense mesurée sur L

Dans la vraie vie, la récompense se calcule sur L(θ), pas sur l'état caché. Le réseau A est donc entraîné sur cette récompense-là.

| Récompense | Écart-type | Corrélation avec la récompense sur l'état caché |
|---|---|---|
| Sur l'état caché | 14,6 | 1 |
| Sur L, au même relevé 24 h après (retenue) | 23,2 | 0,59 |
| Sur L, en moyenne sur la journée | 22,1 | 0,63 |

La mesure sur L est nettement plus bruitée. Elle suffit pourtant à A, qui moyenne sur plus de cent mille demandes.

### Le réseau A

Sur les patients de réglage. L'« avantage » d'une demande est ce que A en attend de plus que d'une demande au hasard dans le même contexte : c'est ce qui guide B.

| Mesure | Valeur |
|---|---|
| Corrélation entre l'avantage prédit et la vraie récompense | 0,49 |
| Vraie récompense des demandes que A préfère (le meilleur cinquième) | 55,4 |
| Vraie récompense de celles qu'il déconseille (le pire cinquième) | 45,5 |
| Erreur sur la récompense : valeur constante, A général, A avec vecteur | 22,8 / 21,7 / 21,4 |

La « vraie récompense » est ici celle qui compare l'état du lendemain à l'état attendu sans la demande : elle isole l'effet de la demande.

### Le réseau B, en boucle fermée

Chaque politique fait vivre les mêmes patients pendant 84 jours, avec les mêmes tirages. Seules les zones changent. Les réseaux ne voient que θ.

Sur 927 patients **entièrement nouveaux**, tirés avec une autre graine et regardés une seule fois, tous réglages arrêtés :

| Politique | Récompense de la demande | Réponses | Demandes trop lourdes | Gain d'état |
|---|---|---|---|---|
| Zone au hasard | 49,8 | 54 % | 55 % | −1,1 |
| Règle fixe du code actuel | 54,5 | 74 % | 47 % | 4,2 |
| **Réseau B, sans vecteur personnel** | **60,1** | **92 %** | **35 %** | **11,5** |
| Réseau B, avec vecteur personnel | 60,1 | 92 % | 31 % | 11,4 |
| Oracle, qui lit la vérité cachée | 59,8 | 96 % | 0 % | 15,8 |

- **Récompense de la demande** : contre l'état attendu sans elle. 50 veut dire qu'elle n'a rien changé.
- **Gain d'état** : ce que les demandes ont ajouté à l'état des patients sur les quatre dernières semaines, en centièmes. C'est la mesure la plus parlante.
- Sur les 452 patients de test du jeu d'origine, les chiffres sont les mêmes à 0,7 point près. Ce groupe a été consulté plusieurs fois pendant la mise au point : il ne compte plus comme un test.

Ce qu'on peut en dire :

- **B fait nettement mieux que la règle fixe** : presque trois fois son gain d'état, et 92 % de réponses au lieu de 74 %.
- **B atteint les trois quarts du gain de l'oracle** sans rien voir de caché.
- **Le vecteur personnel n'apporte pas de gain mesurable ici.** Avec une soixantaine de réactions bruitées par patient, il ne dégrade rien, mais il n'améliore ni la récompense ni la prédiction des réponses. Il réduit seulement la part des demandes trop lourdes, de 35 à 31 %.
- **L'oracle n'est pas un maximum.** Il vise ce qui convient au patient sans jamais le surcharger. Ses patients vont mieux, donc chaque demande a moins de chemin à leur faire parcourir : sa récompense par demande plafonne.

### Ce qui n'a pas marché, et pourquoi le code a changé

La première version suivait la section 13 d'origine : un seul réseau A, qui recevait la position brute de la demande. En boucle fermée, B faisait alors **moins bien que la règle fixe** (50,9 contre 54,2 sur les patients de test).

1. **A n'apprenait que des tendances droites.** Les données montrent un optimum au milieu des axes ; A en retenait « plus c'est proche des intérêts du patient, mieux c'est », et B poussait tout au bout de l'axe. Remède : les bosses. La corrélation entre l'avantage prédit et la vérité passe de 0,39 à 0,49.
2. **B allait là où A n'avait pas de données.** Remède : le comité, l'avis prudent, et un second passage où B choisit sept zones sur dix.
3. **Les vecteurs personnels apprenaient du bruit** et dégradaient B. Remède : A prédit aussi la réponse, signal plus net, et les vecteurs sont retenus bien plus fort près de zéro.

### Limites

- **Tout est simulé.** Les réseaux retrouvent les règles de `ml/simulation`, écrites à la main. La règle fixe et le simulateur partagent la même hypothèse sur l'axe des intérêts (plus le patient va mal, plus la demande se rapproche de ses intérêts) : l'avance de B sur cet axe ne prouve donc rien, et son gain vient surtout des axes de coût et d'une zone plus étroite.
- **Un seul entraînement, une seule graine.** L'écart entre deux entraînements n'est pas mesuré.
- **L'essai de capacité n'est pas fait**, ni le test sur des règles de simulateur différentes (section 13).
- **Les axes d'une vraie demande ne sont pas encore notés par un modèle.** Dans l'app, cinq des six positions viennent du format de la demande (`ml/formats.py`), posées à la main.
