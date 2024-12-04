import json
import os
import sys

from postprocess.otc.service import OTCAgent



sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from browser_use.agent.service import Agent
from browser_use.agent.views import AgentHistoryList

from browser_use.controller.service import Controller


# Initialize controller first
controller = Controller()


class LoginInfo(BaseModel):
    username: str
    password: str


class WebpageInfo(BaseModel):
    link: str = 'https://theydo.com'


@controller.action('Go to the webpage', param_model=WebpageInfo)
def go_to_webpage(webpage_info: WebpageInfo):
    print("Opening the webpage...")
    return webpage_info.link


# video: https://preview.screen.studio/share/EtOhIk0P
async def main():
    task = '''
    0. Signin with username: berkant+123@pyne.ai, password: Password!123
    1. Start a journey.
    2. Check the templates.
    3. Select the "Basic customer journey" template.
    4. Click "Continue".
    5. Upload the research (e.g., transcript, stickies, or sample transcript).
    6. Initiate AI mapping.
    7. Open the journey library.
    8. Click on a pre-populated sample journey.
    9. Hover over an opportunity box.
    11. Click on an example opportunity.
    12. Adjust scoring for customer and business value.
    13. Switch to the opportunity list view.
    14. Open the opportunity matrix.
    15. Go back to the journey library.
    16. Click into the AI-generated journey.
    '''

    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(task=task, llm=model, controller=controller)
    otc_agent = OTCAgent(llm=model)
 
    history : AgentHistoryList = await agent.run()
    history_path = 'history.json'
    agent.save_history(file_path=history_path)
    
    
    # history_content = json.load(open(history_path))
    # history = AgentHistoryList.model_validate(history_content)
    # print("History content:", type(history_content))
 
    for i, h in enumerate(history.history):
        print("State was:", h.state.title)
        print("On track condition URL:", h.state.url) 
        await otc_agent.process(h.state.url)
        if h.state.interacted_element:
            print("Clicked element", h.state.interacted_element.xpath)

        
    

if __name__ == '__main__':
    asyncio.run(main())
