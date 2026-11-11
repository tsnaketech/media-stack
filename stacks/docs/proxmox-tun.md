# Autoriser TUN dans le LXC Proxmox

Cette procédure prépare le périphérique `/dev/net/tun` pour Gluetun dans le
LXC **104**, qui héberge Docker. Adapter ce numéro pour une autre installation.
Les commandes des étapes 1 à 5 s’exécutent **sur Proxmox, en root**, pas dans le
LXC ni dans un conteneur Docker.

Le redémarrage du LXC interrompt temporairement ses services Docker. Prévoir cette
interruption avant l’étape 4. Le serveur Proxmox lui-même reste en fonctionnement.

## Comprendre le passage du périphérique

TUN est un périphérique virtuel Linux utilisé par les logiciels de tunnel VPN.
Son nœud `/dev/net/tun` est un périphérique caractère identifié par **10:200**.
Deux réglages complémentaires sont nécessaires dans le LXC :

- autoriser l’utilisation du périphérique dans son groupe de contrôle ;
- monter le nœud de Proxmox dans son système de fichiers.

Docker le transmet ensuite à Gluetun grâce à `devices` et à la capacité
`NET_ADMIN` déjà déclarées dans [le Compose VPN](../vpn/docker-compose.yml).

## 1. Charger TUN sur Proxmox

```sh
modprobe tun
ls -l /dev/net/tun
```

La sortie doit commencer par `c` et contenir `10, 200`. Pour charger le module aux
prochains démarrages du serveur :

```sh
printf 'tun\n' > /etc/modules-load.d/tun.conf
```

Si le nœud est toujours absent, résoudre ce point sur Proxmox avant de poursuivre.

## 2. Sauvegarder la configuration du LXC

```sh
cp /etc/pve/lxc/104.conf "/root/104.conf.before-tun-$(date +%Y%m%d-%H%M%S)"
```

Le nom daté conserve un exemplaire distinct de la configuration existante.

## 3. Ajouter l’autorisation et le montage

```sh
nano /etc/pve/lxc/104.conf
```

Ajouter les deux lignes suivantes si elles ne sont pas déjà présentes, en
conservant les autres paramètres :

```ini
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

| Réglage | Rôle |
| --- | --- |
| `c 10:200 rwm` | Autorise l’accès au périphérique caractère TUN dans le LXC. |
| `/dev/net/tun` | Chemin du périphérique sur Proxmox. |
| `dev/net/tun` | Chemin de destination relatif à la racine du LXC. |
| `bind,create=file` | Monte le nœud existant et prépare son emplacement de destination. |

Cette syntaxe vise une installation utilisant **cgroup v2**. Elle ne nécessite
pas de convertir le LXC en conteneur privilégié ni de désactiver AppArmor.

## 4. Arrêter puis démarrer le LXC

```sh
pct shutdown 104
pct status 104
```

Attendre que son état soit `stopped`, puis démarrer :

```sh
pct start 104
```

Un arrêt/démarrage complet recharge la configuration LXC, y compris le montage.
Les services Docker ayant une politique de redémarrage adaptée reviennent ensuite.

## 5. Vérifier depuis Proxmox

```sh
pct exec 104 -- sh -c 'test -c /dev/net/tun && ls -l /dev/net/tun'
```

La commande doit réussir et afficher un périphérique caractère avec **10, 200**.
Dans un LXC non privilégié, l’affichage `nobody:nogroup` peut résulter du mapping
des identifiants : vérifier le type de périphérique et les droits d’accès.

## 6. Vérifier le Compose dans le LXC

À partir d’ici, exécuter **dans le LXC 104** :

```sh
cd /opt/media-stack/stacks
test -c /dev/net/tun
python3 scripts/stack-compose.py vpn config --quiet
```

L’accès à TUN prépare seulement le périphérique. Pour établir le VPN, renseigner
également le fournisseur et ses secrets dans `vpn/.env`, puis suivre
[l’activation de Gluetun](../vpn/README.md#activation-et-vérification).

## Diagnostic et retour arrière

| Symptôme | Vérification |
| --- | --- |
| TUN absent sur Proxmox | Vérifier le résultat de `modprobe tun` et le périphérique hôte. |
| TUN présent sur Proxmox mais absent dans le LXC | Vérifier les deux lignes, le numéro du LXC et son arrêt/démarrage complet. |
| Docker ne trouve pas `/dev/net/tun` | Vérifier le périphérique dans le LXC avant de lancer le Compose. |
| Gluetun signale `Operation not permitted` | Vérifier l’autorisation cgroup du LXC, le montage et `NET_ADMIN` côté Docker. |
| TUN existe mais le VPN échoue | Vérifier ensuite les paramètres du fournisseur et les journaux Gluetun. |

Pour annuler le passage du périphérique, retirer les deux lignes ajoutées à
`104.conf`, puis effectuer un nouvel arrêt/démarrage du LXC. La sauvegarde datée
permet de comparer avec les réglages initiaux.

Références : [configuration LXC](https://github.com/lxc/lxc/blob/main/doc/lxc.container.conf.sgml.in),
[configuration des conteneurs Proxmox](https://pve.proxmox.com/pve-docs/pct.conf.5.html).
