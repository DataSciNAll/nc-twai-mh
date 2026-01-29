"""Run safety evaluations on AI Foundry agent using adversarial simulator (SDK v1)."""

import os
import json
import asyncio
import logging
from pathlib import Path
from pprint import pprint

import pandas as pd
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, AzureDeveloperCliCredential
from azure.ai.evaluation import ContentSafetyEvaluator, evaluate
from azure.ai.evaluation.simulator import (
    AdversarialScenario,
    AdversarialSimulator,
    SupportedLanguages,
)
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder

# Setup logging
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("safety_eval")
logger.setLevel(logging.INFO)

# Load environment from azd
azure_dir = Path(__file__).parent.parent / ".azure"
env_name = os.environ.get("AZURE_ENV_NAME", "")
if not env_name and (azure_dir / "config.json").exists():
    with open(azure_dir / "config.json") as f:
        config = json.load(f)
        env_name = config.get("defaultEnvironment", "")

env_path = azure_dir / env_name / ".env"
if env_path.exists():
    load_dotenv(env_path)

OUTPUT_DIR = Path(__file__).parent.parent / "evals" / "safety_results"


def get_azure_credential():
    """Get Azure credential for evaluation."""
    tenant_id = os.getenv("AZURE_TENANT_ID")
    if tenant_id:
        return AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
    return AzureDeveloperCliCredential(process_timeout=60)


def get_agents_client():
    """Create AI Agents client."""
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    return AgentsClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )


def call_agent(question: str) -> str:
    """Call the agent and return response."""
    agents_client = get_agents_client()
    agent_id = os.environ.get("AZURE_AGENT_ID")
    
    if not agent_id:
        return "Error: AZURE_AGENT_ID not set"
    
    try:
        thread = agents_client.threads.create()
        
        agents_client.messages.create(
            thread_id=thread.id,
            role="user",
            content=question
        )
        
        run = agents_client.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_id,
        )
        
        messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        
        for msg in messages:
            if msg.role == "assistant" and msg.text_messages:
                return msg.text_messages[-1].text.value
        
        return "No response"
        
    except Exception as e:
        logger.error(f"Error calling agent: {e}")
        return f"Error: {str(e)}"


async def callback(
    messages: list[dict],
    stream: bool = False,
    session_state=None,
    context=None,
):
    """Callback function for adversarial simulator that calls the agent."""
    messages_list = messages["messages"]
    latest_message = messages_list[-1]
    query = latest_message["content"]
    
    try:
        response_text = call_agent(query)
        message = {"content": response_text, "role": "assistant"}
        
        return {
            "messages": messages_list + [message]
        }
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return {
            "messages": messages_list + [{"content": f"Error: {str(e)}", "role": "assistant"}]
        }


async def run_simulator(max_simulations: int):
    """Run adversarial simulator and save outputs."""
    credential = get_azure_credential()
    azure_ai_project = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    
    scenario = AdversarialScenario.ADVERSARIAL_QA
    adversarial_simulator = AdversarialSimulator(
        azure_ai_project=azure_ai_project,
        credential=credential
    )
    
    logger.info(f"Running adversarial simulation with {max_simulations} max simulations...")
    
    outputs = await adversarial_simulator(
        scenario=scenario,
        target=callback,
        max_simulation_results=max_simulations,
        language=SupportedLanguages.English,
        randomization_seed=1,
    )
    
    # Save simulation outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    simulation_data_path = OUTPUT_DIR / "simulation_data_v1.jsonl"
    
    logger.info(f"Saving {len(outputs)} simulation outputs...")
    valid_outputs = 0
    
    with open(simulation_data_path, "w") as f:
        for output in outputs:
            if "messages" not in output or len(output["messages"]) < 2:
                continue
            
            query = output["messages"][0]["content"]
            response = output["messages"][1]["content"]
            
            if not response:
                continue
            
            f.write(json.dumps({"query": query, "response": response}) + "\n")
            valid_outputs += 1
    
    logger.info(f"Saved {valid_outputs} valid outputs")
    return azure_ai_project, str(simulation_data_path), valid_outputs


def run_safety_evaluation(azure_ai_project: str, data_path: str, num_simulations: int):
    """Run safety evaluation."""
    if num_simulations == 0:
        logger.error("No valid simulation outputs to evaluate.")
        return
    
    credential = get_azure_credential()
    
    safety_evaluator = ContentSafetyEvaluator(
        credential=credential,
        azure_ai_project=azure_ai_project
    )
    
    logger.info(f"\nStarting safety evaluation...")
    logger.info(f"  Data file: {data_path}")
    logger.info(f"  Simulations: {num_simulations}")
    
    result = evaluate(
        data=data_path,
        evaluators={"safety": safety_evaluator},
        evaluator_config={
            "safety": {
                "column_mapping": {
                    "query": "${data.query}",
                    "response": "${data.response}"
                }
            }
        },
        azure_ai_project=azure_ai_project,
        evaluation_name="safety_evaluation_agent_v1",
        output_path=str(OUTPUT_DIR / "safety_results_v1.jsonl")
    )
    
    # Display results
    tabular_result = pd.DataFrame(result.get("rows"))
    
    print("\n" + "=" * 50)
    print("--- Summarized Metrics ---")
    pprint(result["metrics"])
    print("\n--- Results Preview ---")
    print(tabular_result.head())
    print("\n--- Evaluation Complete ---")
    print(f"Results saved to: {OUTPUT_DIR / 'safety_results_v1.jsonl'}")
    
    if "studio_url" in result:
        print(f"\nView results in AI Foundry:")
        print(f"  {result['studio_url']}")
    
    print("=" * 50)
    
    # Save summary
    with open(OUTPUT_DIR / "safety_summary_v1.json", "w") as f:
        json.dump(result["metrics"], f, indent=2)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run safety evaluation on agent (SDK v1)")
    parser.add_argument("--max_simulations", type=int, default=25, help="Max adversarial simulations")
    args = parser.parse_args()
    
    # Verify agent ID
    agent_id = os.environ.get("AZURE_AGENT_ID")
    if not agent_id:
        print("Error: AZURE_AGENT_ID not set. Run 04_create_agent_v1.py first.")
        exit(1)
    
    print(f"Running safety evaluation on agent: {agent_id}")
    
    # Run simulation
    azure_ai_project, data_path, num_simulations = asyncio.run(
        run_simulator(args.max_simulations)
    )
    
    # Run evaluation
    run_safety_evaluation(azure_ai_project, data_path, num_simulations)
