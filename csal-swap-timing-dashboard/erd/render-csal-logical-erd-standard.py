from html import escape
from pathlib import Path
import math
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle


OUT = Path(__file__).resolve().parent
BASE = "csal-booking-cutoff-logical-erd-standard"
PAGE_W, PAGE_H = 12.0, 16.0
WHITE, BLACK, MID, LIGHT, GRID = "#FFFFFF", "#111111", "#666666", "#F3F3F3", "#B8B8B8"
HEADER_H, COLUMN_H, ROW_H = 0.38, 0.25, 0.265


ENTITIES = [
    {"id": "plan", "title": "CSAL_PLAN", "x": 4.15, "y": 12.35, "w": 3.70,
     "rows": [("bigint", "csal_id", "LK"), ("string", "customer", ""),
              ("string", "agreement", ""), ("string", "tcr", ""),
              ("string", "office", ""), ("string", "service", ""),
              ("string", "week_num", ""), ("string", "finalized_voyage", ""),
              ("decimal", "requested_teu", ""), ("decimal", "adjusted_teu", ""),
              ("decimal", "submitted_teu", ""), ("string", "acceptance_status", "")]},
    {"id": "audit", "title": "CSAL_AUDIT_TRAIL", "x": 0.35, "y": 8.05, "w": 3.25,
     "rows": [("bigint", "uuid", "LK"), ("bigint", "csal_id", "FK"),
              ("string", "type", ""), ("string", "change_field", ""),
              ("string", "change_from", ""), ("string", "change_to", ""),
              ("string", "user_name", ""), ("string", "date_time", "")]},
    {"id": "assoc", "title": "CSAL_BOOKING_ASSOC_EVT", "x": 4.05, "y": 7.25, "w": 3.90,
     "rows": [("bigint", "id", "LK"), ("bigint", "csal_id", "FK"),
              ("string", "shipment_num", "FK"), ("boolean", "match_ind", ""),
              ("string", "corp_svc_cde", ""), ("string", "corp_vsl_voy", ""),
              ("string", "sail_week", ""), ("string", "tcr_srgn_cde", ""),
              ("string", "loading_office", ""), ("timestamp", "rec_upd_dt_utc", "")]},
    {"id": "vessel", "title": "CSAL_VESSEL_VOYAGE", "x": 8.55, "y": 8.20, "w": 3.10,
     "rows": [("bigint", "uuid", "LK"), ("string", "service", "AK"),
              ("string", "week_num", "AK"), ("string", "voyage", "AK"),
              ("timestamp", "rec_upd_dt_utc", "")]},
    {"id": "shipment", "title": "CSAL_SHIPMENT", "x": 0.45, "y": 3.50, "w": 3.20,
     "rows": [("string", "shipment_number", "LK"), ("string", "agreement_number", ""),
              ("string", "tcr", ""), ("string", "sub_tcr", ""),
              ("string", "shipment_status", ""), ("timestamp", "rec_cre_dt_utc", ""),
              ("timestamp", "rec_upd_dt_utc", "")]},
    {"id": "detail", "title": "CSAL_BOOKING_DETAIL", "x": 4.00, "y": 1.80, "w": 4.15,
     "rows": [("string", "shipment_num", "LK"), ("string", "corp_svc_cde", ""),
              ("string", "corp_vsl_cde", ""), ("string", "corp_voy_num", ""),
              ("string", "corp_voy_dir", ""), ("string", "lpol_port_cde", ""),
              ("string", "f_load_svc_cde", ""), ("string", "f_load_vsl_cde", ""),
              ("string", "f_load_voy_num", ""), ("string", "f_load_dir", ""),
              ("string", "fpol_port_cde", ""), ("timestamp", "rec_cre_dt_utc", ""),
              ("timestamp", "rec_upd_dt_utc", "")]},
    {"id": "stop", "title": "CSAL_VOY_STOP_DTL", "x": 8.65, "y": 1.05, "w": 3.05,
     "rows": [("bigint", "id", "LK"), ("string", "msg_business_key", "AK"),
              ("string", "port_code", "JOIN"), ("string", "arr_svvd", "JOIN"),
              ("string", "dep_svvd", "JOIN"), ("boolean", "use_dep_svvd", ""),
              ("boolean", "is_load_allowed", ""), ("boolean", "is_omitted", ""),
              ("boolean", "is_tentative_schedule", ""),
              ("timestamp", "tcr_cutoff_date", "TARGET"),
              ("timestamp", "rec_upd_dt_utc", "")]},
]

for entity in ENTITIES:
    entity["h"] = HEADER_H + COLUMN_H + ROW_H * len(entity["rows"])
BY_ID = {entity["id"]: entity for entity in ENTITIES}


def draw_entity(ax, entity):
    x, y, w, h = entity["x"], entity["y"], entity["w"], entity["h"]
    ax.add_patch(Rectangle((x, y), w, h, facecolor=WHITE, edgecolor=BLACK,
                           linewidth=1.15, zorder=3))
    ax.add_patch(Rectangle((x, y + h - HEADER_H), w, HEADER_H,
                           facecolor=BLACK, edgecolor=BLACK, linewidth=1.0, zorder=4))
    ax.text(x + w / 2, y + h - HEADER_H / 2, entity["title"], color=WHITE,
            fontsize=7.7, fontweight="bold", ha="center", va="center", zorder=5)
    column_y = y + h - HEADER_H - COLUMN_H
    ax.add_patch(Rectangle((x, column_y), w, COLUMN_H, facecolor=LIGHT,
                           edgecolor=BLACK, linewidth=0.65, zorder=4))
    type_x, key_x = x + w * 0.25, x + w * 0.85
    ax.plot([type_x, type_x], [y, y + h - HEADER_H], color=GRID, linewidth=0.55, zorder=5)
    ax.plot([key_x, key_x], [y, y + h - HEADER_H], color=GRID, linewidth=0.55, zorder=5)
    ax.text(x + w * 0.125, column_y + COLUMN_H / 2, "TYPE", fontsize=5.3,
            color=BLACK, fontweight="bold", ha="center", va="center", zorder=6)
    ax.text(type_x + (key_x - type_x) / 2, column_y + COLUMN_H / 2, "COLUMN",
            fontsize=5.3, color=BLACK, fontweight="bold", ha="center", va="center", zorder=6)
    ax.text(key_x + (x + w - key_x) / 2, column_y + COLUMN_H / 2, "KEY",
            fontsize=5.3, color=BLACK, fontweight="bold", ha="center", va="center", zorder=6)
    for index, (dtype, name, key) in enumerate(entity["rows"]):
        row_top = column_y - index * ROW_H
        row_bottom = row_top - ROW_H
        if index % 2:
            ax.add_patch(Rectangle((x, row_bottom), w, ROW_H, facecolor="#FAFAFA",
                                   edgecolor="none", zorder=3))
        ax.plot([x, x + w], [row_bottom, row_bottom], color=GRID, linewidth=0.45, zorder=5)
        ax.text(x + 0.08, row_bottom + ROW_H / 2, dtype, fontsize=5.35, color=MID,
                ha="left", va="center", zorder=6)
        ax.text(type_x + 0.08, row_bottom + ROW_H / 2, name, fontsize=5.65,
                color=BLACK, fontweight="bold" if key else "normal",
                ha="left", va="center", zorder=6)
        ax.text(key_x + (x + w - key_x) / 2, row_bottom + ROW_H / 2, key,
                fontsize=4.8, color=BLACK, fontweight="bold", ha="center", va="center", zorder=6)


def normalized_vector(start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def draw_cardinality(ax, endpoint, inside_point, cardinality):
    ux, uy = normalized_vector(endpoint, inside_point)
    px, py = -uy, ux
    def point(distance):
        return endpoint[0] + ux * distance, endpoint[1] + uy * distance
    def bar(distance):
        cx, cy = point(distance)
        ax.plot([cx - px * 0.09, cx + px * 0.09], [cy - py * 0.09, cy + py * 0.09],
                color=BLACK, linewidth=1.0, zorder=9)
    if cardinality == "one":
        bar(0.07); bar(0.16)
    elif cardinality == "zero_one":
        bar(0.07)
        cx, cy = point(0.21)
        ax.add_patch(Circle((cx, cy), 0.052, facecolor=WHITE, edgecolor=BLACK,
                            linewidth=0.9, zorder=9))
    else:
        tip_x, tip_y = point(0.04)
        joint_x, joint_y = point(0.22)
        for sign in (-1, 0, 1):
            ax.plot([tip_x, joint_x + px * 0.11 * sign],
                    [tip_y, joint_y + py * 0.11 * sign], color=BLACK,
                    linewidth=1.0, zorder=9)
        if cardinality == "zero_many":
            cx, cy = point(0.32)
            ax.add_patch(Circle((cx, cy), 0.052, facecolor=WHITE, edgecolor=BLACK,
                                linewidth=0.9, zorder=9))
        else:
            bar(0.31)


def draw_relationship(ax, points, source_card, target_card, label, label_xy, dashed=False):
    ax.plot([p[0] for p in points], [p[1] for p in points], color=BLACK,
            linewidth=0.9, linestyle=(0, (4, 3)) if dashed else "solid", zorder=7)
    draw_cardinality(ax, points[0], points[1], source_card)
    draw_cardinality(ax, points[-1], points[-2], target_card)
    ax.text(label_xy[0], label_xy[1], label, fontsize=5.15, color=BLACK,
            ha="center", va="center", bbox=dict(facecolor=WHITE, edgecolor="none", pad=1.0), zorder=10)


def render_preview():
    fig, ax = plt.subplots(figsize=(12, 16), dpi=200)
    fig.patch.set_facecolor(WHITE); ax.set_facecolor(WHITE)
    ax.set_xlim(0, PAGE_W); ax.set_ylim(0, PAGE_H); ax.axis("off")
    for entity in ENTITIES:
        draw_entity(ax, entity)
    plan, audit, assoc = BY_ID["plan"], BY_ID["audit"], BY_ID["assoc"]
    vessel, shipment = BY_ID["vessel"], BY_ID["shipment"]
    detail, stop = BY_ID["detail"], BY_ID["stop"]
    draw_relationship(ax, [(plan["x"] + .35, plan["y"]), (plan["x"] + .35, 11.55),
                           (audit["x"] + audit["w"] - .30, 11.55),
                           (audit["x"] + audit["w"] - .30, audit["y"] + audit["h"])],
                      "one", "zero_many", "csal_id", (3.40, 11.55))
    draw_relationship(ax, [(plan["x"] + plan["w"] / 2, plan["y"]),
                           (plan["x"] + plan["w"] / 2, assoc["y"] + assoc["h"])],
                      "one", "zero_many", "csal_id", (6.00, 11.55))
    draw_relationship(ax, [(plan["x"] + plan["w"] - .35, plan["y"]),
                           (plan["x"] + plan["w"] - .35, 11.35),
                           (vessel["x"] + vessel["w"] / 2, 11.35),
                           (vessel["x"] + vessel["w"] / 2, vessel["y"] + vessel["h"])],
                      "zero_many", "one", "service + week_num", (9.15, 11.35), True)
    draw_relationship(ax, [(assoc["x"] + .45, assoc["y"]), (assoc["x"] + .45, 6.55),
                           (shipment["x"] + shipment["w"] - .35, 6.55),
                           (shipment["x"] + shipment["w"] - .35, shipment["y"] + shipment["h"])],
                      "zero_many", "one", "shipment_num = shipment_number", (3.40, 6.55))
    draw_relationship(ax, [(assoc["x"] + assoc["w"] / 2, assoc["y"]),
                           (assoc["x"] + assoc["w"] / 2, detail["y"] + detail["h"])],
                      "zero_many", "one", "shipment_num", (6.00, 6.50))
    draw_relationship(ax, [(vessel["x"] + vessel["w"] / 2, vessel["y"]),
                           (vessel["x"] + vessel["w"] / 2, 6.35),
                           (stop["x"] + stop["w"] / 2, 6.35),
                           (stop["x"] + stop["w"] / 2, stop["y"] + stop["h"])],
                      "one", "one_many", "service + week + voyage to SVVD", (10.15, 6.35), True)
    draw_relationship(ax, [(detail["x"] + detail["w"], detail["y"] + detail["h"] - .55),
                           (8.38, detail["y"] + detail["h"] - .55),
                           (8.38, 5.42),
                           (9.15, 5.42),
                           (9.15, stop["y"] + stop["h"])],
                      "zero_many", "one", "exact SVVD + port",
                      (8.78, 5.58))
    ax.text(.42, .38, "Logical analysis keys and cardinalities; physical Databricks PK/FK constraints are not confirmed.",
            fontsize=5.5, color=MID, ha="left", va="center")
    plt.subplots_adjust(left=.02, right=.98, top=.99, bottom=.02)
    fig.savefig(OUT / f"{BASE}.png", dpi=240, facecolor=WHITE, bbox_inches="tight", pad_inches=.08)
    svg_path = OUT / f"{BASE}.svg"
    fig.savefig(svg_path, facecolor=WHITE, bbox_inches="tight", pad_inches=.08)
    fig.savefig(OUT / f"{BASE}.pdf", facecolor=WHITE, bbox_inches="tight", pad_inches=.08)
    plt.close(fig)
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n"
    )


def html_entity(entity):
    rows = ["<tr style='background:#F3F3F3;border-top:1px solid #111111;'><td style='width:24%;padding:4px 5px;font-size:8px;font-weight:700;text-align:center;'>TYPE</td><td style='width:61%;padding:4px 5px;font-size:8px;font-weight:700;text-align:center;'>COLUMN</td><td style='width:15%;padding:4px 5px;font-size:8px;font-weight:700;text-align:center;'>KEY</td></tr>"]
    for index, (dtype, name, key) in enumerate(entity["rows"]):
        bg = "#FAFAFA" if index % 2 else "#FFFFFF"
        weight = "700" if key else "400"
        rows.append(f"<tr style='background:{bg};border-top:1px solid #B8B8B8;'><td style='padding:4px 5px;color:#666666;font-size:8px;'>{escape(dtype)}</td><td style='padding:4px 5px;color:#111111;font-size:8px;font-weight:{weight};'>{escape(name)}</td><td style='padding:4px 5px;color:#111111;font-size:7px;font-weight:700;text-align:center;'>{escape(key)}</td></tr>")
    return "<div style='font-family:Helvetica,Arial,sans-serif;'><div style='background:#111111;color:#FFFFFF;font-size:11px;font-weight:700;padding:7px;text-align:center;'>" + escape(entity["title"]) + "</div><table style='width:100%;border-collapse:collapse;'>" + "".join(rows) + "</table></div>"


def add_vertex(root, cell_id, value, x, y, w, h, style):
    cell = ET.SubElement(root, "mxCell", {"id": cell_id, "value": value, "style": style,
                                         "parent": "1", "vertex": "1"})
    ET.SubElement(cell, "mxGeometry", {"as": "geometry", "x": str(round(x, 2)),
                                       "y": str(round(y, 2)), "width": str(round(w, 2)),
                                       "height": str(round(h, 2))})


def add_edge(root, cell_id, value, source, target, start_arrow, end_arrow, dashed=False):
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
             "strokeColor=#111111;strokeWidth=1.2;fontSize=9;labelBackgroundColor=#FFFFFF;"
             f"startArrow={start_arrow};startFill=0;endArrow={end_arrow};endFill=0;")
    if dashed:
        style += "dashed=1;dashPattern=5 4;"
    cell = ET.SubElement(root, "mxCell", {"id": cell_id, "value": value, "style": style,
                                         "parent": "1", "edge": "1", "source": source,
                                         "target": target})
    ET.SubElement(cell, "mxGeometry", {"as": "geometry", "relative": "1"})


def drawio_xy(entity):
    scale = 100.0
    return (entity["x"] * scale, (PAGE_H - entity["y"] - entity["h"]) * scale,
            entity["w"] * scale, entity["h"] * scale)


def render_drawio():
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "modified": "2026-09-21T00:00:00.000Z",
                                    "agent": "draw.io", "version": "24.7.17", "type": "device"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": "csal-raw-tcr-cutoff-erd",
                                                 "name": "CSAL TCR Cutoff ERD"})
    model = ET.SubElement(diagram, "mxGraphModel", {"dx": "1200", "dy": "1600", "grid": "1",
                                                     "gridSize": "10", "guides": "1", "tooltips": "1",
                                                     "connect": "1", "arrows": "1", "fold": "1", "page": "1",
                                                     "pageScale": "1", "pageWidth": "1200", "pageHeight": "1600",
                                                     "math": "0", "shadow": "0"})
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"}); ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    entity_style = "rounded=0;whiteSpace=wrap;html=1;overflow=fill;fillColor=#FFFFFF;strokeColor=#111111;strokeWidth=1.2;align=left;verticalAlign=top;spacing=0;shadow=0;"
    for entity in ENTITIES:
        add_vertex(root, entity["id"], html_entity(entity), *drawio_xy(entity), entity_style)
    add_edge(root, "plan_audit", "csal_id", "plan", "audit", "ERone", "ERzeroToMany")
    add_edge(root, "plan_assoc", "csal_id", "plan", "assoc", "ERone", "ERzeroToMany")
    add_edge(root, "plan_vessel", "service + week_num", "plan", "vessel", "ERzeroToMany", "ERone", True)
    add_edge(root, "assoc_shipment", "shipment_num = shipment_number", "assoc", "shipment", "ERzeroToMany", "ERone")
    add_edge(root, "assoc_detail", "shipment_num", "assoc", "detail", "ERzeroToMany", "ERone")
    add_edge(root, "vessel_stop", "service + week + voyage to SVVD", "vessel", "stop", "ERone", "ERoneToMany", True)
    add_edge(root, "detail_stop", "exact SVVD + port", "detail", "stop", "ERzeroToMany", "ERone")
    add_vertex(root, "footnote", "Logical analysis keys and cardinalities; physical Databricks PK/FK constraints are not confirmed.",
               42, 1538, 1110, 24, "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=8;fontColor=#666666;")
    tree = ET.ElementTree(mxfile); ET.indent(tree, space="  ")
    tree.write(OUT / f"{BASE}.drawio", encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    render_preview()
    render_drawio()
