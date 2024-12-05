from datetime import date
import json
import logging
import os
import sys
import uuid

import htmlrag
from langchain_core.messages import (
    BaseMessage,
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
    xpath: str
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
    username: str = "berkant+auto3@pyne.ai"
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
            - If you cannot proceed on login page, you must use action 'perform_login'.
            - When you pass a step successfully, use action 'find_relative_elements'.
            
            
        1. Create a journey with basic template.
        2.  Use sample transcript as the evidence for the journey mapping. Add evidence to the journey. Pick template.
        3.  Go to journeys again. Open [AI] Sample Journey. Display opportunity matrix and adjust the scoring for customer and business value.
        4.  When you open the opportunity matrix, if face with placeholder or empty state. Use action 'load_checkpoint' to go back to the latest successful url. And try sample journey again until you see the opportunity matrix that has data.
        5.  Go back to the journey library.
        6. Done.
        """

model = ChatOpenAI(model="gpt-4o")
agent = Agent(task=task, llm=model, controller=controller)


def map_input_to_model(input_data: str):
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
                xpath = "//" + step.get("xpath", "")

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

    thoughts_str = ""
    for i, t in enumerate(history.successful_actions()):
        thoughts_str += f"{i}. Intention was:{t.text}: \n Clicked element xpath was: {t.xpath}\n Memory: {t.thought.memory}\n Next goal: {t.thought.next_goal}\n"

    messages = [
        (
            "system",
            """
                 You are a website agent click analyzer. Use the following actions to analyze the website and provide me a summary of the actions, mapping Xpaths of the actions taken on the website in the summary you will provide.
                 Do not hallucinate or make up actions which the user did not ask for, and keep the flow of the actions in logical order derived from the thoughts.
                 Do not include anything related with login and cookie settings in the output.
                 """,
        ),
        (
            "human",
            f"Here are successful actions taken along with the xpath selectors:{thoughts_str}",
        ),
    ]

    summarizer_model = ChatOpenAI(model="gpt-4o").with_structured_output(
        ActionSummaryList, include_raw=False, strict=True
    )

    response = await summarizer_model.ainvoke(messages)
    structured_output = ActionSummaryList.model_validate(response)
    print("Response:", structured_output.model_dump_json())

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
    #                                 "xpath": "html/body/div[2]/div/div/main/div/div/div[2]/div[2]/div/div/div/div[2]/div[2]/button",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'Continue' to proceed with the selected template.",
    #                                 "xpath": "html/body/div[2]/div/div[4]/div/div[2]/div[2]/div[2]/div[3]/span/button",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'I want to add evidence' to proceed with adding evidence to the journey.",
    #                                 "xpath": "html/body/div[2]/div/div[4]/div/div[2]/div[2]/div[2]/div[2]/div/div/div/span/div/button",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'Use a sample transcript' to add evidence.",
    #                                 "xpath": "html/body/div[2]/div/div/4/div/div[2]/div[2]/div[2]/div[2]/div/div/form/fieldset/div/button",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'Map my Journey' to proceed with journey mapping.",
    #                                 "xpath": "html/body/div[2]/div/div/4/div/div[2]/div[2]/div[2]/div[2]/div/div/div/span/button",
    #                                 "step_type": "userClick"
    #                             }
    #                         ]
    #                     },
    #                     {
    #                         "section_name": "Interact with the Dashboard and Opportunity Matrix",
    #                         "steps": [
    #                             {
    #                                 "description": "Continue to the dashboard to proceed.",
    #                                 "xpath": "html/body/div[2]/div/div/main/div/div/div/div[2]/div[2]/div/div/div/div/div/div/div/div/div/div/div[3]/span/button",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Open [AI] Sample Journey.",
    #                                 "xpath": "html/body/div[2]/div/div/nav/div/div[2]/div[5]/div[2]/div/div/div/a",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Click 'Opportunities' to view the opportunity matrix.",
    #                                 "xpath": "html/body/div[2]/div/div/main/div/div/div/div[2]/div[2]/div/div/div/div/div[2]/div/div/div/button[3]",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Adjust the scoring of the opportunity matrix for customer and business value.",
    #                                 "xpath": "html/body/div[4]/div",
    #                                 "step_type": "userClick"
    #                             },
    #                             {
    #                                 "description": "Adjust the scoring for customer and business value for the circles on the opportunity matrix.",
    #                                 "xpath": "html/body/div/div/div/main/div[2]/div/div/div/div/div/div/div[2]/div/div/img",
    #                                 "step_type": "userClick"
    #                             }
    #                         ]
    #                     },
    #                     {
    #                         "section_name": "Navigate Back to the Journey Library",
    #                         "steps": [
    #                             {
    #                                 "description": "Go back to the journey library.",
    #                                 "xpath": "html/body/div[2]/div/div/main/div/div/div/div/div/nav/ol/li/a",
    #                                 "step_type": "userClick"
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     }"""

    output = map_input_to_model(structured_output.model_dump_json())

    res = requests.post(
        "http://localhost:3000/api/storyteller",
        headers={
            "test-ai-storyteller-key": "8MRVo444GP5FGVGm51whO0FXgXKhw1YwsXrTQajbaXdrQo26WG2Y8dA4k690dksv",
            "Content-Type": "application/json",
        },
        json=json.dumps(output, indent=4),
    )

    print("output is:L", output)
    print("Status Code:", res.status_code)
    print("Response Text:", res.text)


if __name__ == "__main__":
    asyncio.run(main())
