import sqlite3
import random
import datetime
import math
import string
import os
import sys
from rich import print
from typing import Dict, List, Tuple


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.normpath(os.path.join(CURRENT_DIR, "../templates"))

with open(
    os.path.join(TEMPLATES_DIR, 'invoice_template.txt'),
    'r', encoding='utf-8') as rf:
    INVOICE_TEMPLATE = rf.read()

with open(
    os.path.join(TEMPLATES_DIR, 'approval_template.txt'),
    'r', encoding='utf-8') as rf:
    APPROVAL_TEMPLATE = rf.read()


def create_transaction_table(db_path: str):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL UNIQUE,
            invoice_id TEXT NOT NULL,
            approval_id TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            supplier_rating TEXT,
            applicant_name TEXT NOT NULL,
            approver_name TEXT NOT NULL,
            transaction_date DATE NOT NULL,
            transaction_amount REAL NOT NULL
        );
        """

        cursor.execute(create_table_query)
        
        conn.commit()

    except sqlite3.Error as e:
        print(f'Someting went wrong: {str(e)}')
    finally:
        if conn:
            conn.close()


def generate_random_id(prefix, length=8):
    """
    trasaction_id: TRN-xxxxxxxx;
    invoice_id: INV-xxxxxxxx;
    approval_id: APP-xxxxxxxx;
    """
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=length))
    return f"{prefix}-{random_part}"


def normal_transactions_seasonal(
    base_amount=10000, 
    years=2, 
    seasonality_factor=0.4, 
    annual_growth_rate=0.08, 
    randomness_factor=0.1
):
    transactions = []
    today = datetime.date.today()
    today = today - datetime.timedelta(days=30)   # shift to last month
    start_year = today.year - years

    for year in range(start_year, today.year + 1):
        current_year_base = base_amount * (1 + annual_growth_rate) ** (
            year - start_year)
        
        for month in range(1, 13):
            if year == today.year and month > today.month:
                break

            day_offset = random.randint(-3, 3)
            transaction_day = 15 + day_offset
            try:
                transaction_date = datetime.date(year, month, transaction_day)
            except ValueError:
                transaction_date = datetime.date(year, month, 28)

            seasonal_effect = math.sin((month / 12) * 2 * math.pi - math.pi / 2)
            seasonal_multiplier = 1 + seasonal_effect * seasonality_factor

            random_multiplier = 1 + random.uniform(
                -randomness_factor, randomness_factor)
            
            final_amount = current_year_base * seasonal_multiplier * random_multiplier

            transactions.append((transaction_date, round(final_amount, 2)))
            
    return transactions


def normal_transactions_stable_monthly(
    base_amount=5000, 
    years=2, 
    day_of_month=5,
    day_fluctuation=3,
    annual_growth_rate=0.05, 
    randomness_factor=0.1
):
    transactions = []
    today = datetime.date.today()
    today = today - datetime.timedelta(days=30)   # shift to last month
    start_year = today.year - years
    for year in range(start_year, today.year + 1):
        current_year_base = base_amount * (1 + annual_growth_rate) ** (
            year - start_year)
        
        for month in range(1, 13):
            if year == today.year and month > today.month:
                break
            day_offset = random.randint(-day_fluctuation, day_fluctuation)
            transaction_day = day_of_month + day_offset
            try:
                last_day_of_month = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day if month < 12 else 31
                transaction_day = max(1, min(transaction_day, last_day_of_month))
                transaction_date = datetime.date(year, month, transaction_day)
            except ValueError:
                transaction_date = datetime.date(year, month, 28)

            random_multiplier = 1 + random.uniform(-randomness_factor, randomness_factor)
            
            final_amount = current_year_base * random_multiplier
            transactions.append((transaction_date, round(final_amount, 2)))
            
    return transactions


def abnormal_transactions_just_below_threshold(
    threshold: float = 10000.0,
    months_period: int = 6,
    num_transactions_per_month: int = 3,
    amount_range_from_threshold: Tuple[float, float] = (0.95, 0.99),
    day_range: Tuple[int, int] = (1, 28)
) -> List[Tuple[datetime.date, float]]:
    """
    Generates abnormal transaction data, which has occurred frequently in the recent period and whose amount is slightly below a certain approval threshold.

    :param threshold: The amount threshold for approval.
    :param months_period: The time range for generating data (recent months).
    :param num_transactions_per_month: The number of abnormal transactions generated each month.
    :param amount_range_from_threshold: The amount range, expressed as a percentage of the threshold.
            For example, (0.95, 0.99) means the amount is between threshold*0.95 and threshold*0.99.
    :param day_range: The range of days in a month when the transaction occurred, for example (1, 28).

    :return: A list containing (transaction date, transaction amount) tuples.
    """
    transactions = []
    today = datetime.date.today()
    
    lower_bound_amount = threshold * amount_range_from_threshold[0]
    upper_bound_amount = threshold * amount_range_from_threshold[1]

    for i in range(months_period):
        target_month = (today.month - 2 - i) % 12 + 1
        target_year = today.year + (today.month - 2 - i) // 12
        
        for _ in range(num_transactions_per_month):
            try:
                transaction_day = random.randint(day_range[0], day_range[1])
                transaction_date = datetime.date(target_year, target_month, transaction_day)
            except ValueError:
                transaction_date = datetime.date(target_year, target_month, 28)

            final_amount = random.uniform(lower_bound_amount, upper_bound_amount)
            
            transactions.append((transaction_date, round(final_amount, 2)))
            
    return transactions



def generate_transaction_materials(
    transactions: List[Tuple[datetime.date, float]],
    supplier_info: Dict[str, str],
    supplier_rating: str,
    requestor: Dict[str, str],
    approvor: Dict[str, str]
):
    ids = []
    invoices = []
    approvals = []
    for trans_date, trans_amout in transactions:
        trans_id = generate_random_id('TRA', 8)
        invoice_id = generate_random_id('INV', 8)
        approval_id = generate_random_id('APP', 8)
        ids.append(
            [trans_id, invoice_id, approval_id]
        )
        invoice_content = INVOICE_TEMPLATE.format(
            invoice_number = invoice_id,
            invoice_issue_date = trans_date.isoformat(),
            supplier_company_name = supplier_info['company_name'],
            supplier_address = supplier_info['address'],
            supplier_contact_person = supplier_info['contact_person'],
            supplier_phone_number = supplier_info['phone'],
            supplier_email = supplier_info['email'],
            self_company_contact_person = requestor['name'],
            supplier_products = supplier_info['main_product_or_service'],
            amount = trans_amout
        )

        invoices.append(invoice_content)

        request_date = trans_date - datetime.timedelta(days=random.randint(5,10))
        approval_date = request_date + datetime.timedelta(days=random.randint(1,2))
        approval_content = APPROVAL_TEMPLATE.format(
            approval_form_id = approval_id,
            requester_name = requestor['name'],
            requester_department = requestor['department'],
            request_date = request_date.isoformat(),
            supplier_company_name = supplier_info['company_name'],
            supplier_rating = supplier_rating,
            supplier_contact_person = supplier_info['contact_person'],
            supplier_phone_number = supplier_info['phone'],
            supplier_products = supplier_info['main_product_or_service'],
            estimated_cost = int(trans_amout - (trans_amout % 10) + 10),
            approvor_name = approvor['name'],
            approval_date = approval_date.isoformat()
        )

        approvals.append(approval_content)

    return ids, invoices, approvals


def insert_transaction_data(
    db_path: str, 
    transactions: List[Tuple[datetime.date, float]],
    ids: List[List[str]], 
    supplier_info: Dict[str, str],
    supplier_rating: str,
    requestor: Dict[str, str],
    approvor: Dict[str, str]
):
    insert_sql = """
        INSERT INTO transactions (
            transaction_id, invoice_id, approval_id, 
            supplier_name, supplier_rating, applicant_name, 
            approver_name, transaction_date, transaction_amount
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    insert_data = []
    for i in range(len(ids)):
        insert_data.append(
            (
                ids[i][0],
                ids[i][1],
                ids[i][2],
                supplier_info['company_name'],
                supplier_rating,
                requestor['name'],
                approvor['name'],
                transactions[i][0],
                transactions[i][1]
            )
        )

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.executemany(insert_sql, insert_data)
        conn.commit()
        conn.close()
    except Exception as e:
        raise e


if __name__ == '__main__':
    # transactions_list = normal_transactions_seasonal(base_amount=20000)
    # print(transactions_list)

    # transactions_list = normal_transactions_stable_monthly(base_amount=5000)
    # print(transactions_list)

    transactions_list = abnormal_transactions_just_below_threshold()
    print(transactions_list)