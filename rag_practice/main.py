from adapters import AIAdapter
from decorators import catch_exceptions
from lib import FileSystem
from lib.config import Config
from lib.logger import Logger
from repositories import PoliciesRepository


@catch_exceptions()
def main() -> None:
    logger = Logger(name="main")
    cfg = Config()
    fs = FileSystem()
    policies_repo = PoliciesRepository(cfg)
    ai = AIAdapter(cfg)
    policy_1 = fs.read("policy_1.md")
    policy_2 = fs.read("policy_2.md")

    # Add policies to the repository
    policies_repo.add_policy(
        "HR-WFH-001",
        policy_1,
        {
            "document_id": "HR-WFH-001",
            "title": "Employee Work From Home Policy",
            "category": "human_resources",
            "version": "1.0",
            "department": "Human Resources",
            "effective_date": "2026-01-01",
            "section": "Working Hours",
            "source_type": "policy",
            "access_level": "internal",
            "language": "en",
        },
    )

    policies_repo.add_policy(
        "SEC-DP-002",
        policy_2,
        {
            "document_id": "SEC-DP-002",
            "title": "Customer Data Privacy and Security Policy",
            "category": "security",
            "version": "1.0",
            "section": "Access Control",
            "effective_date": "2026-01-01",
        },
    )

    _query = "Does the company reimburse internet expenses?"
    # Search for relevant policies
    policy = policies_repo.search_policies(_query)

    if policy:
        response = ai.chat(
            f"Based on the following policy, answer the question: {_query}\n\nPolicy: {policy}"
        )
        logger.info(response)
    else:
        logger.warning("No relevant policies found.")


if __name__ == "__main__":
    main()
