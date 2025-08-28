"""
LangGraph Product Recommendation Agent with Memory
"""

from typing import List, Dict, Any, Optional, Sequence
from datetime import datetime
import json
import uuid

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI

from .config import config
from .tools.database_tools import DatabaseTools
from .memory import ConversationMemory, SessionManager
from .mission_control_agent import GraphState
# Removed custom tracing - using LangSmith directly


class ProductAgent:
    """
    LangGraph agent for product recommendations with memory
    """
    
    def __init__(self, tenant_id: str, session_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.session_id = session_id or str(uuid.uuid4())
        
        # Initialize tools - single unified search tool
        self.db_tools = DatabaseTools(tenant_id)
        self.search_tool = self.db_tools.get_traced_tool()  # Single search tool
        self.tools = [self.search_tool]
        self.tool_node = ToolNode(self.tools)
        
        # Initialize LLM with verbose logging
        self.llm = ChatOpenAI(
            model=config.openai_model,
            temperature=0.7,
            openai_api_key=config.openai_api_key,
            verbose=True  # Enable verbose logging for this LLM instance
        )
        
        # Initialize memory
        self.memory = ConversationMemory(self.session_id, tenant_id)
        self.session_manager = SessionManager()
        
        # Build the graph
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        # Define the graph
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("plan", self._plan_action)
        workflow.add_node("execute_tool", self._execute_tool)
        workflow.add_node("validate_results", self._validate_results)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("update_memory", self._update_memory)
        
        # Add edges
        workflow.set_entry_point("plan")
        
        # workflow.add_edge("retrieve_context", "plan")  # Context now handled by mission control
        
        workflow.add_conditional_edges(
            "plan",
            self._should_execute_tool,
            {
                "execute_tool": "execute_tool",
                "generate_response": "generate_response"
            }
        )
        
        workflow.add_edge("execute_tool", "validate_results")
        
        workflow.add_conditional_edges(
            "validate_results",
            self._should_continue_or_respond,
            {
                "continue": "plan",  # Loop back for more actions
                "respond": "generate_response"  # Generate final response
            }
        )
        workflow.add_edge("generate_response", "update_memory")
        workflow.add_edge("update_memory", END)
        
        # Add memory checkpointer for conversation persistence
        memory = MemorySaver()
        graph = workflow.compile(checkpointer=memory)
        
        # Set recursion limit (this is done differently in LangGraph)
        return graph
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for the agent"""
        return """You are an intelligent e-commerce product recommendation assistant.
        
Your role is to help users find products, answer questions about products, and make personalized recommendations.

## Your Capabilities:
1. Search products by specific criteria (type, price, vendor, discount)
2. Find products using natural language descriptions
3. Combine filters with semantic search for best results
4. Remember conversation context

## Guidelines:
- Be helpful and conversational
- Ask clarifying questions when search criteria are vague
- Explain why you're recommending certain products
- Present products in a clear, organized way
- Include key details: name, price, vendor, key features
- Suggest follow-up actions or related searches
"""
    
    
    def _plan_action(self, state: GraphState) -> GraphState:
        """Plan the next action based on current state"""
        print(f"🧠 STEP: plan_action - about to call LLM")
        
        # Create planning prompt using chat_messages (clean conversation history)
        # SystemMessage goes to internal_messages, not chat_messages
        messages = [
            SystemMessage(content=self._create_system_prompt()),
            *state.chat_messages  # Only user ↔ assistant conversation
        ]
        
        # Add context about current products if any
        # This SystemMessage is for LLM context only, NOT part of user conversation
        if state.current_products:
            context = f"Currently showing {len(state.current_products)} products."
            messages.append(SystemMessage(content=context))
        
        
        # Get LLM decision
        planning_prompt = f"""Based on the conversation, decide what action to take.

Available tool:
- search_products: Unified search that handles both filters and semantic queries

Analyze the user query and extract:
1. Filters (exact matches): product_type, vendor, min_price, max_price, has_discount, tags
2. Semantic query: Natural language description for similarity search
3. Number of results (k): Default 12

Examples:
- "Show me Nike shoes under $100" → {{"action": "search_products", "params": {{"filters": {{"vendor": "Nike", "product_type": "Shoes", "max_price": 100}}, "k": 12}}}}
- "Comfortable running shoes for marathon" → {{"action": "search_products", "params": {{"semantic_query": "comfortable running shoes for marathon", "k": 12}}}}
- "Red jackets on sale" → {{"action": "search_products", "params": {{"filters": {{"product_type": "Jackets", "has_discount": true}}, "semantic_query": "red", "k": 12}}}}

Respond with the tool call or 'respond' if ready to answer.
Format: {{"action": "search_products", "params": {{...}}}} or {{"action": "respond"}}
"""
        # This HumanMessage is for internal LLM prompting, NOT part of user conversation
        messages.append(HumanMessage(content=planning_prompt))
        
        # Add all LLM request messages to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + messages
        
        print(f"📞 CALLING LLM with {len(messages)} messages")
        print(f"📞 MESSAGES ARE:\n")
        for msg in messages:
            print(msg)
        response = self.llm.invoke(messages)
        print(f"📨 LLM RESPONSE: {response.content[:100]}...")
        
        # Add LLM response to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + [AIMessage(content=f"PLAN_ACTION_LLM_RESPONSE: {response.content}")]
        
        try:
            decision = json.loads(response.content)
            state.next_action = decision.get("action", "respond")
            
            if decision.get("params"):
                # Store parameters for tool execution
                state.tool_params = decision["params"]
            else:
                # Clear tool_params if no params provided
                state.tool_params = {}
            
            print(f"🎯 PARSED DECISION: action={state.next_action}, params={state.tool_params or {}}")
        except Exception as e:
            print(f"❌ JSON parsing failed: {e}, raw response: {response.content}")
            # Default to generating response if parsing fails
            state.next_action = "respond"
        
        return state
    
    def _should_execute_tool(self, state: GraphState) -> str:
        """Decide whether to execute a tool or generate response"""
        action = state.next_action or "respond"
        
        if action == "search_products":
            return "execute_tool"
        else:
            return "generate_response"
    
    def _should_continue_or_respond(self, state: GraphState) -> str:
        """Decide whether to continue searching or generate final response"""
        action = state.next_action or "respond"
        
        if action == "respond":
            return "respond"
        elif action == "search_products":
            return "continue"
        else:
            return "respond"
    
    def _execute_tool(self, state: GraphState) -> GraphState:
        """Execute the selected tool"""
        tool_name = state.next_action
        tool_params = state.tool_params or {}
        
        print(f"🛠️ STEP: execute_tool - tool: {tool_name}, params: {tool_params}")
        
        # Find the tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        
        print(f"🔍 Available tools: {[t.name for t in self.tools]}")
        print(f"🎯 Looking for tool: {tool_name}")
        print(f"✅ Tool found: {bool(tool)}")
        
        if tool:
            try:
                # Execute tool with proper parameter handling
                print(f"🔧 Executing {tool_name} with params: {tool_params}")
                
                if tool_name == "search_products":
                    # Extract parameters for search
                    filters = tool_params.get('filters', {})
                    semantic_query = tool_params.get('semantic_query', None)
                    k = tool_params.get('k', 12)
                    result = tool.func(filters=filters, semantic_query=semantic_query, k=k)
                else:
                    # Should not happen with single tool
                    result = []
                
                print(f"✅ Tool execution successful, got {len(result) if isinstance(result, list) else 1} results")
                
                # Store results
                if isinstance(result, list):
                    state.current_products = result
                
                # Add tool result to internal_messages (NOT chat_messages)
                # These are internal processing details, not part of user conversation
                result_message = SystemMessage(
                    content=f"Tool {tool_name} executed successfully. Result: {json.dumps(result, default=str)[:500]}..."
                )
                state.internal_messages = list(state.internal_messages) + [result_message]
                
            except Exception as e:
                # Handle tool execution errors - goes to internal_messages (NOT chat_messages)
                # Tool errors are internal processing details, not part of user conversation
                error_message = ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_name
                )
                state.internal_messages = list(state.internal_messages) + [error_message]
        
        return state
    
    def _validate_results(self, state: GraphState) -> GraphState:
        """Validate that results match user intent"""
        
        if not state.current_products:
            return state
        
        # Create validation prompt - get user query from chat_messages (clean conversation)
        user_query = state.chat_messages[0].content if state.chat_messages else ""
        products = state.current_products[:5]  # Validate top 5
        
        validation_prompt = f"""User asked: {user_query}

Found {len(state.current_products)} products. Here are the top 5:
{json.dumps(products, indent=2, default=str)}

Do these products match what the user is looking for? 
Rate the relevance (1-10) and explain if we should:
1. Show these results
2. Search again with different criteria
3. Ask for clarification

Response format: {{"relevance": 8, "action": "show", "reason": "..."}}
"""
        
        # These messages are for internal LLM validation, NOT part of user conversation
        messages = [
            SystemMessage(content="You are validating search results for relevance."),
            HumanMessage(content=validation_prompt)
        ]
        
        # Add all LLM request messages to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + messages
        
        response = self.llm.invoke(messages)
        
        # Add LLM response to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + [AIMessage(content=f"VALIDATE_RESULTS_LLM_RESPONSE: {response.content}")]
        
        try:
            validation = json.loads(response.content)
            
            if validation.get("relevance", 0) < 6:
                # Low relevance - need to search again or clarify
                if validation.get("action") == "clarify":
                    state.next_action = "respond"  # Ask for clarification
                else:
                    state.next_action = "search_again"
            else:
                # Good results - proceed to response
                state.next_action = "respond"
                
        except:
            # Default to showing results if validation fails
            state.next_action = "respond"
        
        return state
    
    def _generate_response(self, state: GraphState) -> GraphState:
        """Generate final response to user"""
        
        # Build context for response generation using clean chat history
        # SystemMessage is for LLM context, not part of conversation
        messages = [
            SystemMessage(content=self._create_system_prompt()),
            *state.chat_messages  # Only user ↔ assistant conversation
        ]
        
        # Add instruction for response format
        if state.current_products:
            products = state.current_products
            response_prompt = f"""Based on the search results, provide a helpful response to the user.

Found {len(products)} products matching their criteria.

Guidelines:
1. Summarize what you found
2. Highlight the top 3-5 most relevant products
3. Explain why each is a good match
4. Suggest follow-up actions (view details, find similar, refine search)
5. Be conversational and helpful

Products data:
{json.dumps(products[:5], indent=2, default=str)}
"""
        else:
            response_prompt = """Provide a helpful response to the user's question.
Be conversational and suggest how you can help them find products."""
        
        # This HumanMessage is for internal LLM prompting, NOT part of user conversation
        messages.append(HumanMessage(content=response_prompt))
        
        # Add all LLM request messages to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + messages
        
        response = self.llm.invoke(messages)
        state.final_answer = response.content
        
        # Add LLM response to internal_messages for debugging flow
        state.internal_messages = list(state.internal_messages) + [AIMessage(content=f"GENERATE_RESPONSE_LLM_RESPONSE: {response.content}")]
        
        # Add assistant response to chat_messages (this IS part of user conversation)
        # This is what the user will see as the bot's response
        state.chat_messages = list(state.chat_messages) + [AIMessage(content=response.content)]
        
        return state
    
    def _update_memory(self, state: GraphState) -> GraphState:
        """Update conversation memory and session data"""
        
        # Save conversation turn using chat_messages (clean conversation history)
        # Find the latest user message in chat_messages
        user_message = None
        for msg in reversed(state.chat_messages):
            if isinstance(msg, HumanMessage):
                user_message = msg
                break
        
        if user_message:
            self.memory.add_message(user_message.content, "user")
        
        # Save assistant response (final_answer) to memory
        if state.final_answer:
            self.memory.add_message(state.final_answer, "assistant")
        
        # Update session last active time
        self.session_manager.update_session(
            self.session_id,
            self.tenant_id,
            {"last_active": datetime.now().isoformat()}
        )
        
        return state
    
    async def chat(self, initial_state: GraphState) -> str:
        """
        Main chat interface - expects initial_state with context already loaded
        
        Args:
            initial_state: GraphState with messages including conversation history
            
        Returns:
            Agent's response
        """
        print(f"\n🤖 AGENT: Starting chat workflow with {len(initial_state.chat_messages)} chat messages and {len(initial_state.internal_messages)} internal messages")
        
        print(f"🔄 AGENT: Running LangGraph workflow...")
        
        # Run the graph with thread ID configuration and recursion limit
        config = {
            "configurable": {"thread_id": self.session_id},
            "recursion_limit": 50
        }
        final_state = await self.graph.ainvoke(initial_state, config)
        
        print(f"✅ AGENT: Workflow completed. Final answer exists: {bool(final_state.final_answer)}")
        
        # Print all internal messages to see the complete LLM interaction flow
        print(f"\n🔍 INTERNAL MESSAGE FLOW ({len(final_state.internal_messages)} messages):")
        print("=" * 80)
        for i, msg in enumerate(final_state.internal_messages, 1):
            msg_type = type(msg).__name__
            content_preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            print(f"{i:2d}. [{msg_type}] {content_preview}")
            print("-" * 40)
        print("=" * 80)
        
        return final_state.final_answer or "I'm sorry, I couldn't process your request."
    
    def reset_session(self):
        """Reset the conversation session"""
        self.session_id = str(uuid.uuid4())
        self.memory = ConversationMemory(self.session_id, self.tenant_id)
        self.session_manager.clear_session(self.session_id, self.tenant_id)