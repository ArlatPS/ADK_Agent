from google.adk.runners import Runner
from google.adk.plugins.logging_plugin import (
    LoggingPlugin,
) 
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import root_agent
from typing import Union, List
import os

if not os.getenv('GOOGLE_API_KEY'):
    raise ValueError("Please set GOOGLE_API_KEY environment variable")

async def run_session(
    runner_instance: Runner,
    user_queries: Union[List[str], str] = None,
    user_id: str = 'default',
    session_name: str = "default",
):
    print(f"\n ### Session: {session_name}")

    app_name = runner_instance.app_name

    try:
        session = await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_name
        )
    except:
        session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_name
        )

    if user_queries:
        if type(user_queries) == str:
            user_queries = [user_queries]

        for query in user_queries:
            print(f"\nUser > {query}")

            query = types.Content(role="user", parts=[types.Part(text=query)])

            async for event in runner_instance.run_async(
                user_id=user_id, session_id=session.id, new_message=query
            ):
                if event.content and event.content.parts:
                    if (
                        event.content.parts[0].text != "None"
                        and event.content.parts[0].text
                    ):
                        print(f"Gemini > ", event.content.parts[0].text)
    else:
        print("No queries!")

session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name="NewSportAgentApp",
    plugins=[LoggingPlugin()],
    session_service=session_service
)

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Running example - multiple messages in a single session
        await run_session(
            runner,
            [
                "I want to start running",
                "Trail running, for ultra event 50km + 5000 elevation",
                "Currently I don't run, but I have large mountaineering experience"
            ],
            "user_0",
            "session_0"
        )

        # Cycling example - multiple messages in the same interrupted session
        await run_session(
            runner,
            "I want to start cycling",
            "user_1",
            "session_1"
        )

        await run_session(
            runner,
            "I am interested in time trial events, currently I ride 200km per week",
            "user_1",
            "session_1"
        )
    
    asyncio.run(main())
