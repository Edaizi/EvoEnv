from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import math
import random
import datetime as dt
import networkx as nx


# ==========================
# Data Models
# ==========================
@dataclass
class Company:
    name: str
    address: str
    lat: float
    lon: float

@dataclass
class Location:
    name: str
    intro: str
    address: str
    lat: float
    lon: float
    ticket_cost: Optional[float] = None  # Fixed ticket cost (mutually exclusive with ticket_cost_by_period)
    ticket_cost_by_period: Optional[Dict[str, float]] = None  # Pricing by period: {'early': price, 'mid': price, 'late': price}
    category: str = "Park"
    interest_score: float = 4.0
    
    def get_ticket_cost_by_date(self, date: dt.date) -> float:
        """Get ticket cost based on the date (early/mid/late month period).
        
        Args:
            date: The visit date
            
        Returns:
            Ticket cost for that date period
        """
        if self.ticket_cost_by_period is not None:
            day = date.day
            # Divide month into three periods: early (1-10), mid (11-20), late (21-31)
            if day <= 10:
                period = 'early'
            elif day <= 20:
                period = 'mid'
            else:
                period = 'late'
            return self.ticket_cost_by_period[period]
        elif self.ticket_cost is not None:
            return self.ticket_cost
        else:
            return 0.0

@dataclass
class Restaurant:
    name: str
    intro: str
    address: str
    lat: float
    lon: float
    cuisine: str = "Chinese"
    avg_price_per_person: float = 80.0,
    interest_score: float = 4.0,


@dataclass
class ItineraryPlan:
    morning_location: Location
    lunch_restaurant: Restaurant
    afternoon_location: Location
    schedule: List[str]
    interest_score: float
    cost_per_person: float
    total_travel_distance: float
    end_time: str
    overall_score: float
    score_breakdown: Dict[str, float]


# ==========================
# Utilities
# ==========================
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points in kilometers."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlbd = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlbd / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def parse_time_str(t: str) -> int:
    """Convert HH:MM to minutes from midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)

def format_hhmm(minutes_from_midnight: int) -> str:
    """Convert minutes-from-midnight to HH:MM."""
    h = minutes_from_midnight // 60
    m = minutes_from_midnight % 60
    return f"{h:02d}:{m:02d}"

def is_interval_covered(intervals: List[Tuple[str, str]], start: str, end: str) -> bool:
    """Check if any interval fully covers [start, end]."""
    s = parse_time_str(start)
    e = parse_time_str(end)
    for (a, b) in intervals:
        sa = parse_time_str(a)
        eb = parse_time_str(b)
        if sa <= s and eb >= e:
            return True
    return False


def random_point_around(lat: float, lon: float, radius_km: float) -> Tuple[float, float]:
    """Generate a random point within radius_km around (lat, lon) approximately."""
    r = radius_km * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    dlat = (r * math.cos(theta)) / 111.0
    dlon = (r * math.sin(theta)) / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return (lat + dlat, lon + dlon)


# ==========================
# Node ID helpers
# ==========================
def nid_company(c: Company) -> str: return f"company:{c.name}"
def nid_loc(l: Location) -> str: return f"loc:{l.name}"
def nid_res(r: Restaurant) -> str: return f"res:{r.name}"


# ==========================
# Distance and Paths on Graph
# ==========================
def shortest_distance_km(u: str, v: str, G: nx.Graph) -> float:
    """Shortest-path distance by 'weight' on the given graph."""
    return nx.shortest_path_length(G, source=u, target=v, weight="weight")

def shortest_path_nodes(u: str, v: str, G: nx.Graph) -> List[str]:
    """Return node sequence for the shortest path."""
    return nx.shortest_path(G, source=u, target=v, weight="weight")