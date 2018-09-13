import logging
import sys
from xml.etree import ElementTree as ET
import requests

TALLY_HOST = sys.argv[1]
TALLY_PORT = sys.argv[2] if len(sys.argv) == 3 else 9000
TALLY_PATH = "http://{}:{}".format(TALLY_HOST, TALLY_PORT)

logging.basicConfig(level=logging.INFO)

logging.info("Connecting to Tally Server on {}".format(TALLY_PATH))
try:
    response = requests.get(TALLY_PATH, timeout=1)
    if response.status_code == 200:
        logging.info("Connected")
except:
    logging.warning("Connection Failed")
