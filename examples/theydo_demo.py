from datetime import date
import json
import logging
import os
import sys
import uuid

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
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer

supabase_key = os.environ.get("SUPABASE_KEY")
supabase_url = os.environ.get("SUPABASE_URL")


# Initialize controller first
controller = Controller()


class GuideIntroMessage(BaseModel):
    text: str


class AgentStep(BaseModel):
    description: str
    xpath_id: str
    step_type: Optional[str]  # Allow it to be optional

    @field_validator("step_type")
    def set_default_step_type(cls, value):
        return "userClick"


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
    # link: str = "https://app.theydo.com/"
    link: str = "https://app.shortcut.com/"


class UserLogin(BaseModel):
    # username: str = "demo+test@pyne.ai"
    username: str = "ashish@pyne.ai"
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


# urls = ["https://app.theydo.com/"]
# loader = AsyncHtmlLoader(urls)
# docs = loader.load()
# html2text = Html2TextTransformer()
# docs_transformed = html2text.transform_documents(docs)

# print("Content extracted:", docs_transformed[0].page_content)
task = """
        1. **Access the Stories Page:**   - Navigate to the Stories page by selecting "Stories" in the Shortcut sidebar menu.
        2. **Create a New Story:**   - Click on the "Create Story" button to start a new Story.
        3. **Fill in Story Details:**   - Enter the necessary details for your Story, such as the title and description.   - Optionally, add metadata like attachments, labels, and comments.
        4. **Assign the Story to a Team:**   - In the Story creation form, locate the "Team" field.   - Select the appropriate Team from the dropdown menu. Ensure that the Team is associated with the desired Workflow.
        5. **Select the Workflow State:**   - Find the "Workflow State" field in the Story creation form.   - Choose the initial Workflow State for the Story. This should align with the Workflow associated with the selected Team.
        6. **Assign Owners and Followers:**   - Assign an Owner to the Story if needed.   - Add Followers to keep them notified of the Story\'s progress.
        7. **Save the Story:**   - Once all details are filled in, click the "Create Story" button to save and create the Story.By following these steps, you will have successfully created a Story and assigned it to a Team within a specific Workflow in Shortcut.
    """


# task = """
#         IMPORTANT RULES:
#             - If task requires login use action 'login' to login to the website.
#             - If you face with any trial limit error popup, close it.
#             - If you cannot proceed on login page, you must use action 'perform_login' to bypass.
            
#         1- Interact all the items in the page and provide me a final context of the whole webpage. 
#         """

model = ChatOpenAI(model="gpt-4o")
agent = Agent(
    task=task,
    llm=model,
    controller=controller,
)


def map_input_to_model(intro: str, input_data: str, xpaths: dict[str, str]):
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
        intro_data = json.loads(intro)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON string provided: {e}")

    paragraphs = []
    references = []

    # Create the introductory message
    intro_message = GuideIntroMessage(text=intro_data.get("text"))
    intro_uuid = generate_uuid()
    paragraph = ParagraphContent(
        type="paragraph",
        content=[
            Step(
                type="step",
                attrs=StepAttributes(id=intro_uuid, type="question"),
                content=[StepContent(type="text", text=intro_message.text)],
            )
        ],
    )
    paragraphs.append(paragraph)
    intro_reference = {
        "id": intro_uuid,
        "type": "anotation",
        "from": 1,
        "to": 1,
        "createdAt": "2024-12-03T13:48:03.020Z",
        "item": {
            "isCheckpoint": True,
            "onTrackConditions": {"isEnabled": True, "conditions": []},
            "type": "question",
            "questionType": "multipleChoice",
            "choices": [
                {
                    "id": "80875365-3d60-4ad4-ae6a-7434067a7867",
                    "text": "Yes",
                    "type": "proceedNext",
                    "buttonVariant": "primary",
                },
                {
                    "id": "d1f48ea7-4b93-402f-b814-57a2bde7811e",
                    "text": "Not now",
                    "type": "suspendTour",
                    "buttonVariant": "secondary",
                },
            ],
            "title": "Would you like to start a demo?",
        },
        "orphaned": False,
        "offsetTop": 66,
    }

    references.append(intro_reference)

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


async def create_intro_message(tour_description: str):
    with open("success.json", "r") as f:
        data = json.load(f)
        introductory_model = ChatOpenAI(model="gpt-4o").with_structured_output(
            GuideIntroMessage, include_raw=False, strict=True
        )

        human_message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"Actions: {data}",
                },
                {"type": "text", "text": f"Tour description is: {tour_description}"},
            ]
        )

        system_message = SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": """
                    Important rules:
                    1. Avoid cookies or login-related actions in the output.
                    2. Do not reference or hint at the input actions, steps, or user progress in the welcome message.
                    3. Always conclude the text with an engaging question that asks them to they want a demo or not.
                    4. Use the ADAI (Attention, Desire, Action, Impact) method to create a compelling and engaging message but keep the attention part more smooth for website onboard video.
                    5. Be clear, engaging, and universally relevant to new users, avoiding any reliance on context from the input actions.
                    6. Use company name in the welcome message.
                    You are a website demo agent welcoming new users. Your task is to create a generic and engaging introduction that conveys the core value of the platform and encourages exploration, regardless of any specific user actions or progress.

                    Example input actions:
                    [
                        "{\"id\":\"19\",\"xpath\":\"html/body/div[2]/div/div[4]/div/div[2]/div[2]/div[2]/div[3]/span/button\",\"text\":\"Click 'Continue' to proceed with the journey creation using the selected template.\",\"thought\":{\"memory\":\"Selected the basic customer journey template. Ready to proceed with adding evidence.\",\"next_goal\":\"Click 'Continue' to proceed with the journey creation using the selected template.\"}}",
                        "{\"id\":\"20\",\"xpath\":\"html/body/div[2]/div/div[4]/div/div[2]/div[2]/div[2]/div[2]/div/div/div/span/div/button\",\"text\":\"Click 'I want to add evidence' to proceed with adding evidence.\",\"thought\":{\"memory\":\"Journey creation started. Ready to add evidence.\",\"next_goal\":\"Click 'I want to add evidence' to proceed with adding evidence.\"}}"
                    ]
                    """,
                }
            ]
        )

        msg = [system_message, human_message]
        response = await introductory_model.ainvoke(msg)
        structured_output = GuideIntroMessage.model_validate(response)

        print("Response from the introductory model:", response)
        return structured_output


async def main():
    tour_description = "I want to have an in product tour for TheyDo AI journey feature. Tour should create an AI journey with basic template and after the creation it should show opportunity matrix and highlight that our customers find opportunity matrix page the be the most convincing communication tool to align their leadership team as well as other stakeholders."

    history: AgentHistoryList = await agent.run()

    history_path = "./history.json"
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
    structured_output = ActionSummaryList.model_validate(response)

    intro_message = await create_intro_message(tour_description=tour_description)
    output = map_input_to_model(
        intro_message.model_dump_json(), structured_output.model_dump_json(), xpaths
    )
    output_json = json.dumps(output)

    res = requests.post(
        "http://localhost:3000/api/storyteller",
        headers={
            "test-ai-storyteller-key": "8MRVo444GP5FGVGm51whO0FXgXKhw1YwsXrTQajbaXdrQo26WG2Y8dA4k690dksv",
            "Content-Type": "application/json",
        },
        json=output_json,
    )

    print("Response from the Storyteller API:", res.json())

    # with open("success.json", "r") as f:
    #     data = json.load(f)
    #     introductory_model = ChatOpenAI(model="gpt-4o").with_structured_output(
    #         GuideIntroMessage, include_raw=False, strict=True
    #     )

    #     human_message = HumanMessage(
    #         content=[
    #             {
    #                 "type": "text",
    #                 "text": f"Actions: {data}",
    #                 "text": f"User's tour description:{tour_description}",
    #             },
    #         ]
    #     )

    #     system_message = SystemMessage(
    #         content=[
    #             {
    #                 "type": "text",
    #                 "text": """
    #             Important rules:
    #             1. Avoid cookies or login-related actions in the output.
    #             2. Do not reference or hint at the input actions, steps, or user progress in the welcome message.
    #             3. Always conclude the text with an engaging question that asks them to they want a demo or not.
    #             5. Be clear, engaging, and universally relevant to new users, avoiding any reliance on context from the input actions.
    #             6. Use input user task description to create a compelling and engaging message.
    #             7. Do not exceed 7 seconds of reading time for the welcome message.

    #             You are a website demo agent welcoming new users. Your task is to create a generic and engaging introduction that conveys the core value of the platform and encourages exploration, regardless of any specific user actions or progress.

    #             Example input actions:
    #             [
    #                 "{\"id\":\"19\",\"xpath\":\"html/body/div[2]/div/div[4]/div/div[2]/div[2]/div[2]/div[3]/span/button\",\"text\":\"Click 'Continue' to proceed with the journey creation using the selected template.\",\"thought\":{\"memory\":\"Selected the basic customer journey template. Ready to proceed with adding evidence.\",\"next_goal\":\"Click 'Continue' to proceed with the journey creation using the selected template.\"}}",
    #                 "{\"id\":\"20\",\"xpath\":\"html/body/div[2]/div/div[4]/div/div[2]/div[2]/div[2]/div[2]/div/div/div/span/div/button\",\"text\":\"Click 'I want to add evidence' to proceed with adding evidence.\",\"thought\":{\"memory\":\"Journey creation started. Ready to add evidence.\",\"next_goal\":\"Click 'I want to add evidence' to proceed with adding evidence.\"}}"
    #             ]

    #             Example user task:
    #                 1. Create a journey with basic template.
    #                 2. Go back to the journey library.
    #                 3. Open sample journey. Navigate the opportunitites and go to matrix tab.
    #                 6. If you stuck in a loop. Finish the task.
    #                 6.  Done.
    #             """,
    #             }
    #         ]
    #     )

    #     msg = [system_message, human_message]
    #     intro_message = await introductory_model.ainvoke(msg)
    #     print("Response from the introductory model:", intro_message)


if __name__ == "__main__":
    asyncio.run(main())
