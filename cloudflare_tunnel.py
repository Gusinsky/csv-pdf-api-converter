# filename: cloudflare_tunnel.py
import os
import random
import string
import time
import requests
import subprocess
import atexit
from cloudflare_config import *

class CloudflareTunnelManager:
    def __init__(self):
        self.tunnel_id = None
        self.tunnel_name = f"csv-api-tunnel-{int(time.time())}"
        self.tunnel_token = None
        self.tunnel_url = None
        self.cloudflared_process = None
        self.is_cleaning_up = False

        # Register the cleanup function to be called upon script exit
        atexit.register(self.cleanup)

    def generate_random_prefix(self):
        """Generate a random 4-letter prefix for the subdomain."""
        return ''.join(random.choices(string.ascii_lowercase, k=4))

    def create_tunnel_and_dns(self):
        """Creates the tunnel, DNS record, and config, then retrieves the token."""
        print("--- Starting Cloudflare Tunnel Setup ---")
        try:
            headers = {
                'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}',
                'Content-Type': 'application/json'
            }

            # 1. Create the Tunnel
            print(f"Creating tunnel: {self.tunnel_name}...")
            tunnel_creation_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel"
            tunnel_data = {'name': self.tunnel_name, 'tunnel_secret': os.urandom(32).hex()}
            response = requests.post(tunnel_creation_url, headers=headers, json=tunnel_data)
            response.raise_for_status()
            tunnel = response.json()['result']
            self.tunnel_id = tunnel['id']
            print(f"✅ Tunnel created with ID: {self.tunnel_id}")

            # 2. Create DNS CNAME Record
            subdomain = STATIC_SUBDOMAIN if USE_STATIC_URL else self.generate_random_prefix()
            self.tunnel_url = f"{subdomain}.{DOMAIN}"
            print(f"Creating DNS record for: {self.tunnel_url}...")
            
            self._delete_existing_dns_record(headers, self.tunnel_url)

            dns_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
            dns_data = {
                'name': self.tunnel_url,
                'type': 'CNAME',
                'content': f"{self.tunnel_id}.cfargotunnel.com",
                'proxied': True,
                'comment': f"Managed by Python script for tunnel {self.tunnel_id}"
            }
            response = requests.post(dns_url, headers=headers, json=dns_data)
            response.raise_for_status()
            print("✅ DNS record created successfully.")

            # 3. Configure Tunnel Routing
            print("Configuring tunnel routing...")
            config_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/{self.tunnel_id}/configurations"
            config_data = {
                'config': {
                    'ingress': [
                        {'hostname': self.tunnel_url, 'service': f'http://localhost:{LOCAL_PORT}'},
                        {'service': 'http_status:404'}
                    ]
                }
            }
            response = requests.put(config_url, headers=headers, json=config_data)
            response.raise_for_status()
            print("✅ Tunnel routing configured.")
            
            # 4. Get the Tunnel Token
            print("Retrieving tunnel token...")
            token_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/{self.tunnel_id}/token"
            response = requests.get(token_url, headers=headers)
            response.raise_for_status()
            self.tunnel_token = response.json()['result']
            print("✅ Token retrieved successfully.")
            print("--- Setup Complete ---")
            return self.tunnel_url

        except requests.exceptions.HTTPError as e:
            print(f"❌ Error during setup: {e.response.status_code} {e.response.reason} for url: {e.request.url}")
            print(f"   Response body: {e.response.text}")
            return None
        except Exception as e:
            print(f"❌ An unexpected error occurred during creation: {str(e)}")
            return None
            
    def run_tunnel(self):
        """Runs cloudflared using the token and waits for user interruption."""
        if not self.tunnel_token:
            print("❌ Cannot run tunnel: token not available.")
            return

        print("\n--- Starting Local Connector ---")
        command = ["cloudflared", "tunnel", "run", "--token", self.tunnel_token]
        
        try:
            # Start the cloudflared process
            self.cloudflared_process = subprocess.Popen(command)
            print(f"✅ Connector process started with PID: {self.cloudflared_process.pid}")
            
            # This call will block until the process is terminated (e.g., by cleanup)
            self.cloudflared_process.wait()

        except FileNotFoundError:
            print("\n❌ Error: 'cloudflared' executable not found.")
            print("   Please ensure Cloudflare's cloudflared is installed and in your system's PATH.")
        except Exception as e:
            print(f"\n❌ An error occurred while running the tunnel: {e}")

    def _delete_existing_dns_record(self, headers, hostname):
        """Helper to delete a CNAME record if it exists to prevent conflicts."""
        if not hostname: return
        dns_records_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"
        params = {'type': 'CNAME', 'name': hostname}
        response = requests.get(dns_records_url, headers=headers, params=params)
        if response.ok:
            records = response.json()['result']
            if records:
                record_id = records[0]['id']
                print(f"   Found existing DNS record {record_id} for {hostname}. Deleting it.")
                requests.delete(f"{dns_records_url}/{record_id}", headers=headers)

    def cleanup(self):
        """Terminates the subprocess and deletes the Cloudflare tunnel resources."""
        if self.is_cleaning_up:
            return
        self.is_cleaning_up = True

        print("\n--- Initiating Cleanup ---")
        if self.cloudflared_process and self.cloudflared_process.poll() is None:
            print(f"Terminating cloudflared process (PID: {self.cloudflared_process.pid})...")
            self.cloudflared_process.terminate()
            try:
                self.cloudflared_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("   Process did not terminate gracefully, killing.")
                self.cloudflared_process.kill()
            self.cloudflared_process = None
            print("✅ Process terminated.")

        if self.tunnel_id:
            print(f"Deleting tunnel {self.tunnel_id} and its DNS records on Cloudflare...")
            try:
                headers = {'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}', 'Content-Type': 'application/json'}
                self._delete_existing_dns_record(headers, self.tunnel_url)

                tunnel_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/{self.tunnel_id}"
                response = requests.delete(tunnel_url, headers=headers, json={})
                if response.status_code == 200:
                    print(f"✅ Tunnel {self.tunnel_id} deleted successfully.")
                else:
                    print(f"   Tunnel info: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"⚠️ Error during Cloudflare resource cleanup: {str(e)}")
            self.tunnel_id = None
        print("--- Cleanup Complete ---")