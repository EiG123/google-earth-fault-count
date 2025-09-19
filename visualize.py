import plotly.graph_objects as go

def visualize_kml_data_interactive(points, redlines):
    fig = go.Figure()

    # วาด Redlines
    for line in redlines:
        x, y = line.xy
        fig.add_trace(go.Scattergeo(
            lon=list(x),  # 🔧 แปลงเป็น list
            lat=list(y),  # 🔧 แปลงเป็น list
            mode='lines',
            line=dict(color='gray', width=1.5, dash='dash'),
            name='Redline'
        ))


    # วาด Segment ระหว่าง Site
    # for i in range(len(sites) - 1):
    #     site_a = sites[i]
    #     site_b = sites[i + 1]
    #     fig.add_trace(go.Scattergeo(
    #         lon=[site_a['lon'], site_b['lon']],
    #         lat=[site_a['lat'], site_b['lat']],
    #         mode='lines',
    #         line=dict(color='orange', width=2),
    #         name='Segment' if i == 0 else '',
    #         showlegend=(i == 0)
    #     ))

    # วาด Sites
    # fig.add_trace(go.Scattergeo(
    #     lon=[s['lon'] for s in sites],
    #     lat=[s['lat'] for s in sites],
    #     mode='markers',
    #     marker=dict(size=10, color='red', symbol='circle'),
    #     name='Sites'
    # ))

    # วาด Points
    fig.add_trace(go.Scattergeo(
        lon=[p['lon'] for p in points],
        lat=[p['lat'] for p in points],
        mode='markers',
        marker=dict(size=6, color='blue', symbol='x'),
        name='Points'
    ))

    fig.update_layout(
        title="Interactive KML Visualization",
        geo=dict(
            projection_type="equirectangular",
            showland=True,
            showcountries=True,
            showlakes=True,
            landcolor="rgb(243, 243, 243)",
            lakecolor="rgb(204, 204, 255)",
            resolution=50,
            showcoastlines=True,
            coastlinecolor="gray",
        ),
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='black'
        )
    )

    fig.show()
