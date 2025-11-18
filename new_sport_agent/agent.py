from google.adk.agents import Agent, ParallelAgent, BaseAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.genai import types
from google.adk.tools import AgentTool, FunctionTool, google_search
import secrets
import logging

logger = logging.getLogger(__name__)

retry_config=types.HttpRetryOptions(
    attempts=3,  
    exp_base=7,  
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

model = Gemini(
    model='gemini-2.5-flash',
    retry_options=retry_config
)

sport_research_agent = Agent(
    model=model,
    name='SportResearchAgent',
    output_key='sport_research_findings',
    description='An agent that researches important information about a sport, including athlete requirements and necessary gear.',
    instruction="""
        You are an expert researcher for sports. Your task is to gather detailed information by using google_search tool about the specified sport, focusing on:
        1. Athlete requirements: physical and skill requirements needed to participate in the sport.
        2. Necessary gear: a comprehensive list of equipment and gear needed to start practicing the sport.
        Provide your findings in a clear and organized manner.
    """,
    tools=[google_search]
)

gear_summarize_agent = Agent(
    model=model,
    name='GearSummarizeAgent',
    output_key='gear_list',
    description='An agent that summarizes and lists the necessary gear for a sport based on research findings.',
    instruction="""
        You are an expert in sports gear. Your task is to summarize and create a comprehensive list of necessary gear based on the research findings provided about the sport.
        Be specific about each item, so do not list general term like "clothing" but instead specify items like "running vest", etc.
        Ensure that the list is clear, organized, and includes all essential items needed to start practicing the sport.
        Return the necessary gear and up to 3 optional items.
        Expected output MUST BE a comma-separated list of gear item names only, without descriptions or additional text.
    """
)

class GearRecommendationWorker(BaseAgent):
    """Worker that finds recommendations for a single gear item."""
    def __init__(self, *, name: str, run_id: str, gear_item: str):
        super().__init__(name=name)
        self._run_id = run_id
        self._gear_item = gear_item
        logger.info(f"Initialized GearRecommendationWorker: name={name}, run_id={run_id}, gear_item={gear_item}")
    
    async def _run_async_impl(self, ctx):
        from google.adk.events import Event, EventActions
        
        logger.info(f"[{self.name}] Starting recommendation search for: {self._gear_item}")
        
        item_name = self._gear_item

        logger.info(f"[{self.name}] Creating agent for gear item: {item_name}")
        agent = Agent(
            model=model,
            name=f'{self.name}_agent',
            description=f'Recommends products for {item_name}',
            instruction=f"""
                You are an expert in sports gear recommendations. 
                The gear item you need to recommend is: "{item_name}". Recommend products only for this item.
                For this gear item, perform research using google_search and suggest 3 specific products, 
                including their names, brief descriptions, and estimated prices.
                Provide links to purchase if possible.
                Ensure recommendations are suitable for beginners.
                Provide your response in a clear format.
            """,
            tools=[google_search]
        )
        
        logger.info(f"[{self.name}] Running agent to get recommendations...")
        recommendation_text = ""
        async for event in agent.run_async(ctx):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        recommendation_text += part.text
            yield event
        
        logger.info(f"[{self.name}] Completed recommendations for {item_name}. Text: {recommendation_text[:300]}")
        
        state_key = f"recommendation:{self._run_id}:{self.name}"
        logger.info(f"[{self.name}] Storing result in session state with key: {state_key}")
        
        yield Event(
            author=self.name,
            content=types.Content(
                role=self.name,
                parts=[types.Part(text=f"Recommendations for {item_name}: {recommendation_text}")]
            ),
            actions=EventActions(
                state_delta={state_key: recommendation_text}
            )
        )
        
        logger.info(f"[{self.name}] GearRecommendationWorker completed successfully")

class GearRecommendationCoordinator(BaseAgent):
    """Coordinates parallel gear recommendations for multiple items."""
    
    async def _run_async_impl(self, ctx):
        from google.adk.events import Event, EventActions
        
        gear_list_str = ctx.session.state.get('gear_list', '')
        
        logger.info(f"[GearRecommendationCoordinator] Retrieved gear_list from state: {gear_list_str[:200]}...")
        
        if not gear_list_str:
            yield Event(
                author=self.name,
                content=types.Content(
                    role=self.name,
                    parts=[types.Part(text="No gear items found to make recommendations for.")]
                ),
                actions=EventActions(escalate=True)
            )
            return
        
        gear_items = [item.strip() for item in gear_list_str.split('\n') if item.strip()]
        
        if len(gear_items) <= 1:
            gear_items = [item.strip() for item in gear_list_str.split(',')]
        
        gear_items = [item for item in gear_items if item and (item[0].isupper() or item[0].isdigit())]
        
        logger.info(f"[GearRecommendationCoordinator] Parsed {len(gear_items)} gear items: {gear_items}")
        
        gear_items = gear_items[:3]
        
        logger.info(f"[GearRecommendationCoordinator] Processing first 3 items: {gear_items}")
        
        run_id = secrets.token_hex(2)
        
        state_delta = {"current_recommendation_run": run_id}
        
        yield Event(
            author=self.name,
            content=types.Content(
                role=self.name,
                parts=[types.Part(text=f"Finding recommendations for {len(gear_items)} gear items in parallel: {', '.join(gear_items)}")]
            ),
            actions=EventActions(state_delta=state_delta)
        )
        
        workers = [
            GearRecommendationWorker(
                name=f'GearRec_{idx}',
                run_id=run_id,
                gear_item=item_name
            )
            for idx, item_name in enumerate(gear_items)
        ]
        
        parallel = ParallelAgent(
            name=f'ParallelGearRecs_{run_id}',
            sub_agents=workers
        )
        
        async for event in parallel.run_async(ctx):
            yield event
        
        logger.info(f"[GearRecommendationCoordinator] Parallel execution completed")
        
        recommendations = []
        for idx in range(len(gear_items)):
            rec_key = f"recommendation:{run_id}:GearRec_{idx}"
            rec_text = ctx.session.state.get(rec_key, "")
            if rec_text:
                recommendations.append(rec_text)
        
        all_recs = "\n\n".join(recommendations)
        logger.info(f"[GearRecommendationCoordinator] Collected {len(recommendations)} recommendations")
        
        yield Event(
            author=self.name,
            content=types.Content(
                role=self.name,
                parts=[types.Part(text=f"Completed all gear recommendations:\n\n{all_recs}")]
            ),
            actions=EventActions(escalate=True)
        )

sport_workflow_agent = SequentialAgent(
    name='SportWorkflowAgent',
    sub_agents=[
        sport_research_agent,
        gear_summarize_agent,
        GearRecommendationCoordinator(name='GearRecommendationCoordinator')
    ]
)

root_agent = Agent(
    model=model,
    name='root_agent',
    description='A conversational assistant that helps users get into new sports by gathering requirements and providing detailed guidance.',
    instruction="""
        You are a friendly and knowledgeable assistant helping users get into new sports.
        
        When a user expresses interest in a sport (e.g., "I want to start running"), you should:
        
        1. FIRST, ask clarifying questions to understand their needs better. DO NOT immediately call any tools. Ask questions like:
           - What type of [sport] are they interested in? (e.g., road running, trail running, marathon training)
           - Do they have any prior experience with endurance sports or similar activities?
           - What are their goals? (e.g., fitness, competition, social, weight loss)
           - What is their current fitness level?
           - Are there any constraints? (e.g., budget, time, injuries)
        
        2. ONLY AFTER gathering sufficient information from the user, call the 'SportWorkflowAgent' tool with a detailed description including:
           - The specific type of sport they want to do
           - Their experience level
           - Their goals
           - Any relevant constraints
        
        3. After the SportWorkflowAgent completes, provide a final personalized summary to the user based on:
           - The research findings
           - The gear recommendations - make sure you list the gear items clearly and if 'SportWorkflowAgent' provided links to purchase, include those as well. Pick the best option based on user answers and recommend it.
           - Their specific goals and constraints
        
        Be conversational and helpful. Don't overwhelm the user with too many questions at once - ask up to 2 key questions first.
    """,
    tools=[AgentTool(sport_workflow_agent)]
)

