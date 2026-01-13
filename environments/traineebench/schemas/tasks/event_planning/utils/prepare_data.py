from typing import List, Tuple, Optional
import random
import datetime as dt

from environments.traineebench.schemas.tasks.event_planning.utils.common import Company, Location, Restaurant, random_point_around


def generate_available_dates(
    num_people: int,
    ym: str = None,
    min_days_per_person: int = 3,
    max_days_per_person: int = 7,
    seed: Optional[int] = None
) -> Tuple[List[Tuple[str, str]], Tuple[str, str], str]:
    """Generate random available date ranges for members with a guaranteed common period.
    
    This function generates available dates for each person, ensuring there's
    a common time interval that falls entirely within one period (early/mid/late month).
    
    Args:
        num_people: Number of people
        ym: Year-month string in format "YYYY-MM" (e.g., "2025-10"). If None, uses current month.
        min_days_per_person: Minimum number of consecutive available days per person
        max_days_per_person: Maximum number of consecutive available days per person
        seed: Random seed for reproducibility
        
    Returns:
        A tuple containing:
        - List of (start_date, end_date) tuples in "YYYY-MM-DD" format for each person's available dates
        - (start_date, end_date) tuple in "YYYY-MM-DD" format representing the common available period
        - Period name: 'early' (1-10), 'mid' (11-20), or 'late' (21-31)
    
    Example:
        >>> available_dates, common_period, period_name = generate_available_dates(
        ...     num_people=5, ym="2025-10", seed=42
        ... )
        >>> print(f"Common period: {common_period[0]} to {common_period[1]} ({period_name} month)")
        >>> for i, (start, end) in enumerate(available_dates, 1):
        ...     print(f"Person {i}: {start} to {end}")
    """
    if seed is not None:
        random.seed(seed)
    
    # Parse year and month from ym string
    if ym is None:
        ym = dt.datetime.utcnow().strftime("%Y-%m")
    
    year, month = map(int, ym.split("-"))
    
    # Get the number of days in the month
    if month == 12:
        next_month = dt.date(year + 1, 1, 1)
    else:
        next_month = dt.date(year, month + 1, 1)
    days_in_month = (next_month - dt.date(year, month, 1)).days
    
    # Define period boundaries
    periods = {
        'early': (1, min(10, days_in_month)),
        'mid': (11, min(20, days_in_month)),
        'late': (21, days_in_month)
    }
    
    # Filter out invalid periods (e.g., if month has only 28 days)
    valid_periods = {name: bounds for name, bounds in periods.items() 
                     if bounds[0] <= days_in_month}
    
    # Randomly select a period for the common interval
    period_name = random.choice(list(valid_periods.keys()))
    period_start, period_end = valid_periods[period_name]
    
    # Generate a common interval within the selected period
    # The common interval should be at least 1 day
    common_length = random.randint(1, min(3, period_end - period_start + 1))
    common_start = random.randint(period_start, period_end - common_length + 1)
    common_end = common_start + common_length - 1
    common_period = (common_start, common_end)
    
    # Generate available dates for each person
    # Each person's range must include the common period
    available_dates = []
    
    for _ in range(num_people):
        # Determine how many days this person is available
        person_days = random.randint(min_days_per_person, max_days_per_person)
        
        # The person's available range must include the common period
        # So we need: person_start <= common_start and person_end >= common_end
        
        # Calculate the earliest possible start (must be within the same period)
        earliest_start = max(period_start, common_start - (person_days - common_length))
        # Calculate the latest possible start
        latest_start = common_start
        
        if earliest_start > latest_start:
            # If the person's days are less than needed, adjust
            person_start = period_start
            person_end = min(period_end, person_start + person_days - 1)
        else:
            person_start = random.randint(earliest_start, latest_start)
            person_end = person_start + person_days - 1
            
            # Make sure we don't exceed the period boundary
            if person_end > period_end:
                person_end = period_end
                person_start = max(period_start, person_end - person_days + 1)
        
        # Ensure the common period is covered
        person_start = min(person_start, common_start)
        person_end = max(person_end, common_end)
        
        # Ensure we stay within the period
        person_start = max(period_start, person_start)
        person_end = min(period_end, person_end)
        
        available_dates.append((person_start, person_end))
    
    # Convert day numbers to YYYY-MM-DD format
    available_dates_formatted = [
        (f"{year}-{month:02d}-{start:02d}", f"{year}-{month:02d}-{end:02d}")
        for start, end in available_dates
    ]
    common_period_formatted = (
        f"{year}-{month:02d}-{common_period[0]:02d}",
        f"{year}-{month:02d}-{common_period[1]:02d}"
    )
    
    return available_dates_formatted, common_period_formatted, period_name


# ==========================
# Sample Data Generation
# ==========================
def generate_candidate_locations(company: Company, n: int = 6, radius_km: float = 25.0, seed: int = 42,
                                enable_period_pricing: bool = True) -> List[Location]:
    """Generate candidate locations with optional period-based pricing.
    
    Args:
        company: Company location
        n: Number of locations to generate
        radius_km: Radius around company to generate locations
        seed: Random seed
        enable_period_pricing: If True, some locations will have different prices for early/mid/late month
    """
    random.seed(seed)
    categories = ["Park", "Historic Site", "Lakeside", "Greenway", "Garden", "Village"]
    name_prefix = ["Maple", "Willow", "Silverlake", "Cloudhill", "Riverside", "Autumn", "Rainbow", "Stonegate"]
    place_suffix = ["Forest", "Wetland", "Cultural Park", "Old Town", "Eco Park", "Country Park"]
    street_suffix = ["Rd", "St", "Ave", "Ln"]
    out: List[Location] = []
    used_names = set()  # Track used names to ensure uniqueness
    
    for _ in range(n):
        lat, lon = random_point_around(company.lat, company.lon, radius_km)
        
        # Generate unique name
        max_attempts = 100
        for attempt in range(max_attempts):
            name = f"{random.choice(name_prefix)} {random.choice(place_suffix)}"
            if name not in used_names:
                used_names.add(name)
                break
            if attempt == max_attempts - 1:
                # If all combinations exhausted, add a number suffix
                name = f"{name} {len(used_names) + 1}"
                used_names.add(name)
        
        intro = f"{name}: a fall outing destination."
        address = f"No.{random.randint(1, 999)} {random.choice(name_prefix)} {random.choice(street_suffix)}"
        ticket = random.choice([0, 20, 30, 40, 50, 80, 100])
        interest = round(random.uniform(3.2, 4.9), 2)
        cat = random.choice(categories)
        
        # For some locations (about 50%), set different prices for early/mid/late month periods
        # Mutually exclusive: either ticket_cost or ticket_cost_by_period
        fixed_cost = None
        period_pricing = None
        
        if enable_period_pricing and ticket > 0 and random.random() < 0.5:
            # Early month: typically lower price (off-peak), 80-90% of base
            # Mid month: base price or slightly higher, 95-105% of base
            # Late month: typically higher price (peak period), 110-130% of base
            period_pricing = {
                'early': round(ticket * random.uniform(0.8, 0.9), 2),
                'mid': round(ticket * random.uniform(0.95, 1.05), 2),
                'late': round(ticket * random.uniform(1.1, 1.3), 2)
            }
            intro += f" Pricing: Early month ¥{period_pricing['early']}, Mid month ¥{period_pricing['mid']}, Late month ¥{period_pricing['late']}."
        else:
            fixed_cost = float(ticket) if ticket > 0 else None
        
        out.append(Location(name=name, intro=intro, address=address, lat=lat, lon=lon,
                            ticket_cost=fixed_cost, 
                            ticket_cost_by_period=period_pricing,
                            category=cat, interest_score=interest))
    return out


def generate_candidate_restaurants(company: Company, n: int = 10, radius_km: float = 15.0, seed: int = 43,
                                 locations: Optional[List[Location]] = None) -> List[Restaurant]:
    """Generate candidate restaurants distributed around company and locations.
    
    Args:
        company: Company location
        n: Total number of restaurants to generate
        radius_km: Radius around each center point to generate restaurants
        seed: Random seed
        locations: Optional list of locations. If provided, restaurants will be distributed
                  around both company and locations (50% around company, 50% around locations)
    """
    random.seed(seed)
    cuisines = ["Shanghai", "Jiangsu/Zhejiang", "Sichuan", "Northeastern", "BBQ", "Hotpot", "Farmhouse", "Light Meal"]
    name_stem = ["Taste", "Cloud", "Harmony", "Old Stove", "Autumn", "Pine", "Maple", "Neighbor"]
    street_suffix = ["Rd", "St", "Ave", "Ln"]
    out: List[Restaurant] = []
    used_names = set()  # Track used names to ensure uniqueness
    
    # Determine distribution: if locations provided, split restaurants between company and locations
    if locations and len(locations) > 0:
        # 50% around company, 50% distributed around locations
        n_company = n // 2
        n_locations = n - n_company
        
        # Generate restaurants around company
        for _ in range(n_company):
            lat, lon = random_point_around(company.lat, company.lon, radius_km)
            _add_restaurant(lat, lon, cuisines, name_stem, street_suffix, out, used_names)
        
        # Generate restaurants around locations (distribute evenly)
        for i in range(n_locations):
            # Cycle through locations to distribute evenly
            loc = locations[i % len(locations)]
            # Use smaller radius around locations (about 60% of company radius)
            loc_radius = radius_km * 0.6
            lat, lon = random_point_around(loc.lat, loc.lon, loc_radius)
            _add_restaurant(lat, lon, cuisines, name_stem, street_suffix, out, used_names)
    else:
        # If no locations provided, generate all around company (backward compatibility)
        for _ in range(n):
            lat, lon = random_point_around(company.lat, company.lon, radius_km)
            _add_restaurant(lat, lon, cuisines, name_stem, street_suffix, out, used_names)
    
    return out

def _add_restaurant(lat: float, lon: float, cuisines: List[str], name_stem: List[str], 
                   street_suffix: List[str], out: List[Restaurant], used_names: set) -> None:
    """Helper function to add a restaurant with unique name."""
    # Generate unique name
    max_attempts = 100
    for attempt in range(max_attempts):
        c = random.choice(cuisines)
        name = f"{random.choice(name_stem)} · {c}"
        if name not in used_names:
            used_names.add(name)
            break
        if attempt == max_attempts - 1:
            # If all combinations exhausted, add a number suffix
            name = f"{name} {len(used_names) + 1}"
            used_names.add(name)
    
    intro = f"{name}: specializes in {c}."
    address = f"No.{random.randint(1, 999)} {random.choice(name_stem)} {random.choice(street_suffix)}"
    avg_price = random.choice([50, 60, 70, 80, 90, 100, 120])
    interest = round(random.uniform(3.2, 4.9), 2)
    out.append(Restaurant(name=name, intro=intro, address=address, lat=lat, lon=lon,
                          cuisine=c, avg_price_per_person=float(avg_price), interest_score=interest))