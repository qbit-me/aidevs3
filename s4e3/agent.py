import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional

from agent_tools import AgentTool


@dataclass
class ContextEntry:
    """Represents a single context entry from tool execution"""
    tool_name: str
    step_description: str
    parameters: Dict[str, Any]
    result: Any
    timestamp: datetime
    related_info: Dict[str, Any]


class Agent:
    """Agent that can understand tasks and execute tools"""

    def __init__(self, available_tools: List[AgentTool], llm_service):
        """
        Initialize the agent with tools and LLM service

        Args:
            available_tools (List[AgentTool]): List of tools available to the agent
            llm_service: OpenAiService instance for LLM interactions
        """
        self.tools = {tool.name: tool for tool in available_tools}
        self.llm_service = llm_service
        self.memory = {}
        self.context_history: List[ContextEntry] = []
        self.current_task: Optional[str] = None

    async def run(self, task_description: str) -> Any:
        """
        Main entry point for task execution. Creates execution plan and handles the execution flow.

        Args:
            task_description (str): Description of the task to perform

        Returns:
            Any: Result of the task execution

        Raises:
            Exception: If task execution fails
        """
        self.current_task = task_description
        try:
            # Create execution plan
            execution_plan = await self.plan(task_description)

            # Execute each step in the plan
            for step in execution_plan['plan']:
                result = await self.execute(step)

                # Create structured context entry
                context_entry = ContextEntry(
                    tool_name=step['tool_name'],
                    step_description=step['step'],
                    parameters=step['parameters'],
                    result=result,
                    timestamp=datetime.now(),
                    related_info={}
                )

                # Extract information and update related info
                if result:
                    extracted_info = await self._extract_information(
                        result,
                        execution_plan['required_information']
                    )
                    context_entry.related_info = extracted_info

                self.context_history.append(context_entry)

            return self.memory

        except Exception as e:
            print(f"Error executing task: {e}")
            raise

    async def plan(self, task_description: str) -> Dict[str, Any]:
        """
        Creates a multi-step execution plan for the given task.

        Args:
            task_description (str): Description of the task to perform

        Returns:
            dict: Contains execution plan with steps and required information
        """
        # Format context history for the prompt
        formatted_context = self._format_context_for_prompt()

        prompt = f"""Given the following task description, create a plan of actions and determine which tools to use.
        Available tools:
        {self._format_tools_for_prompt()}
        
        Task description: {task_description}
        
        Context History:
        {formatted_context}
        
        Previous findings: {self.memory}
        
        <rules>
        1. Keep any placeholders in the format [[PLACEHOLDER_NAME]] exactly as they are - do not modify or replace them.
        2. Consider the context history when planning next steps to avoid redundant operations.
        </rules>
        
        Respond in the following JSON format:
        {{
            "_thinking": "Describe your thought process here about how you're approaching this task, what considerations you're making, and why you're choosing specific steps",
            "plan": [
                {{
                    "step": "description of the step",
                    "tool_name": "name of the tool to use", 
                    "parameters": {{
                        parameters to pass to the tool
                    }}
                }}
            ],
            "required_information": [
                "list of information we need to extract to complete the task"
            ]
        }}
        """
        # print(prompt)

        response = await self.llm_service.completion(
            messages=[
                {"role": "system", "content": prompt},
            ],
            response_format={"type": "json_object"}
        )

        print(response.choices[0].message.content)

        try:
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            raise ValueError(f"Failed to parse LLM response: {e}")

    async def execute(self, step: Dict[str, Any]) -> Any:
        """
        Executes a single step from the execution plan.

        Args:
            step (dict): Step information containing tool_name and parameters

        Returns:
            Any: Result of the tool execution
        """
        tool_name = step['tool_name']
        parameters = step['parameters']

        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]
        return tool.execute(parameters)

    def _format_context_for_prompt(self) -> str:
        """Formats the context history into a readable string for the prompt"""
        if not self.context_history:
            return "No previous context available."

        context_entries = []
        for entry in self.context_history:
            context_str = (
                f"Step: {entry.step_description}\n"
                f"Tool Used: {entry.tool_name}\n"
                f"Parameters: {json.dumps(entry.parameters, indent=2)}\n"
                f"Related Information: {json.dumps(entry.related_info, indent=2)}\n"
                f"Timestamp: {entry.timestamp.isoformat()}\n"
                "---"
            )
            context_entries.append(context_str)

        return "\n".join(context_entries)

    async def _extract_information(self, content: Any, required_info: List[str]) -> Dict[str, Any]:
        """Extract specific information from content and return it"""
        prompt = f"""
        From the following content, extract information about: {required_info}
        
        Content: {content}
        
        Respond with only the relevant information in JSON format.
        """

        response = await self.llm_service.completion(
            messages=[
                {"role": "system", "content": prompt},
            ],
            response_format={"type": "json_object"}
        )

        extracted_info = json.loads(response.choices[0].message.content)
        self.memory.update(extracted_info)
        return extracted_info

    def _format_tools_for_prompt(self) -> str:
        """Formats the available tools into a string for the prompt"""
        tool_descriptions = []
        for tool in self.tools.values():
            desc = f"Tool: {tool.name}\n"
            desc += f"Description: {tool.description}\n"
            desc += "Required parameters:\n"
            for param, param_desc in tool.required_params.items():
                desc += f"- {param}: {param_desc}\n"
            if hasattr(tool, 'optional_params'):
                desc += "Optional parameters:\n"
                for param, param_desc in tool.optional_params.items():
                    desc += f"- {param}: {param_desc}\n"
            tool_descriptions.append(desc)
        return "\n".join(tool_descriptions)
