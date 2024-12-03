from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from postprocess.otc.views import ExaminedUrl


class OTCAgent:
    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def _create_system_message_url_examiner(self) -> SystemMessage:  # type: ignore
        """
        Creates a system message to instruct the LLM to classify static and dynamic parts of a URL.
        """
        system_message = (
            "You are an AI agent that understands URLs and can classify their components. "
            "Your task is to identify which parts of the URL are static and which are dynamic. "
            "Static parts are consistent across requests, while dynamic parts vary based on user or context. "
            "Return a structured JSON object with `static_parts` and `dynamic_parts` keys."
        )
        return SystemMessage(content=system_message)

    async def process(self, url: str) -> ExaminedUrl:
        """
        Sends the URL classification task to the LLM and returns the response.

        Args:
            url (str): The URL to be classified.

        Returns:
            ExaminedUrl: A structured object containing classified URL components.
        """
        # Create the system message
        sys_message = self._create_system_message_url_examiner()

        # Create the user message with the URL
        user_message = HumanMessage(content=url)

        # Send the task to the LLM
        llm = self.llm.with_structured_output(ExaminedUrl, include_raw=False)
        response: dict[str, Any] = await llm.ainvoke([sys_message, user_message])  # type: ignore

        # Parse the response
        parsed: ExaminedUrl = response['parsed']

        return parsed