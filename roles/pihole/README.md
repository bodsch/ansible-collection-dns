# ansible-pihole


```yaml
pihole_version: 6.1.2

pihole_direct_download: false

pihole_arch:
  install_type: archive   # source | archive
  source_repository: https://github.com/pi-hole/pi-hole.git
  archive: https://github.com/pi-hole/pi-hole/archive/refs/tags/v{{ pihole_version }}.tar.gz

pihole_config: {}
#   dns:
#     upstreams:
#       - '1.1.1.1'
#       - '1.0.0.1'
#       - '9.9.9.9'
#     CNAMEdeepInspect: true
#     blockESNI: true
#     EDNS0ECS: true
#     ignoreLocalhost: false
#     showDNSSEC: true
#     analyzeOnlyAandAAAA: false
#     piholePTR: PI.HOLE
#     replyWhenBusy: ALLOW
#     blockTTL: 2
#     domainNeeded: false
#     expandHosts: false
#     domain: pi.hole
#     bogusPriv: true
#     dnssec: false
#     interface: "{{ ansible_default_ipv4.interface }}"
#     listeningMode: LOCAL
#     queryLogging: true
#     port: 53
#     cache:
#       size: 10000
#       optimizer: 3600
#       upstreamBlockedTTL: 86400
#     blocking:
#       active: true
#       mode: NULL
#       edns: TEXT
#     specialDomains:
#       mozillaCanary: true
#       iCloudPrivateRelay: true
#       designatedResolver: true
#     reply:
#       host:
#         force4: false
#         force6: false
#       blocking:
#         force4: false
#         force6: false
#     rateLimit:
#       count: 1000
#       interval: 60
#   dhcp:
#     active: false
#     ipv6: false
#     rapidCommit: false
#     multiDNS: false
#     logging: false
#     ignoreUnknownClients: false
#   ntp:
#     ipv4:
#       active: true
#     ipv6:
#       active: true
#     sync:
#       active: true
#       server: pool.ntp.org
#       interval: 3600
#       count: 8
#       rtc:
#         set: false
#         utc: true
#   resolver:
#     resolveIPv4: true
#     resolveIPv6: true
#     networkNames: true
#     refreshNames: IPV4_ONLY
#   database:
#     DBimport: true
#     maxDBdays: 91
#     DBinterval: 60
#     useWAL: true
#     network:
#       parseARPcache: true
#       expire: 91
#   webserver:
#     domain: pi.hole
#     port: 80
#     threads: 50
#     headers:
#       - 'X-DNS-Prefetch-Control: off'
#       - "Content-Security-Policy: default-src 'self' 'unsafe-inline';"
#       - 'X-Frame-Options: DENY'
#       - 'X-XSS-Protection: 0'
#       - 'X-Content-Type-Options: nosniff'
#       - 'Referrer-Policy: strict-origin-when-cross-origin'
#     serve_all: false
#     session:
#       timeout: 3200
#       restore: true
#     tls:
#       cert: /etc/pihole/tls.pem
#     paths:
#       webroot: /var/www/html
#       webhome: /admin/
#     interface:
#       boxed: true
#       theme: default-light
#     api:
#       max_sessions: 16
#       prettyJSON: true
#       pwhash: $BALLOON-SHA256$v=1$s=1024,t=32$RSqXeRU/3QMJIAVOw0jvRA==$SlkKXw2Xhq5Y0OlnGiH+BOpm0MPdPYn3vgXHqucnRjg=
#       app_sudo: false
#       cli_pw: true
#       maxHistory: 86400
#       maxClients: 10
#       client_history_global_max: true
#       allow_destructive: true
#       temp:
#         limit: 60.0
#         unit: C
#   files:
#     pid: /run/pihole-FTL.pid
#     database: /etc/pihole/pihole-FTL.db
#     gravity: /etc/pihole/gravity.db
#     gravity_tmp: /var/tmp
#     macvendor: /etc/pihole/macvendor.db
#     log:
#       ftl: /var/log/pihole/FTL.log
#       dnsmasq: /var/log/pihole/pihole.log
#       webserver: /var/log/pihole/webserver.log
#   misc:
#     privacylevel: 0
#     delay_startup: 10
#     nice: -10
#     addr2line: true
#     etc_dnsmasq_d: false
#     extraLogging: false
#     readOnly: false
#     check:
#       load: true
#       shmem: 90
#       disk: 90
#   debug:
#     database: false
#     networking: false
#     locks: false
#     queries: false
#     flags: false
#     shmem: false
#     gc: false
#     arp: false
#     regex: false
#     api: false
#     tls: false
#     overtime: false
#     status: false
#     caps: false
#     dnssec: false
#     vectors: false
#     resolver: false
#     edns0: false
#     clients: false
#     aliasclients: false
#     events: false
#     helper: false
#     config: false
#     inotify: false
#     webserver: false
#     extra: false
#     reserved: false
#     ntp: false
#     netlink: false
#     all: false

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
