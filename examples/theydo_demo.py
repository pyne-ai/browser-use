from datetime import date
import json
import logging
import os
import sys
import uuid

import htmlrag
from langchain_core.messages import (
    SystemMessage,
)
import requests


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_use.browser.context import BrowserContext
from browser_use.dom.views import DOMState

from datetime import datetime
import asyncio
from typing import List, Optional, Union

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from pydantic import BaseModel, field_validator

from browser_use.agent.service import Agent
from browser_use.agent.views import ActionResult, AgentHistoryList

from browser_use.controller.service import Controller

supabase_key = os.environ.get("SUPABASE_KEY")
supabase_url = os.environ.get("SUPABASE_URL")


# Initialize controller first
controller = Controller()


class AgentStep(BaseModel):
    description: str
    xpath_id: str
    step_type: Optional[str]  # Allow it to be optional

    @field_validator("step_type")
    def set_default_step_type(cls, value):
        return value or "userClick"


class Section(BaseModel):
    section_name: str
    steps: List[AgentStep]


class ActionSummary(BaseModel):
    sections: List[Section]


class ActionSummaryList(BaseModel):
    actions: List[ActionSummary]


class MemoryItem(BaseModel):
    memory: str
    next_goal: str


class LoginInfo(BaseModel):
    username: str
    password: str


class WebpageInfo(BaseModel):
    link: str = "https://theydo.com"


class UserLogin(BaseModel):
    username: str = "berkant+auto4@pyne.ai"
    password: str = "Password!123"


class MarksAttrs(BaseModel):
    id: str


class Mark(BaseModel):
    type: str
    attrs: MarksAttrs


class TextContent(BaseModel):
    type: str
    text: str


class StepAttributes(BaseModel):
    id: str
    type: str


class StepContent(BaseModel):
    type: str
    text: str


class Step(BaseModel):
    type: str
    attrs: StepAttributes
    content: List[StepContent]


class ParagraphContent(BaseModel):
    type: str
    content: List[Step]


class DocContent(BaseModel):
    type: str
    content: List[ParagraphContent]


class MainModel(BaseModel):
    content: DocContent


def generate_uuid():
    """Generate a unique UUID."""
    return str(uuid.uuid4())


@controller.action("Go to the webpage", param_model=WebpageInfo)
def go_to_webpage(webpage_info: WebpageInfo):
    return webpage_info.link


@controller.action("Signin/login to website", param_model=UserLogin)
def login(user: UserLogin):
    print("Logging in with username:", user.username)
    return user.model_dump_json()


@controller.action("Get page context", requires_browser=True)
async def get_page_context(browser: BrowserContext):
    logging.info("Getting page context..")
    agent = ChatOpenAI(model="gpt-4o")  # type: ignore
    page = await browser.get_page_html()
    cleaned_html = htmlrag.clean_html(page)

    human_message = HumanMessage(
        content=[
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{browser.current_state.screenshot}"
                },
            },
            {"type": "text", "text": f"Here is the cleaned html page: {cleaned_html}"},
        ]
    )

    system_message = SystemMessage(
        content=[
            {
                "type": "text",
                "text": "Please analyze the page and provide me with the context.",
            },
        ]
    )

    msg = [system_message, human_message]

    response = await agent.ainvoke(msg)
    return ActionResult(extracted_content=response.model_dump_json())


task = """
        IMPORTANT RULES:
            - If task requires login use action 'login' to login to the website.
            - If you face with any trial limit error popup, close it.
            - If you cannot proceed on login page, you must use action 'perform_login' to bypass.


        1.  Create a journey with basic template.
        2.  Use sample transcript as the evidence for the journey mapping. Add evidence to the journey. Pick template.
        3.  Go to journeys again. Open '[AI] Sample Journey'. Display opportunity matrix.
        5.  Go back to the journey library.
        6.  If you stuck in a loop. Finish the task.
        6.  Done.
        """


# task = """
#         IMPORTANT RULES:
#             - If task requires login use action 'login' to login to the website.
#             - If you face with any trial limit error popup, close it.
#             - If you cannot proceed on login page, you must use action 'perform_login' to bypass.


#         1. Create a journey with basic template.
#         2. Go back to the journey library.
#         3. Open sample journey. Navigate the opportunitites and go to matrix tab.
#         6. If you stuck in a loop. Finish the task.
#         6.  Done.
#         """

model = ChatOpenAI(model="gpt-4o")
agent = Agent(
    task=task,
    llm=model,
    controller=controller,
)


def map_input_to_model(input_data: str, xpaths: dict[str, str]):
    """
    Accepts a JSON string as input, parses it, and converts it to the required model format.

    Args:
        input_data (str): JSON string representing the input data.

    Returns:
        dict: A dictionary containing the transformed `content` and `references`.
    """
    # Parse the JSON string into a Python dictionary
    try:
        parsed_data = json.loads(input_data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON string provided: {e}")

    paragraphs = []
    references = []

    for action in parsed_data.get("actions", []):
        for section in action.get("sections", []):
            steps = []
            current_index = 0
            for step in section.get("steps", []):
                step_id = generate_uuid()
                description = step["description"]
                try:
                    xpath_id = step["xpath_id"]
                    xpath = "//" + str(xpaths[xpath_id])
                    logging.info(f"Xpath: {xpath}")
                except KeyError:
                    logging.error(
                        f"""
                        XPath ID {xpath_id} not found in the provided xpaths. Skipping step. \n
                        Available xpaths: {xpaths}
                        """
                    )
                    pass
                # Calculate `from` and `to` indices
                from_index = current_index
                to_index = from_index + len(description)
                current_index = to_index + 1  # Add space for the next description

                # Create step
                step_data = Step(
                    type="step",
                    attrs=StepAttributes(id=step_id, type=step["step_type"]),
                    content=[StepContent(type="text", text=description)],
                )
                steps.append(step_data)

                # Add reference for the step
                references.append(
                    {
                        "id": step_id,
                        "type": step["step_type"],
                        "from": from_index,
                        "to": to_index,
                        "createdAt": "2024-12-05T12:00:00.000Z",
                        "item": {
                            "type": step["step_type"],
                            "isCheckpoint": False,
                            "targetElementSelector": xpath,
                            "virtualCursor": {"animationType": "move"},
                            "clickDetectionMethod": "click",
                        },
                        "offsetTop": 0,
                        "orphaned": False,
                    }
                )

            paragraph = ParagraphContent(type="paragraph", content=steps)
            paragraphs.append(paragraph)
    return {
        "content": DocContent(type="doc", content=paragraphs).model_dump(),
        "references": references,
    }


async def main():
    history: AgentHistoryList = await agent.run()

    history_path = "history.json"
    agent.save_history(file_path=history_path)

    xpaths = {t.id: t.xpath for i, t in enumerate(history.successful_actions())}

    with open("success.json", "w") as f:
        temp_list = []
        for a in history.successful_actions():
            temp_list.append(a.model_dump_json())
        json.dump(temp_list, f, indent=4)

    thoughts_str = ""
    for i, t in enumerate(history.successful_actions()):
        thoughts_str += f"{i}. Intention was:{t.text}: \n Clicked element key was: {t.id}\n Memory: {t.thought.memory}\n Next goal: {t.thought.next_goal}\n"

    messages = [
        (
            "system",
            """
                 You are a website agent click analyzer. Use the following actions to analyze the website clicks.
                 Remove duplicated actions to reduce redundancy.
                 Do not hallucinate or make up actions which the user did not ask for, and keep the flow of the actions in logical order derived from the thoughts.
                 Do not include anything related with login and cookie settings in the output.
                 Use clicked element key to identify the clicked element.
                """,
        ),
        (
            "human",
            f"Actions taken are:{thoughts_str}",
        ),
    ]

    summarizer_model = ChatOpenAI(model="gpt-4o").with_structured_output(
        ActionSummaryList, include_raw=False, strict=True
    )

    response = await summarizer_model.ainvoke(messages)
    logging.info("Response from the summarizer model:", response)
    structured_output = ActionSummaryList.model_validate(response)
    logging.info("Structured output:", structured_output)

    # xpaths = {"1": "test", "2": "stest"}

    # input_data = """
    #     {
    #         "actions": [
    #             {
    #                 "sections": [
    #                     {
    #                         "section_name": "Create a Customer Journey",
    #                         "steps": [
    #                             {
    #                                 "description": "Create a journey using the basic customer journey template.",
    #                                 "xpath_id": "1",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'Continue' to proceed with the selected template.",
    #                                 "xpath_id": "1",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'I want to add evidence' to proceed with adding evidence to the journey.",
    #                                 "xpath_id": "1",
    #                                 "step_type": "userClick"
    #                             }
    #                         ]
    #                     },
    #                     {
    #                         "section_name": "Interact with the Dashboard and Opportunity Matrix",
    #                         "steps": [
    #                             {
    #                                 "description": "Continue to the dashboard to proceed.",
    #                                 "xpath_id": "2",
    #                                 "step_type": "userClick"
    #                             }
    #                         ]
    #                     },
    #                     {
    #                         "section_name": "Navigate Back to the Journey Library",
    #                         "steps": [
    #                             {
    #                                 "description": "Go back to the journey library.",
    #                                 "xpath_id": "1",
    #                                 "step_type": "userClick"
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     }"""

    output = map_input_to_model(structured_output.model_dump_json(), xpaths)

    print("Output:", json.dumps(output, indent=4))

    res = requests.post(
        "http://localhost:3000/api/storyteller",
        headers={
            "test-ai-storyteller-key": "8MRVo444GP5FGVGm51whO0FXgXKhw1YwsXrTQajbaXdrQo26WG2Y8dA4k690dksv",
            "Content-Type": "application/json",
        },
        json=json.dumps(output, indent=4),
    )

    print("Response from the Storyteller API:", res.json())


if __name__ == "__main__":
    asyncio.run(main())
