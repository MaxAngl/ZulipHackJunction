# Needed sur la montre (Connect IQ)

App Garmin pour Forerunner 965 (et Vívoactive 6), issue #27. Elle :

1. se lie au patient : la montre affiche un code à 6 chiffres, le patient le saisit dans l'app web (onglet Profile, carte « Garmin watch ») ;
2. envoie toutes les 30 s ses mesures du moment (fréquence cardiaque, stress, Body Battery, respiration, pas, étages, minutes intensives, FC de repos) sur `POST /api/watch/sync`, et le backend en tire θ ;
3. affiche la demande en attente ; START ouvre « Yes, I'll help » ou « Not now ».

Elle ne tourne que lorsqu'elle est ouverte : pas d'envoi en arrière-plan. Testée le 14/11 dans le simulateur (Forerunner 965, Vívoactive 6) et sur une vraie Forerunner 965.

## Prérequis (une fois)

- Java 17 : `winget install Microsoft.OpenJDK.17`.
- Le Connect IQ SDK Manager (developer.garmin.com/connect-iq/sdk), connecté au compte Garmin : télécharger le dernier SDK, puis dans l'onglet Devices chercher « 965 » pour ne prendre que la Forerunner 965 (sinon il télécharge toutes les montres).
- Une clé de développeur, **hors du repo**. Elle signe l'app : **les mises à jour d'une beta doivent être signées avec la même clé**, ne pas la perdre ni la commiter.

```bash
openssl genrsa -out developer_key.pem 4096
openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt
```

## HTTPS obligatoire, même dans le simulateur

La montre refuse le HTTP (message « Server needs HTTPS »). Pour le dev, un tunnel gratuit et sans compte suffit :

```bash
cloudflared tunnel --url http://localhost:8000
```

Il affiche une adresse `https://….trycloudflare.com`, qui change à chaque lancement. La mettre dans `resources/settings/properties.xml` (`ServerUrl`) avant de compiler, ou la régler dans l'app Garmin Connect (réglages de l'app Needed). Ne pas la commiter : elle ne dure que le temps du tunnel.

## Compiler et lancer dans le simulateur

Depuis la racine du repo, `monkeyc`, `monkeydo` et `simulator.exe` sont dans le dossier `bin` du SDK :

```bash
monkeyc -f watch/monkey.jungle -d fr965 -o watch/bin/needed.prg -y <clé>.der
simulator.exe        # le laisser ouvert : fermer le terminal qui l'a lancé le ferme aussi
monkeydo watch/bin/needed.prg fr965
```

`monkeydo` affiche les plantages de l'app avec la ligne fautive (exemple vu : `floorsClimbed` n'existe pas sur une montre sans altimètre, d'où les tests `has` dans `Readings.mc`).

## Installer sur la vraie montre, en beta (sans câble)

1. Paquet pour le Store : `monkeyc -f watch/monkey.jungle -e -o watch/bin/needed.iq -y <clé>.der`.
2. https://apps.garmin.com/developer/upload, avec le compte Garmin de la montre : envoyer `needed.iq`, version `0.1.0` (puis plus grande à chaque envoi), cocher **Beta App**. Une beta n'est visible que par ce compte et n'est pas relue par Garmin.
3. Fiche du Store : textes et images prêts dans `watch/store/` (`cover.png` 500 x 500, captures rondes 454 x 454). « Does your app collect user data? » : **Yes**, avec le lien vers `/privacy.html` du backend (`frontend/public/privacy.html`).
4. La beta n'apparaît pas dans la recherche du Store : passer par https://apps.garmin.com/developer/dashboard, ouvrir l'app et l'installer (ou ouvrir le lien de sa page sur le téléphone, dans Connect IQ).
5. Ouvrir Needed sur la montre et saisir son code dans le Profil du patient.

Plusieurs montres : chacune a son code et son jeton, et n'agit que pour le patient qui a saisi son code. Une montre par patient : en lier une autre remplace la première.
