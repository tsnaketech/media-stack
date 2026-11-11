# JDownloader 2

JDownloader est installé dans `download` avec l’image communautaire
[`jlesage/jdownloader-2`](https://github.com/jlesage/docker-jdownloader-2).
Son interface graphique est accessible dans un navigateur, sur le port `5800`.
L’accès local ne nécessite pas de compte MyJDownloader.
Les URL propres à une installation sont consignées dans sa documentation locale.

## Utilisation

Ouvrir `https://IP_DU_SERVEUR:5800`, puis se connecter avec
`JDOWNLOADER_USERNAME` et `JDOWNLOADER_PASSWORD` du `.env` privé de `download`.
L’interface utilise HTTPS, nécessaire au cookie de connexion sécurisé.
Les certificats locaux auto-signés peuvent provoquer une demande d’acceptation
dans le navigateur. La route Traefik utilise aussi HTTPS, avec redirection depuis HTTP.

Dans le collecteur de liens (LinkGrabber), ajouter l’URL de la page ou du fichier.
Vérifier les fichiers détectés avant de démarrer les téléchargements.
Une analyse approfondie peut extraire les liens d’une page non reconnue ;
la compatibilité, les CAPTCHA et la connexion à l’hébergeur dépendent du site.
Les comptes d’hébergeurs se règlent dans l’application et restent dans ses données privées.

### Coller un lien depuis Firefox

Si `Ctrl+V` ne transmet pas le presse-papiers du PC au bureau distant :

1. Ouvrir le panneau latéral de l’interface Web sur le bord gauche.
2. Coller le lien dans le champ **Clipboard** (presse-papiers).
3. Cliquer hors du champ pour transmettre son contenu au conteneur.
4. Revenir dans JDownloader, ouvrir **Ajouter des liens**, puis utiliser `Ctrl+V`.

La synchronisation automatique dépend du navigateur et de ses permissions.
Le champ Clipboard fournit une méthode manuelle sans modifier les réglages de Firefox.

## Stockage et variables

| Données | Conteneur | Hôte par défaut |
|---|---|---|
| Configuration, comptes et file | `/config` | `download/data/jdownloader` |
| Nouveaux téléchargements | `/output` | `/downloads/direct` |

`JDOWNLOADER_DOWNLOAD_PATH=/output` définit la destination native au démarrage.
Le hook `scripts/configure-jdownloader.sh` conserve les autres réglages.
`JDOWNLOADER_SUBFOLDERS=false` désactive les règles natives de sous-dossiers
par paquet et par site. Les paquets déjà en file peuvent conserver leur chemin
spécifique ; les ajuster dans l’interface.
Pour modifier le stockage hôte, régler `SHARED_DOWNLOADS_DIR` puis recréer le service.

Dans un LXC non privilégié, le démarrage nécessite aussi la traversée du dossier
`direct` par root du LXC, pour contrôler les droits avant de lancer l’application.
Si les ACL héritées ne l’autorisent pas, exécuter sur Proxmox, après création du dossier :

```sh
setfacl -m u:100000:--x /mnt/share/downloads/direct
```

Cette ACL donne uniquement la traversée ; UID 101000 conserve les droits d’écriture.
Adapter le chemin et les UID si le mappage LXC change.

### Accès depuis Windows via Samba

Le groupe `1000` des applications dans le LXC correspond au GID `101000` sur
Proxmox, et peut différer du groupe Samba du partage. Les nouveaux dossiers
peuvent donc être accessibles aux applications mais refusés au client Windows.

Identifier le compte Unix réellement utilisé par Samba, en tenant compte des
éventuels paramètres `force user` ou mappings d’utilisateurs du partage.
L’UID propriétaire d’une bibliothèque ne prouve pas l’identité du compte Samba.
Une ACL de lecture sur `direct` et ses descendants, avec héritage sur les dossiers,
conserve les propriétaires et les droits des applications. Exécuter **sur Proxmox**,
en remplaçant `sambauser` si nécessaire :

```sh
set -e
id sambauser
smb_uid=$(id -u sambauser)
acl_backup="/root/jdownloader-direct-acl-$(date +%Y%m%d-%H%M%S).txt"
getfacl -R -p /mnt/share/downloads/direct > "$acl_backup"
setfacl -R -m "u:${smb_uid}:r-X" /mnt/share/downloads/direct
find /mnt/share/downloads/direct -type d -exec setfacl -m "d:u:${smb_uid}:r-x" {} +
```

Les parents du partage doivent aussi autoriser la traversée. Cette correction
donne la lecture depuis Windows ; elle n’accorde pas l’écriture ou la suppression.
Voir le [guide des permissions](../../docs/permissions.md) pour le mapping des UID.

Les variables `JDOWNLOADER_*` de `download/.env.example` règlent la bibliothèque, la version,
la langue, l’umask, la mémoire Java et le compte Web. L’initialisation génère
un mot de passe privé pour une nouvelle installation ; génération manuelle :
`openssl rand -hex 24`. La limite Java de `256M` n’inclut pas la mémoire du bureau Web.
Après modification du `.env`, recréer le service.

## VPN et exploitation

JDownloader utilise `network_mode: "container:gluetun"` : le DNS, les routes et
le pare-feu appartiennent à Gluetun. Le service n’a pas de réseau ou port publié
propre. `JDOWNLOADER_PORT` et `JDOWNLOADER_WEB_BIND_IP` se règlent dans `vpn/.env` ;
le port interne `5800` figure dans `FIREWALL_INPUT_PORTS`. VNC externe et
MyJDownloader Direct Connection ne sont pas publiés.

Depuis la racine `stacks` :

```sh
python3 scripts/initialize.py prepare
./scripts/vpn-up.sh
python3 scripts/stack-compose.py download ps jdownloader
python3 scripts/stack-compose.py download logs --tail=60 jdownloader
docker exec gluetun readlink /proc/self/ns/net
docker exec jdownloader readlink /proc/self/ns/net
docker exec jdownloader curl -fsS --max-time 15 https://ipinfo.io/json
docker exec jdownloader curl -fsS --interface eth0 --connect-timeout 3 --max-time 5 https://1.1.1.1/cdn-cgi/trace
```

Les espaces réseau et sorties publiques doivent correspondre à Gluetun.
La requête forcée sur `eth0` doit échouer alors que la requête normale réussit.
Après chaque recréation de Gluetun, `vpn-up.sh` reconnecte les trois clients
à son nouvel espace réseau. L’interface peut rester accessible même si le
tunnel VPN est indisponible. Voir le [guide VPN](../../vpn/README.md).
