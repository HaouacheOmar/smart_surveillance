smart_surveillance_project/
│
├── manage.py
├── requirements.txt
├── docker-compose.yml
│
├── config/                  # Configuration globale Django
│   ├── __init__.py
│   ├── settings.py          # Configuration (DB, SimpleJWT, DRF, etc.)
│   ├── urls.py              # Routeur central (regroupe les URLs des modules)
│   └── wsgi.py / asgi.py
│
├── modules/                 # Répertoire contenant tous les modules métiers
│   │
│   ├── authentication/      # Module 1 : Gestion des utilisateurs & JWT
│   │   ├── models.py        # Utilisateur personnalisé / Rôles (Admin, etc.)
│   │   ├── services.py      # Logique métier d'authentification
│   │   ├── serializers.py   # Sérialiseurs DRF (Login, Token refresh)
│   │   ├── views.py         # ViewSets pour l'authentification (SimpleJWT)
│   │   └── urls.py          # Routes du module
│   │
│   ├── cameras/             # Module 2 : Gestion des caméras et Mapping
│   │   ├── models.py        # Modèle Camera (IP, RTSP, Password chiffré)
│   │   ├── services.py      # Gestion des snapshots initiaux et configuration
│   │   ├── serializers.py   # CRUD Caméras & Mapping des Hallways/Caisses
│   │   ├── views.py         # ViewSets DRF pour la config admin
│   │   └── urls.py
│   │
│   ├── monitoring/          # Module 3 : État des caisses, couloirs & affichage LCD
│   │   ├── models.py        # Historique, états en temps réel (Hallway, Caisses, Occupations)
│   │   ├── services.py      # Traitement des métriques reçues de l'IA
│   │   ├── serializers.py   # Formats de données pour le LCD et le Dashboard
│   │   ├── views.py         # ViewSets pour l'affichage CCTV et front-end
│   │   └── urls.py
│   │
│   └── ai_bridge/           # Module 4 : Passerelle de communication avec FastAPI
│       ├── services.py      # Client pour interagir avec le service FastAPI (commandes RTSP, flux)
│       └── tasks.py         # Gestion des flux asynchrones (si nécessaire)
│
└── vision_service/          # Service IA séparé (Hébergé sur FastAPI)
    ├── main.py              # Point d'entrée FastAPI
    ├── model_loader.py      # Chargement de YOLO26 Pose + DeepSORT
    ├── tracker.py           # Logique de comptage, floutage facial & 4 coins
    └── requirements.txt     # Dépendances IA (Ultralytics, OpenCV, PyTorch, etc.)


Implementation.md - Spécifications Techniques
Ce document décrit l'architecture logicielle, la stack technique et les choix d'implémentation retenus pour le développement du Système Intelligent de Surveillance des Caisses et des Files d'Attente.

1. Architecture Globale (Monolithe Modulaire & Découplé)
Le projet adopte une architecture monolithique modulaire pour la partie métier et gestion, couplée à un service de vision par ordinateur indépendant et un frontend moderne.

Frontend : React (Interface utilisateur, Tableau de bord administrateur CCTV, affichage dynamique).

Backend (Métier & API) : Django (Monolithe Modulaire avec Django REST Framework).

Service IA (Traitement Vidéo) : FastAPI (Microservice dédié au traitement lourd des flux vidéo).

2. Stack Technique Détaillée
A. Frontend (Interface Utilisateur)
Framework : React (avec Vite).

Gestion des sessions : Communication par cookies sécurisés avec le backend (pas de stockage sensible en localStorage / sessionStorage).

B. Backend Principal (Django & DRF)
Framework : Django

API REST : Django REST Framework (DRF) utilisant systématiquement des ViewSet (ModelViewSet) pour structurer les endpoints par ressource.

Sécurité & Authentification : djangorestframework-simplejwt configuré avec des Cookies HttpOnly :

Access Token : Durée de vie courte (10 minutes).

Refresh Token : Durée de vie de 24 heures.

Les jetons sont stockés dans des cookies HttpOnly, Secure et SameSite pour immuniser l'application contre les attaques de type XSS.

Documentation API : drf-spectacular pour la génération automatique et interactive de la documentation Swagger UI / ReDoc.

C. Service de Vision par Ordinateur (IA)
Framework : FastAPI (hébergé séparément ou en conteneur dédié).

Modèles & Tracking :

YOLO26 Pose : Détection des personnes, estimation de pose (repérage des 4 coins du corps), et délimitation des zones (couloirs / caisses).

DeepSORT : Suivi multi-objets (multi-object tracking) pour le comptage précis et continu des personnes dans les files d'attente.

Fonctionnalités de confidentialité : Anonymisation automatique (floutage facial léger) des personnes tout en préservant le traçage géométrique des contours.

4. Flux de Fonctionnement et Sécurité
Phase de Configuration Initiale (Admin) :

L'administrateur se connecte via l'interface React. Le backend Django valide les identifiants et pose les cookies JWT HttpOnly.

L'admin ajoute les caméras (IP, URL RTSP, mot de passe) via les ViewSets DRF du module cameras.

Le système génère un premier snapshot pour permettre à l'administrateur de mapper visuellement les couloirs (hallways) et les caisses.

Phase de Traitement Vidéo (IA) :

Le service FastAPI récupère les flux RTSP configurés.

YOLO26 Pose + DeepSORT analysent les images en temps réel : application du floutage des visages, traçage des 4 coins des personnes, et délimitation colorée des caisses et couloirs.

Le service FastAPI pousse les métriques calculées vers le module Django monitoring.

Phase de Restitution :

Les informations d'occupation (ex. : caisse libre, nombre de personnes par couloir) sont envoyées en temps réel vers les écrans LCD et affichées sur le tableau de bord CCTV de l'interface React.