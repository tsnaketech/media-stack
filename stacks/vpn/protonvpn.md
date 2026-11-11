# Proton VPN Plus avec Gluetun

Le projet utilisé est [passteque/gluetun](https://github.com/passteque/gluetun).
Son dépôt a changé de nom, mais l’image officielle reste
`qmcgaw/gluetun:latest`, comme indiqué dans son README.

La stack utilise WireGuard, des serveurs Proton compatibles P2P en Belgique et
le pare-feu intégré de Gluetun. Le passage de TUN du LXC vers un conteneur Docker
avec `NET_ADMIN` a été testé : création et suppression d’une interface temporaire,
sans connexion à un serveur VPN.

## Obtenir les paramètres Proton

1. Ouvrir [le générateur WireGuard Proton](https://account.proton.me/u/0/vpn/WireGuard).
2. Donner un nom à la configuration, par exemple `homelab-gluetun`, et choisir
   la plateforme Linux ainsi qu’un serveur Belgique compatible P2P.
3. Générer et télécharger le fichier de configuration.
4. Dans sa section `[Interface]`, relever **PrivateKey** et **Address**.

Conserver ce fichier comme un secret. La clé privée WireGuard est distincte du
mot de passe du compte Proton et de la clé publique du serveur.
[Guide officiel Proton](https://protonvpn.com/support/wireguard-configurations).

## Remplir le `.env` local

Dans le LXC, modifier `/opt/media-stack/stacks/vpn/.env` :

```dotenv
VPN_SERVICE_PROVIDER=protonvpn
VPN_TYPE=wireguard
SERVER_COUNTRIES=Belgium
FREE_ONLY=off
PORT_FORWARD_ONLY=on
WIREGUARD_PRIVATE_KEY='replace-with-PrivateKey'
WIREGUARD_ADDRESSES='10.2.0.2/32'
VPN_PORT_FORWARDING=off
```

Remplacer la clé et adapter l’adresse à la valeur `Address` de son fichier.
Le fournisseur intégré sélectionne les endpoints et les clés publiques depuis
sa liste de serveurs : laisser `WIREGUARD_PUBLIC_KEY`, `WIREGUARD_ENDPOINT_IP`,
`WIREGUARD_ENDPOINT_PORT` et `WIREGUARD_PRESHARED_KEY` vides dans cette méthode.
Les identifiants OpenVPN restent inutilisés avec WireGuard.

`PORT_FORWARD_ONLY=on` filtre les serveurs compatibles avec la redirection de
ports/P2P ; cette option ne demande pas à elle seule un port entrant. La demande
est pilotée séparément par `VPN_PORT_FORWARDING`.

Le `.env` est exclu de Git et doit conserver ses droits :

```sh
chmod 600 /opt/media-stack/stacks/vpn/.env
```

La clé réelle ne doit pas être ajoutée au `.env.example` ou à la documentation.

## Activer et contrôler

Après avoir renseigné la clé et l’adresse, depuis la racine du dépôt :

```sh
cd /opt/media-stack/stacks
python3 scripts/stack-compose.py vpn config --quiet
python3 scripts/stack-compose.py vpn up -d
python3 scripts/stack-compose.py vpn ps
python3 scripts/stack-compose.py vpn logs --since=5m --tail=80
```

Vérifier que Gluetun est sain, que les journaux confirment la connexion et que
l’adresse de sortie correspond au VPN. La présence de TUN seule ne démontre pas
qu’un tunnel est établi. qBittorrent est raccordé avec `scripts/vpn-up.sh`. Les autres applications
nécessitent un raccordement explicite à
l’espace réseau de Gluetun pour utiliser ce tunnel ; voir le
[guide VPN](README.md#raccordement-des-applications).

## Redirection de ports ultérieure

Pour utiliser la redirection de ports Proton, générer la configuration WireGuard
avec l’option **NAT-PMP / Port Forwarding**, puis définir `VPN_PORT_FORWARDING=on`.
Proton attribue un port dynamique. Le client BitTorrent devra utiliser le port
obtenu et être raccordé au tunnel ; la mise à jour automatique du port
sont une étape supplémentaire à configurer avant de compter sur cette fonction.
La configuration actuelle laisse cette demande de port désactivée.

Référence : [paramètres Proton dans Gluetun](https://github.com/qdm12/gluetun-wiki/blob/main/setup/providers/protonvpn.md).
