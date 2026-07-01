# ============================================================
# old_scripts/generate_graph.py
# Generate graph-based visualizations from bibliographic data.
# ============================================================
import json
import networkx as nx
import matplotlib.pyplot as plt

# Load data
with open("volume1.json", "r") as f:
    data = json.load(f)

articles = data["volume1"]

# Create directed graph
G = nx.DiGraph()

for article in articles:
    article_node = article["title"]

    # Add article node
    G.add_node(article_node, type="article")

    # Add work references
    works = article.get("references", {}).get("works", [])
    
    for work in works:
        work_title = work["title"]
        author = work.get("author", "Unknown")

        G.add_node(work_title, type="work", author=author)
        G.add_edge(article_node, work_title)

    
pos = nx.spring_layout(G)

color_map = []
for node in G:
    if G.nodes[node]["type"] == "article":
        color_map.append("lightblue")
    else:
        color_map.append("lightcoral")

nx.draw(
    G,
    pos,
    with_labels=True,
    node_color=color_map,
    node_size=2000,
    font_size=8
)

plt.title("Logic Network: Mind Volume 1")
plt.tight_layout() # This helps prevent the labels from getting cut off at the edges
plt.show()