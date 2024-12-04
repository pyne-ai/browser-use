import json
import os
import sys



sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, field_validator, validator

from browser_use.agent.service import Agent
from browser_use.agent.views import AgentHistoryList

from browser_use.controller.service import Controller

supabase_key = os.environ.get("SUPABASE_KEY")
supabase_url = os.environ.get("SUPABASE_URL")


# Initialize controller first
controller = Controller()

class Step(BaseModel):
    description: str
    xpath: str
    step_type: Optional[str]  # Allow it to be optional

    @field_validator("step_type")
    def set_default_step_type(cls, value):
        return value or "userClick"


class Section(BaseModel):
    section_name: str
    steps: List[Step]


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
    link: str = 'https://theydo.com'

class UserLogin(BaseModel):
    username: str = 'berkant+auto2@pyne.ai'
    password: str = 'Password!123'


@controller.action('Go to the webpage', param_model=WebpageInfo)
def go_to_webpage(webpage_info: WebpageInfo):
    return webpage_info.link

@controller.action('Signin/login to website', param_model=UserLogin)
def login(user: UserLogin):
    print("Logging in with username:", user.username)
    return user.model_dump_json()



# video: https://preview.screen.studio/share/EtOhIk0P
async def main():    
    #todo: This task should be well defined
    task = '''
                IMPORTANT RULES:
                    - If task requires login use action 'login' to login to the website.
                    - If you face with any trial limit error popup, close it.
                    - If you cannot proceed on login page, you must use action 'perform_logic'.
                    
                1. Create a journey with basic template.
                2.  Use sample transcript as the evidence for the journey mapping. Add evidence to the journey. Pick template.
                3.  Go to journeys again. Open [AI] Sample Journey. Display opportunity matrix and adjust the scoring for customer and business value.
                4.  When you open the opportunity matrix, if face with placeholder or empty state. Use action 'load_checkpoint' to go back to the latest successful url. And try sample journey again until you see the opportunity matrix that has data.
                5.  Go back to the journey library.
                6. Done.
        '''
        
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(task=task, llm=model, controller=controller)

    history : AgentHistoryList = await agent.run()
    
    
    history_path = 'history.json'
    agent.save_history(file_path=history_path)

    thoughts_str = ""
    for i,t in enumerate(history.successful_actions()):
        thoughts_str += f"{i}. Intention was:{t.text}: \n Clicked element xpath was: {t.xpath}\n Memory: {t.thought.memory}\n Next goal: {t.thought.next_goal}\n"
    

    messages = [("system", 
                 """
                 You are a website agent click analyzer. Use the following actions to analyze the website and provide me a summary of the actions, mapping Xpaths of the actions taken on the website in the summary you will provide. 
                 Do not hallucinate or make up actions which the user did not ask for, and keep the flow of the actions in logical order derived from the thoughts. 
                 Do not include anything related with login and cookie settings in the output.
                 """),
                ("human", f"Here are successful actions taken along with the xpath selectors:{thoughts_str}")]
    
    summarizer_model = ChatOpenAI(model='gpt-4o').with_structured_output(ActionSummaryList, include_raw=False, strict=True)
    
    
    response = summarizer_model.invoke(messages)
    structured_output = ActionSummaryList.model_validate(response)
    
    print("Response:", structured_output.model_dump_json())
    

if __name__ == '__main__':
    asyncio.run(main())
