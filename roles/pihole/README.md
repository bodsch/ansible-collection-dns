# ansible-pihole


```yaml
pihole_version: 6.1.2

pihole_direct_download: false

pihole_arch:
  install_type: archive   # source | archive
  source_repository: https://github.com/pi-hole/pi-hole.git
  archive: https://github.com/pi-hole/pi-hole/archive/refs/tags/v{{ pihole_version }}.tar.gz

pihole_config_setup:
  dns:
    interface: "{{ ansible_default_ipv4.interface }}"
    domain: pi.hole
    cache:
      size: 10000
      optimizer: 3600
    upstreams:
      - "1.1.1.1"
      - "1.0.0.1"
      - "9.9.9.9"
    bogusPriv: true
    dnssec: false
  dhcp: {}
  ntp: {}
  resolver: {}
  database: {}
  files:
    gravity_tmp: /var/tmp
  webserver:
    domain: pi.hole
    port: 8080
    session:
      timeout: 1600
    interface:
      boxed: true
      theme: default-light
    api:
      prettyJSON: true
      temp:
        limit: "60.0"
        unit: C
  misc:
    delay_startup: 10
  debug: {}

pihole_groups: []
#   - name: admin
#     description: "Admin Group"
#     enabled: true

pihole_clients: []
#   - ip: 192.168.0.10
#     name: laptop
#     comment: "Kids Laptop"
#     enabled: true
#     groups:
#       - kids

# Custom lists (optional)
pihole_custom_denylists: []
# Beispiele für zusätzliche Blocklisten
#   - address: "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
#   - address: "https://someonewhocares.org/hosts/zero/hosts"
#   - address: "https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/BaseFilter/sections/adservers.txt"
#   - address: "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext"
#   - address: "https://raw.githubusercontent.com/crazy-max/WindowsSpyBlocker/master/data/hosts/spy.txt"
#   - address: "https://raw.githubusercontent.com/hoshsadiq/adblock-nocoin-list/master/hosts.txt"  # Krypto-Mining Blocker
#   - address: "https://raw.githubusercontent.com/Perflyst/PiHoleBlocklist/master/SmartTV-AGH.txt"  # Smart TV Telemetrie
#   - address: https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
#     comment: "default list"
#     enabled: true

pihole_domain_allowlist: []
  # Beispiele für Domains die NICHT blockiert werden sollen
  # Häufig benötigte Domains:
  # - "googleadservices.com"           # Google Ads (für manche Shopping-Seiten nötig)
  # - "googlesyndication.com"          # Google AdSense
  # - "amazon-adsystem.com"            # Amazon Werbung
  # - "doubleclick.net"                # Google DoubleClick (für manche Seiten nötig)
  #
  # Microsoft/Windows Updates:
  # - "delivery.mp.microsoft.com"      # Windows Updates
  # - "tlu.dl.delivery.mp.microsoft.com"
  # - "download.windowsupdate.com"
  #
  # Social Media & Messaging:
  # - "graph.facebook.com"             # Facebook API
  # - "scontent.xx.fbcdn.net"          # Facebook Inhalte
  # - "web.whatsapp.com"               # WhatsApp Web
  #
  # Streaming Services:
  # - "widget-cdn.rpxnow.com"          # Für verschiedene Login-Widgets
  # - "secure.netflix.com"             # Netflix
  # - "tv.youtube.com"                 # YouTube TV
  #
  # Gaming:
  # - "clientconfig.rpx.ol.epicgames.com"  # Epic Games
  # - "tracking.epicgames.com"             # Epic Games (manchmal nötig)

pihole_domain_denylist: []
  # Beispiele für zusätzlich zu blockierende Domains
  # Social Media (falls gewünscht):
  # - "facebook.com"
  # - "twitter.com"
  # - "instagram.com"
  # - "tiktok.com"
  # - "snapchat.com"
  #
  # Tracking & Analytics:
  # - "google-analytics.com"
  # - "googletagmanager.com"
  # - "hotjar.com"
  # - "mouseflow.com"
  # - "crazyegg.com"
  #
  # Werbung & Affiliate:
  # - "outbrain.com"
  # - "taboola.com"
  # - "shareasale.com"
  # - "commission-junction.com"
  #
  # Kryptomining:
  # - "coin-hive.com"
  # - "coinhive.com"
  # - "jsecoin.com"
  #
  # Malware/Phishing (Beispiele):
  # - "malware-domain.com"
  # - "phishing-site.net"
```
