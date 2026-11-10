from IPython.display import Image, display
from langchain.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

from lib.config import Config


class StockAgent:
    def __init__(self, cfg: Config) -> None:
        self._tools = self._list_tools()
        self._llm = self._build_llm(cfg.OPENAI_MODEL, cfg.OPENAI_BASE_URL)
        self._checkpointer = InMemorySaver()
        self._agent = self._build_agent_graph()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def chat(self, message: str, thread_id: str):
        """Start a turn. Returns either a final answer or a pending interrupt."""
        result = self._agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        # self._report(result)
        result = self._handle_interrupt(result, thread_id)
        return result

    def resume(self, decision, thread_id: str):
        """Resume a paused run.

        decision:
          - a single value  -> one pending interrupt (e.g. {"approved": True})
          - a list          -> several pending interrupts, in call order
          - a dict {id: v}  -> several pending interrupts, keyed by interrupt id
        """
        result = self._agent.invoke(
            Command(resume=decision),
            config={"configurable": {"thread_id": thread_id}},
        )
        # self._report(result)
        result = self._handle_interrupt(result, thread_id)
        return result

    def snapshot(self, thread_id: str):
        """Inspect the paused state (next node, pending tool calls, etc.)."""
        return self._agent.get_state({"configurable": {"thread_id": thread_id}})

    def display_flow(self):
        """Display the LangGraph flow diagram."""
        display(Image(self._agent.get_graph().draw_mermaid_png()))

    # ------------------------------------------------------------------ #
    # Builders
    # ------------------------------------------------------------------ #

    def _build_llm(self, model: str, base_url: str):
        return ChatOpenAI(
            model=model,
            base_url=base_url,
        ).bind_tools(self._tools)

    def _build_agent_graph(self):
        graph = StateGraph(MessagesState)
        graph.add_node("agent", self._chat_model)
        graph.add_node("tools", ToolNode(self._tools))
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", tools_condition)
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=self._checkpointer)

    def _chat_model(self, state: MessagesState):
        response = self._llm.invoke(state["messages"])
        return {"messages": [response]}

    def _handle_interrupt(self, response: dict, thread_id: str):
        """Handle human interrupts and resume the conversation."""
        if "__interrupt__" in response:
            approvals: dict = {}
            interrupts = response["__interrupt__"]
            for idx, interrupt in enumerate(interrupts):
                interrupt_id = getattr(interrupt, "id", "n/a")
                interrupt_payload = interrupt.value or {}
                question = interrupt_payload.get("question", "Approve?")
                print(f"[Interrupt {interrupt_id[4:]}]")
                approve = input(f"{question} (y/n): ")
                if approve.lower() == "y":
                    decision = {"approved": True}
                else:
                    decision = {"approved": False}
                approvals[interrupt_id] = decision
            response = self.resume(approvals, thread_id)
        return response

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _report(result: dict) -> None:
        interrupts = result.get("__interrupt__") or ()
        for itr in interrupts:
            print("#" * 40)
            print("\n--- INTERRUPTED: awaiting human decision ---")
            print(f"  interrupt id : {getattr(itr, 'id', 'n/a')}")
            print(f"  payload      : {itr.value}")
            print("#" * 40)

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    def _list_tools(self):
        return [self._get_stock_price, self._buy_stock]

    @tool("get_stock_price")
    @staticmethod
    def _get_stock_price(symbol: str) -> float:
        """Return the current price of a stock given the stock symbol
        :param symbol: stock symbol
        :return: current price of the stock
        """
        return {"MSFT": 200.3, "AAPL": 100.4, "AMZN": 150.0, "RIL": 87.6}.get(
            symbol, 0.0
        )

    @tool("buy_stock")
    @staticmethod
    def _buy_stock(symbol: str, quantity: int) -> str:
        """Execute a stock purchase for the given symbol and quantity.
        :param symbol: stock symbol
        :param quantity: number of shares to buy
        :return: confirmation message
        """
        # ---- HUMAN-IN-THE-LOOP GATE -------------------------------- #
        decision = interrupt(
            {
                "action": "buy_stock",
                "symbol": symbol,
                "quantity": quantity,
                "question": f"Approve buying {quantity} shares of {symbol}?",
                "options": ["approve", "reject", "edit"],
            }
        )
        # ------------------------------------------------------------ #

        # Nothing above this line has side effects: LangGraph replays the
        # tool body from the top when it resumes, so the code above runs twice.

        if not isinstance(decision, dict):
            decision = {"approved": bool(decision)}

        if not decision.get("approved", False):
            return (
                f"Purchase of {quantity} shares of {symbol} was REJECTED by the "
                "human reviewer. Do not retry unless explicitly asked."
            )

        # Allow the human to tweak the order while approving
        final_symbol = decision.get("symbol", symbol)
        final_qty = decision.get("quantity", quantity)

        # >>> This is where the real side effect would go <<<
        return f"Bought {final_qty} shares of {final_symbol} (approved by human)."
