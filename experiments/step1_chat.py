from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3.2:3b", temperature=0)
reply = llm.invoke("In one sentence, what is a laptop warranty?")
print(reply.content)