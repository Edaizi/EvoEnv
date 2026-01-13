Sales Data Analysis Handbook (For Intern)

This short guide explains how to analyze quarterly sales data stored in the CloudDisk.

Data location
- CloudDisk path: `CloudDisk://sales/`
- Files are generated for ALL departments and ALL quarters.
- File naming pattern: `sales_{Department}_Q{Quarter}_{Year}.csv`
  - Example: `sales_Sales_Q2_2025.csv`

CSV schema
- date: ISO date `YYYY-MM-DD` within the target quarter
- employee_id: lowercase identifier derived from the employee name
- name: employee full name
- department: department name
- amount: order amount (float)

Typical analyses
- Per-person total sales within a quarter: sum `amount` grouped by `employee_id`
- Per-department total and average: sum `amount` by department; average = total / unique employees
- Ranking: sort per-person totals descending to get Top-N
- Cross-department operations: union or per-department grouping depending on requirement
- QoQ comparisons: compute current quarter metrics and compare with previous quarter

Suggested workflow
1) Identify the target quarter and departments from the task description
2) Download only the necessary CSV files to the workspace
3) Use a script (e.g., `solve.py`) to compute metrics and write a JSON result
4) Avoid manual copy-paste; prefer reproducible code and clear file paths
5) If any assumptions are unclear, ask colleagues instead of guessing

Output examples
- Top salesperson of a department:
  {
    "employee_id": "john_smith", "name": "John Smith", "total_sales": 12345.67
  }
- Department sales statistics:
  {
    "department": "Sales",
    "employees": 12,
    "total_sales": 345678.9,
    "avg_sales_per_person": 28806.58
  }

Notes
- Amounts can be right-skewed; robust sorting/aggregation logic is recommended
- Quarter index is one of {1,2,3,4}
- Always double-check selected files match the required quarter and departments

