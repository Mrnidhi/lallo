from pathlib import Path
from html import escape
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle


OUT = Path(__file__).resolve().parent
BASE = "csal-booking-cutoff-logical-erd-standard"

PAGE = "#F7F9FC"
WHITE = "#FFFFFF"
INK = "#101828"
MUTED = "#667085"
LINE = "#475467"
GRID = "#E4E7EC"
BLUE = "#175CD3"
GREEN = "#067647"
PURPLE = "#6941C6"


ENTITIES = [
    {
        "id": "nrt_case",
        "title": "NRT BOOKING CASE",
        "stereotype": "derived latest case",
        "color": BLUE,
        "x": 0.65,
        "y": 2.35,
        "w": 4.20,
        "h": 4.70,
        "rows": [
            ("UID", "booking_tcr_key"),
            ("", "booking_number"),
            ("", "svvd"),
            ("", "tcr"),
            ("", "customer"),
            ("", "service"),
            ("", "tcr_cutoff"),
            ("", "selected_nrt_run_ts"),
        ],
    },
    {
        "id": "timing_result",
        "title": "BOOKING–TCR TIMING RESULT",
        "stereotype": "derived analytical view",
        "color": GREEN,
        "x": 5.90,
        "y": 2.35,
        "w": 4.20,
        "h": 4.70,
        "rows": [
            ("UID", "booking_tcr_key (inherited)"),
            ("", "match_tier"),
            ("", "match_method"),
            ("", "join_status"),
            ("", "timing_exclusion_reason"),
            ("D", "has_controlled_match"),
            ("D", "calendar_days_before_tcr"),
            ("D", "lead_time_bucket"),
        ],
    },
    {
        "id": "shipment_profile",
        "title": "SHIPMENT MATCH PROFILE",
        "stereotype": "derived matching profile",
        "color": PURPLE,
        "x": 11.15,
        "y": 2.35,
        "w": 4.20,
        "h": 4.70,
        "rows": [
            ("UID", "shipment_profile_key"),
            ("", "booking_number"),
            ("", "match_scope"),
            ("", "canonical_tcr"),
            ("", "record_created_at"),
            ("", "creation_ts_count"),
            ("", "null_creation_ts_count"),
            ("", "candidate_sources"),
        ],
    },
]


def card(ax, e):
    x, y, w, h = e["x"], e["y"], e["w"], e["h"]
    color = e["color"]

    ax.add_patch(FancyBboxPatch(
        (x + 0.055, y - 0.055), w, h,
        boxstyle="round,pad=0,rounding_size=0.06",
        facecolor="#D0D5DD", edgecolor="none", alpha=0.30, zorder=1,
    ))
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.06",
        facecolor=WHITE, edgecolor=color, linewidth=1.8, zorder=2,
    ))

    header_h = 0.74
    meta_h = 0.46
    ax.add_patch(FancyBboxPatch(
        (x, y + h - header_h), w, header_h,
        boxstyle="round,pad=0,rounding_size=0.06",
        facecolor=color, edgecolor=color, linewidth=0, zorder=3,
    ))
    ax.add_patch(Rectangle((x, y + h - header_h), w, 0.30,
                           facecolor=color, edgecolor="none", zorder=3))
    ax.text(x + 0.22, y + h - header_h / 2, e["title"],
            fontsize=10.7, color=WHITE, fontweight="bold",
            va="center", zorder=4)

    meta_y = y + h - header_h - meta_h
    ax.add_patch(Rectangle((x, meta_y), w, meta_h,
                           facecolor="#F9FAFB", edgecolor="none", zorder=2))
    ax.text(x + 0.22, meta_y + meta_h / 2,
            f"«{e['stereotype']}»", fontsize=7.4, color=MUTED,
            style="italic", va="center", zorder=4)
    ax.plot([x, x + w], [meta_y, meta_y], color=GRID, linewidth=0.8, zorder=3)

    rows = e["rows"]
    row_h = (h - header_h - meta_h) / len(rows)
    for i, (kind, name) in enumerate(rows):
        top = meta_y - i * row_h
        bottom = top - row_h
        if i % 2:
            ax.add_patch(Rectangle((x, bottom), w, row_h,
                                   facecolor="#FCFCFD", edgecolor="none", zorder=2))
        ax.plot([x, x + w], [bottom, bottom], color=GRID,
                linewidth=0.72, zorder=3)

        if kind:
            pill_w = 0.58 if kind == "UID" else 0.42
            ax.add_patch(FancyBboxPatch(
                (x + 0.18, bottom + row_h * 0.23), pill_w, row_h * 0.54,
                boxstyle="round,pad=0.01,rounding_size=0.045",
                facecolor=color, edgecolor="none", alpha=0.12, zorder=3,
            ))
            ax.text(x + 0.18 + pill_w / 2, bottom + row_h / 2, kind,
                    fontsize=6.5, color=color, fontweight="bold",
                    ha="center", va="center", zorder=4)
        ax.text(x + 0.88, bottom + row_h / 2, name,
                fontsize=8.2, color=INK,
                fontweight="bold" if kind == "UID" else "normal",
                va="center", zorder=4)


def exactly_one(ax, x, y, direction):
    for offset in (0.09, 0.19):
        xx = x + direction * offset
        ax.plot([xx, xx], [y - 0.17, y + 0.17], color=LINE,
                linewidth=1.9, zorder=6)


def optional_one(ax, x, y, direction):
    # Maximum (one) is closest to the entity; minimum (zero) is farther out.
    bar_x = x + direction * 0.10
    circle_x = x + direction * 0.27
    ax.add_patch(Circle((circle_x, y), 0.074, facecolor=WHITE,
                        edgecolor=LINE, linewidth=1.7, zorder=6))
    ax.plot([bar_x, bar_x], [y - 0.17, y + 0.17], color=LINE,
            linewidth=1.9, zorder=6)


def optional_many(ax, x, y, direction):
    # Crow's-foot (maximum many) is closest to the entity; zero is farther out.
    tip_x = x + direction * 0.07
    join_x = x + direction * 0.25
    circle_x = x + direction * 0.39
    ax.add_patch(Circle((circle_x, y), 0.074, facecolor=WHITE,
                        edgecolor=LINE, linewidth=1.7, zorder=6))
    ax.plot([tip_x, join_x], [y, y], color=LINE, linewidth=1.8, zorder=6)
    ax.plot([tip_x, join_x], [y + 0.18, y], color=LINE, linewidth=1.8, zorder=6)
    ax.plot([tip_x, join_x], [y - 0.18, y], color=LINE, linewidth=1.8, zorder=6)


def connect(ax, x1, x2, y, left, right, label):
    ax.plot([x1, x2], [y, y], color=LINE, linewidth=1.9, zorder=5)
    {"one": exactly_one, "zero_one": optional_one,
     "zero_many": optional_many}[left](ax, x1, y, 1)
    {"one": exactly_one, "zero_one": optional_one,
     "zero_many": optional_many}[right](ax, x2, y, -1)
    ax.text((x1 + x2) / 2, y + 0.30, label, fontsize=7.7,
            color=INK, fontweight="bold", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.18", facecolor=WHITE,
                      edgecolor=GRID, linewidth=0.8), zorder=7)


def render_preview():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=180)
    fig.patch.set_facecolor(PAGE)
    ax.set_facecolor(PAGE)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(0.65, 8.48, "CSAL booking-to-cutoff timing",
            fontsize=22.5, fontweight="bold", color=INK, va="center")
    ax.text(0.65, 8.08,
            "Logical ERD · entities, identifiers, attributes and relationship cardinalities",
            fontsize=10.4, color=MUTED, va="center")
    ax.text(15.35, 8.30, "LOGICAL MODEL", fontsize=8.1, color=BLUE,
            fontweight="bold", ha="right", va="center",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="#EFF8FF",
                      edgecolor="#B2DDFF", linewidth=0.9))

    for e in ENTITIES:
        card(ax, e)

    y_rel = 4.57
    connect(ax, 4.85, 5.90, y_rel, "one", "one", "has")
    connect(ax, 10.10, 11.15, y_rel, "zero_many", "zero_one", "selects")

    # Relationship definitions are outside the ERD boxes and read in both directions.
    ax.add_patch(FancyBboxPatch(
        (0.65, 1.33), 14.70, 0.67,
        boxstyle="round,pad=0.02,rounding_size=0.07",
        facecolor=WHITE, edgecolor=GRID, linewidth=1.0, zorder=2,
    ))
    ax.text(0.90, 1.75,
            "NRT Booking Case has exactly 1 Timing Result; each Timing Result belongs to exactly 1 NRT Booking Case.",
            fontsize=7.4, color=INK, va="center", zorder=3)
    ax.text(0.90, 1.48,
            "Timing Result selects 0 or 1 Shipment Match Profile; one Profile supports 0 to many Timing Results.",
            fontsize=7.4, color=INK, va="center", zorder=3)

    ax.text(0.65, 0.98, "Notation:", fontsize=7.8, color=INK,
            fontweight="bold", va="center")
    ax.text(1.48, 0.98,
            "circle = zero   ·   bar = one   ·   crow’s foot = many   ·   UID = logical unique identifier   ·   D = derived attribute",
            fontsize=7.5, color=MUTED, va="center")

    ax.plot([0.65, 15.35], [0.73, 0.73], color=GRID, linewidth=0.9)
    ax.text(0.65, 0.48,
            "Source mapping (separate from ERD):  NRT case ← csal_teu_performance_nrt   |   Shipment profile ← csal_shipment   |   Timing result ← csal_tcr_tiered_match_v2",
            fontsize=7.2, color=MUTED, va="center")
    ax.text(0.65, 0.20,
            "Logical identifiers are derived for this analysis; physical Databricks PK/FK constraints are not confirmed.",
            fontsize=7.1, color=MUTED, va="center")

    plt.tight_layout(pad=0.25)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(OUT / f"{BASE}.{ext}", bbox_inches="tight", facecolor=PAGE)
    plt.close(fig)


def html_entity(e):
    rows = []
    color = e["color"]
    for i, (kind, name) in enumerate(e["rows"]):
        bg = "#FCFCFD" if i % 2 else "#FFFFFF"
        rows.append(
            "<tr style='background:%s;border-top:1px solid #E4E7EC;'>"
            "<td style='width:20%%;padding:8px 6px 8px 12px;color:%s;font-weight:700;'>%s</td>"
            "<td style='width:80%%;padding:8px 12px 8px 4px;color:#101828;font-weight:%s;'>%s</td>"
            "</tr>" % (
                bg, color, escape(kind), "700" if kind == "UID" else "400",
                escape(name),
            )
        )
    return (
        "<div style='font-family:Helvetica,Arial,sans-serif;'>"
        f"<div style='background:{color};color:#FFFFFF;font-size:15px;font-weight:700;padding:12px 14px;'>"
        f"{escape(e['title'])}</div>"
        "<div style='background:#F9FAFB;color:#667085;font-size:10px;font-style:italic;padding:8px 14px;border-bottom:1px solid #E4E7EC;'>"
        f"«{escape(e['stereotype'])}»</div>"
        "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
        + "".join(rows) + "</table></div>"
    )


def add_cell(root, cell_id, value, style, parent="1", vertex=False,
             edge=False, source=None, target=None, x=0, y=0, w=0, h=0):
    attrs = {"id": cell_id, "value": value, "style": style, "parent": parent}
    if vertex:
        attrs["vertex"] = "1"
    if edge:
        attrs["edge"] = "1"
    if source:
        attrs["source"] = source
    if target:
        attrs["target"] = target
    cell = ET.SubElement(root, "mxCell", attrs)
    geo = {"as": "geometry"}
    if edge:
        geo["relative"] = "1"
    else:
        geo.update({"x": str(x), "y": str(y), "width": str(w), "height": str(h)})
    ET.SubElement(cell, "mxGeometry", geo)


def render_drawio():
    mxfile = ET.Element("mxfile", {
        "host": "app.diagrams.net", "modified": "2026-09-21T00:00:00.000Z",
        "agent": "draw.io", "version": "24.7.17", "type": "device",
    })
    diagram = ET.SubElement(mxfile, "diagram", {
        "id": "csal-logical-erd-standard", "name": "Logical ERD",
    })
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1600", "dy": "900", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1",
        "pageWidth": "1600", "pageHeight": "900", "math": "0", "shadow": "0",
    })
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    add_cell(root, "title", "CSAL booking-to-cutoff timing",
             "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=26;fontStyle=1;fontColor=#101828;",
             vertex=True, x=60, y=35, w=700, h=42)
    add_cell(root, "subtitle",
             "Logical ERD · entities, identifiers, attributes and relationship cardinalities",
             "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=14;fontColor=#667085;",
             vertex=True, x=60, y=80, w=760, h=30)

    positions = {
        "nrt_case": (60, 185, 420, 470),
        "timing_result": (590, 185, 420, 470),
        "shipment_profile": (1120, 185, 420, 470),
    }
    for e in ENTITIES:
        x, y, w, h = positions[e["id"]]
        add_cell(
            root, e["id"], html_entity(e),
            "rounded=1;arcSize=3;whiteSpace=wrap;html=1;overflow=fill;"
            f"fillColor=#FFFFFF;strokeColor={e['color']};strokeWidth=2;"
            "align=left;verticalAlign=top;spacing=0;shadow=1;",
            vertex=True, x=x, y=y, w=w, h=h,
        )

    add_cell(
        root, "rel_nrt_result", "has",
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        "startArrow=ERone;startFill=0;endArrow=ERone;endFill=0;"
        "strokeColor=#475467;strokeWidth=2;fontSize=12;fontStyle=1;labelBackgroundColor=#FFFFFF;",
        edge=True, source="nrt_case", target="timing_result",
    )
    add_cell(
        root, "rel_result_profile", "selects",
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
        "startArrow=ERzeroToMany;startFill=0;endArrow=ERzeroToOne;endFill=0;"
        "strokeColor=#475467;strokeWidth=2;fontSize=12;fontStyle=1;labelBackgroundColor=#FFFFFF;",
        edge=True, source="timing_result", target="shipment_profile",
    )

    add_cell(root, "relationship_reading",
             "<b>NRT Booking Case</b> has exactly 1 Timing Result; each Timing Result belongs to exactly 1 NRT Booking Case.<br>"
             "<b>Timing Result</b> selects 0 or 1 Shipment Match Profile; one Profile supports 0 to many Timing Results.",
             "text;html=1;strokeColor=#E4E7EC;fillColor=#FFFFFF;rounded=1;arcSize=4;align=left;verticalAlign=middle;spacingLeft=16;fontSize=11;fontColor=#101828;",
             vertex=True, x=60, y=690, w=1480, h=60)
    add_cell(root, "source_mapping",
             "Source mapping (separate from ERD): NRT case ← csal_teu_performance_nrt | Shipment profile ← csal_shipment | Timing result ← csal_tcr_tiered_match_v2<br>"
             "Logical identifiers are derived for this analysis; physical Databricks PK/FK constraints are not confirmed.",
             "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#667085;",
             vertex=True, x=60, y=780, w=1480, h=50)

    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    tree.write(OUT / f"{BASE}.drawio", encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    render_preview()
    render_drawio()
