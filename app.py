import logging
import sys
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup as bs
import requests
from queries import company_query

TALLY_HOST = sys.argv[1]
TALLY_PORT = sys.argv[2] if len(sys.argv) == 3 else 9000
TALLY_PATH = "http://{}:{}".format(TALLY_HOST, TALLY_PORT)

logging.basicConfig(level=logging.INFO)

def main():
    logging.info("Connecting to Tally Server on {}".format(TALLY_PATH))
    try:
        response = requests.get(TALLY_PATH, timeout=1)
        if response.status_code == 200:
            logging.info("Connected")
            companies = get_companies()
            logging.info("Companies Found : {}".format(companies))
    except:
        import traceback
        traceback.print_exc()
        logging.warning("Connection Failed")

def get_companies():
    response = requests.post(TALLY_PATH, data=company_query)
    response = bs(response.text, "xml")
    collection = response.ENVELOPE.BODY.DATA.COLLECTION
    companies = collection.find_all("COMPANY")
    company_list = []
    for company in companies:
        company_list.append(company.NAME.string)
    return company_list

main()
