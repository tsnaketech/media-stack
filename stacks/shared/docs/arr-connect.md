# Connexions arr vers Jellyfin

`Settings → Connect → Jellyfin` utilise le connecteur natif **Emby / Jellyfin**
dans Radarr et Sonarr. Dans Lidarr, un **Custom Script** appelle l’API
Jellyfin pour actualiser la bibliothèque musicale. Les imports, mises à niveau,
renommages et suppressions compatibles déclenchent une actualisation. Ce
mécanisme complète la surveillance temps réel de Jellyfin.

## Commande et variables

Depuis la racine `stacks`, après le démarrage des applications :

```sh
python3 scripts/configure-arr-connect.py
```

Le script est également appelé par `scripts/stacks.sh up`, après la configuration
de Jellyfin. Python 3 et la bibliothèque standard suffisent.

Dans `shared/.env` :

```dotenv
JELLYFIN_CONNECT_ENABLED=true
JELLYFIN_CONNECT_URL=http://jellyfin:8096
JELLYFIN_CONNECT_API_KEY=
JELLYFIN_CONNECT_LIDARR_ENABLED=true
JELLYFIN_CONNECT_LIDARR_MAP_TO=/media/music
JELLYFIN_CONNECT_RADARR_ENABLED=true
JELLYFIN_CONNECT_SONARR_ENABLED=true
JELLYFIN_CONNECT_RADARR_MAP_FROM=/movies
JELLYFIN_CONNECT_RADARR_MAP_TO=/media/movies
JELLYFIN_CONNECT_SONARR_MAP_FROM=/tv
JELLYFIN_CONNECT_SONARR_MAP_TO=/media/tv
```

L’URL est celle accessible depuis les conteneurs arr. Pour Jellyfin local, une clé
vide provoque la création ou réutilisation de la clé dédiée **Homelab Arr Connect**,
avec le compte administrateur déjà déclaré. La clé est enregistrée dans le `.env`
privé en mode `600`, sans être affichée. Une destination personnalisée nécessite
une clé explicitement fournie. Le script ne remplace pas une clé renseignée :
après révocation, renseigner la nouvelle clé ou vider cette variable pour la
régénérer localement.

Les correspondances traduisent les chemins des applications vers les chemins
vus par Jellyfin. Adapter les valeurs si les montages changent. Le script
Lidarr sélectionne la bibliothèque qui contient `JELLYFIN_CONNECT_LIDARR_MAP_TO`.
Il envoie un rafraîchissement récursif à cette bibliothèque. Sa configuration
privée est générée dans `music/data/lidarr/jellyfin-connect.json` en mode `600`.

Lors de la migration de Lidarr, le script remplace l’entrée native correspondante
par **Custom Script** en conservant son nom et ses tags. Le connecteur natif de
Lidarr appelait `/mediabrowser/Library/MediaFolders` lors des imports et recevait
`404` de Jellyfin. Recréer le conteneur Lidarr après ajout du montage du script,
puis relancer la commande de configuration.

`notify=false` désactive **Send Notifications**, non pris en charge par Jellyfin.
`updateLibrary=true` active **Update Library**. Les événements sans rapport avec
les modifications de bibliothèque sont désactivés pour cette connexion.

## Vérification et conservation

Le script teste toutes les connexions avant de créer ou modifier les entrées.
Il les retrouve par destination, conserve leurs noms et tags, et refuse les
doublons ou collisions de noms. Les autres connexions restent inchangées.
Relancer la commande après modification des variables. Une fois le montage
du script en place, les réglages de connexion sont appliqués via les API.

Mettre un indicateur `*_ENABLED=false` ignore la gestion correspondante, sans
supprimer ni désactiver une connexion déjà enregistrée. Vérifier dans chaque
application **Settings → Connect → Jellyfin → Test**. Les tests de connexion
confirment l’accès au serveur ; vérifier la visibilité dans Jellyfin après un
véritable import pour valider le flux complet.

Pour vérifier l’appel de rafraîchissement depuis Lidarr, exécuter depuis
`stacks` avec l’UID/GID applicatif de la stack musique.

```sh
python3 scripts/stack-compose.py music exec -T -u 1000:1000 \
  -e lidarr_eventtype=AlbumDownload lidarr /opt/refresh-lidarr-jellyfin.sh
```

Le script doit indiquer que Jellyfin a accepté la requête avec HTTP `204`.
