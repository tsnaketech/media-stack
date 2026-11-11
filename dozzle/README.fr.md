# Dozzle

[English](README.md) | **Français**

Consultation des journaux Docker sous `/opt/media-stack/dozzle`. Les URL directes et via
Traefik figurent dans le [README principal](../README.local.md). Le port hôte par défaut
est `9999`. Les réglages sont dans `.env`, avec modèle `.env.example` ; les
préférences persistantes sont dans `data/`, hors Git.

## Accès Docker

Le service `docker-proxy` filtre le socket avec LinuxServer socket-proxy.
L’accès de lecture aux conteneurs, journaux, événements et informations système
est activé ; `POST=0` bloque les mutations. Les actions et le terminal Dozzle
sont désactivés. Le proxy n’a aucun port publié et utilise le réseau interne
`infra-observability`, partagé avec Homepage pour l’état des conteneurs.
Dozzle rejoint aussi `proxy-network` pour son interface ; aucun VPN n’est nécessaire.

Aucune authentification n’est configurée : l’interface est réservée au LAN.
Elle peut afficher des données sensibles présentes dans les journaux.
Le filtre Docker bloque les écritures, pas la lecture de secrets éventuellement
exposés dans les métadonnées ou les logs des applications.

## Gestion

Depuis `/opt/media-stack`, avec `proxy-network` existant (créé par Traefik) :

```sh
python3 stacks/scripts/stack-compose.py dozzle config --quiet
python3 stacks/scripts/stack-compose.py dozzle up -d
python3 stacks/scripts/stack-compose.py dozzle ps
python3 stacks/scripts/stack-compose.py dozzle logs --tail=60
```

Ne pas supprimer le réseau Dozzle tant que Homepage l’utilise. Pour arrêter
seulement l’interface : `python3 stacks/scripts/stack-compose.py dozzle stop dozzle`.
Les scripts `stacks/scripts/stacks.sh` et `check-services.py` incluent Dozzle
avec `--with-infra`. Le démarrage de l’infrastructure suit l’ordre Traefik,
Arcane, Dozzle puis Homepage. Sauvegarder `.env` et `data/`.

Sources : [Dozzle](https://dozzle.dev/guide/getting-started),
[connexion au proxy](https://dozzle.dev/guide/remote-hosts),
[LinuxServer socket-proxy](https://docs.linuxserver.io/images/docker-socket-proxy/).
