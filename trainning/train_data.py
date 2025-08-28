import json
import cohere
import numpy as np
from typing import List

co = cohere.ClientV2(
    "yKJqWEwcoD5FXaArm70AjnqV4QRglvDP5yzLPuf8"
)


if __name__ == "__main__":

    with open("your_file.json") as f:
        data = json.load(f)

    search_queries = []

    doc_emb = co.embed(
    model="embed-v4.0",
    input_type="search_document",
    texts=[doc["data"] for doc in data],
    embedding_types=["float"],
    ).embeddings.float

    query_emb = co.embed(
    model="embed-v4.0",
    input_type="search_query",
    texts=search_queries,
    embedding_types=["float"],
    ).embeddings.float

    # Compute dot product similarity and display results
    n = 5
    scores = np.dot(query_emb, np.transpose(doc_emb))[0]
    max_idx = np.argsort(-scores)[:n]

    retrieved_documents = [data[item] for item in max_idx]

    for rank, idx in enumerate(max_idx):
        print(f"Rank: {rank+1}")
        print(f"Score: {scores[idx]}")
        print(f"Document: {retrieved_documents[rank]}\n")

    # Rerank the documents
    results = co.rerank(
        model="rerank-v3.5",
        query=search_queries[0],
        documents=[doc["data"] for doc in retrieved_documents],
        top_n=2,
    )

    # Display the reranking results
    for idx, result in enumerate(results.results):
        print(f"Rank: {idx+1}")
        print(f"Score: {result.relevance_score}")
        print(f"Document: {retrieved_documents[result.index]}\n")

    reranked_documents = [
        retrieved_documents[result.index] for result in results.results
    ]

    messages = [{"role": "user", "content": search_queries[0]}]

    # Generate the response
    response = co.chat(
        model="command-a-03-2025",
        messages=messages,
        documents=reranked_documents,
    )

    # Display the response
    print(response.message.content[0].text)

    # Display the citations and source documents
    if response.message.citations:
        print("\nCITATIONS:")
        for citation in response.message.citations:
            print(citation, "\n")

# text = ""
# for entry in documents:
#     text = text + " " + entry['data']

# item = co.tokenize(
#     text=text, model="command-a-03-2025"
# )
# print(item.token_strings)
# print(len(item.tokens))


# message = "What does it mean to go through the provincial nominee program?"

# messages = [{"role": "user", "content": message}]

# response = co.chat(
#     model="command-a-03-2025",
#     messages=messages,
#     documents=documents,
# )
# print(response.message.content[0].text)
# print(response.message.citations)