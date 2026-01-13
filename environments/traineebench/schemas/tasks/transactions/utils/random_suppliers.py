import random

# --- Data Pools for Random Generation ---
# These lists and dictionaries contain the raw data used to build the company profiles.

# --- Common Data ---
FIRST_NAMES = ['Michael', 'Jennifer', 'Christopher', 'Jessica', 'David', 'Sarah', 'James', 'Emily', 'John', 'Laura']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
COMPANY_SUFFIXES = ['Inc.', 'LLC', 'Corp.', 'Solutions', 'Group', 'Technologies', 'Consulting', 'Services']
STREET_NAMES = ['Main St', 'Oak Ave', 'Pine Ln', 'Maple Dr', 'Cedar Blvd', 'Elm St', 'Wall St']
CITIES = ['New York', 'San Francisco', 'Chicago', 'Austin', 'Seattle', 'Boston', 'Los Angeles']
STATES = ['NY', 'CA', 'IL', 'TX', 'WA', 'MA']

# --- High-Frequency Supplier Data ---
# Data for suppliers whose products/services are consumed regularly.
HIGH_FREQ_PREFIXES = ['Innovate', 'Synergy', 'Quantum', 'Apex', 'NextGen', 'Strive', 'Cloud', 'Data', 'Office']
HIGH_FREQ_BUSINESS_PRODUCTS = {
    'SaaS Provider': ['CRM Software Subscription', 'Project Management Tool', 'Cloud Hosting Services', 'Cybersecurity Suite'],
    'IT Support Services': ['Managed IT Services Contract', 'Helpdesk Support Retainer', 'Network Monitoring Service'],
    'Digital Marketing Agency': ['SEO & SEM Services Retainer', 'Social Media Management', 'Content Marketing Package'],
    'Office Supplies': ['A4 Paper & Stationery', 'Printer Ink & Toner', 'General Office Consumables'],
    'Business Consulting': ['Monthly Financial Advisory', 'HR & Payroll Services', 'Ongoing Legal Retainer']
}

# --- Low-Frequency Supplier Data ---
# Data for suppliers providing one-time or infrequent products/services.
LOW_FREQ_PREFIXES = ['Core', 'Strategic', 'Foundation', 'Global', 'Precision', 'Enterprise', 'Capital', 'Advanced']
LOW_FREQ_BUSINESS_PRODUCTS = {
    'Custom Software Development': ['Enterprise Resource Planning (ERP) System Build', 'Mobile App Development Project', 'Custom Analytics Dashboard'],
    # 'Heavy Machinery & Equipment': ['Industrial CNC Machine', 'Construction Excavator', 'Manufacturing Assembly Line Robotics'],
    'Strategic Consulting Firm': ['Market Entry Analysis Project', 'Corporate Restructuring Plan', 'Digital Transformation Strategy'],
    'Infrastructure Provider': ['Office Building Construction', 'Data Center Setup', 'Warehouse Renovation Project'],
    'Specialized Hardware Vendor': ['High-Performance Computing Cluster', 'Lab Research Equipment', 'Custom Server Racks']
}


def _generate_single_company(name_prefixes, name_suffixes, business_products_map):
    """
    A private helper function to generate a single company profile.
    It's used by the public-facing functions to create either high or low-frequency suppliers.

    Args:
        name_prefixes (list): A list of prefixes for company names.
        name_suffixes (list): A list of suffixes for company names.
        business_products_map (dict): A dictionary mapping business areas to lists of products/services.

    Returns:
        dict: A dictionary containing the details of a single randomly generated company.
    """
    # 1. Generate Company Name
    prefix = random.choice(name_prefixes)
    suffix = random.choice(name_suffixes)
    company_name = f"{prefix} {suffix}"

    # 2. Generate Contact Person
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    contact_person = f"{first_name} {last_name}"

    # 3. Select Business Area and a Corresponding Product
    business_area = random.choice(list(business_products_map.keys()))
    main_product = random.choice(business_products_map[business_area])

    # 4. Generate Address
    street_number = random.randint(100, 9999)
    street_name = random.choice(STREET_NAMES)
    city = random.choice(CITIES)
    state = random.choice(STATES)
    zip_code = f"{random.randint(10000, 99999)}"
    address = f"{street_number} {street_name}, {city}, {state} {zip_code}"

    # 5. Generate Contact Information
    phone_number = f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"
    # Create a simple, clean version of the company name for the email domain
    email_domain = company_name.lower().replace(' ', '').replace('.', '') + '.com'
    email = f"{first_name[0].lower()}.{last_name.lower()}@{email_domain}"

    company_info = {
        "company_name": company_name,
        "contact_person": contact_person,
        "main_business": business_area,
        "main_product_or_service": main_product,
        "address": address,
        "phone": phone_number,
        "email": email
    }
    return company_info


def generate_high_frequency_suppliers(num_suppliers):
    """
    Generates a list of random supplier companies for frequently purchased goods and services.
    These are typically subscription-based or require regular restocking.
    Examples: SaaS, IT support, office supplies, ongoing consulting.

    Args:
        num_suppliers (int): The number of supplier companies to generate.

    Returns:
        list: A list of dictionaries, where each dictionary represents a supplier company.
    """
    suppliers = []
    for _ in range(num_suppliers):
        supplier = _generate_single_company(
            name_prefixes=HIGH_FREQ_PREFIXES,
            name_suffixes=COMPANY_SUFFIXES,
            business_products_map=HIGH_FREQ_BUSINESS_PRODUCTS
        )
        suppliers.append(supplier)
    return suppliers


def generate_low_frequency_suppliers(num_suppliers):
    """
    Generates a list of random supplier companies for infrequently purchased goods and services.
    These are typically one-time projects or major capital expenditures.
    Examples: Custom software projects, heavy machinery, strategic A-to-Z consulting.

    Args:
        num_suppliers (int): The number of supplier companies to generate.

    Returns:
        list: A list of dictionaries, where each dictionary represents a supplier company.
    """
    suppliers = []
    for _ in range(num_suppliers):
        supplier = _generate_single_company(
            name_prefixes=LOW_FREQ_PREFIXES,
            name_suffixes=COMPANY_SUFFIXES,
            business_products_map=LOW_FREQ_BUSINESS_PRODUCTS
        )
        suppliers.append(supplier)
    return suppliers


# --- Example Usage ---
if __name__ == "__main__":
    from pprint import pprint

    # Number of suppliers to generate for the demo
    N = 3

    print("--- Generating High-Frequency Suppliers (e.g., SaaS, Office Supplies) ---")
    high_freq_list = generate_high_frequency_suppliers(N)
    for i, company in enumerate(high_freq_list, 1):
        print(f"\n--- High-Frequency Supplier #{i} ---")
        pprint(company)

    print("\n" + "="*50 + "\n")

    print("--- Generating Low-Frequency Suppliers (e.g., Custom Projects, Heavy Machinery) ---")
    low_freq_list = generate_low_frequency_suppliers(N)
    for i, company in enumerate(low_freq_list, 1):
        print(f"\n--- Low-Frequency Supplier #{i} ---")
        pprint(company)

