"""Draw the usual-price chart as inline SVG."""

from . import report_labels as labels

WIDTH = 720
HEIGHT = 260
LEFT = 60
RIGHT = 680
TOP = 52
BOTTOM = 196


def _x(value, clamp):
    """A value's place on the chart, with everything above the clamp drawn at the edge."""
    if clamp <= 0:
        return LEFT
    scaled = max(0.0, min(float(value) / float(clamp), 1.0))
    return LEFT + scaled * (RIGHT - LEFT)


def _marker(point, clamp):
    """One numbered bid marker, with the off-chart marker kept inside its own group."""
    x = _x(point.total, clamp)
    off = point.off_chart
    if off:
        x = RIGHT - 2
    y = 120 + ((point.number * 23) % 46)
    shape = labels.state_shape(None if point.state == "not_compared" else point.state)
    if shape == "hollow-circle":
        symbol = (f'<circle cx="{x:.1f}" cy="{y}" r="6" fill="none" '
                  f'stroke="#1f4e79" stroke-width="2"/>')
    elif shape == "triangle-up":
        symbol = (f'<polygon points="{x:.1f},{y - 7} {x - 7:.1f},{y + 6} {x + 7:.1f},{y + 6}" '
                  f'fill="#1f4e79"/>')
    elif shape == "triangle-down":
        symbol = (f'<polygon points="{x:.1f},{y + 7} {x - 7:.1f},{y - 6} {x + 7:.1f},{y - 6}" '
                  f'fill="#1f4e79"/>')
    elif shape == "filled-circle":
        symbol = f'<circle cx="{x:.1f}" cy="{y}" r="6" fill="#1f4e79"/>'
    elif shape == "diamond":
        symbol = (f'<polygon points="{x:.1f},{y - 7} {x - 7:.1f},{y} {x:.1f},{y + 7} '
                  f'{x + 7:.1f},{y}" fill="#1f4e79"/>')
    else:
        symbol = (f'<rect x="{x - 5:.1f}" y="{y - 5}" width="10" height="10" '
                  f'fill="#1f4e79"/>')
    parts = [f'<g class="bid-marker">', symbol]
    if off:
        parts.append(f'<g class="bid-marker off-chart">')
        parts.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{BOTTOM}" '
                     f'stroke="#a33" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="{x - 4:.1f}" y="{TOP - 6}" font-size="10" fill="#a33">'
                     f'above chart</text>')
        parts.append("</g>")
    parts.append(f'<text x="{x:.1f}" y="{y - 11}" text-anchor="middle" font-size="11" '
                 f'font-weight="bold">{point.number}</text>')
    parts.append("</g>")
    return "".join(parts)


def render_chart_svg(model) -> str:
    """The chart as one inline SVG, or an empty string when there is no chart to draw."""
    if model.chart is None:
        return ""
    chart = model.chart
    clamp = chart.clamp_max
    q1x = _x(chart.q1, clamp)
    q3x = _x(chart.q3, clamp)
    median_x = _x(chart.usual_price, clamp)
    parts = [
        f'<svg class="chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="Usual price chart of comparable awards and bid totals">',
        "<title>Usual price chart</title>",
        "<desc>comparable awards and bid totals against the usual price and normal range.</desc>",
        f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<line class="axis" x1="{LEFT}" y1="{BOTTOM}" x2="{RIGHT}" y2="{BOTTOM}" '
        f'stroke="#555" stroke-width="1"/>',
        f'<rect class="normal-range" x="{q1x:.1f}" y="{TOP}" width="{max(1.0, q3x - q1x):.1f}" '
        f'height="{BOTTOM - TOP}" fill="#dce9f5"/>',
        f'<line class="usual-price" x1="{median_x:.1f}" y1="{TOP}" x2="{median_x:.1f}" '
        f'y2="{BOTTOM}" stroke="#1f4e79" stroke-width="2"/>',
        f'<text x="{(q1x + q3x) / 2:.1f}" y="{TOP - 8}" text-anchor="middle" '
        f'font-size="11" fill="#1f4e79">Normal range</text>',
        f'<text x="{median_x + 4:.1f}" y="{BOTTOM + 16}" font-size="11" '
        f'fill="#1f4e79">Usual price</text>',
        f'<text x="{RIGHT}" y="{BOTTOM + 16}" text-anchor="end" font-size="10" '
        f'fill="#555">Clamp</text>',
    ]
    for point in chart.pool_points:
        parts.append(f'<circle class="pool-point" cx="{_x(point.total, clamp):.1f}" '
                     f'cy="{BOTTOM - 10}" r="3" fill="#7a9ab8"/>')
    for point in chart.bid_points:
        parts.append(_marker(point, clamp))
    parts.append("</svg>")
    return "".join(parts)
