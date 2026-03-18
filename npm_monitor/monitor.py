import os
import time
import json
import requests


OPTIONS_PATH = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HA_API_URL = "http://supervisor/core/api/states/"

def load_options():
    with open(OPTIONS_PATH, "r") as f:
        return json.load(f)

def update_ha_sensor(entity_id, state, attributes):
    """Vytvoří nebo zaktualizuje senzor přímo v Home Assistantovi."""
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {"state": state, "attributes": attributes}
    try:
        requests.post(f"{HA_API_URL}{entity_id}", json=data, headers=headers)
    except Exception as e:
        print(f"❌ Chyba při aktualizaci HA senzoru: {e}")

def get_npm_token(url, email, password):
    """Získá přístupový token do Nginx Proxy Manager API."""
    try:
        res = requests.post(f"{url}/api/tokens", json={"identity": email, "secret": password})
        res.raise_for_status()
        return res.json().get("token")
    except Exception as e:
        print(f"❌ Nelze se přihlásit do NPM (Zkontroluj URL a heslo): {e}")
        return None

def get_npm_hosts(url, token):
    """Stáhne všechny Proxy Hosts z NPM."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{url}/api/nginx/proxy-hosts", headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Nelze stáhnout seznam domén z NPM: {e}")
        return []

def main():
    options = load_options()
    npm_url = options.get("npm_url", "").rstrip("/")
    npm_email = options.get("npm_email", "")
    npm_password = options.get("npm_password", "")
    interval = options.get("check_interval_minutes", 15)

    print(f"ℹ️ Konfigurace načtena. Kontrola každých {interval} minut.")

    while True:
        print("\n--- Začínám kontrolu endpointů ---")
        token = get_npm_token(npm_url, npm_email, npm_password)

        if token:
            hosts = get_npm_hosts(npm_url, token)
            print(f"✅ Nalezeno {len(hosts)} záznamů v NPM.")

            for host in hosts:
                # NPM může mít více domén pod jedním hostem (např. i www verzi)
                domain_names = host.get("domain_names", [])

                for domain in domain_names:
                    target_url = f"https://{domain}"
                    # HA entity_id povoluje jen písmena, čísla a podtržítka
                    safe_domain = domain.replace(".", "_").replace("-", "_").lower()
                    entity_id = f"binary_sensor.npm_monitor_{safe_domain}"

                    try:
                        # Test URL bez přesměrování
                        response = requests.get(target_url, timeout=5, allow_redirects=False)

                        if response.status_code == 200:
                            print(f"⚠️ ALARM: {target_url} je nezabezpečený! (Status 200)")
                            state = "on" # on = Třída Problem svítí červeně
                        elif response.status_code in [401, 403, 301, 302, 303]:
                            print(f"✅ OK: {target_url} je chráněný. (Status {response.status_code})")
                            state = "off" # off = Vše v pořádku
                        else:
                            print(f"ℹ️ INFO: {target_url} vrací {response.status_code}")
                            state = "off"

                        # Propíšeme výsledek do Home Assistanta
                        update_ha_sensor(entity_id, state, {
                            "device_class": "problem",
                            "friendly_name": f"NPM: {domain}",
                            "status_code": response.status_code,
                            "icon": "mdi:shield-alert" if state == "on" else "mdi:shield-check"
                        })

                    except requests.exceptions.RequestException as e:
                        print(f"⚠️ Nelze se spojit s {target_url}. Přeskakuji.")

        else:
            print("⚠️ Kontrola přeskočena kvůli chybě s NPM API.")

        print(f"--- Hotovo. Další kontrola za {interval} minut. ---")
        time.sleep(interval * 60)

if __name__ == "__main__":
    main()