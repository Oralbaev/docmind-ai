from langgraph.graph import END, START, StateGraph

from app.agent.nodes import AgentLLM, AgentNodes, Retriever
from app.agent.state import AgentState


# Самый длинный путь при max_retries=2 это примерно 11 шагов; запас на случай
# изменения графа. Лимит защищает от бесконечного цикла.
RECURSION_LIMIT = 25


def build_agent_graph(
    llm: AgentLLM,
    retriever: Retriever,
    max_retries: int = 2,
):
    nodes = AgentNodes(llm, retriever, max_retries)

    graph = StateGraph(AgentState)

    graph.add_node("analyze", nodes.analyze)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("grade", nodes.grade)
    graph.add_node("rewrite", nodes.rewrite)
    graph.add_node("generate", nodes.generate)
    graph.add_node("check", nodes.check)
    graph.add_node("fallback", nodes.fallback)
    graph.add_node("off_topic", nodes.off_topic)

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        nodes.route_after_analyze,
        {"retrieve": "retrieve", "off_topic": "off_topic"},
    )
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        nodes.route_after_grade,
        {"generate": "generate", "rewrite": "rewrite", "fallback": "fallback"},
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", "check")
    graph.add_conditional_edges(
        "check",
        nodes.route_after_check,
        {"done": END, "fallback": "fallback"},
    )
    graph.add_edge("fallback", END)
    graph.add_edge("off_topic", END)

    return graph.compile()


async def run_agent(graph, question: str, top_k: int = 5) -> AgentState:
    return await graph.ainvoke(
        {
            "question": question,
            "top_k": top_k,
            "retries": 0,
            "trace": [],
        },
        config={"recursion_limit": RECURSION_LIMIT},
    )
