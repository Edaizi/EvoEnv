import random
import itertools
import math
from rich import print
from typing import Dict, List

# --- Data Pools ---
# Expanded pools to support larger companies
first_names = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Emily", "Peter",
    "Ashley", "Steven", "Kimberly", "Andrew", "Donna", "Joshua", "Michelle", "Brian",
    "Kevin", "Laura", "Jason", "Amy", "Jeff", "Rebecca", "Gary", "Sharon"
]

last_names = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Green", "Baker", "Adams", "Nelson"
]

# --- Company Structure Configuration ---
# Defines the rules for building a company template procedurally.
# Ratios determine the proportional size of departments and roles.
COMPANY_STRUCTURE_CONFIG = {
    # Executive roles are added based on company size thresholds.
    "executives": [
        {'position': 'Chief Executive Officer (CEO)', 'min_size': 1},
        {'position': 'Chief Technology Officer (CTO)', 'min_size': 5},
        {'position': 'Chief Operating Officer (COO)', 'min_size': 15},
        {'position': 'Chief Financial Officer (CFO)', 'min_size': 25},
    ],
    # Department definitions include their overall ratio and the roles within them.
    # Note: The sum of all 'overall_ratio' values must equal 1.0.
    "departments": {
        "Engineering": {
            "overall_ratio": 0.41,  # 41% of non-executive staff
            "manager_position": "Engineering Manager",
            "manager_to_ic_ratio": 8, # 1 manager for every 8 Individual Contributors (ICs)
            "ic_roles": [
                {'position': 'Senior Software Engineer', 'ratio': 0.25},
                {'position': 'Software Engineer', 'ratio': 0.60},
                {'position': 'QA Engineer', 'ratio': 0.10},
                {'position': 'DevOps Specialist', 'ratio': 0.05},
            ]
        },
        "Sales_1": {
            "overall_ratio": 0.06, # 6% of non-executive staff
            "manager_position": "Sales Manager",
            "manager_to_ic_ratio": 7,
            "ic_roles": [
                {'position': 'Account Executive', 'ratio': 0.40},
                {'position': 'Sales Representative', 'ratio': 0.60},
            ]
        },
        "Sales_2": {
            "overall_ratio": 0.06, # 6% of non-executive staff
            "manager_position": "Sales Manager",
            "manager_to_ic_ratio": 7,
            "ic_roles": [
                {'position': 'Account Executive', 'ratio': 0.40},
                {'position': 'Sales Representative', 'ratio': 0.60},
            ]
        },
        "Sales_3": {
            "overall_ratio": 0.06, # 6% of non-executive staff
            "manager_position": "Sales Manager",
            "manager_to_ic_ratio": 7,
            "ic_roles": [
                {'position': 'Account Executive', 'ratio': 0.40},
                {'position': 'Sales Representative', 'ratio': 0.60},
            ]
        },
        "Marketing": {
            "overall_ratio": 0.14, # 14% of non-executive staff
            "manager_position": "Marketing Manager",
            "manager_to_ic_ratio": 5,
            "ic_roles": [
                {'position': 'SEO Specialist', 'ratio': 0.30},
                {'position': 'Content Creator', 'ratio': 0.50},
                {'position': 'Social Media Planner', 'ratio': 0.20},
            ]
        },
        "Product": {
            "overall_ratio": 0.11, # 11% of non-executive staff
            "manager_position": "Product Manager",
            "manager_to_ic_ratio": 6,
            "ic_roles": [
                {'position': 'Product Designer', 'ratio': 0.30},
                {'position': 'UX/UI Designer', 'ratio': 0.70},
            ]
        },
        "Human Resources": {
            "overall_ratio": 0.07, # 7% of non-executive staff
            "manager_position": "HR Manager",
            "manager_to_ic_ratio": 10,
            "ic_roles": [
                {'position': 'Recruiter', 'ratio': 0.50},
                {'position': 'HR Generalist', 'ratio': 0.50},
            ]
        },
        "Finance": {
            "overall_ratio": 0.09, # 9% of non-executive staff
            "manager_position": "Finance Manager",
            "manager_to_ic_ratio": 6, # 1 manager for every 6 ICs
            "ic_roles": [
                {'position': 'Accountant', 'ratio': 0.50},
                {'position': 'Financial Analyst', 'ratio': 0.50},
            ]
        }
    }
}

def distribute_items_by_ratio(total_items: int, ratios: dict) -> dict:
    """
    Distributes a total number of items into bins based on ratios.
    Uses the largest remainder method to ensure the sum is exactly total_items.
    """
    if total_items == 0:
        return {key: 0 for key in ratios}
    
    # Ensure ratios are not empty and their sum is greater than zero
    if not ratios or sum(ratios.values()) <= 0:
        return {key: 0 for key in ratios}

    total_ratio = sum(ratios.values())
    
    # Calculate initial allocation and remainders
    initial_allocations = {}
    remainders = {}
    for key, ratio in ratios.items():
        exact_share = (ratio / total_ratio) * total_items
        initial_allocations[key] = int(exact_share)
        remainders[key] = exact_share - int(exact_share)
        
    # Distribute remaining items based on largest remainder
    current_total = sum(initial_allocations.values())
    items_to_distribute = total_items - current_total
    
    sorted_remainders = sorted(remainders.items(), key=lambda item: item[1], reverse=True)
    
    for i in range(items_to_distribute):
        key_to_increment = sorted_remainders[i][0]
        initial_allocations[key_to_increment] += 1
        
    return initial_allocations

def generate_company_template(total_employees: int) -> list[dict]:
    """
    Generates a structured company template based on a numeric size.
    """
    if total_employees < 1:
        return []

    template = []
    
    # --- 1. Allocate Executives ---
    exec_dept = "Executive"
    exec_allocated_count = 0
    for exec_role in COMPANY_STRUCTURE_CONFIG["executives"]:
        if total_employees >= exec_role['min_size']:
            template.append({
                'department': exec_dept,
                'position': exec_role['position'],
                'count': 1
            })
            exec_allocated_count += 1
    
    # --- 2. Allocate remaining employees to departments ---
    non_exec_pool = total_employees - exec_allocated_count
    dept_ratios = {name: data['overall_ratio'] for name, data in COMPANY_STRUCTURE_CONFIG["departments"].items()}
    department_headcounts = distribute_items_by_ratio(non_exec_pool, dept_ratios)

    # --- 3. Allocate roles within each department ---
    for dept_name, total_headcount in department_headcounts.items():
        if total_headcount == 0:
            continue
            
        dept_config = COMPANY_STRUCTURE_CONFIG["departments"][dept_name]

        # Calculate managers and ICs for the department
        manager_to_ic_ratio = dept_config["manager_to_ic_ratio"]
        # A manager is needed if there are any employees in the department.
        num_managers = math.ceil(total_headcount / (manager_to_ic_ratio + 1)) if total_headcount > manager_to_ic_ratio else (1 if total_headcount > 0 else 0)
        num_managers = min(num_managers, total_headcount) # Can't have more managers than people
        
        num_ics = total_headcount - num_managers

        # Add managers to template
        if num_managers > 0:
            template.append({
                'department': dept_name,
                'position': dept_config['manager_position'],
                'count': num_managers
            })
        
        # Distribute ICs among available roles
        if num_ics > 0:
            ic_ratios = {role['position']: role['ratio'] for role in dept_config['ic_roles']}
            ic_allocations = distribute_items_by_ratio(num_ics, ic_ratios)
            for position, count in ic_allocations.items():
                if count > 0:
                    template.append({
                        'department': dept_name,
                        'position': position,
                        'count': count
                    })
    
    return template

def generate_company_employees_by_size(num_employees: int) -> list[dict]:
    """
    Generates a full company roster with unique names for a given size.

    This is the main function to call. It creates a realistic company structure
    and then populates it with randomly generated, unique employees.

    Args:
        num_employees (int): The desired total number of employees in the company.

    Returns:
        list[dict]: A list of employee dictionaries.

    Raises:
        ValueError: If the company size smaller than 10.
        ValueError: If the company size exceeds available unique name combinations.
    """
    if num_employees < 10:
        raise ValueError('`num_employees` must be an integer larger than 10.')
    # Step 1: Procedurally generate the company structure template.
    company_template = generate_company_template(num_employees)
    
    # This recalculation is a sanity check to match the template's final size
    actual_num_employees = sum(item['count'] for item in company_template)

    # Step 2: Create a list of all job slots to be filled from the template.
    job_slots = []
    for role_info in company_template:
        for _ in range(role_info['count']):
            job_slots.append({
                "department": role_info['department'],
                "position": role_info['position']
            })

    # Step 3: Generate a list of unique names.
    all_possible_names = list(itertools.product(first_names, last_names))
    if actual_num_employees > len(all_possible_names):
        raise ValueError(
            f"Cannot generate {actual_num_employees} employees. "
            f"Only {len(all_possible_names)} unique name combinations are available. "
            f"Please add more names to the data pools."
        )

    selected_name_tuples = random.sample(all_possible_names, actual_num_employees)
    unique_names = [f"{first} {last}" for first, last in selected_name_tuples]
    random.shuffle(unique_names)

    # Step 4: Assign unique names to the job slots.
    company_roster = []
    for i in range(actual_num_employees):
        employee = {
            "name": unique_names[i],
            "department": job_slots[i]['department'],
            "position": job_slots[i]['position']
        }
        company_roster.append(employee)

    return company_roster


def sample_dept(exclusion: List[str] = []):
    all_depts = COMPANY_STRUCTURE_CONFIG['departments'].keys()
    
    available_depts = [dept for dept in all_depts if dept not in exclusion]
    
    if not available_depts:
        return None
    
    return random.choice(available_depts)


def sample_requestor(dept: str, company_employees: List[Dict[str, str]]):
    dept_manager_position = COMPANY_STRUCTURE_CONFIG['departments'][dept]['manager_position']
    dept_ics = [
        employee for employee in company_employees if employee['department'] == dept and employee['position'] != dept_manager_position
    ]
    # Handle cases where a department might only have a manager
    if not dept_ics:
        return get_dept_manager(dept, company_employees)
    return random.choice(dept_ics)


def get_dept_manager(dept: str, company_employees: List[Dict[str, str]]):
    dept_manager_position = COMPANY_STRUCTURE_CONFIG['departments'][dept]['manager_position']
    # Filter for the manager(s) of the specified department
    dept_managers = [employee for employee in company_employees if employee['position'] == dept_manager_position]
    # Handle case where no manager exists for some reason, though logic should prevent this
    if not dept_managers:
        return None 
    return random.choice(dept_managers)


if __name__ == "__main__":
    random.seed(4578)
    # You can now just specify the desired size!
    company_size_to_generate = 10

    try:
        # Generate the full company roster with just one function call.
        my_company = generate_company_employees_by_size(company_size_to_generate)

        # Print the results.
        print(f"\n--- Generated Company Roster for {len(my_company)} Employees ---")
        my_company.sort(key=lambda x: (x['department'], x['position']))

        for i, person in enumerate(my_company, 1):
            print(f"{i:02d}. Name: {person['name']:<22} | Department: {person['department']:<20} | Position: {person['position']}")
    
    except ValueError as e:
        print(f"Error: {e}")
