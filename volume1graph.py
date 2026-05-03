import json
import networkx as nx

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