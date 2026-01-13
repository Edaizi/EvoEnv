import random
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta

from environments.traineebench.schemas.common_config import CommonConfig
from environments.traineebench.schemas.tasks.data_completion import utils

class Domain(Enum):
    SALES = "sales"
    TRANSACTIONS = "transactions"
    INVENTORY = "inventory"
    FINANCE = "finance"
    LOGISTICS = "logistics"
    WEB = "web"


class SalesType(Enum):
    QUARTER_FROM_MONTHS = "quarter_from_months"  # Quarter = M1+M2+M3. Task: Fill missing quarterly sales total by summing up three monthly columns.
    QOQ_RATE = "qoq_rate"  # QoQ = (Q_t - Q_{t-1})/Q_{t-1}. Task: Calculate the quarter-over-quarter growth rate based on the current and previous quarter's total sales.


class TransactionsType(Enum):
    TAX_FEE = "tax_fee"  # fee = amount * rate(category). Task: Compute a fee by looking up a rate in a separate table and multiplying it by the transaction amount.
    TOTAL_FROM_ITEMS = "total_from_items"  #  total = sum(items). Task: Calculate the total amount by summing several item cost columns.


class InventoryType(Enum):
    ENDING_FROM_FLOW = "ending_from_flow"  # end = begin + inbound - outbound - shrinkage. Task: Calculate the ending inventory based on beginning stock plus flows (inbound, outbound, shrinkage).
    DAILY_INTERPOLATION = "daily_interpolation"  # linear interpolation for gaps. Task: Fill gaps in daily stock levels, typically using linear interpolation between known points.


class FinanceType(Enum):
    ACCOUNT_BALANCE_FROM_DETAILS = "account_balance_from_details"  # balance = sum(details). Task: Compute the final account balance by summing various detail columns.
    DEPRECIATION_STRAIGHT_LINE = "depreciation_straight_line"  # (cost-salvage)/life_months. Task: Calculate monthly depreciation using the straight-line method from asset cost, salvage value, and lifespan.


class LogisticsType(Enum):
    ETA_DISTANCE_SLA = "eta_distance_sla"  # eta_h = distance_km/speed + handling. Task: Estimate arrival time (ETA) based on distance and a carrier's Service Level Agreement (SLA) for speed and handling.
    SEGMENT_TIME_SUM = "segment_time_sum"  # total = sum(segment_times). Task: Calculate the total transit time by summing up the durations of individual journey segments.


class WebType(Enum):
    ROLLING_AVG = "rolling_avg"  # rolling 7d average. Task: Calculate the 7-day rolling average for a given metric.
    FUNNEL = "funnel"  # clicks = impressions * ctr. Task: Compute the number of clicks based on impressions and click-through rate (CTR).


DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "very_easy": {"missing_rate": 0.05, "segment_len": 0, "seed": 11, "rows": 30},
    "easy": {"missing_rate": 0.08, "segment_len": 1, "seed": 12, "rows": 50},
    "medium": {"missing_rate": 0.15, "segment_len": 3, "seed": 13, "rows": 80},
    "hard": {"missing_rate": 0.25, "segment_len": 5, "seed": 14, "rows": 120},
    "very_hard": {"missing_rate": 0.35, "segment_len": 7, "seed": 15, "rows": 200},
}


class DataCompletionGenerator:
    def __init__(
        self,
        common_config: CommonConfig,
        domain: str,
        task_type: str,
        difficulty: str = "medium",
        rows: int | None = None,
    ) -> None:
        self.common_config = common_config
        self.workspace_path = common_config.workspace_path
        self.cloud_root = common_config.cloud_disk_path / "data_completion"
        self.answer_root = common_config.task_root_path / "data_completion_answers"
        self.cloud_root.mkdir(exist_ok=True, parents=True)
        self.answer_root.mkdir(exist_ok=True, parents=True)

        self.domain = Domain(domain)
        self.task_type = task_type
        self.difficulty = difficulty if difficulty in DIFFICULTY_PRESETS else "medium"

        self.random = random.Random(DIFFICULTY_PRESETS[self.difficulty]["seed"])
        
        # dataset size control
        self.rows = int(rows) if rows is not None else int(DIFFICULTY_PRESETS[self.difficulty]["rows"])


        self.domain_dir = self.cloud_root / self.domain.value
        self.domain_dir.mkdir(exist_ok=True, parents=True)

        self._copy_manuals()

        # A mapping from (domain, type) to the generation function in utils
        self.GENERATION_MAP = {
            (Domain.SALES, SalesType.QUARTER_FROM_MONTHS.value): utils.gen_sales_quarter_from_months,
            (Domain.SALES, SalesType.QOQ_RATE.value): utils.gen_sales_qoq,
            (Domain.TRANSACTIONS, TransactionsType.TAX_FEE.value): utils.gen_transactions_tax_fee,
            (Domain.TRANSACTIONS, TransactionsType.TOTAL_FROM_ITEMS.value): utils.gen_transactions_total_from_items,
            (Domain.INVENTORY, InventoryType.ENDING_FROM_FLOW.value): utils.gen_inventory_ending_from_flow,
            (Domain.INVENTORY, InventoryType.DAILY_INTERPOLATION.value): utils.gen_inventory_daily_interpolation,
            (Domain.FINANCE, FinanceType.ACCOUNT_BALANCE_FROM_DETAILS.value): utils.gen_finance_account_balance,
            (Domain.FINANCE, FinanceType.DEPRECIATION_STRAIGHT_LINE.value): utils.gen_finance_depreciation,
            (Domain.LOGISTICS, LogisticsType.ETA_DISTANCE_SLA.value): utils.gen_logistics_eta,
            (Domain.LOGISTICS, LogisticsType.SEGMENT_TIME_SUM.value): utils.gen_logistics_segment_sum,
            (Domain.WEB, WebType.ROLLING_AVG.value): utils.gen_web_rolling,
            (Domain.WEB, WebType.FUNNEL.value): utils.gen_web_funnel,
        }

        # generate dataset and answers
        self.dataset_csv, self.expected_csv, self.target_column, self.description = self._generate()

    def _copy_manuals(self):
        manuals_text = (
            "# Data Completion Task Handbook\n\n"
            "This handbook provides the rules for completing missing data in various domains.\n"
            "You should ONLY modify the specified target column; other columns must remain unchanged.\n\n"
            "## Domain-Specific Rules\n\n"
            "### Sales\n"
            "- **Quarterly Sum**: `quarter_total = m1 + m2 + m3`. Any one of these can be derived if the others are known.\n"
            "- **QoQ Growth**: `qoq = (current_quarter_total - previous_quarter_total) / previous_quarter_total`. Any term can be derived if others are known. Notes that quarter 1 has not qoq value, you should not fill it.\n\n"
            "### Transactions\n"
            "- **Tax/Fee Calculation**: `fee = amount * rate`. The `rate` is determined by the transaction `category` and must be looked up yourself.\n"
            "- **Total from Items**: `total = item_a + item_b + item_c`. Any term can be derived.\n\n"
            "### Inventory\n"
            "- **Ending Flow**: `ending = begin + inbound - outbound - shrinkage`. This is a balance equation, any term can be derived.\n"
            "- **Daily Interpolation**: Missing `stock_level` values should be filled using linear interpolation between the nearest known data points (before and after the gap).\n\n"
            "### Finance\n"
            "- **Account Balance**: `balance = detail1 + detail2 + detail3`. Any term can be derived.\n"
            "- **Depreciation**: `monthly_dep = (cost - salvage) / life_months`. This is the straight-line method. Any term can be derived.\n\n"
            "### Logistics\n"
            "- **ETA Calculation**: `eta_hours = distance_km / speed_kmh + handling_h`. Speed and handling parameters must be looked up yourself.\n"
            "- **Segment Time Sum**: `total_time = seg1 + seg2 + seg3`. Any term can be derived.\n\n"
            "### Web\n"
            "- **Rolling Average**: `rolling_7d` is the 7-day moving average of the `metric` column.\n"
            "- **Funnel Conversion**: `clicks = impressions * ctr`. Any term can be derived.\n"
        )
        with open(self.cloud_root / "manuals_for_data_completion.md", "w", encoding="utf-8") as wf:
            wf.write(manuals_text)


    def _generate(self) -> Tuple[Path, Path, str, str]:
        gen_func = self.GENERATION_MAP.get((self.domain, self.task_type))
        if not gen_func:
            raise NotImplementedError(f"Unsupported domain/type: {self.domain.value}/{self.task_type}")
        return gen_func(self)


    def _render_description(self, output_filename: str) -> str:
        domain_name = self.domain.value
        resource_hint = f"- Data directory: `CloudDisk://data_completion/{domain_name}/`."

        # Add specific hints for tasks requiring NPC interaction
        npc_hint = ""
        if self.domain == Domain.TRANSACTIONS and self.task_type == TransactionsType.TAX_FEE.value:
            npc_hint = "- Hint: You may need to consult the Finance department for information on calculation parameters."
        elif self.domain == Domain.LOGISTICS and self.task_type == LogisticsType.ETA_DISTANCE_SLA.value:
            npc_hint = "- Hint: You may need to consult the Sales_1 department for information on carrier service level agreements (SLA)."

        objective_desc = (
            f"- For this task, you need to find the data file under the data directory and fill in the missing values in the file.\n"
        )
        if npc_hint:
            objective_desc += f"{npc_hint}\n"

        return (
            f"Mentor: Please complete the data missed for `{domain_name}`.\n\n"
            f"Resources:\n"
            f"{resource_hint}\n"
            f"- Handbook: `CloudDisk://data_completion/manuals_for_data_completion.md`.\n\n"
            f"Objective:\n"
            f"{objective_desc}"
            f"- Only modify the target column; keep other columns exactly the same.\n\n"
            f"Required Output:\n"
            f"- Write a CSV `{output_filename}` in the workspace root with the same structure, with missing cells correctly filled.\n\n"
        )

    def add_task(self, task_name: str, deadline: str):
        output_filename = f"data_completion_{self.dataset_csv.name}"
        self.common_config.config['tasks'].append(
            {
                "task_description": self._render_description(output_filename),
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": "data_completion_check",
                    "args": {
                        "domain": self.domain.value,
                        "task_type": self.task_type,
                        "original_csv": str(self.dataset_csv),
                        "expected_csv": str(self.expected_csv),
                        "target_column": self.target_column,
                        "output_path": str(self.common_config.workspace_path / output_filename),
                        "tolerance": 0.1,
                    }
                }
            }
        )

        npc_prompt_injection = ""
        target_dept = ""
    
        if self.domain == Domain.TRANSACTIONS and self.task_type == TransactionsType.TAX_FEE.value:
            target_dept = "Finance"
            npc_prompt_injection = f"Please check the `rates.csv` file in the `CloudDisk://data_completion/transactions/` directory for rate information."
    
        elif self.domain == Domain.LOGISTICS and self.task_type == LogisticsType.ETA_DISTANCE_SLA.value:
            target_dept = "Sales_1" # Logistics task is temporarily assigned to the Sales_1 department
            npc_prompt_injection = f"Please check the `carrier_sla.csv` file in the `CloudDisk://data_completion/logistics/` directory for SLA details."
        
        if target_dept and npc_prompt_injection:
            for env_agent in self.common_config.config['agents']['env_agents']:
                if env_agent['infos']['department'] == target_dept:
                    env_agent['system_prompt'] += (
                        f"\n- When asked about parameters for the data completion task, respond with: '{npc_prompt_injection}' "
                        "Do not perform any other actions."
                    )

        # General handbook hint: any NPC asked "how to complete missing data" should point to the handbook
        for env_agent in self.common_config.config['agents']['env_agents']:
            env_agent['system_prompt'] += (
                "\n- When asked how to complete missing data, respond with: 'Please refer to the Handbook at CloudDisk://data_completion/manuals_for_data_completion.md'. Do not perform any other actions."
        )


def random_data_completion_task(seed: int = 1234) -> Dict[str, Any]:
    random.seed(seed)
    # Pick a random domain
    domain = random.choice(list(Domain))
    
    # Pick a valid task type for that domain
    if domain == Domain.SALES:
        task_type = random.choice(list(SalesType)).value
    elif domain == Domain.TRANSACTIONS:
        task_type = random.choice(list(TransactionsType)).value
    elif domain == Domain.INVENTORY:
        task_type = random.choice(list(InventoryType)).value
    elif domain == Domain.FINANCE:
        task_type = random.choice(list(FinanceType)).value
    elif domain == Domain.LOGISTICS:
        task_type = random.choice(list(LogisticsType)).value
    elif domain == Domain.WEB:
        task_type = random.choice(list(WebType)).value

    return {
        "domain": domain.value,
        "task_type": task_type,
        "difficulty": random.choice(["very_easy", "easy", "medium", "hard", "very_hard"]),
    }


if __name__ == "__main__":
    params = random_data_completion_task()
    print(f"Generating random task: {params}")
    
    # # 6 domains × 2 types × 5 difficulties = 60 tasks
    # # Here we just run the random one
    # dir_name = f"tasks/tmp_data_completion_random"
    # common = CommonConfig(dir_name, start_time=datetime.fromisoformat('2025-10-20T17:00:00'))
    # gen = DataCompletionGenerator(
    #     common_config=common,
    #     domain=params["domain"],
    #     task_type=params["task_type"],
    #     difficulty=params["difficulty"]
    # )
    
    # gen.add_task(
    #     task_name=f"data_completion_{params['domain']}_{params['task_type']}",
    #     deadline=datetime.fromisoformat('2025-11-20T20:00:00')
    # )
    # common.save_config()
    # print(f"Generated: {dir_name}")
