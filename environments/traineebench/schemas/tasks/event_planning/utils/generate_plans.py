from typing import List, Dict, Optional, Any
import math
import json
import os
import datetime as dt
import networkx as nx

from environments.traineebench.schemas.tasks.event_planning.utils.common import *


# ==========================
# Planning and Scoring using the Graph
# ==========================
def enumerate_candidate_plans(
    company: Company,
    locations: List[Location],
    restaurants: List[Restaurant],
    G: nx.Graph,
    visit_date: Optional[dt.date] = None,
    morning_start: str = "09:00",
    activity_duration_minutes: int = 120,
    lunch_duration_minutes: int = 90,
    speed_kmh: float = 30.0,
    return_to_company: bool = True,
    **kwargs
) -> List[ItineraryPlan]:
    """Enumerate morning -> lunch -> afternoon plans using shortest-path distances on G.
    
    Args:
        visit_date: The date of the visit (used for period-based pricing). If None, uses default pricing.
    """
    # Use current date if not specified
    if visit_date is None:
        visit_date = dt.date.today()
    # Company id
    cid = nid_company(company)

    # Node id helpers
    def lid(l: Location) -> str: return nid_loc(l)
    def rid(r: Restaurant) -> str: return nid_res(r)

    def travel_time_minutes(distance_km: float) -> int:
        """Convert distance (km) to minutes with an average speed."""
        return int(math.ceil(distance_km / speed_kmh * 60))

    start_min = parse_time_str(morning_start)

    plans: List[ItineraryPlan] = []
    for i, L1 in enumerate(locations):
        for j, L2 in enumerate(locations):
            if i == j:
                continue
            for R in restaurants:
                t = start_min

                # Distances on graph
                d1 = shortest_distance_km(cid, lid(L1), G)
                tt1 = travel_time_minutes(d1)
                t += tt1
                arrive_L1 = t
                leave_L1 = arrive_L1 + activity_duration_minutes

                d2 = shortest_distance_km(lid(L1), rid(R), G)
                tt2 = travel_time_minutes(d2)
                t = leave_L1 + tt2
                arrive_R = t
                leave_R = arrive_R + lunch_duration_minutes

                d3 = shortest_distance_km(rid(R), lid(L2), G)
                tt3 = travel_time_minutes(d3)
                t = leave_R + tt3
                arrive_L2 = t
                leave_L2 = arrive_L2 + activity_duration_minutes

                d4, tt4 = 0.0, 0
                arrive_company = leave_L2
                if return_to_company:
                    d4 = shortest_distance_km(lid(L2), cid, G)
                    tt4 = travel_time_minutes(d4)
                    arrive_company = leave_L2 + tt4

                # interest_score
                interest_score = L1.interest_score + L2.interest_score + R.interest_score
                # Budget - use date-based pricing
                l1_cost = L1.get_ticket_cost_by_date(visit_date)
                l2_cost = L2.get_ticket_cost_by_date(visit_date)
                cost_per_person = l1_cost + l2_cost + R.avg_price_per_person

                schedule = [
                    f"{morning_start} Gather at company ({company.name}) and depart ({round(d1, 2)} km to destination)",
                    f"{format_hhmm(arrive_L1)} Arrive at {L1.name}; activity ~{activity_duration_minutes//60}h; ticket ¥{l1_cost}",
                    f"{format_hhmm(leave_L1)} Depart {L1.name} ({round(d2, 2)} km to restaurant)",
                    f"{format_hhmm(arrive_R)} Arrive at {R.name} for lunch; ~{lunch_duration_minutes} minutes; avg. price ¥{R.avg_price_per_person}",
                    f"{format_hhmm(leave_R)} Depart {R.name} ({round(d3, 2)} km to destination)",
                    f"{format_hhmm(arrive_L2)} Arrive at {L2.name}; activity ~{activity_duration_minutes//60}h; ticket ¥{l2_cost}",
                ]
                if return_to_company:
                    schedule.append(f"{format_hhmm(leave_L2)} Depart {L2.name} ({round(d4, 2)} km to company)")
                    schedule.append(f"{format_hhmm(arrive_company)} Return to company; end of trip")
                else:
                    schedule.append(f"{format_hhmm(arrive_company)} Trip ends; dismiss")

                plans.append(ItineraryPlan(
                    morning_location=L1,
                    lunch_restaurant=R,
                    afternoon_location=L2,
                    schedule=schedule,
                    interest_score = interest_score,  # metric
                    cost_per_person=round(cost_per_person, 2),  # metric
                    total_travel_distance=round(d1 + d2 + d3 + d4, 2),  # metric,
                    end_time=format_hhmm(arrive_company), # metric
                    overall_score=0.0,  # metric
                    score_breakdown={},
                ))
    return plans


def score_plans(plans: List[ItineraryPlan], weights: List[float]) -> List[ItineraryPlan]:
    """Score plans by cost (lower better), interest_score (higher better), compactness (lower distance better)."""
    if not plans:
        return plans

    costs = [p.cost_per_person for p in plans]
    travels = [p.total_travel_distance for p in plans]
    interest_raw = [p.interest_score for p in plans]

    def norm(x, lo, hi, invert=False):
        if hi - lo < 1e-9:
            return 0.5
        v = (x - lo) / (hi - lo)
        return 1 - v if invert else v

    W_COST, W_IS, W_COMPACT = weights['cost'], weights['interest'], weights['distance']
    min_cost, max_cost = min(costs), max(costs)
    min_travel, max_travel = min(travels), max(travels)
    min_interest, max_interest = min(interest_raw), max(interest_raw)

    for p, r_raw in zip(plans, interest_raw):
        cost_norm = norm(p.cost_per_person, min_cost, max_cost, invert=True)
        interest_norm = norm(r_raw, min_interest, max_interest, invert=False)
        compact_norm = norm(p.total_travel_distance, min_travel, max_travel, invert=True)
        overall_score = W_COST * cost_norm + W_IS * interest_norm + W_COMPACT * compact_norm
        p.overall_score = round(overall_score, 4)
        p.score_breakdown = {
            "cost_norm": round(cost_norm, 4),
            "interest_norm": round(interest_norm, 4),
            "compactness_norm": round(compact_norm, 4),
            "overall_score": round(overall_score, 4)
        }

    plans.sort(key=lambda x: x.overall_score, reverse=True)
    return plans


def generate_plan_with_metrics(
    company: Company,
    locations: List[Location],
    restaurants: List[Restaurant],
    G: nx.Graph,
    path: str,
    visit_date: Optional[dt.date] = None,
    **kwargs
) -> None:
    """Generate plans with computed metrics and save the json output.
    
    Args:
        visit_date: The date of the visit (used for period-based pricing)
    """
    all_plans = enumerate_candidate_plans(company, locations, restaurants, G, visit_date=visit_date, **kwargs)
    scored_plans = score_plans(all_plans, kwargs["weights"])

    plans_dict = []
    for p in scored_plans:
        output = {}
        output['plan'] = {
            'morning': p.morning_location.name,
            'lunch': p.lunch_restaurant.name,
            'afternoon': p.afternoon_location.name
        }
        output['schedule'] = p.schedule
        output['metrics'] = {
            'interest_score': p.interest_score,
            'cost_per_person': p.cost_per_person,
            'total_travel_distance': p.total_travel_distance,
            'overall_score': p.overall_score,
            'end_time': p.end_time
        }
        plans_dict.append(output)

    # Get optimal plans for each metric
    optimal_plans = get_optimal_plans_by_metrics(scored_plans)
    
    # Add all optimal plans to the output
    # Each value in optimal_plans is a list of plans; output all of them
    optimal_plans_dict = {}
    for metric, plans in optimal_plans.items():
        optimal_plans_dict[metric] = [
            {
                "plan": {
                    'morning': p.morning_location.name,
                    'lunch': p.lunch_restaurant.name,
                    'afternoon': p.afternoon_location.name
                },
                "metrics": {
                    'interest_score': p.interest_score,
                    'cost_per_person': p.cost_per_person,
                    'total_travel_distance': p.total_travel_distance,
                    'overall_score': p.overall_score,
                    'end_time': p.end_time
                },
                "schedule": p.schedule
            }
            for p in plans
        ]
    # Combine all plans and optimal plans in the output
    output = {
        "all_plans": plans_dict,
        "optimal_plans": optimal_plans_dict
    }
    
    # export to a json file
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output


def export_planning_guidelines(extra_info: Dict[str, Any], filepath: str) -> str:
    """Export event planning guidelines to a separate text file.
    
    Args:
        extra_info: Dictionary containing planning parameters:
            - morning_start: Start time for morning activities (HH:MM format)
            - activity_duration_minutes: Duration of each location visit in minutes
            - lunch_duration_minutes: Duration of lunch in minutes
            - speed_kmh: Average travel speed in km/h
            - weights: Dictionary with scoring weights (interest, cost, distance)
        filepath: Path to save the guideline file
        
    Returns:
        Absolute path to the saved file
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("EVENT PLANNING GUIDELINES\n")
        f.write("=" * 80 + "\n\n")

        f.write("The same location can NOT be scheduled for both the morning and afternoon of the same day. \n\n")
        
        # Schedule Parameters
        f.write("SCHEDULE PARAMETERS\n")
        f.write("-" * 80 + "\n\n")
        
        morning_start = extra_info.get('morning_start', '09:00')
        activity_duration = extra_info.get('activity_duration_minutes', 120)
        lunch_duration = extra_info.get('lunch_duration_minutes', 90)
        
        f.write(f"Morning Start Time: {morning_start}\n")
        f.write(f"  - All team building events begin at this time\n")
        f.write(f"  - Participants gather at the company and depart together\n\n")
        
        f.write(f"Activity Duration: {activity_duration} minutes ({activity_duration//60} hours)\n")
        f.write(f"  - Time allocated for each location visit (morning and afternoon)\n")
        f.write(f"  - Includes sightseeing, activities, and rest time\n\n")
        
        f.write(f"Lunch Duration: {lunch_duration} minutes\n")
        f.write(f"  - Time allocated for lunch at the restaurant\n")
        f.write(f"  - Includes ordering, dining, and rest time\n\n")
        
        # Travel Parameters
        f.write("\nTRAVEL PARAMETERS\n")
        f.write("-" * 80 + "\n\n")
        
        speed_kmh = extra_info.get('speed_kmh', 30.0)
        f.write(f"Average Travel Speed: {speed_kmh} km/h\n")
        f.write(f"  - Used to calculate travel time between locations\n")
        f.write(f"  - Formula: Travel time (minutes) = Distance (km) / {speed_kmh} × 60\n")
        f.write(f"  - Accounts for city traffic and road conditions\n\n")
        
        # Scoring System
        f.write("\nSCORING SYSTEM\n")
        f.write("-" * 80 + "\n\n")
        
        weights = extra_info.get('weights', {'interest': 0.4, 'cost': 0.4, 'distance': 0.2})
        w_interest = weights.get('interest', 0.4)
        w_cost = weights.get('cost', 0.4)
        w_distance = weights.get('distance', 0.2)
        
        f.write("Overall Score Calculation:\n\n")
        f.write(f"  The overall score balances three key metrics with the following weights:\n\n")
        f.write(f"  1. Interest Score (weight: {w_interest})\n")
        f.write(f"     - Higher is better\n")
        f.write(f"     - Sum of location and restaurant interest ratings\n")
        
        f.write(f"  2. Cost per Person (weight: {w_cost})\n")
        f.write(f"     - Lower is better\n")
        f.write(f"     - Includes location tickets and restaurant meal costs\n")
        f.write(f"     - Note: Some locations have period-based pricing (early/mid/late month)\n\n")
        
        f.write(f"  3. Travel Distance (weight: {w_distance})\n")
        f.write(f"     - Lower is better\n")
        f.write(f"     - Total distance: Company → Morning Location → Restaurant → Afternoon Location → Company\n\n")
        
        f.write(f"  Formula:\n")
        f.write(f"    overall_score = {w_interest} × interest_norm + {w_cost} × (1 - cost_norm) + {w_distance} × (1 - distance_norm)\n\n")
        
        f.write(f"  Normalization:\n")
        f.write(f"    - Each metric is normalized to the [0, 1] range\n")
        f.write(f"    - Normalization is based on the min/max values across all candidate plans:\n")
        f.write(f"      x_norm = (x - x_min) / (x_max - x_min); if x_min == x_max then x_norm = 0.5\n")
        f.write(f"    - For cost and distance: lower raw values correspond to higher normalized scores (1 - normalized value)\n")
        f.write(f"    - For interest: higher raw values correspond to higher normalized scores (normalized value)\n\n")
        
        f.write("=" * 80 + "\n")
    
    return os.path.abspath(filepath)


def export_locations_restaurants_info(locations: List[Location], restaurants: List[Restaurant], filepath: str) -> str:
    """Export locations and restaurants information to a text file.
    
    Args:
        locations: List of location objects
        restaurants: List of restaurant objects
        filepath: Path to save the text file
        
    Returns:
        Absolute path to the saved file
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("LOCATIONS AND RESTAURANTS INFORMATION\n")
        f.write("=" * 80 + "\n\n")
        
        # Write locations information
        f.write("TOURIST LOCATIONS\n")
        f.write("-" * 80 + "\n\n")
        for idx, loc in enumerate(locations, 1):
            f.write(f"{idx}. {loc.name}\n")
            f.write(f"   Category: {loc.category}\n")
            f.write(f"   Address: {loc.address}\n")
            f.write(f"   Coordinates: ({loc.lat:.6f}, {loc.lon:.6f})\n")
            if loc.ticket_cost_by_period:
                f.write(f"   Period Pricing:\n")
                f.write(f"     - Early month (1-10): ¥{loc.ticket_cost_by_period['early']}\n")
                f.write(f"     - Mid month (11-20): ¥{loc.ticket_cost_by_period['mid']}\n")
                f.write(f"     - Late month (21-31): ¥{loc.ticket_cost_by_period['late']}\n")
            elif loc.ticket_cost is not None:
                f.write(f"   Ticket Cost: ¥{loc.ticket_cost}\n")
            else:
                f.write(f"   Ticket Cost: Free\n")
            f.write(f"   Interest Score: {loc.interest_score}/5.0\n")
            f.write(f"   Description: {loc.intro}\n")
            f.write("\n")
        
        # Write restaurants information
        f.write("\n" + "=" * 80 + "\n")
        f.write("RESTAURANTS\n")
        f.write("-" * 80 + "\n\n")
        for idx, rest in enumerate(restaurants, 1):
            f.write(f"{idx}. {rest.name}\n")
            f.write(f"   Cuisine: {rest.cuisine}\n")
            f.write(f"   Address: {rest.address}\n")
            f.write(f"   Coordinates: ({rest.lat:.6f}, {rest.lon:.6f})\n")
            f.write(f"   Average Price per Person: ¥{rest.avg_price_per_person}\n")
            f.write(f"   Interest Score: {rest.interest_score}/5.0\n")
            f.write(f"   Description: {rest.intro}\n")
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write(f"Total Locations: {len(locations)}\n")
        f.write(f"Total Restaurants: {len(restaurants)}\n")
        f.write("=" * 80 + "\n")
    
    return os.path.abspath(filepath)


def get_optimal_plans_by_metrics(plans: List[ItineraryPlan]) -> Dict[str, List[ItineraryPlan]]:
    """
    Return plans with optimal metrics for each category:
    - Highest interest_score
    - Lowest cost per person
    - Shortest total travel distance
    - Highest overall score
    If multiple plans share the optimal value, return all of them.
    """
    if not plans:
        return {}

    def get_all_with_best(plans, key, reverse=False):
        sorted_plans = sorted(plans, key=key, reverse=reverse)
        best_value = key(sorted_plans[0])
        return [p for p in sorted_plans if key(p) == best_value]

    optimal_plans = {
        "highest_interest": get_all_with_best(plans, key=lambda x: x.interest_score, reverse=True),
        "lowest_cost": get_all_with_best(plans, key=lambda x: x.cost_per_person),
        "shortest_distance": get_all_with_best(plans, key=lambda x: x.total_travel_distance),
        "highest_score": get_all_with_best(plans, key=lambda x: x.overall_score, reverse=True)
    }

    return optimal_plans