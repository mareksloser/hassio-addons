import os
import time
import json
import requests

OPTIONS_PATH = "/data/options.json"
HA_API_URL = "http://homeassistant:8123/api/states/"

def load_options():
    with open(OPTIONS_PATH, "r") as f:
        return json.load(f)

def update_ha_sensor(entity_id, state, attributes, ha_token):
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    data = {"state": state, "attributes": attributes}
    try:
        res = requests.post(f"{HA_API_URL}{entity_id}", json=data, headers=headers)
        if res.status_code not in (200, 201):
            print(f"❌ Chyba zápisu do HA pro {entity_id} - Status {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ Chyba spojení s HA API: {e}")

def get_npm_token(url, email, password):
    try:
        res = requests.post(f"{url}/api/tokens", json={"identity": email, "secret": password})
        res.raise_for_status()
        return res.json().get("token")
    except Exception as e:
        print(f"❌ Nelze se přihlásit do NPM: {e}")
        return None

def get_npm_hosts(url, token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{url}/api/nginx/proxy-hosts", headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Nelze stáhnout seznam domén: {e}")
        return []

def main():
    options = load_options()
    npm_url = options.get("npm_url", "").rstrip("/")
    npm_email = options.get("npm_email", "")
    npm_password = options.get("npm_password", "")
    ha_token = options.get("ha_token", "")
    interval = options.get("check_interval_minutes", 15)
    ignored_domains = options.get("ignored_domains", [])

    if not ha_token:
        print("❌ CHYBA: Chybí Home Assistant token!")
        return

    # Osekáme zadané výjimky o https:// a mezery, aby se to snadno porovnávalo
    clean_ignored = [d.replace("https://", "").replace("http://", "").strip().lower() for d in ignored_domains]

    print(f"ℹ️ Konfigurace načtena. Kontrola každých {interval} minut.")
    if clean_ignored:
        print(f"🛡️ Whitelist povolených webů: {', '.join(clean_ignored)}")

    while True:
        print("\n--- Začínám kontrolu endpointů ---")
        token = get_npm_token(npm_url, npm_email, npm_password)

        if token:
            hosts = get_npm_hosts(npm_url, token)
            print(f"✅ Nalezeno {len(hosts)} záznamů v NPM.")

            for host in hosts:
                domain_names = host.get("domain_names", [])

                for domain in domain_names:
                    clean_domain = domain.strip().lower()
                    target_url = f"https://{clean_domain}"
                    safe_domain = clean_domain.replace(".", "_").replace("-", "_")
                    entity_id = f"binary_sensor.npm_monitor_{safe_domain}"

                    # Kontrola, zda je doména na whitelistu
                    is_ignored = clean_domain in clean_ignored

                    try:
                        response = requests.get(target_url, timeout=5, allow_redirects=False)

                        if response.status_code == 200:
                            if is_ignored:
                                print(f"✅ OK (Whitelist): {target_url} je veřejný, ale je to POVOLENO. (Status 200)")
                                state = "off"
                                icon = "mdi:shield-check-outline"
                            else:
                                print(f"⚠️ ALARM: {target_url} je NEZABEZPEČENÝ! (Status 200)")
                                state = "on"
                                icon = "mdi:shield-alert"

                        elif response.status_code in [401, 403, 301, 302, 303]:
                            print(f"✅ OK: {target_url} je chráněný. (Status {response.status_code})")
                            state = "off"
                            icon = "mdi:shield-check"
                        else:
                            print(f"ℹ️ INFO: {target_url} vrací {response.status_code}")
                            state = "off"
                            icon = "mdi:shield-check"

                        update_ha_sensor(entity_id, state, {
                            "device_class": "problem",
                            "friendly_name": f"NPM: {domain}",
                            "status_code": "Whitelist (200)" if (response.status_code == 200 and is_ignored) else response.status_code,
                            "icon": icon
                        }, ha_token)

                    except requests.exceptions.RequestException:
                        print(f"⚠️ Nelze se spojit s {target_url}. Přeskakuji.")

        else:
            print("⚠️ Kontrola přeskočena kvůli chybě s NPM API.")

        print(f"--- Hotovo. Další kontrola za {interval} minut. ---")
        time.sleep(interval * 60)

if __name__ == "__main__":
    main()