
import plotly.graph_objects as go

# ── Palette — vivid, high-contrast against blue-grey ─────────────────────────
COLORS = [
    "#E63946",  # crimson red       — Wildfires
    "#2196F3",  # vivid blue        — Severe Storms
    "#FF6D00",  # deep orange       — Volcanoes
    "#00BFA5",  # teal              — Sea and Lake Ice
    "#9C27B0",  # purple            — Floods
    "#FFB300",  # amber             — Drought
    "#00897B",  # green teal        — Landslides
    "#F06292",  # pink              — other
]

# ── Layout defaults ───────────────────────────────────────────────────────────
_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",   # transparent — inherits viewer background
    plot_bgcolor="#FFFFFF",           # white plot area for contrast
    font=dict(
        family="Inter, Arial, sans-serif",
        size=13,
        color="#1a1a2e",             # near-black text
    ),
    title=dict(
        font=dict(size=16, color="#1a1a2e"),
        x=0.02,
    ),
    xaxis=dict(
        gridcolor="#c8d0dc",
        linecolor="#8a94a6",
        tickfont=dict(color="#1a1a2e"),
        title=dict(font=dict(color="#1a1a2e")),
        zerolinecolor="#8a94a6",
    ),
    yaxis=dict(
        gridcolor="#c8d0dc",
        linecolor="#8a94a6",
        tickfont=dict(color="#1a1a2e"),
        title=dict(font=dict(color="#1a1a2e")),
        zerolinecolor="#8a94a6",
    ),
    legend=dict(
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="#c8d0dc",
        borderwidth=1,
        font=dict(color="#1a1a2e"),
    ),
)


def apply_theme(fig: go.Figure) -> go.Figure:
    """
    Apply the disaster-intel theme to any Plotly figure.

    Usage:
        fig = px.bar(...)
        apply_theme(fig)
        fig.show()
    """
    fig.update_layout(**_LAYOUT)

    # Re-colour traces that haven't been explicitly coloured
    for i, trace in enumerate(fig.data):
        if hasattr(trace, "marker") and trace.marker.color is None:
            trace.marker.color = COLORS[i % len(COLORS)]

    return fig


def themed_colors() -> list:
    """Return the palette list — pass to color_discrete_sequence."""
    return COLORS
