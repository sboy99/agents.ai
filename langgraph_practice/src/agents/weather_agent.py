from langchain.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langsmith import traceable

from lib.config import Config


class WeatherAgent:
    def __init__(self, cfg: Config):
        self._tools = [self.search]
        self._llm = self._build_llm(cfg.OPENAI_MODEL, cfg.OPENAI_BASE_URL)
        self._agent = self._build_agent_graph()

    # Tool definitions

    @tool
    @staticmethod
    def search(query: str):
        """Call to surf the web."""
        city = query.lower()
        if "sf" in city or "san francisco" in city:
            return "It's 60 degrees and foggy."
        elif "nyc" in city or "new york" in city:
            return "It's 75 degrees and cloudy."
        elif "la" in city or "los angeles" in city:
            return "It's 85 degrees and sunny."
        return "It's 90 degrees and sunny."

    def chat(self, message: str, thread_id: str):
        """Start a chat session with the weather agent."""
        return self._agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id}},
        )

    @traceable
    def _call_model(self, state: MessagesState):
        """Call the LLM to get weather information."""
        messages = state["messages"]
        response = self._llm.invoke(messages)
        return {"messages": [response]}

    def _build_llm(self, model_name: str, base_url: str):
        """Build and configure the LLM model with tools."""
        return ChatOpenAI(model=model_name, base_url=base_url)
        # .bind_tools(self._tools)

    def _build_agent_graph(self):
        """Build and configure the agent graph."""
        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", ToolNode(self._tools))
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")
        checkpoint = InMemorySaver()
        return workflow.compile(checkpoint)
