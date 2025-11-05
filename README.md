
# EngineeringTeam Crew

Welcome to the EngineeringTeam Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file**

- Modify `src/engineering_team/config/agents.yaml` to define your agents
- Modify `src/engineering_team/config/tasks.yaml` to define your tasks
- Modify `src/engineering_team/crew.py` to add your own logic, tools and specific args
- Modify `src/engineering_team/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command initializes the engineering_team Crew, assembling the agents and assigning them tasks as defined in your configuration.


## Understanding Your Crew

The engineering_team Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Running the Generated Code

The crewAI agents have generated a trading account demo application with a Gradio UI. To run the generated application:

1. Navigate to the output directory:ash
   cd output
   2. Run the application using uv:h
   uv run app.py
   3. The Gradio interface will launch and you can access it in your web browser. The application provides a trading account demo where you can:
   - Create an account with initial deposit
   - Deposit and withdraw cash
   - Buy and sell shares (AAPL, TSLA, GOOGL)
   - View account statements, holdings, and transaction history

![Generated UI Screenshot](Screenshot 2025-11-05 at 6.29.31 PM.png)
![Generated UI Screenshot](Screenshot 2025-11-05 at 6.29.50 PM.png)