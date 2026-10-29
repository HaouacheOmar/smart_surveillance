Spécifications Fonctionnelles : Système Intelligent de Surveillance des Files d'Attente et des Caisses
1. Vue d'ensemble du projet
Le système est une solution intelligente de vision par ordinateur conçue pour surveiller les couloirs (hallways) menant aux caisses d'un établissement. Il analyse en temps réel les flux vidéo des caméras de surveillance pour détecter l'occupation des caisses, compter les personnes en attente, et afficher ces informations de manière dynamique sur des écrans LCD ainsi que sur un tableau de bord administrateur (CCTV).

2. Rôles et Authentification
Authentification : Une page de connexion sécurisée est requise pour l'accès des utilisateurs (notamment l'administrateur).

Profil Administrateur : Il dispose des privilèges complets pour la configuration initiale, la gestion des caméras et la supervision en temps réel.

3. Fonctionnalités de l'Administrateur (Configuration Initiale & Gestion)
Lors de la première configuration ou de la maintenance, l'administrateur peut :

Gérer les caméras : Ajouter ou supprimer des flux vidéo en configurant les paramètres suivants :

Adresse IP

URL RTSP

Mot de passe d'authentification

Cartographie interactive : À l'aide d'une première capture d'écran (snapshot) générée par le système, l'administrateur effectue le mapping visuel en délimitant les zones des couloirs (hallways) et des caisses associées.

4. Logique de Détection et de Gestion des Files d'Attente
Association Couloir / Caisses : Un couloir peut contenir une ou plusieurs caisses.

Affichage de l'état des caisses : Le système évalue en temps réel si les caisses sont occupées ou vides et identifie les couloirs disposant de caisses libres.

Confidentialité et Détection (Vision par Ordinateur) :

Le flux vidéo d'analyse affiche les contours colorés distincts pour les couloirs, les caisses et les personnes.

Les personnes détectées subissent un flou facial léger (ou anonymisation du visage) pour garantir la protection de la vie privée, tout en conservant un encadrement précis (délimitation des quatre coins du corps/contour).

5. Restitution et Affichage en Temps Réel
Écrans LCD : Diffusion en temps réel des informations clés (ex. : "Caisse X occupée - Hallway Y - Nombre de personnes : Z" ou indication des caisses et couloirs vides).

Interface d'Administration (CCTV) : Un tableau de bord affichant le flux vidéo en direct avec des superpositions graphiques (bounding boxes colorées) pour le suivi des couloirs, des caisses et des clients.