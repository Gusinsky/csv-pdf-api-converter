# filename: start_with_cloudflare.py
import os
import signal
import subprocess
import sys
import time
from cloudflare_tunnel import CloudflareTunnelManager

# Global references to the processes for the signal handler
flask_process = None
tunnel_manager = None

def signal_handler(signum, frame):
    """Gracefully shut down all services on SIGINT or SIGTERM."""
    print("\n👋 Ctrl+C detected. Shutting down all services...")
    # The atexit hook in CloudflareTunnelManager will handle cleanup,
    # but we can terminate Flask here explicitly.
    if flask_process:
        flask_process.terminate()
    # The cleanup for the tunnel manager is handled by its atexit registration
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("--- Starting Application ---")
    
    # Create necessary directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("temp_uploads", exist_ok=True)

    # Use a port from cloudflare_config.py for consistency
    from cloudflare_config import LOCAL_PORT
    flask_port = str(LOCAL_PORT)
    print(f"Starting Flask server on port {flask_port}...")

    # Start Flask as a background process
    flask_process = subprocess.Popen(
        ["flask", "run", f"--port={flask_port}"],
        stdout=sys.stdout, # Show Flask output directly in the console
        stderr=sys.stderr
    )

    # Give Flask a moment to start up
    time.sleep(2)

    # Instantiate the tunnel manager
    tunnel_manager = CloudflareTunnelManager()
    
    try:
        # Create tunnel resources on Cloudflare and get the URL
        # This is the CORRECTED method call
        public_url = tunnel_manager.create_tunnel_and_dns()

        if public_url:
            print(f"\n🚀 Public URL is active at: https://{public_url}")
            print("Application is running. Press Ctrl+C to stop.")
            
            # This is the KEY CHANGE:
            # We now call run_tunnel(), which starts cloudflared and blocks,
            # keeping the script alive until interrupted.
            tunnel_manager.run_tunnel()
        else:
            print("\n❌ Failed to create Cloudflare tunnel. Shutting down.")
            # If tunnel setup fails, stop the Flask app
            flask_process.terminate()
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ A critical error occurred: {str(e)}")
    finally:
        # This block will run on normal exit. 
        # The signal_handler and atexit handle shutdown from Ctrl+C.
        print("\n--- Main script finished. Cleaning up. ---")
        if flask_process:
            flask_process.terminate()
        # The tunnel_manager's cleanup is handled by its atexit registration
        sys.exit(0)