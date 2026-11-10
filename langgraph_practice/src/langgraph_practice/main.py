from agents import stock_agent as agents
from lib.config import Config

messages = [
    "What's the price of Apple stock?",
    "What's the price of Google stock?",
    "What's the price of Microsoft stock?",
    "Buy 5 microsoft stock with 3 apple stock",
    "Whats my total expenditure?",
]


def main() -> None:
    cfg = Config()
    agent = agents.StockAgent(cfg)

    for message in messages:
        response = agent.chat(message, "1")
        print("-" * 40)
        print(f"User: {message}")
        print(f"Agent: {response['messages'][-1].content}")
        print("-" * 40)


if __name__ == "__main__":
    main()
