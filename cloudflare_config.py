import os
from dotenv import load_dotenv

load_dotenv()

#Cloudflare API Configuration
CLOUDFLARE_API_TOKEN = os.getenv('CLOUDFLARE_API_TOKEN')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')
CLOUDFLARE_ZONE_ID = os.getenv('CLOUDFLARE_ZONE_ID')

#Tunnel Configurationz
USE_STATIC_URL = True  #Either use a static url or a random 4-letter prefix.
STATIC_SUBDOMAIN = "apiparser"  #Only used if USE_STATIC_URL is True
DOMAIN = "cfsedev.org" 

#Application Conf
LOCAL_PORT = 8000 