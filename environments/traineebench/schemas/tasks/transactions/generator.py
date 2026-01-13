import os
from pathlib import Path
import random
import shutil
from typing import List, Dict, Callable
from datetime import datetime

from environments.traineebench.schemas.tasks.transactions.utils.random_suppliers import (
    generate_high_frequency_suppliers,
)

from environments.traineebench.schemas.tasks.transactions.utils.random_transactions import (
    create_transaction_table,
    normal_transactions_seasonal,
    normal_transactions_stable_monthly,
    generate_transaction_materials,
    insert_transaction_data,
    abnormal_transactions_just_below_threshold
)

from environments.traineebench.schemas.utils.random_employees import (
    sample_dept,
    sample_requestor,
    get_dept_manager
)

from environments.traineebench.schemas.common_config import CommonConfig


CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


class TransactionGenerator:
    def __init__(
        self, common_config: CommonConfig,
        num_normal_transactions: int, 
        num_abnormal_transactions: int,
    ) -> None:
        self.common_config = common_config
        self.num_normal_transactions = num_normal_transactions
        self.num_abnormal_transactions = num_abnormal_transactions

        self.invoice_root_path = common_config.cloud_disk_path / 'financial/invoices'
        self.invoice_root_path.mkdir(exist_ok=True, parents=True)
        self.approval_root_path = common_config.cloud_disk_path / 'financial/approvals'
        self.approval_root_path.mkdir(exist_ok=True, parents=True)

        self.db_path = common_config.workspace_path / 'transactions.db'

        create_transaction_table(self.db_path)

        self.copy_manuals()
        self.generate_data_and_files()


    def copy_manuals(self):
        shutil.copy2(
            CURRENT_DIR / "templates/manuals_for_transactions_data_review.md",
            self.common_config.cloud_disk_path / "financial/manuals_for_transactions_data_review.md"
        )

    
    def generate_transactions(
        self, company_employees: List[Dict[str, str]],
        num_transactions: int,
        suppliers: List[Dict[str, str]],
        suppliers_ratings: List[str],
        transaction_functions: List[Callable]
    ):
        requestors = []
        approvors = []

        for i in range(num_transactions):
            transaction_func = random.choice(transaction_functions)
            supplier_info = suppliers[i]
            transactions = transaction_func()
            dept = sample_dept()
            approvor = get_dept_manager(dept, company_employees)
            approvors.append(approvor)
            if suppliers_ratings:
                supplier_rating = random.choice(suppliers_ratings)
            else:
                supplier_rating = ''
            requestor = sample_requestor(dept, company_employees)
            requestors.append(requestor)
            ids, invoices, approvals = generate_transaction_materials(
                transactions,
                supplier_info,
                supplier_rating,
                requestor,
                approvor
            )

            insert_transaction_data(
                self.db_path,
                transactions,
                ids,
                supplier_info,
                supplier_rating,
                requestor,
                approvor
            )

            for i in range(len(invoices)):
                invoice = invoices[i]
                invoice_save_path = self.invoice_root_path / f'{ids[i][1]}.txt'
                with open(invoice_save_path, 'w', encoding='utf-8') as wf:
                    wf.write(invoice)

                approval = approvals[i]
                approval_save_path = self.approval_root_path / f'{ids[i][2]}.txt'
                with open(approval_save_path, 'w', encoding='utf-8') as wf:
                    wf.write(approval)


    def generate_data_and_files(self):
        # generate normal transactions
        normal_suppliers = generate_high_frequency_suppliers(
            self.num_normal_transactions
        )
        self.generate_transactions(
            self.common_config.company_employees, self.num_normal_transactions,
            normal_suppliers, ['A', 'B'],
            [
                normal_transactions_seasonal,
                normal_transactions_stable_monthly
            ]
        )

        # generate abnormal transactions
        if self.num_abnormal_transactions:
            abnormal_suppliers = generate_high_frequency_suppliers(
                self.num_abnormal_transactions
            )
            self.gt_answer = [elem['company_name'] for elem in abnormal_suppliers]
            self.generate_transactions(
                self.common_config.company_employees, self.num_abnormal_transactions,
                abnormal_suppliers, [],
                [
                    abnormal_transactions_just_below_threshold,
                ]
            )
        else:
            self.gt_answer = []


    def add_task(self, task_name: str, deadline: str):
        self.common_config.config['tasks'].append(
            {
                # ===== fully observe version prompt =====
                # "task_description": "Your should review transaction data, which is stored in `Workspace://transactions.db`. You can see all the data in the `transactions` table. You can find some tips to help you solve problems in `CloudDisk:manuals_for_intern.md`. When you review data, first seek help from one colleague in the Finance department to avoid making wrong moves. When you are finished reviewing the data, please create a file `transaction_data_review_report.json` in your workspace and fill it with the name of the supplier whose transactions you found to be abnormal in the following format:\n\n```JSON\n\"abnormal_suppliers\": [\"suppliers_names\"]\n```",

                # ===== partially observe version prompt =====
                "task_description": "Your should review transaction data, which is stored in `Workspace://transactions.db`. You can see all the data in the `transactions` table. You can find some tips to help you solve problems in `CloudDisk:manuals_for_intern.md`. When you are finished reviewing the data, please create a file `transaction_data_review_report.json` in your workspace and fill it with the name of the supplier whose transactions you found to be abnormal in the following format:\n\n```JSON\n\"abnormal_suppliers\": [\"suppliers_names\"]\n```",
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": "abnormal_supplier",
                    "args": {
                        "checkpoint_files": [
                            'manuals_for_intern.md', 
                            'manuals_for_transactions_data_review.md'
                        ],
                        "output_file": "transaction_data_review_report.json",
                        "gt_answer": self.gt_answer
                    }
                }
            }
        )

        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['department'] == 'Finance':
                env_agent['system_prompt'] = env_agent['system_prompt'] + '\n- When she asks about transaction data review, direct her to `CloudDisk://financial/manuals_for_transactions_data_review.md` . \n- When she asks about transaction invoices, direct her to `CloudDisk://financial/approvals/` and `CloudDisk://financial/invoices/`.\n'
