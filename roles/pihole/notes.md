
/usr/bin/pihole-FTL --config dns.hosts '[ "192.168.0.4 matrix.vpn", "192.168.0.4 matrix.lan" ]'

#!/bin/bash

WHITELIST="/path/to/whitelist.txt"
BLACKLIST="/path/to/blacklist.txt"

# Whitelist importieren
if [[ -f "$WHITELIST" ]]; then
    while IFS= read -r domain || [ -n "$domain" ]; do
        [[ -z "$domain" || "$domain" == \#* ]] && continue
        pihole allow "$domain" --comment "Whitelist import"
    done < "$WHITELIST"
fi

# Blacklist importieren
if [[ -f "$BLACKLIST" ]]; then
    while IFS= read -r domain || [ -n "$domain" ]; do
        [[ -z "$domain" || "$domain" == \#* ]] && continue
        pihole deny "$domain" --comment "Blacklist import"
    done < "$BLACKLIST"
fi

# Listen neu laden
pihole reloadlists


git config --global --add safe.directory /var/www/html/admin
