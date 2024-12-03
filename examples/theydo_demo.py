import json
import os
import sys



sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

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
    next_goal: str


class ActionSummary(BaseModel):
    name: str
    steps: List[Step]
    
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
    username: str = 'berkant+buse@pyne.ai'
    password: str = 'Password!123'


class Checkpoint(BaseModel):
    url: str
    state_file: str = "checkpoint.json"

    def save_checkpoint(self):
        """Save the current state to a file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump({"url": self.url}, f)
            print(f"Checkpoint saved at: {self.url}")
        except Exception as e:
            print(f"Failed to save checkpoint: {e}")

    @classmethod
    def load_checkpoint(cls):
        """Load the saved state from a file."""
        try:
            if os.path.exists(cls.state_file):
                with open(cls.state_file, "r") as f:
                    data = json.load(f)
                    return cls(url=data.get("url", ""))
            else:
                print("No checkpoint file found. Starting fresh.")
                return None
        except Exception as e:
            print(f"Failed to load checkpoint: {e}")
            return None
        

@controller.action('Go to the webpage', param_model=WebpageInfo)
def go_to_webpage(webpage_info: WebpageInfo):
    return webpage_info.link

@controller.action('Signin/login to website', param_model=UserLogin)
def login(user: UserLogin):
    print("Logging in with username:", user.username)
    return user.model_dump_json()

@controller.action('Save checkpoint', param_model=Checkpoint)
def save_checkpoint(ckpt: Checkpoint):
    print("Saving checkpoint...")
    ckpt.save_checkpoint()
    return f"Checkpoint saved at {ckpt.url}"
        
@controller.action('Load checkpoint', param_model=Checkpoint)
def load_checkpoint(ckpt: Checkpoint):
    return f"Loaded checkpoint from {ckpt.url}"


# video: https://preview.screen.studio/share/EtOhIk0P
async def main():    
    #todo: This task should be well defined
    task = '''
                IMPORTANT RULES:
                    - If task requires logn use action 'login' to login to the website.
                    - If you face with any trial limit error popup, close it.
                    - Define checkpoints where you can maintain same the state of the website. If you
                    - DO NOT interact with customer support widgets in website.
                    - On each successful action, call action 'save_checkpoint' save the checkpoint.
                    - If you cannot see next step in the website, call action 'load_checkpoint' and go to gathered checkpoint.
                    
                1. Create a journey with basic template.
                2.  Use sample tranctript as the evidence for the journey mapping. If you fail interacting with the evidence skip this step.
                3.  Open AI sample journey. Display opportunity matrix and adjust the scoring for customer and business value.
                4.  Go back to the journey library.
                5. Done.
        '''
        
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(task=task, llm=model, controller=controller)

    history : AgentHistoryList = await agent.run()
    history_path = 'history.json'
    agent.save_history(file_path=history_path)
    
    
    thoughts_str = ""
    for i,t in enumerate(history.successful_actions()):
        thoughts_str += f"{i}. Intention was:{t.text}: \n Clicked element xpath was: {t.xpath}\n Memory: {t.thought.memory}\n Next goal: {t.thought.next_goal}\n\n"
    

    messages = [("system", "You are a website agent click analyzer. Use the following actions to analyze the website and provide me a summary of the actions, mapping Xpaths of the actions taken on the website in the summary you will provide, do not hallucinate or make up actions which the user did not ask for, and keep the flow of the actions in logical order derived from the thoughts."),
                ("human", f"Here are successful actions taken along with the xpath selectors:{thoughts_str}")]
    
    summarizer_model = ChatOpenAI(model='gpt-4o').with_structured_output(ActionSummaryList, include_raw=False, strict=True)
    
    
    
    

    response = summarizer_model.invoke(messages)
    print("Response:", response)
    
    

if __name__ == '__main__':
    asyncio.run(main())
