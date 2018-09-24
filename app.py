import json
import logging
import re
import sys
from itertools import chain
from operator import itemgetter
from bs4 import BeautifulSoup as bs
import requests
from queries import account_query, company_query, group_account_query


TALLY_HOST = sys.argv[1]
TALLY_PORT = sys.argv[2] if len(sys.argv) == 3 else 9000
TALLY_PATH = "http://{}:{}".format(TALLY_HOST, TALLY_PORT)


ERPNEXT_HOST = sys.argv[3]
ERPNEXT_PORT = sys.argv[4] if len(sys.argv) == 5 else 8000
ERPNEXT_PATH = "http://{}:{}".format(ERPNEXT_HOST, ERPNEXT_PORT)
logging.basicConfig(level=logging.INFO)


def main():
    logging.info("Connecting to Tally Server on {}".format(TALLY_PATH))
    try:
        response = requests.get(TALLY_PATH, timeout=1)
        if response.status_code == 200:
            logging.info("Connected to Tally")
            logging.info("Querying Tally Companies")
            tally_companies = get_tally_companies()
            if tally_companies:
                logging.info("Tally Companies Found : {}".format(tally_companies))
                # Hardcoding for now
                # Should be chosen from UI
                index = tally_companies.index("Service Lee Technologies Private Limited - 17-18")
                tally_company = tally_companies[index]
                logging.info("Choosing Tally company : {}".format(tally_company))

                # Hardcoding connection details for now
                logging.info("Connecting to ERPNext Server on {}".format(ERPNEXT_PATH))
                session = connect_to_erpnext(ERPNEXT_PATH, "Administrator", "admin")
                if session:
                    logging.info("Connected to ERPNext")
                    logging.info("Querying ERPNext Companies")
                    erpnext_companies = get_erpnext_companies(session)
                    logging.info("ERPNext Companies Found : {}".format(erpnext_companies))

                    # Hardcoding for now
                    # Should be chosen from UI
                    index = erpnext_companies.index("Sandbox US")
                    erpnext_company = erpnext_companies[index]
                    logging.info("Choosing ERPNext company : {}".format(erpnext_company))
                    logging.info("Migrating Tally company : {} to ERPNext company : {}".format(tally_company, erpnext_company))
                    migrate_company(session, tally_company, erpnext_company)
            else:
                logging.warning("No Companies Found")
    except:
        import traceback
        traceback.print_exc()
        logging.warning("Connection Failed")


def get_tally_companies():
    response = requests.post(TALLY_PATH, data=company_query)
    response = bs(response.text, "xml")
    collection = response.ENVELOPE.BODY.DATA.COLLECTION
    companies = collection.find_all("COMPANY")
    company_list = []
    for company in companies:
        company_list.append(company.NAME.string)
    return company_list


def connect_to_erpnext(server_path, username, password):
    session = requests.Session()
    response = session.post(server_path,
        data={
            'cmd': 'login',
            'usr': username,
            'pwd': password
        }
    )
    if response.status_code == 200:
        data = response.json()
        logging.info("Logged in as {}".format(data["full_name"]))
        return session
    else:
        logging.warning("Login failed")


def get_erpnext_companies(session):
    response = session.get("{}/api/resource/Company".format(ERPNEXT_PATH)).json()
    return list(map(itemgetter("name"), response["data"]))


def migrate_company(session, tally_company, erpnext_company):
    logging.info("Migrate Chart of Accounts")
    migrate_chart_of_accounts(session, tally_company, erpnext_company)
    logging.info("Migrated Chart of Accounts")


def migrate_chart_of_accounts(session, tally_company, erpnext_company):
    logging.info("Querying Tally Group accounts")
    group_accounts = get_group_accounts(tally_company)
    logging.info("Tally Group Accounts Found : {}".format(len(group_accounts)))

    logging.info("Querying Tally Non-Group accounts")
    non_group_accounts = get_accounts(tally_company)
    logging.info("Tally Non-Group Accounts Found : {}".format(len(non_group_accounts)))

    all_accounts = group_accounts + non_group_accounts
    logging.info("Sending all accounts")
    session.post("{}/api/method/erpnext.erpnext_integrations.tally_migration.create_chart_of_accounts".format(ERPNEXT_PATH),
        data={"company": erpnext_company, "accounts": json.dumps(all_accounts)}
    )
    logging.info("Accounts sent")


def get_group_accounts(tally_company):
    response = requests.post(TALLY_PATH, data=group_account_query.format(tally_company))
    response = bs(sanitize(response.text), "xml")
    collection = response.ENVELOPE.BODY.DATA.COLLECTION
    accounts = collection.find_all("GROUP")
    accounts_dict = {}
    for account in accounts:
        if account["NAME"] in ("Sundry Creditors", "Sundry Debtors"):
            is_group = 0
        else:
            is_group = 1
        accounts_dict.setdefault(int(account.DEPTH.string), []).append({
            "account_name": account["NAME"],
            "is_group": is_group,
            "parent_account": get_parent_account(account),
        })
    account_list = list(chain(*map(itemgetter(1), sorted(accounts_dict.items()))))
    return account_list


def get_accounts(tally_company):
    response = requests.post(TALLY_PATH, data=account_query.format(tally_company))
    response = bs(sanitize(response.text), "xml")
    collection = response.ENVELOPE.BODY.DATA.COLLECTION
    accounts = collection.find_all("LEDGER")
    account_list = []
    for account in accounts:
        parent_account = get_parent_account(account)
        if parent_account in ("Sundry Creditors", "Sundry Debtors"):
            continue
        account_list.append({
            "account_name": account["NAME"],
            "is_group": 0,
            "parent_account": parent_account,
        })
    return account_list


def get_parent_account(account):
    if account.PARENT.string.strip() == "Primary":
        return {
            ("Yes", "Yes"): "Expenses",
            ("Yes", "No"): "Assets",
            ("No", "Yes"): "Incomes",
            ("No", "No"): "Liabilities",
        }[(account.ISDEEMEDPOSITIVE.string, account.ISREVENUE.string)]
    return account.PARENT.string


def sanitize(string):
    return re.sub("&#4;", "", string)


if __name__ == "__main__":
    main()
