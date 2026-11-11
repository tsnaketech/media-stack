# Droits des bibliothèques : Proxmox, LXC et Docker

Les URL ci-dessous utilisent `IP_DU_SERVEUR`, à remplacer par l’adresse de votre hôte.

Cette procédure illustre un LXC non privilégié hébergeant Docker. Les blocs
indiquent où exécuter les commandes. Sur Proxmox, définir `CT_ID` avec son numéro :

```bash
CT_ID=YOUR_CT_ID
```

Les chemins `/srv/media/library` et `/srv/media/downloads` sont des exemples à
adapter au stockage de l’hôte. Les valeurs `1000:1000` supposent les UID/GID par
défaut des applications : les adapter si les fichiers `.env` ou le mapping LXC
changent. Les commandes de correction sont
à utiliser en cas de besoin, pas à relancer systématiquement au démarrage.

## 1. Comprendre les chemins et les identifiants

| Niveau | Exemple pour la musique |
|---|---|
| Proxmox | `/srv/media/library/music` |
| LXC | `/media/music` |
| Lidarr / Navidrome | `/music` |

Le montage du LXC est `mp0: /srv/media/library,mp=/media`.

Pour le configurer, exécuter **sur Proxmox**, après vérification de `pct config "$CT_ID"`
pour ne pas remplacer un autre montage existant :

```bash
pct set "$CT_ID" -mp0 /srv/media/library,mp=/media
```

Après application du montage (redémarrer le LXC si nécessaire), vérifier :

```bash
pct config "$CT_ID"
pct exec "$CT_ID" -- findmnt -T /media
```

Les sous-dossiers `music`, `movies`, `tv`, `books` et `audiobooks` sont
alors accessibles sous `/media` dans le LXC, selon leurs ACL. Le montage des
téléchargements `mp1` est décrit dans le [guide du stockage](downloads-storage.md).

Le LXC est non privilégié : ses identifiants sont traduits côté Proxmox.

| Identifiant dans le LXC | Identifiant sur Proxmox avec le mapping par défaut |
|---|---|
| UID 0, root du LXC / moteur Docker | UID 100000 |
| UID 1000, utilisateur des applications | UID 101000 |
| GID 1000, groupe des applications | GID 101000 |

Un groupe **1000 sur Proxmox** ne correspond donc pas au groupe
1000 du LXC. L'ACL nominative `user:101000` accorde les droits à l'utilisateur
applicatif sans changer le propriétaire ou le groupe utilisés par Samba.
Un propriétaire ou groupe hors mapping peut apparaître comme `nobody` ou
`nogroup` dans le LXC ; ce nom seul ne permet pas de conclure à un refus d'accès.

**Sur Proxmox**, vérifier avant de corriger :

```bash
pct config "$CT_ID"
pct exec "$CT_ID" -- cat /proc/self/uid_map
pct exec "$CT_ID" -- cat /proc/self/gid_map
ls -ldn /srv/media/library /srv/media/library/music
getfacl -n /srv/media/library/music
```

La ligne `0 100000 65536` indique que l'intervalle d'identifiants du LXC
commençant à 0 est traduit vers celui commençant à 100000 sur l'hôte.

## 2. Lire les droits et les ACL

Sur un dossier, `r` permet de lister les noms, `w` d'ajouter ou retirer des
entrées, et `x` de traverser le dossier pour atteindre ses éléments. Chaque
parent du chemin doit pouvoir être traversé. Un fichier demande ses propres
droits de lecture ou d'écriture ; la suppression dépend surtout du dossier parent.

Dans `drwxrws---+`, le `s` du groupe est le bit setgid : les nouveaux éléments
héritent du groupe du dossier. Le `+` indique des ACL supplémentaires.

Dans la sortie de `getfacl` :

- `user:101000:rwx` s'applique au dossier ou fichier actuel.
- `default:user:101000:rwx` définit l'héritage pour les nouveaux éléments ; cette
  entrée ne donne pas à elle seule accès au dossier actuel.
- `mask::` limite les droits effectifs des utilisateurs nommés et des groupes.
  Une annotation `#effective:` signale des droits limités par ce masque.

`setfacl -m` ajoute ou modifie une entrée ; `-R` traite les éléments existants.
Le `X` majuscule accorde l'exécution aux dossiers et aux fichiers déjà exécutables,
sans rendre tous les fichiers musicaux exécutables. `setfacl` recalcule normalement
le masque : vérifier les autres entrées après modification, car leurs droits
effectifs peuvent aussi évoluer.

## 3. Sauvegarder les ACL avant modification

**Sur Proxmox**, choisir un nouveau nom de sauvegarde :

```bash
acl_backup="/root/media-acl-$(date +%Y%m%d-%H%M%S).txt"
getfacl -R -p /srv/media/library > "$acl_backup"
printf 'Sauvegarde ACL : %s\n' "$acl_backup"
```

`-p` conserve les chemins absolus. Pour restaurer ce relevé, remplacer le chemin
ci-dessous par le fichier sauvegardé :

```bash
setfacl --restore=/root/media-acl-YYYYMMDD-HHMMSS.txt
```

La restauration peut aussi rétablir les propriétaires, groupes et indicateurs
consignés. Elle ne restaure pas les fichiers supprimés et ne couvre pas les
nouveaux fichiers absents du relevé.

## 4. Donner accès aux applications

**Sur Proxmox**, ces commandes reproduisent les droits appliqués aux bibliothèques.
Elles conservent les propriétaires et les groupes existants :

```bash
# Traverser le dossier parent.
setfacl -m u:101000:--x /srv/media/library

# Autoriser l'accès aux éléments existants.
setfacl -R -m u:101000:rwX \
  /srv/media/library/{music,movies,tv,books,audiobooks}

# Définir l'héritage sur tous les dossiers existants.
find /srv/media/library/{music,movies,tv,books,audiobooks} -type d \
  -exec setfacl -m d:u:101000:rwx {} +
```

Les accolades nécessitent Bash. Les dossiers doivent déjà exister.
L'héritage reste soumis aux permissions demandées à la création : un logiciel
créant des fichiers très restrictifs ou les déplaçant depuis un autre dossier
peut nécessiter une vérification supplémentaire.

Les bibliothèques ont reçu l'accès en écriture lors de l'installation. Pour un
service uniquement lecteur, une ACL `r-X` et une ACL par défaut `r-x` permettent
une politique plus restrictive. Audiobookshelf est déjà monté en lecture seule
par Compose : l'ACL de l'hôte ne peut pas lever cette restriction Docker.

## 5. Permettre au moteur Docker de préparer un montage

L'accès de l'application et celui du moteur Docker sont distincts. Si Docker
échoue en préparant `/media/music` alors que l'UID 1000 peut y écrire, vérifier
la traversée du chemin par root du LXC.

**Sur Proxmox**, pour la musique uniquement :

```bash
setfacl -m u:100000:--x /srv/media/library
setfacl -m u:100000:r-x /srv/media/library/music
pct exec "$CT_ID" -- stat /media/music
```

Le `r-x` sur la musique donne à root du LXC la lecture et la traversée du dossier.
Pour un simple besoin de traversée, `--x` peut suffire. Ne pas appliquer les droits
de root récursivement à toutes les bibliothèques sans besoin identifié.

**Limite d'isolation :** un autre LXC utilisant le même mapping peut aussi traduire
son root en UID 100000 et son utilisateur 1000 en UID 101000. Ces ACL identifient
des UID hôte, pas un numéro de LXC. Elles peuvent donc profiter à un autre LXC si
le même chemin lui est exposé. Une séparation stricte nécessite des identifiants
hôte distincts et un mapping dédié, avec adaptation des permissions existantes.

## 6. Corriger les données locales des applications

**Dans le LXC**, `chown 1000:1000` concerne les données locales sous `/opt`.
Ne pas remplacer les ACL du partage Samba par un `chown -R` global.

Exemple pour Navidrome, dont `/data` doit être accessible en écriture :

```bash
cd /opt/media-stack/stacks/music
docker compose stop navidrome
mkdir -p data/navidrome
chown -R 1000:1000 data/navidrome
docker compose up -d navidrome
```

Pour les téléchargements partagés, préparer les dossiers sans changer
récursivement les propriétaires des téléchargements existants :

```bash
mkdir -p /downloads/{music,movies,tv}
chown 1000:1000 /downloads /downloads/{music,movies,tv}
```

Les images LinuxServer utilisent `PUID`/`PGID`. Navidrome et Audiobookshelf
utilisent la directive Compose `user: "1000:1000"` ; leurs variables `PUID`/`PGID`
ne configurent pas directement l'utilisateur de leur processus.

## 7. Tester avec l'utilisateur réel

**Sur Proxmox**, vérifier l'écriture de l'UID 1000 du LXC, sans utiliser root
pour la création du fichier de test :

```bash
pct exec "$CT_ID" -- setpriv --reuid=1000 --regid=1000 --clear-groups \
  sh -c 'f=$(mktemp /media/music/.permission-test.XXXXXX) && rm -- "$f"'
```

L'absence d'erreur indique que création et suppression ont réussi. Un nom
commençant par `.` est caché ; utiliser `ls -lan` pour l'afficher si un test manuel
l'a laissé en place.

**Dans le LXC**, vérifier aussi le volume réellement exposé à Radarr :

```bash
cd /opt/media-stack/stacks
python3 scripts/stack-compose.py movie exec -T -u 1000:1000 radarr \
  sh -c 'f=$(mktemp /movies/.permission-test.XXXXXX) && rm -- "$f"'
python3 scripts/stack-compose.py audiobook exec -T audiobookshelf \
  sh -c 'ls /audiobooks >/dev/null'
```

Le premier test écrit un petit fichier temporaire ; le second vérifie seulement
la lecture. Adapter le chemin et le service à la bibliothèque concernée.

## 8. Distinguer les erreurs

| Message | Vérification prioritaire |
|---|---|
| `File exists` avec `mkdir` | Le dossier existe ; `mkdir -p` accepte ce cas. |
| `Permission denied` | UID réel, traversée des parents, ACL et masque. |
| `Read-only file system` | Options du montage Proxmox/LXC et suffixe Docker `:ro`. |
| Navidrome ne peut ouvrir sa base | Droits du dossier local `data/navidrome` monté sous `/data`. |
| Lidarr : `unable to set supplementary group list` | Capacités Docker, notamment un éventuel `cap_drop: ALL`. |

**Sur Proxmox**, pour une erreur de lecture seule :

```bash
findmnt -T /srv/media/library/music -o TARGET,SOURCE,FSTYPE,OPTIONS
pct exec "$CT_ID" -- findmnt -T /media/music -o TARGET,SOURCE,FSTYPE,OPTIONS
```

Une ACL ne rend pas un montage `ro` inscriptible. Après une modification de
montage nécessitant un arrêt/démarrage du LXC, planifier cette interruption et
vérifier ensuite les options effectives. Ajouter `:rw` dans Compose ne peut pas
rendre inscriptible un système de fichiers sous-jacent en lecture seule.

## 9. Donner accès aux partages Samba depuis Windows

Exécuter ce bloc **sur Proxmox**, dans Bash. Utiliser le compte Unix du
partage Samba dans `SAMBA_USER`. Le bloc applique
une ACL nominative de lecture à la bibliothèque et aux téléchargements, puis
configure son héritage sur les dossiers existants.

```bash
SAMBA_USER=YOUR_SAMBA_USER
if smb_uid=$(id -u "$SAMBA_USER"); then
  share_dirs=(/srv/media/library /srv/media/downloads)

  setfacl -R -P -m "u:${smb_uid}:r-X" "${share_dirs[@]}" &&
    find "${share_dirs[@]}" -type d \
      -exec setfacl -m "d:u:${smb_uid}:r-x" {} + &&
    runuser -u "$SAMBA_USER" -- ls -l "${share_dirs[@]}"
fi
```

`r-X` donne la lecture des fichiers et la traversée des dossiers.
Cette commande remplace l’entrée ACL du compte Samba lorsqu’elle existe déjà.
Les ACL par défaut s’appliquent aux nouveaux éléments créés dans les dossiers.
La dernière commande vérifie que le compte Samba peut lister les deux racines.

## Références

- [Conteneurs non privilégiés Proxmox](https://pve.proxmox.com/wiki/Unprivileged_LXC_containers)
- [Manuel setfacl](https://man7.org/linux/man-pages/man1/setfacl.1.html)
- [Manuel getfacl](https://man7.org/linux/man-pages/man1/getfacl.1.html)
