# Core orchestration layer for the log investigation assistant.
#
# This module is the heart of the application: it decides whether a question is generic or incident-driven,
# performs retrieval when needed, calls the local Ollama model, and streams the answer back to the web UI.
# The rest of the app depends on this module because it combines the raw search layer with the LLM layer.

import json
import os
import re
import time
from functools import lru_cache
from typing import Any, Dict, Iterator, List, Optional, TypedDict

import requests

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - fallback for lightweight test environments
    END = "__end__"
    START = "__start__"

    class StateGraph:
        def __init__(self, _state_schema):
            self.nodes = {}
            self.edges = {}
            self.conditionals = {}
            self.entry_point = None

        def add_node(self, name, node):
            self.nodes[name] = node

        def add_edge(self, start, end):
            if start == START:
                self.entry_point = end
            else:
                self.edges[start] = end

        def add_conditional_edges(self, start, condition_fn, mapping):
            self.conditionals[start] = (condition_fn, mapping)

        def compile(self):
            return _CompiledStateGraph(self)

    class _CompiledStateGraph:
        def __init__(self, graph):
            self.graph = graph

        def invoke(self, state):
            current = self.graph.entry_point
            while current != END:
                node = self.graph.nodes[current]
                state = {**state, **node(state)}
                if current in self.graph.conditionals:
                    condition_fn, mapping = self.graph.conditionals[current]
                    current = mapping[condition_fn(state)]
                    continue
                current = self.graph.edges.get(current, END)
            return state

from config.settings import TOP_K_RESULTS
from search.similarity_search import find_similar_logs

# Ollama connection details allow the project to run against a local model without cloud dependencies.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

SYSTEM_PROMPT = """
You are a helpful log investigation assistant for a platform operations team.
Your job is to help identify likely root causes from application logs and respond in a clear, concise, actionable way.

Rules:
- Use the search_logs tool when the user describes a failure, timeout, exception, outage, or service problem.
- Prefer the most relevant matches and explain them in plain language.
- If no close matches are found, say so clearly and suggest a more specific error message.
- Keep responses conversational and brief.
"""

FEEDBACK_HISTORY: List[Dict[str, Any]] = []


class AgentState(TypedDict, total=False):
    # State schema used by LangGraph. This keeps the graph deterministic while passing data between nodes.
    query: str
    system_prompt: str
    decision: str
    top_k: int
    tool_calls: List[Dict[str, Any]]
    results: Dict[str, Any]
    answer: str
    reasoning: str
    follow_up_questions: List[str]
    iterations: int
    last_error: str


def search_logs_tool(query: str, top_k: int = TOP_K_RESULTS) -> Dict[str, Any]:
    # Wrapper around the vector search layer. If the query is empty we return an empty result set safely.
    if not query or not query.strip():
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    return find_similar_logs(query)


def refine_query_tool(query: str) -> str:
    # Trim and narrow overly broad queries. This helps avoid noisy retrieval when the original query is very long.
    if not query:
        return query
    tokens = re.findall(r"\b[\w-]+\b", query.lower())
    if len(tokens) > 6:
        return " ".join(tokens[:6])
    return query.strip()


def classify_intent(query: str) -> Dict[str, Any]:
    # This is the routing gate: generic explanatory questions bypass retrieval, while operational issues continue through RAG.
    text = (query or "").strip()
    if not text:
        return {"is_generic": True, "reason": "empty query", "decision": "respond"}

    lower = text.lower()
    generic_keywords = [
        "what is",
        "what are",
        "how do i",
        "how can i",
        "why does",
        "why is",
        "explain",
        "tell me about",
        "define",
        "help me understand",
        "general question",
        "concept",
        "overview",
    ]
    if any(keyword in lower for keyword in generic_keywords):
        return {"is_generic": True, "reason": "generic informational question", "decision": "respond"}

    investigation_keywords = [
        "error",
        "timeout",
        "failure",
        "exception",
        "latency",
        "database",
        "service",
        "crash",
        "outage",
        "warning",
        "connect",
        "connection",
        "failed",
        "panic",
        "deadlock",
        "timeouts",
        "api",
        "pod",
        "deployment",
        "incident",
    ]

    if any(keyword in lower for keyword in investigation_keywords):
        return {"is_generic": False, "reason": "log investigation keywords detected", "decision": "tool_call"}

    return {"is_generic": False, "reason": "default operational intent", "decision": "tool_call"}


def decide_step_node(state: AgentState) -> AgentState:
    # Decide whether this query should go straight to the LLM or execute search first.
    query = (state.get("query") or "").strip()
    if not query:
        return {"decision": "respond", "iterations": state.get("iterations", 0) + 1}

    intent = classify_intent(query)
    decision = intent["decision"]
    return {"decision": decision, "iterations": state.get("iterations", 0) + 1}


def tool_call_node(state: AgentState) -> AgentState:
    # Perform the retrieval and record which tool was used.
    query = state.get("query", "")
    top_k = state.get("top_k", TOP_K_RESULTS)
    results = search_logs_tool(query, top_k=top_k)
    tool_call = {
        "tool": "search_logs",
        "query": query,
        "top_k": top_k,
        "matched_results": len(results.get("documents", [[]])[0]) if results.get("documents") else 0,
    }
    return {"tool_calls": [tool_call], "results": results, "decision": "respond"}


def call_local_llm(messages: List[Dict[str, str]], model: str = OLLAMA_MODEL, stream: bool = False) -> Any:
    # Send a chat payload to the local Ollama API. This can be used for both synchronous and streaming responses.
    payload = {"model": model, "messages": messages, "stream": stream}
    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=60, stream=stream)
        response.raise_for_status()
        if stream:
            return response
        payload_data = response.json()
        return payload_data.get("message", {}).get("content", "").strip()
    except Exception:
        return "" if not stream else None


def call_local_llm_details(messages: List[Dict[str, str]], model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    # Same as call_local_llm, but includes token and timing metadata from the Ollama response.
    payload = {"model": model, "messages": messages, "stream": False}
    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=60, stream=False)
        response.raise_for_status()
        payload_data = response.json()
        return {
            "content": payload_data.get("message", {}).get("content", "").strip(),
            "prompt_eval_count": payload_data.get("prompt_eval_count"),
            "eval_count": payload_data.get("eval_count"),
            "total_duration": payload_data.get("total_duration"),
        }
    except Exception:
        return {"content": "", "prompt_eval_count": None, "eval_count": None, "total_duration": None}


def stream_local_llm(messages: List[Dict[str, str]], model: str = OLLAMA_MODEL) -> Iterator[str]:
    # Convenience generator for streamed text-only chunks from Ollama.
    for event in stream_local_llm_details(messages, model=model):
        if event.get("type") == "content":
            yield event.get("text", "")


def stream_local_llm_details(messages: List[Dict[str, str]], model: str = OLLAMA_MODEL) -> Iterator[Dict[str, Any]]:
    # Parse the raw stream from Ollama line-by-line and convert it into structured events.
    response = call_local_llm(messages, model=model, stream=True)
    if not response:
        yield {"type": "metrics", "input_tokens": None, "output_tokens": None, "total_tokens": None}
        return

    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode('utf-8', errors='replace') if isinstance(raw_line, bytes) else str(raw_line)
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = chunk.get("message", {}).get("content", "")
        if content:
            yield {"type": "content", "text": content}
        if chunk.get("done"):
            prompt_tokens = chunk.get("prompt_eval_count")
            output_tokens = chunk.get("eval_count")
            yield {
                "type": "metrics",
                "input_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": (prompt_tokens or 0) + (output_tokens or 0),
            }
            break


def build_reasoning(query: str, results: Dict[str, Any]) -> str:
    # Turn the best vector match into a concise reasoning statement for the UI and final answer.
    documents = results.get("documents", [[]])[0] if results.get("documents") else []
    metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
    if not documents:
        return "No close log matches were found, so the agent is treating this as a likely missing-signal case and will ask for more specific failure details."

    best = documents[0]
    service = (metadatas[0] or {}).get("service", "unknown service")
    severity = (metadatas[0] or {}).get("severity", "unknown")
    return f"The issue appears to align with a likely failure pattern: '{best}' affecting {service} at severity {severity}. The agent is using that as the leading root-cause signal and will summarize the most relevant follow-up guidance."


def build_follow_up_questions(query: str, results: Dict[str, Any]) -> List[str]:
    # Produce one or two targeted follow-up prompts based on the retrieved matches.
    documents = results.get("documents", [[]])[0] if results.get("documents") else []
    if not documents:
        return [
            "Can you share the exact error text or stack trace?",
            "Which service or pod is experiencing the problem?",
        ]

    service = ((results.get("metadatas", [[]])[0]) or [{}])[0].get("service", "this service")
    return [
        f"Is the issue isolated to {service}?",
        "Do you want me to correlate this with a deployment or recent change?",
    ]


def build_tool_result_cards(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Convert raw Chroma results into UI-friendly metadata cards.
    documents = results.get("documents", [[]])[0] if results.get("documents") else []
    metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
    distances = results.get("distances", [[]])[0] if results.get("distances") else []
    cards: List[Dict[str, Any]] = []
    for idx, document in enumerate(documents):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        distance = distances[idx] if idx < len(distances) else None
        cards.append(
            {
                "rank": idx + 1,
                "document": document,
                "service": metadata.get("service", "unknown"),
                "severity": metadata.get("severity", "unknown"),
                "distance": float(distance) if isinstance(distance, (int, float)) else None,
            }
        )
    return cards


def execute_search_tool(query: str, top_k: int = TOP_K_RESULTS) -> Dict[str, Any]:
    # Wrapper that tolerates older call signatures for compatibility with tests and different integration layers.
    try:
        return search_logs_tool(query, top_k=top_k)
    except TypeError:
        return search_logs_tool(query)


def build_conversational_answer(query: str, results: Dict[str, Any], system_prompt: str = SYSTEM_PROMPT) -> str:
    # Compose a human-friendly answer from the matched logs and optionally the LLM.
    documents = results.get("documents", [[]])[0] if results.get("documents") else []
    metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
    distances = results.get("distances", [[]])[0] if results.get("distances") else []

    if not documents:
        fallback = "I couldn't find a close log match. Please try a more specific error message or include the service name and the exact exception text."
        llm_payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"The user issue is: {query}. There were no similar logs. Respond helpfully and ask for a more specific error detail."},
            ],
            "stream": False,
        }
        try:
            response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=llm_payload, timeout=30)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "").strip()
            if content:
                return content
        except Exception:
            pass
        return fallback

    best_document = documents[0]
    best_metadata = metadatas[0] if metadatas else {}
    best_distance = distances[0] if distances else None
    service = best_metadata.get("service", "unknown service")
    severity = best_metadata.get("severity", "unknown")
    distance = f" (distance: {best_distance:.3f})" if isinstance(best_distance, (int, float)) else ""

    summary = (
        f"I found a likely match: '{best_document}' in the {service} service "
        f"(severity: {severity}){distance}. This appears closely related to your issue and is a good starting point for triage."
    )

    if len(documents) > 1:
        related = ", ".join(documents[1:3])
        summary += f" Related entries include: {related}."

    llm_prompt = (
        f"System: {system_prompt}\n"
        f"User issue: {query}\n"
        f"Search results: {documents[:3]}\n"
        f"Please give a brief, conversational answer that references the likely root cause and next steps."
    )
    llm_answer = call_local_llm([{"role": "user", "content": llm_prompt}])
    if llm_answer:
        return llm_answer
    return summary


def final_response_node(state: AgentState) -> AgentState:
    # Final node in the graph: generate answer, reasoning, and follow-up suggestions in one place.
    query = state.get("query", "")
    results = state.get("results", {})
    system_prompt = state.get("system_prompt", SYSTEM_PROMPT)
    answer = build_conversational_answer(query, results, system_prompt)
    reasoning = build_reasoning(query, results)
    follow_up = build_follow_up_questions(query, results)
    return {"answer": answer, "reasoning": reasoning, "follow_up_questions": follow_up}


def build_step_timings(*, search_ms: Optional[float] = None, answer_ms: Optional[float] = None, follow_up_ms: Optional[float] = None, total_ms: Optional[float] = None) -> Dict[str, float]:
    # Utility to format execution timings into a consistent dictionary used in the frontend.
    timings: Dict[str, float] = {}
    if search_ms is not None:
        timings["search_logs"] = round(search_ms, 2)
    if answer_ms is not None:
        timings["answer_generation"] = round(answer_ms, 2)
    if follow_up_ms is not None:
        timings["follow_up_generation"] = round(follow_up_ms, 2)
    if total_ms is not None:
        timings["total_agent_time"] = round(total_ms, 2)
    return timings


@lru_cache(maxsize=1)
def build_agent_graph():
    # Build the state graph once and reuse it for repeated requests.
    graph = StateGraph(AgentState)
    graph.add_node("decide_step", decide_step_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("final_response", final_response_node)

    graph.add_edge(START, "decide_step")
    graph.add_conditional_edges(
        "decide_step",
        lambda state: "tool_call" if state.get("decision") == "tool_call" else "final_response",
        {"tool_call": "tool_call", "final_response": "final_response"},
    )
    graph.add_edge("tool_call", "final_response")
    graph.add_edge("final_response", END)

    return graph.compile()


def run_log_agent(query: str, top_k: int = TOP_K_RESULTS, system_prompt: str = SYSTEM_PROMPT, max_steps: int = 3) -> Dict[str, Any]:
    # Entry point for the full agent run. It handles intent routing, optional retrieval, and final answer generation.
    started_at = time.perf_counter()
    current_query = (query or "").strip()
    results = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    tool_chain: List[Dict[str, Any]] = []
    reasoning = "No analysis performed yet."
    follow_up_questions: List[str] = []
    timings: Dict[str, float] = {}
    plan = {
        "planner": {"role": "planner", "objective": "outline investigation steps"},
        "analyst": {"role": "analyst", "objective": "inspect relevant log matches and service signals"},
        "reporter": {"role": "reporter", "objective": "summarize findings and recommended next steps"},
        "steps": ["intent_check", "search_logs", "analyze_results", "report_findings"],
    }

    intent = classify_intent(current_query)
    if not current_query:
        answer = "I need a specific error or service issue to investigate."
        timings["total_agent_time"] = round((time.perf_counter() - started_at) * 1000, 2)
        return {
            "query": query,
            "system_prompt": system_prompt,
            "decision": "respond",
            "answer": answer,
            "tool_calls": tool_chain,
            "results": results,
            "reasoning": reasoning,
            "follow_up_questions": follow_up_questions,
            "plan": plan,
            "tool_results": build_tool_result_cards(results),
            "timings": timings,
        }

    if intent["is_generic"]:
        # Generic, explanatory questions do not need RAG lookup. Use the model directly.
        answer_start = time.perf_counter()
        llm_answer = call_local_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_query},
        ])
        answer = llm_answer or (
            "I can help explain that concept generally, but for specific log incidents I’ll need the exact error, service, and timeframe."
        )
        timings["answer_generation"] = round((time.perf_counter() - answer_start) * 1000, 2)
        reasoning = f"Generic intent detected; skipped RAG retrieval because the question is informational rather than an operational incident."
        timings["total_agent_time"] = round((time.perf_counter() - started_at) * 1000, 2)
        return {
            "query": query,
            "system_prompt": system_prompt,
            "decision": "respond",
            "answer": answer,
            "tool_calls": tool_chain,
            "results": results,
            "reasoning": reasoning,
            "follow_up_questions": [
                "Would you like me to turn this into a more specific log-investigation prompt?",
            ],
            "plan": plan,
            "tool_results": [],
            "timings": timings,
        }

    for step in range(max_steps):
        if step == 0:
            decision = decide_step_node({"query": current_query})["decision"]
        else:
            decision = "tool_call"

        if decision != "tool_call":
            answer_start = time.perf_counter()
            answer = build_conversational_answer(current_query, results, system_prompt)
            timings["answer_generation"] = round((time.perf_counter() - answer_start) * 1000, 2)
            reasoning = build_reasoning(current_query, results)
            follow_up_start = time.perf_counter()
            follow_up_questions = build_follow_up_questions(current_query, results)
            timings["follow_up_generation"] = round((time.perf_counter() - follow_up_start) * 1000, 2)
            timings["total_agent_time"] = round((time.perf_counter() - started_at) * 1000, 2)
            return {
                "query": query,
                "system_prompt": system_prompt,
                "decision": decision,
                "answer": answer,
                "tool_calls": tool_chain,
                "results": results,
                "reasoning": reasoning,
                "follow_up_questions": follow_up_questions,
                "plan": plan,
                "tool_results": build_tool_result_cards(results),
                "timings": timings,
            }

        search_start = time.perf_counter()
        results = execute_search_tool(current_query, top_k=top_k)
        timings["search_logs"] = round((time.perf_counter() - search_start) * 1000, 2)
        tool_chain.append({
            "step": step + 1,
            "tool": "search_logs",
            "query": current_query,
            "top_k": top_k,
            "matched_results": len(results.get("documents", [[]])[0]) if results.get("documents") else 0,
        })

        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        if documents or step == max_steps - 1:
            break

        current_query = refine_query_tool(current_query)

    answer_start = time.perf_counter()
    answer = build_conversational_answer(current_query, results, system_prompt)
    timings["answer_generation"] = round((time.perf_counter() - answer_start) * 1000, 2)
    reasoning = build_reasoning(current_query, results)
    follow_up_start = time.perf_counter()
    follow_up_questions = build_follow_up_questions(current_query, results)
    timings["follow_up_generation"] = round((time.perf_counter() - follow_up_start) * 1000, 2)
    timings["total_agent_time"] = round((time.perf_counter() - started_at) * 1000, 2)
    return {
        "query": query,
        "system_prompt": system_prompt,
        "decision": "respond",
        "answer": answer,
        "tool_calls": tool_chain,
        "results": results,
        "reasoning": reasoning,
        "follow_up_questions": follow_up_questions,
        "plan": plan,
        "tool_results": build_tool_result_cards(results),
        "timings": timings,
    }


def stream_log_agent(query: str, top_k: int = TOP_K_RESULTS, system_prompt: str = SYSTEM_PROMPT, max_steps: int = 3) -> Iterator[str]:
    # Produce a stream of SSE events so the frontend can render partial progress and final answer content in real time.
    result = run_log_agent(query, top_k=top_k, system_prompt=system_prompt, max_steps=max_steps)

    planning = result.get("plan", {})
    if planning:
        yield "data: " + json.dumps({"type": "planning", "plan": planning}) + "\n\n"

    reasoning = result.get("reasoning", "")
    if reasoning:
        yield "data: " + json.dumps({"type": "reasoning", "text": reasoning}) + "\n\n"

    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        yield "data: " + json.dumps({"type": "tool_calls", "tool_calls": tool_calls}) + "\n\n"

    tool_results = result.get("tool_results", [])
    if tool_results:
        yield "data: " + json.dumps({"type": "tool_results", "tool_results": tool_results}) + "\n\n"

    timings = result.get("timings", {})
    if timings:
        yield "data: " + json.dumps({"type": "timings", "timings": timings}) + "\n\n"

    answer = result.get("answer", "")
    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"User question: {query}\nContext: {result.get('results', {})}\nDraft answer: {answer}"},
    ]
    llm_answer = ""
    token_metrics = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    for event in stream_local_llm_details(llm_messages):
        event_type = event.get("type")
        if event_type == "content":
            chunk = event.get("text", "")
            if not chunk:
                continue
            llm_answer += chunk
            yield "data: " + json.dumps({"type": "answer", "text": chunk}) + "\n\n"
        elif event_type == "metrics":
            token_metrics = {
                "input_tokens": event.get("input_tokens"),
                "output_tokens": event.get("output_tokens"),
                "total_tokens": event.get("total_tokens"),
            }
            yield "data: " + json.dumps({"type": "metrics", "metrics": token_metrics}) + "\n\n"

    if not llm_answer:
        yield "data: " + json.dumps({"type": "answer", "text": answer}) + "\n\n"

    if result.get("follow_up_questions"):
        yield "data: " + json.dumps({"type": "follow_up", "questions": result.get("follow_up_questions", [])}) + "\n\n"


def handle_agent_feedback(query: str, reaction: str, feedback_message: Optional[str] = None) -> Dict[str, Any]:
    # Capture user sentiment and use it to improve the next answer if the response was not helpful.
    normalized_reaction = (reaction or "neutral").strip().lower()
    if normalized_reaction not in {"like", "dislike"}:
        normalized_reaction = "neutral"

    FEEDBACK_HISTORY.append({
        "query": query,
        "reaction": normalized_reaction,
        "message": feedback_message or "",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    })

    if normalized_reaction == "like":
        answer = run_log_agent(query)
        return {
            "status": "recorded",
            "reaction": normalized_reaction,
            "query": query,
            "answer": answer.get("answer", ""),
            "follow_up_questions": answer.get("follow_up_questions", []),
            "refined_answer": answer.get("answer", ""),
        }

    improved_query = (
        f"{query}. The previous answer was disliked because it was too generic or not specific enough. "
        f"Please provide a more concrete, actionable, service-focused explanation with likely root causes, severity cues, and next steps."
    )
    if feedback_message:
        improved_query += f" Additional feedback: {feedback_message}"

    answer = run_log_agent(improved_query)
    return {
        "status": "recorded",
        "reaction": normalized_reaction,
        "query": query,
        "feedback": feedback_message or "",
        "answer": answer.get("answer", ""),
        "follow_up_questions": answer.get("follow_up_questions", []),
        "refined_answer": answer.get("answer", ""),
    }
