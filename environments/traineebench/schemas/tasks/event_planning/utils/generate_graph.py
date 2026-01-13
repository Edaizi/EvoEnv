import math
import json
import os
import datetime as dt
import matplotlib.pyplot as plt
import networkx as nx

from environments.traineebench.schemas.tasks.event_planning.utils.common import *


# ==========================
# Dedicated NetworkX Graph Builder
# ==========================
def build_nx_graph(company: Company,
                   locations: List[Location],
                   restaurants: List[Restaurant],
                   connect: str = "mst") -> nx.Graph:
    """
    Build a NetworkX weighted graph that connects company + locations + restaurants.
    - Node attributes: type ('company'/'location'/'restaurant'), name, lon, lat, pos=(lon, lat)
    - Edge attribute: weight (km, haversine)
    - connect='mst': return Minimum Spanning Tree (clean/sparse, default)
      connect='complete': return the complete graph with all pairwise edges
    """
    # Build complete graph with all nodes
    G_full = nx.Graph()

    # Add nodes with attributes
    cid = nid_company(company)
    G_full.add_node(cid, type="company", name=company.name, lon=company.lon, lat=company.lat, pos=(company.lon, company.lat))
    for l in locations:
        nid = nid_loc(l)
        G_full.add_node(nid, type="location", name=l.name, lon=l.lon, lat=l.lat, pos=(l.lon, l.lat))
    for r in restaurants:
        nid = nid_res(r)
        G_full.add_node(nid, type="restaurant", name=r.name, lon=r.lon, lat=r.lat, pos=(r.lon, r.lat))

    nodes = list(G_full.nodes())
    # Pre-fetch coordinates
    coords = {n: (G_full.nodes[n]["lat"], G_full.nodes[n]["lon"]) for n in nodes}

    # Add pairwise weighted edges (km)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            lat1, lon1 = coords[a]
            lat2, lon2 = coords[b]
            w = haversine_km(lat1, lon1, lat2, lon2)
            G_full.add_edge(a, b, weight=w)

    if connect == "complete":
        return G_full

    if connect != "mst":
        raise ValueError("connect must be 'mst' or 'complete'")

    # Compute MST on the complete graph
    T = nx.minimum_spanning_tree(G_full, weight="weight")
    return T


def export_graph_to_json(G: nx.Graph, filepath: str, include_mst: bool = True) -> str:
    """
    Export graph nodes/edges to JSON.
    - Nodes include: id, type, name, lon, lat
    - Edges include: u, v, distance_km
    - Optionally include MST edge list (for clean drawing on the web, etc.)
    """
    nodes = []
    for n, data in G.nodes(data=True):
        nodes.append({
            "id": n,
            "type": data.get("type"),
            "name": data.get("name"),
            "lon": float(data.get("lon")),
            "lat": float(data.get("lat")),
        })

    edges = [{"u": u, "v": v, "distance_km": float(round(d.get("weight", 0.0), 4))}
             for u, v, d in G.edges(data=True)]

    content = {
        "projection": "lonlat",
        "meta": {
            "generated_at": dt.datetime.utcnow().isoformat() + "Z",
            "nodes": len(nodes),
            "edges": len(edges),
            "graph_type": "tree" if nx.is_tree(G) else "graph"
        },
        "nodes": nodes,
        "edges": edges
    }

    if include_mst and not nx.is_tree(G):
        T = nx.minimum_spanning_tree(G, weight="weight")
        mst_edges = [{"u": u, "v": v, "distance_km": float(round(d.get("weight", 0.0), 4))}
                     for u, v, d in T.edges(data=True)]
        content["mst_edges"] = mst_edges

    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    return os.path.abspath(filepath)


# ==========================
# Plotting (MST with distance labels)
# ==========================
def plot_graph_mst(G: nx.Graph,
                   filepath: str = "mst_map.png",
                   label_fontsize: int = 7,
                   line_color: str = "purple",
                   line_width: float = 2.0) -> str:
    """
    Plot the MST of the given graph (even if G is complete) with distance labels.
    Node positions are taken from node attribute 'pos' = (lon, lat).
    Node name labels are offset along a normal direction to adjacent edges to avoid overlap.
    """
    # If G is not a tree, compute its MST for a clean drawing
    G_draw = G if nx.is_tree(G) else nx.minimum_spanning_tree(G, weight="weight")

    # Extract positions
    pos_attr = nx.get_node_attributes(G_draw, "pos")
    if not pos_attr:
        raise ValueError("Graph nodes must have 'pos'=(lon,lat) attributes.")

    lons = [xy[0] for xy in pos_attr.values()]
    lats = [xy[1] for xy in pos_attr.values()]

    plt.figure(figsize=(12, 10))
    margin = 0.03
    if lons and lats:
        plt.xlim(min(lons) - margin, max(lons) + margin)
        plt.ylim(min(lats) - margin, max(lats) + margin)

    ax = plt.gca()
    fig = plt.gcf()

    # Helpers
    def to_px(xy):
        X = ax.transData.transform(xy)
        return X[0], X[1]

    def unit(vx, vy, eps=1e-9):
        m = math.hypot(vx, vy)
        if m < eps:
            return 0.0, 0.0
        return vx / m, vy / m
    
    # Track occupied regions to avoid label overlap
    occupied_regions = []
    
    def check_overlap(x, y, width, height):
        """Check if a region overlaps with any occupied region"""
        for ox, oy, ow, oh in occupied_regions:
            if not (x + width < ox or x > ox + ow or y + height < oy or y > oy + oh):
                return True
        return False
    
    def find_best_label_position(x, y, text_width, text_height, base_offset_px, preferred_angles=None):
        """Find the best position for a label that doesn't overlap with existing labels"""
        if preferred_angles is None:
            # Try 8 directions: N, NE, E, SE, S, SW, W, NW
            preferred_angles = [90, 45, 0, -45, -90, -135, 180, 135]
        
        for angle in preferred_angles:
            rad = math.radians(angle)
            
            # Try increasing distances
            for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
                offset = base_offset_px * mult
                dx = offset * math.cos(rad)
                dy = offset * math.sin(rad)
                
                # Convert to data coordinates
                px_x, px_y = to_px((x, y))
                label_px_x = px_x + dx
                label_px_y = px_y + dy
                
                # Check if this position is free
                if not check_overlap(label_px_x - text_width/2, label_px_y - text_height/2, 
                                   text_width, text_height):
                    # Convert pixel offset to points for annotate
                    dx_pts = dx * 72.0 / fig.dpi
                    dy_pts = dy * 72.0 / fig.dpi
                    return dx_pts, dy_pts, label_px_x, label_px_y
        
        # If all positions are occupied, use the first preferred angle with max offset
        rad = math.radians(preferred_angles[0])
        offset = base_offset_px * 3.5
        dx = offset * math.cos(rad)
        dy = offset * math.sin(rad)
        px_x, px_y = to_px((x, y))
        dx_pts = dx * 72.0 / fig.dpi
        dy_pts = dy * 72.0 / fig.dpi
        return dx_pts, dy_pts, px_x + dx, px_y + dy

    # Offset label away from edges using smart positioning
    def place_label(nid: str, color: str, text: str, base_offset_px: float = 15.0):
        x, y = pos_attr[nid]
        px_x, px_y = to_px((x, y))
        neigh = list(G_draw.neighbors(nid))

        # Calculate preferred direction (away from edges)
        sx, sy = 0.0, 0.0
        for nb in neigh:
            nx_, ny_ = pos_attr[nb]
            nbx, nby = to_px((nx_, ny_))
            vx, vy = nbx - px_x, nby - px_y
            ux, uy = unit(vx, vy)
            sx += ux
            sy += uy

        # Principal direction (if none, use NE)
        dirx, diry = unit(sx, sy)
        if dirx == 0.0 and diry == 0.0:
            dirx, diry = unit(1.0, 1.0)

        # Normal direction to avoid overlapping with incident edges
        nxp, nyp = unit(-diry, dirx)
        
        # Increase offset for company node
        if G_draw.nodes[nid].get("type") == "company":
            base_offset_px *= 1.5
        
        # Calculate preferred angle from normal direction
        preferred_angle = math.degrees(math.atan2(nyp, nxp))
        
        # Generate candidate angles centered around preferred direction
        preferred_angles = [preferred_angle + offset for offset in 
                          [0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180]]
        
        # Estimate text size (rough approximation)
        text_width = len(text) * label_fontsize * 0.6
        text_height = label_fontsize * 1.5
        
        # Find best position
        dx_pts, dy_pts, final_px_x, final_px_y = find_best_label_position(
            x, y, text_width, text_height, base_offset_px, preferred_angles
        )
        
        # Mark this region as occupied
        occupied_regions.append((final_px_x - text_width/2, final_px_y - text_height/2, 
                               text_width, text_height))

        ax.annotate(
            text,
            xy=(x, y), xycoords="data",
            xytext=(dx_pts, dy_pts), textcoords="offset points",
            fontsize=label_fontsize, color=color,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, alpha=0.9, linewidth=0.8),
            arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.6, shrinkA=0, shrinkB=0)
        )

    # Draw nodes with different markers/colors by type
    def draw_node(nid: str):
        x, y = pos_attr[nid]
        t = G_draw.nodes[nid].get("type", "other")
        name = G_draw.nodes[nid].get("name", nid.split(":", 1)[-1])
        labels = ax.get_legend_handles_labels()[1]

        if t == "company":
            plt.scatter(x, y, marker='*', c='red', s=160, label=None if "Company" in labels else "Company")
            place_label(nid, color="red", text=" " + name)
        elif t == "location":
            plt.scatter(x, y, marker='o', c='royalblue', s=60, label=None if "Location" in labels else "Location")
            place_label(nid, color="navy", text=" " + name)
        else:
            plt.scatter(x, y, marker='s', c='orange', s=55, label=None if "Restaurant" in labels else "Restaurant")
            place_label(nid, color="saddlebrown", text=" " + name)

    for n in G_draw.nodes():
        draw_node(n)

    # Draw MST edges with distance labels
    def disp_vec(x0, y0, x1, y1):
        X0 = ax.transData.transform((x0, y0))
        X1 = ax.transData.transform((x1, y1))
        return (X1[0] - X0[0], X1[1] - X0[1])

    def v_norm(v):
        m = math.hypot(v[0], v[1])
        return (0.0, 0.0) if m == 0.0 else (v[0] / m, v[1] / m)

    for u, v, data in G_draw.edges(data=True):
        x1, y1 = pos_attr[u]
        x2, y2 = pos_attr[v]
        w = data.get("weight", 0.0)
        
        # Draw the edge
        plt.plot([x1, x2], [y1, y2], color=line_color, linewidth=line_width, alpha=0.85)
        
        # Place label at midpoint
        xm, ym = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        edge_text = f"{w:.1f} km"
        
        # Estimate text size for edge label (add padding for bbox and safety margin)
        edge_text_width = len(edge_text) * (label_fontsize - 1) * 0.9 + 10
        edge_text_height = (label_fontsize - 1) * 2 + 8
        
        # Convert to pixel coordinates for overlap checking
        px_xm, px_ym = to_px((xm, ym))
        
        # First try: place directly on the edge
        if not check_overlap(px_xm - edge_text_width/2, px_ym - edge_text_height/2,
                           edge_text_width, edge_text_height):
            # No overlap, place directly on edge
            occupied_regions.append((px_xm - edge_text_width/2, px_ym - edge_text_height/2,
                                   edge_text_width, edge_text_height))
            ax.text(
                xm, ym, edge_text,
                fontsize=label_fontsize - 1,
                color=line_color,
                ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=line_color, alpha=0.9, linewidth=0.6)
            )
        else:
            # Overlap detected, try offset positions perpendicular to the edge
            ex_px, ey_px = disp_vec(x1, y1, x2, y2)
            nx_px, ny_px = v_norm((-ey_px, ex_px))
            
            best_pos = None
            # Try both sides with increasing offset
            for side_mult in [1.0, -1.0]:
                for offset_mult in [1.5, 2.0, 2.5, 3.0, 3.5]:
                    offset_px = 18.0 * side_mult * offset_mult
                    dx_pts = (nx_px * offset_px) * 72.0 / fig.dpi
                    dy_pts = (ny_px * offset_px) * 72.0 / fig.dpi
                    
                    label_px_x = px_xm + dx_pts * fig.dpi / 72.0
                    label_px_y = px_ym + dy_pts * fig.dpi / 72.0
                    
                    if not check_overlap(label_px_x - edge_text_width/2, label_px_y - edge_text_height/2,
                                       edge_text_width, edge_text_height):
                        best_pos = (dx_pts, dy_pts, label_px_x, label_px_y)
                        break
                if best_pos:
                    break
            
            # Use best position found, or default to first offset with larger distance
            if best_pos is None:
                offset_px = 25.0
                dx_pts = (nx_px * offset_px) * 72.0 / fig.dpi
                dy_pts = (ny_px * offset_px) * 72.0 / fig.dpi
                label_px_x = px_xm + dx_pts * fig.dpi / 72.0
                label_px_y = px_ym + dy_pts * fig.dpi / 72.0
                best_pos = (dx_pts, dy_pts, label_px_x, label_px_y)
            
            # Mark region as occupied
            occupied_regions.append((best_pos[2] - edge_text_width/2, best_pos[3] - edge_text_height/2,
                                   edge_text_width, edge_text_height))
            
            # Draw with offset and indicator line
            ax.annotate(
                edge_text,
                xy=(xm, ym), xycoords="data",
                xytext=(best_pos[0], best_pos[1]), textcoords="offset points",
                fontsize=label_fontsize - 1, color=line_color,
                ha='center', va='center',
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=line_color, alpha=0.9, linewidth=0.6),
                arrowprops=dict(
                    arrowstyle='-',
                    connectionstyle='arc3,rad=0',
                    color=line_color,
                    lw=0.8,
                    alpha=0.6,
                    linestyle=':'
                )
            )

    plt.title("MST of Company–Locations–Restaurants (distance labeled)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.grid(alpha=0.25)
    plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(filepath, dpi=160)
    plt.close()
    return os.path.abspath(filepath)