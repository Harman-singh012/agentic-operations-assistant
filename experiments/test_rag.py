from agent.rag import search

for r in search("How long is the warranty?"):
    print("-", r.metadata["source"], "|", r.page_content[:150].replace("\n", " "))