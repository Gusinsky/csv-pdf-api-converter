import os
import signal
import subprocess
import sys
import time
from cloudflare_tunnel import CloudflareTunnelManager

flask_process = None
tunnel_manager = None

def signal_handler(signum, frame):
    """Gracefully shut down all services on SIGINT or SIGTERM."""
    print("\n👋 Ctrl+C detected. Shutting down all services...")
    if flask_process:
        flask_process.terminate()

    sys.exit(0)

if __name__ == "__main__":

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("--- Starting Application ---")
    

    os.makedirs("data", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("temp_uploads", exist_ok=True)


    from cloudflare_config import LOCAL_PORT
    flask_port = str(LOCAL_PORT)
    print(f"Starting Flask server on port {flask_port}...")


    flask_process = subprocess.Popen(
        ["flask", "run", f"--port={flask_port}"],
        stdout=sys.stdout, #Show Flask output directly in the console
        stderr=sys.stderr
    )


    time.sleep(2)


    tunnel_manager = CloudflareTunnelManager()
    
    try:

        public_url = tunnel_manager.create_tunnel_and_dns()

        if public_url:
            print(f"\n🚀 Public URL is active at: https://{public_url}")
            print("Application is running. Press Ctrl+C to stop.")
            

            tunnel_manager.run_tunnel()
        else:
            print("\n❌ Failed to create Cloudflare tunnel. Shutting down.")

            flask_process.terminate()
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ A critical error occurred: {str(e)}")
    finally:

        print("\n--- Main script finished. Cleaning up. ---")
        if flask_process:
            flask_process.terminate()

        sys.exit(0)