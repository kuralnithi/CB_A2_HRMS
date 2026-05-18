"""
Unified AI Router using LangGraph.
Classifies user intent and routes to the correct sub-agent:
  - POLICY_QA → Policy RAG Agent
  - SQL_QUERY → SQL Agent
  - HR_ACTION → HR Action Agent
  - UNKNOWN  → General response
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.llm import get_groq_llm
from app.services.ai.policy_rag import query_policy_rag
from app.services.ai.sql_agent import query_sql_agent
from app.services.ai.action_agent import execute_hr_action
from app.services.ai.permissions import check_permission, get_refusal_message

import json
import re

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for the NovaWorks HR Copilot.
Given a user message, classify the intent into ONE of these categories:

1. POLICY_QA - Questions about HR policies, rules, guidelines, procedures, company policies.
   Examples: "What is the leave policy?", "Can I work from home?", "How many sick leaves?"

2. SQL_QUERY - Questions about employees, projects, departments, skills, data lookups.
   Examples: "Which projects are ongoing?", "Who knows Python?", "Show my project assignments."

3. HR_ACTION - Requests to PERFORM an action (apply leave, create ticket, approve leave, etc.)
   Examples: "Apply sick leave for tomorrow", "Create a ticket for VPN issue", "Approve Rahul's leave"

4. UNKNOWN - Greetings, off-topic, unclear, or cannot be classified.
   Examples: "Hello", "What's the weather?", "Tell me a joke"

Return ONLY valid JSON:
{{"intent": "<INTENT>", "confidence": <0.0-1.0>, "reason": "<brief explanation>"}}
"""

ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", ROUTER_SYSTEM_PROMPT),
    ("human", "{message}")
])


async def classify_intent(message: str) -> dict:
    """Classify user message intent using a fast LLM (Groq)."""
    llm = get_groq_llm(temperature=0.0)
    chain = ROUTER_PROMPT | llm | StrOutputParser()
    raw = await chain.ainvoke({"message": message})

    try:
        cleaned = raw.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        result = json.loads(cleaned)
        return result
    except (json.JSONDecodeError, ValueError):
        return {"intent": "UNKNOWN", "confidence": 0.0, "reason": "Failed to parse intent"}


async def route_query(
    message: str,
    user_id: int,
    employee_id: int,
    role: str,
    access_token: str,
) -> dict:
    """
    Main entry point: classify intent → route to correct agent → return result.
    
    Returns:
        dict with 'intent', 'confidence', 'data' keys.
    """
    # Step 1: Classify intent
    intent_result = await classify_intent(message)
    intent = intent_result.get("intent", "UNKNOWN")
    confidence = intent_result.get("confidence", 0.0)

    # Step 2: Route to the correct agent
    if intent == "POLICY_QA":
        data = await query_policy_rag(message)
        return {
            "intent": intent,
            "confidence": confidence,
            "data": {
                "answer": data["answer"],
                "sources": data.get("sources", []),
            }
        }

    elif intent == "SQL_QUERY":
        # Check if this is a general "view all employees" query which is restricted for employees
        if role == "EMPLOYEE" and any(word in message.lower() for word in ["all employees", "everybody", "everyone", "department", "list employees"]):
            return {
                "intent": intent,
                "confidence": confidence,
                "data": {
                    "answer": get_refusal_message("view_all_employees"),
                    "sql": None,
                    "rows": [],
                }
            }
            
        data = await query_sql_agent(message, user_id, employee_id, role)
        return {
            "intent": intent,
            "confidence": confidence,
            "data": {
                "answer": data["answer"],
                "sql": data.get("sql"),
                "rows": data.get("rows", []),
            }
        }

    elif intent == "HR_ACTION":
        data = await execute_hr_action(message, user_id, employee_id, role, access_token)
        return {
            "intent": intent,
            "confidence": confidence,
            "data": {
                "answer": data["answer"],
                "action": data.get("action"),
                "result": data.get("result"),
            }
        }

    else:
        return {
            "intent": "UNKNOWN",
            "confidence": confidence,
            "data": {
                "answer": "I'm the NovaWorks HR Copilot. I can help you with:\n\n"
                          "📋 **HR Policies** — Ask about leave, remote work, expenses, or code of conduct.\n"
                          "🔍 **HR Data** — Look up employees, projects, departments, and skills.\n"
                          "⚡ **HR Actions** — Apply for leave, create tickets, and more.\n\n"
                          "How can I help you today?",
            }
        }
