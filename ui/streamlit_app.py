import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from ingestion.ingest_logs import ensure_logs_ingested
from search.similarity_search import find_similar_logs


@st.cache_resource
def initialize_vector_store():

    return ensure_logs_ingested()


with st.spinner("Preparing vector database..."):
    ingestion_ran = initialize_vector_store()

st.title("AI Log Failure Detection")

st.write("Search for similar application failures using Vector DB")

if ingestion_ran:
    st.success("Logs were ingested into the vector database.")

query = st.text_input("Enter error message or failure description")

threshold = 1.8

if st.button("Search"):

    if query:

        st.write(query)
        results = find_similar_logs(query)

        st.subheader("Similar Failures Found")

        docs = results["documents"][0]
        metadata = results["metadatas"][0]
        distances = results["distances"][0]
        matches_found = False

        for i in range(len(docs)):

            if distances[i] < threshold:
                matches_found = True
                st.write("Failure:", docs[i])
                st.write("Service:", metadata[i]["service"])
                st.write("Severity:", metadata[i]["severity"])
                st.write("Distance:", round(distances[i], 3))

                st.divider()

        if not matches_found:
            st.info("No close matches found for this query. Try a more specific error message.")
