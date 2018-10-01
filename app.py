import json
import logging
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import chain
from operator import itemgetter
from bs4 import BeautifulSoup as bs
import requests
from queries import account_query, company_query, company_period_query, group_account_query, stock_item_query, voucher_count_query, voucher_register_query


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

    logging.info("Migrate Items")
    migrate_items(session, tally_company, erpnext_company)
    logging.info("Migrated Items")

    logging.info("Migrate Vouchers")
    migrate_vouchers(session, tally_company, erpnext_company)
    logging.info("Migrated Vouchers")


def migrate_chart_of_accounts(session, tally_company, erpnext_company):
    logging.info("Querying Tally Group accounts")
    group_accounts = get_group_accounts(tally_company)
    logging.info("Tally Group Accounts Found : {}".format(len(group_accounts)))

    logging.info("Querying Tally Non-Group accounts")
    non_group_accounts, parties = get_accounts(tally_company)
    logging.info("Tally Non-Group Accounts Found : {}".format(len(non_group_accounts)))
    logging.info("Tally Parties Found : {}".format(len(parties)))

    all_accounts = group_accounts + non_group_accounts
    logging.info("Sending all accounts")
    response = session.post("{}/api/method/erpnext.erpnext_integrations.tally_migration.create_chart_of_accounts".format(ERPNEXT_PATH),
        data={"company": erpnext_company, "accounts": json.dumps(all_accounts)}
    )
    logging.info("Accounts sent")

    logging.info("Sending all parties")
    response = session.post("{}/api/method/erpnext.erpnext_integrations.tally_migration.create_parties".format(ERPNEXT_PATH),
        data={"company": erpnext_company, "parties": json.dumps(parties)}
    )
    logging.info("Parties sent")


def migrate_items(session, tally_company, erpnext_company):
    logging.info("Querying Tally Items")
    items = list(get_stock_items(tally_company, erpnext_company))
    logging.info("Tally Items Found : {}".format(len(items)))

    logging.info("Sending Tally Items")
    response = session.post("{}/api/method/erpnext.erpnext_integrations.tally_migration.create_items".format(ERPNEXT_PATH),
        data={"company": erpnext_company, "items": json.dumps(items)}
    )
    logging.info("Tally Items sent")


def migrate_vouchers(session, tally_company, erpnext_company):
    logging.info("Querying Tally Voucher Count")
    voucher_count = get_voucher_count(tally_company)
    logging.info("Tally Vocuhers Found : {}".format(voucher_count))

    count = 0
    for start_date, end_date in get_date_segments(tally_company, voucher_count):
        logging.info("Querying Tally Vouchers for {} to {}".format(start_date, end_date))
        vouchers = list(get_vouchers(tally_company, erpnext_company, start_date, end_date))
        logging.info("Tally Vouchers Found : {}".format(len(vouchers)))

        logging.info("Sending Tally Vouchers for {} to {}".format(start_date, end_date))
        response = session.post("{}/api/method/erpnext.erpnext_integrations.tally_migration.create_vouchers".format(ERPNEXT_PATH),
            data={"company": erpnext_company, "vouchers": json.dumps(vouchers)}
        )
        logging.info("Vouchers sent")
        count += len(vouchers)
        logging.info("Vouchers sent : {}".format(count))
        #return


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
    parties = []
    for account in accounts:
        parent_account = get_parent_account(account)
        if parent_account in ("Sundry Creditors", "Sundry Debtors"):
            account_party_mapping = {
                "Sundry Creditors": "Supplier",
                "Sundry Debtors": "Customer"
            }
            parties.append({
                "party_type": account_party_mapping[parent_account],
                "party_name": account["NAME"],
            })
        else:
            account_list.append({
                "account_name": account["NAME"],
                "is_group": 0,
                "parent_account": parent_account,
            })
    return account_list, parties


def get_parent_account(account):
    if account.PARENT.string.strip() == "Primary":
        return {
            ("Yes", "Yes"): "Expenses",
            ("Yes", "No"): "Assets",
            ("No", "Yes"): "Incomes",
            ("No", "No"): "Liabilities",
        }[(account.ISDEEMEDPOSITIVE.string, account.ISREVENUE.string)]
    return account.PARENT.string


def get_stock_items(tally_company, erpnext_company):
    response = requests.post(TALLY_PATH, data=stock_item_query.format(tally_company))
    response = bs(sanitize(response.text), "xml")
    collection = response.ENVELOPE.BODY.DATA.COLLECTION
    items = collection.find_all("STOCKITEM")
    for item in items:
        yield {
            "doctype": "Item",
            "item_code" : item["NAME"],
            "stock_uom": item.BASEUNITS.string,
            "is_stock_item": 0,
            "item_group": "All Item Groups",
            "company": erpnext_company,
            "item_defaults": [{"company": erpnext_company}]
        }


def get_voucher_count(tally_company):
    response = requests.post(TALLY_PATH, data=voucher_count_query.format(tally_company))
    response = bs(sanitize(response.text), "xml")
    result = int(response.ENVELOPE.BODY.DATA.RESULT.string)
    return result


VOUCHER_BATCH_SIZE = 200
def get_date_segments(tally_company, voucher_count):
    company_start_date, company_end_date = get_company_period(tally_company)
    difference = company_end_date - company_start_date
    daily_voucher_count = voucher_count // difference.days
    days_to_batch_size = VOUCHER_BATCH_SIZE // daily_voucher_count
    start = company_start_date
    while start <= company_end_date:
        end = start + timedelta(days=days_to_batch_size)
        yield (start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        start = end + timedelta(days=1)


def get_company_period(tally_company):
    response = requests.post(TALLY_PATH, data=company_period_query.format(tally_company))
    response = bs(sanitize(response.text), "xml")

    start = response.ENVELOPE.BODY.DATA.COLLECTION.COMPANY.STARTINGFROM.string
    start = datetime.strptime(start, "%Y%m%d")

    end = response.ENVELOPE.BODY.DATA.COLLECTION.COMPANY.ENDINGAT.string
    end = datetime.strptime(end, "%Y%m%d")

    return (start, end)


def get_vouchers(tally_company, erpnext_company, start_date, end_date):
    response = requests.post(TALLY_PATH, data=voucher_register_query.format(tally_company, start_date, end_date))
    response = bs(sanitize(emptify(response.text)), "xml")
    #with open("20170403-20170403.xml", "rb") as f:
    #    response = f.read().decode('utf_8', 'ignore')

    #with open("{}-{}.xml".format(start_date, end_date), "w") as f:
    #    f.write(sanitize(emptify(response.text)))

    #response = bs(sanitize(emptify(response)), "xml")
    collection = response.ENVELOPE.BODY.DATA
    messages = collection.find_all("TALLYMESSAGE")
    for message in messages:
        try:
            voucher = message.VOUCHER
            if voucher is None:
                continue
            inventory_entries = voucher.find_all("INVENTORYENTRIES.LIST") + voucher.find_all("ALLINVENTORYENTRIES.LIST") + voucher.find_all("INVENTORYENTRIESIN.LIST") + voucher.find_all("INVENTORYENTRIESOUT.LIST")
            if voucher.VOUCHERTYPENAME.string not in ["Journal", "Receipt", "Payment", "Contra"] and inventory_entries:
                function = voucher_to_invoice
            else:
                function = voucher_to_journal_entry
            yield function(voucher, erpnext_company)
        except:
            import traceback
            traceback.print_exc()


def voucher_to_journal_entry(voucher, erpnext_company):
    accounts = []
    ledger_entries = voucher.find_all("ALLLEDGERENTRIES.LIST") + voucher.find_all("LEDGERENTRIES.LIST")
    for ledger_entry in ledger_entries:
        account = {
            "account": ledger_entry.LEDGERNAME.string,
            "is_party": ledger_entry.ISPARTYLEDGER.string == "Yes",
        }
        amount = Decimal(ledger_entry.AMOUNT.string)
        if amount > 0:
            account["credit_in_account_currency"] = str(abs(amount))
        else:
            account["debit_in_account_currency"] = str(abs(amount))
        accounts.append(account)

    journal_entry = {
        "doctype": "Journal Entry",
        "naming_series": "JV-",
        "tally_id": voucher.GUID.string,
        "posting_date": voucher.DATE.string,
        "accounts": accounts,
        "company": erpnext_company,
    }
    return journal_entry


def voucher_to_invoice(voucher, erpnext_company):
    if voucher.VOUCHERTYPENAME.string in ["Sales", "Credit Note"]:
        doctype = "Sales Invoice"
        naming_series = "SINV-"
        party_field = "customer"
    elif voucher.VOUCHERTYPENAME.string in ["Purchase", "Debit Note"]:
        doctype = "Purchase Invoice"
        naming_series = "PINV-"
        party_field = "supplier"

    invoice = {
        "doctype": doctype,
        "naming_series": naming_series,
        "tally_id": voucher.GUID.string,
        party_field: voucher.PARTYNAME.string,
        "posting_date": voucher.DATE.string,
        "due_date": voucher.DATE.string,
        "items": list(get_voucher_items(voucher, doctype)),
        "taxes": list(get_voucher_taxes(voucher)),
        "set_posting_time": 1,
        "disable_rounded_total": 1,
        "company": erpnext_company,
    }
    return invoice


def get_voucher_items(voucher, doctype):
    inventory_entries = voucher.find_all("INVENTORYENTRIES.LIST") + voucher.find_all("ALLINVENTORYENTRIES.LIST") + voucher.find_all("INVENTORYENTRIESIN.LIST") + voucher.find_all("INVENTORYENTRIESOUT.LIST")
    if doctype == "Sales Invoice":
        account_field = "income_account"
    elif doctype == "Purchase Invoice":
        account_field = "expense_account"
    for inventory_entry in inventory_entries:
        try:
            yield {
                "item_code": inventory_entry.STOCKITEMNAME.string,
                "description": inventory_entry.STOCKITEMNAME.string,
                "qty": inventory_entry.ACTUALQTY.string.split()[0].strip(),
                "uom": inventory_entry.ACTUALQTY.string.split()[-1].strip(),
                "conversion_factor": 1,
                "price_list_rate": inventory_entry.RATE.string.split("/")[0],
                account_field: inventory_entry.find_all("ACCOUNTINGALLOCATIONS.LIST")[0].LEDGERNAME.string,
            }
        except:
            import traceback
            traceback.print_exc()


def get_voucher_taxes(voucher):
    ledger_entries = voucher.find_all("ALLLEDGERENTRIES.LIST") + voucher.find_all("LEDGERENTRIES.LIST")
    for ledger_entry in ledger_entries:
        if ledger_entry.ISPARTYLEDGER.string == "No":
            yield {
                "charge_type": "Actual",
                "account_head": ledger_entry.LEDGERNAME.string,
                "description": ledger_entry.LEDGERNAME.string,
                "tax_amount": str(abs(Decimal(ledger_entry.AMOUNT.string))),
            }


def sanitize(string):
    return re.sub("&#4;", "", string)


def emptify(string):
    string = re.sub(r"<\w+/>", "", string)
    string = re.sub(r"<([\w.]+)>\s*<\/\1>", "", string)
    string = re.sub(r"\r\n", "", string)
    return string


if __name__ == "__main__":
    main()
