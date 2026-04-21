# agent_brain.py
# NOTE: This module is not used by the main CLI features.
# It is kept as a standalone Groq-powered agent for future use.
# Replaces ChatOllama (requires local Ollama server) with ChatGroq (cloud-based, no server needed).

import os
from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from tools.app_manager import install_application

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# 1. LLM Setup (Groq - Llama3.1 via API)
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=GROQ_API_KEY or None)

# 2. Tools List
tools = [install_application]

# 3. Prompt Template (System Prompt)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an advanced AI Agent named 'ALOA' capable of executing system commands. "
               "You have access to tools to install software. "
               "If a user asks to install something, use the install_application tool. "
               "Speak in Hinglish (Hindi + English mix)."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 4. Bind Tools to LLM
agent = create_tool_calling_agent(llm, tools, prompt)

# 5. Create Executor
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

def chat_with_aloa(user_input):
    response = agent_executor.invoke({"input": user_input})
    return response['output']