# Guide de Déploiement en Ligne Gratuit & Test Mobile (PWA)

Ce document explique comment héberger l'application **Needed** gratuitement en ligne avec HTTPS afin de l'essayer sur n'importe quel smartphone et de l'installer en tant que Web App (PWA).

---

## 1. Option recommandée : Hébergement Cloud Gratuit sur Render.com

Render offre un hébergement gratuit pour les applications conteneurisées (Docker) avec HTTPS automatique.

### Étapes (3 minutes) :

1. **Pousser les modifications sur GitHub** :
   ```bash
   git add .
   git commit -m "feat: support PWA mobile et configuration déploiement Docker / Render"
   git push origin main
   ```

2. **Créer le service sur Render** :
   - Rendez-vous sur [render.com](https://render.com) et connectez-vous (avec votre compte GitHub).
   - Cliquez sur **New +** > **Web Service**.
   - Choisissez **Build and deploy from a Git repository** et sélectionnez votre dépôt `ZulipHackJunction` (ou collez l'URL `https://github.com/MaxAngl/ZulipHackJunction`).
   - Donnez un nom (ex: `needed-app`).
   - L'environnement détecté sera automatiquement **Docker** (grâce au fichier `Dockerfile` à la racine).
   - Choisissez la région la plus proche (ex: **Frankfurt (EU)**) et sélectionnez le plan **Free**.
   - *(Optionnel)* Dans **Advanced > Environment Variables**, ajoutez votre variable `GEMINI_API_KEY` si vous souhaitez activer la génération dynamique par IA.
   - Cliquez sur **Deploy Web Service**.

3. **Accéder à l'application** :
   - Dès la fin du build (2-3 minutes), Render vous fournit une URL HTTPS sécurisée : `https://needed-app.onrender.com`.

---

## 2. Option alternative : Hugging Face Spaces (100% gratuit & permanent)

Hugging Face Spaces permet d'héberger des conteneurs Docker gratuitement sans carte bancaire :
1. Créez un nouveau Space sur [huggingface.co/spaces](https://huggingface.co/spaces).
2. Choisissez le SDK **Docker** (Blank).
3. Poussez le contenu de ce dépôt sur le Space Git.
4. L'application démarre automatiquement sur `https://<nom-du-space>.hf.space`.

---

## 3. Option Immédiate : Tunnel HTTPS instantané depuis votre PC

Si vous voulez **immédiatement tester sur vos smartphones** sans attendre de créer un compte cloud :

1. Lancez le serveur local :
   ```bash
   cd ZulipHackJunction
   uv run uvicorn backend.main:app --port 8000
   ```

2. Dans un second terminal, ouvrez un tunnel HTTPS public :
   ```bash
   npx --yes localtunnel --port 8000
   ```
   *Vous obtiendrez une URL publique `https://xxxx.loca.lt` accessible depuis n'importe quel téléphone connecté à 4G/5G ou Wi-Fi.*

---

## 4. Comment installer la Web App (PWA) sur votre téléphone

Grâce aux fichiers `manifest.webmanifest`, `sw.js` et aux icônes ajoutés au projet :

### Sur Android (Google Chrome) :
1. Ouvrez l'URL HTTPS sur Chrome.
2. Un bandeau **"Ajouter Needed à l'écran d'accueil"** s'affiche automatiquement en bas de l'écran (ou appuyez sur le menu `⋮` en haut à droite > **Installer l'application**).
3. L'icône Needed s'ajoute à votre écran d'accueil et s'ouvre en plein écran comme une application native.

### Sur iPhone / iPad (Safari) :
1. Ouvrez l'URL HTTPS dans **Safari** (important : Safari est requis pour installer une PWA sur iOS).
2. Appuyez sur le bouton **Partager** (l'icône avec un carré et une flèche vers le haut).
3. Faites défiler vers le bas et appuyez sur **Sur l'écran d'accueil** (Add to Home Screen).
4. Appuyez sur **Ajouter**. L'application Needed s'affiche sur votre bureau iOS sans barre d'adresse Safari.
