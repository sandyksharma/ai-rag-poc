# AI Travel Planner

## 1. Project Overview

AI Travel Planner is a production-inspired multi-agent AI application
built to demonstrate modern AI engineering using **FastAPI**,
**LangGraph**, **Llama 3.1 (Ollama)**, **PostgreSQL**, **ChromaDB**, and
**Neo4j**.

The goal is to build a reusable AI platform rather than a simple
chatbot.

------------------------------------------------------------------------

## 2. Objectives

-   Learn enterprise AI architecture
-   Implement multi-agent orchestration
-   Build Hybrid RAG + GraphRAG
-   Use local-first open-source technologies
-   Create a reusable platform for future domains

------------------------------------------------------------------------

## 3. Technology Stack

  Layer              Technology
  ------------------ --------------------
  Language           Python 3.12
  API                FastAPI
  AI Orchestration   LangGraph
  LLM                Llama 3.1 (Ollama)
  Vector Store       ChromaDB
  Graph DB           Neo4j Community
  Relational DB      PostgreSQL
  ORM                SQLAlchemy 2.x
  Validation         Pydantic v2
  Testing            pytest
  Containers         Docker Compose

------------------------------------------------------------------------

## 4. High Level Architecture

``` text
User
  |
React UI (future)
  |
FastAPI
  |
LangGraph Orchestrator
  |---- Planner Agent
  |---- RAG Agent
  |---- Graph Agent
  |---- Weather Agent
  |---- Budget Agent
  |---- Itinerary Agent
  |
Datastores
  |- PostgreSQL
  |- ChromaDB
  |- Neo4j
  |- Ollama
```

------------------------------------------------------------------------

## 5. Repository Structure

``` text
travel-ai/
├── backend/
├── docs/
├── docker/
├── tests/
├── prompts/
├── graph/
├── database/
├── frontend/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

------------------------------------------------------------------------

## 6. Request Flow

1.  User submits a prompt.
2.  FastAPI validates the request.
3.  LangGraph determines workflow.
4.  Planner Agent decomposes the task.
5.  RAG Agent retrieves relevant knowledge from ChromaDB.
6.  Graph Agent queries Neo4j relationships.
7.  Domain agents enrich the plan.
8.  Response Composer assembles the final answer.
9.  FastAPI returns the response.

------------------------------------------------------------------------

## 7. Design Principles

-   Modular architecture
-   Separation of concerns
-   Explainable AI
-   Stateless APIs with stateful AI memory
-   Domain extensibility
-   Local-first development

------------------------------------------------------------------------

## 8. Future Roadmap

-   Flight integration
-   Hotel integration
-   Maps
-   Voice interface
-   Streaming responses
-   Authentication
-   Observability
-   GraphRAG enhancements

------------------------------------------------------------------------

## 9. Learning Outcomes

This project teaches:

-   FastAPI
-   LangGraph
-   Multi-agent systems
-   Hybrid RAG
-   GraphRAG
-   Docker
-   PostgreSQL
-   Neo4j
-   ChromaDB
-   Enterprise project structure
