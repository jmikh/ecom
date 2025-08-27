"""
LangGraph Product Recommendation Agent with Memory
"""

from typing import TypedDict, List, Dict, Any, Optional, Sequence
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
# Removed custom tracing - using LangSmith directly


class AgentState(TypedDict):
    """State schema for the agent"""
    messages: Sequence[BaseMessage]
    session_id: str
    tenant_id: str
    user_context: Dict[str, Any]  # User preferences, previously viewed products, etc.
    current_products: List[Dict[str, Any]]  # Products being discussed
    search_history: List[Dict[str, Any]]  # Previous searches in session
    next_action: Optional[str]  # Next action to take
    tool_params: Optional[Dict[str, Any]]  # Parameters for tool execution
    final_answer: Optional[str]  # Final response to user


class ProductAgent:
    """
    LangGraph agent for product recommendations with memory
    """
    
    def __init__(self, tenant_id: str, session_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.session_id = session_id or str(uuid.uuid4())
        
        # Initialize tools - use traced tools for better LangSmith visibility
        self.db_tools = DatabaseTools(tenant_id)
        self.tools = self.db_tools.get_traced_tools()  # Use @tool decorated versions
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
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("plan", self._plan_action)
        workflow.add_node("execute_tool", self._execute_tool)
        workflow.add_node("validate_results", self._validate_results)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("update_memory", self._update_memory)
        
        # Add edges
        workflow.set_entry_point("retrieve_context")
        
        workflow.add_edge("retrieve_context", "plan")
        
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
        schema_info = self.db_tools.get_schema_info()
        
        return f"""You are an intelligent e-commerce product recommendation assistant.
        
Your role is to help users find products, answer questions about products, and make personalized recommendations.

## Available Information:
- Total products: {schema_info['total_products']}
- Product types: {', '.join(schema_info['product_types'][:10])}...
- Vendors: {', '.join(schema_info['vendors'][:10])}...
- Price range: ${schema_info['price_range']['min']:.2f} - ${schema_info['price_range']['max']:.2f}
- Options available: {', '.join(schema_info['available_options'])}

## Your Capabilities:
1. Search products by specific criteria (type, price, vendor, discount)
2. Find products using natural language descriptions
3. Get detailed information about specific products
4. Find similar products to ones the user likes
5. Remember user preferences and previous interactions
6. Make personalized recommendations based on browsing history

## Guidelines:
- Be helpful and conversational
- Ask clarifying questions when search criteria are vague
- Explain why you're recommending certain products
- Remember what products the user has already seen
- Provide diverse options when making recommendations
- Always validate that results match user intent before presenting them

## Response Format:
- Present products in a clear, organized way
- Include key details: name, price, vendor, key features
- Explain why each product matches the user's needs
- Suggest follow-up actions or related searches
"""
    
    def _retrieve_context(self, state: AgentState) -> AgentState:
        """Retrieve conversation context and user history"""
        print(f"🔍 STEP: retrieve_context")
        
        # Get conversation history
        history = self.memory.get_conversation_history()
        
        # Get user context (preferences, viewed products)
        user_context = self.session_manager.get_session_data(
            self.session_id, 
            self.tenant_id
        )
        
        # Update state
        state["user_context"] = user_context or {}
        
        # Add history to messages if not already present
        if not any(isinstance(m, AIMessage) for m in state["messages"][:-1]):
            history_messages = []
            for item in history[-5:]:  # Last 5 exchanges
                if item["role"] == "user":
                    history_messages.append(HumanMessage(content=item["content"]))
                elif item["role"] == "assistant":
                    history_messages.append(AIMessage(content=item["content"]))
            
            # Insert history before current message
            if history_messages:
                state["messages"] = history_messages + state["messages"]
        
        return state
    
    def _plan_action(self, state: AgentState) -> AgentState:
        """Plan the next action based on current state"""
        print(f"🧠 STEP: plan_action - about to call LLM")
        
        # Plan the next action based on current state
        
        # Create planning prompt
        messages = [
            SystemMessage(content=self._create_system_prompt()),
            *state["messages"]
        ]
        
        # Add context about current products if any
        if state.get("current_products"):
            context = f"Currently showing {len(state['current_products'])} products."
            messages.append(SystemMessage(content=context))
        
        # Add search history context
        if state.get("search_history"):
            searches = [str(s["query"]) for s in state["search_history"][-3:]]
            context = f"Recent searches: {', '.join(searches)}"
            messages.append(SystemMessage(content=context))
        
        # Get LLM decision
        planning_prompt = f"""Based on the conversation, decide what action to take.

Available tools:
- sql_search_tool: For structured searches (price, category, vendor filters)
- semantic_search_tool: For natural language product searches
- get_schema_info_tool: To understand available product types and price ranges
- get_product_details_tool: For detailed product information
- get_similar_products_tool: To find similar products

For the user query, choose the most appropriate tool:
- If asking about products with specific criteria (price, type, vendor) → sql_search_tool
- If asking with natural language descriptions → semantic_search_tool
- If asking "what do you have" or general questions → get_schema_info_tool

Respond with the exact tool name and parameters, or 'respond' if ready to answer.
Format: {{"action": "tool_name", "params": {{...}}}} or {{"action": "respond"}}
"""
        messages.append(HumanMessage(content=planning_prompt))
        
        print(f"📞 CALLING LLM with {len(messages)} messages")
        response = self.llm.invoke(messages)
        print(f"📨 LLM RESPONSE: {response.content[:100]}...")
        
        try:
            decision = json.loads(response.content)
            state["next_action"] = decision.get("action", "respond")
            
            if decision.get("params"):
                # Store parameters for tool execution
                state["tool_params"] = decision["params"]
            else:
                # Clear tool_params if no params provided
                state["tool_params"] = {}
            
            print(f"🎯 PARSED DECISION: action={state['next_action']}, params={state.get('tool_params', {})}")
        except Exception as e:
            print(f"❌ JSON parsing failed: {e}, raw response: {response.content}")
            # Default to generating response if parsing fails
            state["next_action"] = "respond"
        
        return state
    
    def _should_execute_tool(self, state: AgentState) -> str:
        """Decide whether to execute a tool or generate response"""
        action = state.get("next_action", "respond")
        
        if action in ["sql_search_tool", "semantic_search_tool", "get_product_details_tool", 
                     "get_similar_products_tool", "get_schema_info_tool"]:
            return "execute_tool"
        else:
            return "generate_response"
    
    def _should_continue_or_respond(self, state: AgentState) -> str:
        """Decide whether to continue searching or generate final response"""
        action = state.get("next_action", "respond")
        
        if action == "respond":
            return "respond"
        elif action in ["sql_search_tool", "semantic_search_tool", "get_product_details_tool", 
                       "get_similar_products_tool", "get_schema_info_tool"]:
            return "continue"
        else:
            return "respond"
    
    def _execute_tool(self, state: AgentState) -> AgentState:
        """Execute the selected tool"""
        tool_name = state.get("next_action")
        tool_params = state.get("tool_params", {})
        
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
                
                if tool_name == "sql_search_tool":
                    # Extract filters from tool_params and call with correct signature
                    filters = {k: v for k, v in tool_params.items() if k != 'limit'}
                    limit = tool_params.get('limit', 20)
                    result = tool.func(filters, limit)
                elif tool_name == "semantic_search_tool":
                    query = tool_params.get('query', '')
                    limit = tool_params.get('limit', 20)
                    result = tool.func(query, limit)
                elif tool_name == "get_similar_products_tool":
                    product_id = tool_params.get('product_id')
                    limit = tool_params.get('limit', 5)
                    result = tool.func(product_id, limit)
                elif tool_name == "get_product_details_tool":
                    product_ids = tool_params.get('product_ids', [])
                    result = tool.func(product_ids)
                else:
                    # For tools that don't need parameters
                    result = tool.func()
                
                print(f"✅ Tool execution successful, got {len(result) if isinstance(result, list) else 1} results")
                
                # Store results
                if isinstance(result, list):
                    state["current_products"] = result
                    
                    # Update search history
                    if "search_history" not in state:
                        state["search_history"] = []
                    
                    state["search_history"].append({
                        "query": tool_params,
                        "tool": tool_name,
                        "results": len(result),
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Add tool result to messages as system message instead of ToolMessage
                # to avoid OpenAI API tool calling format requirements
                result_message = SystemMessage(
                    content=f"Tool {tool_name} executed successfully. Result: {json.dumps(result, default=str)[:500]}..."
                )
                state["messages"].append(result_message)
                
            except Exception as e:
                # Handle tool execution errors
                error_message = ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_name
                )
                state["messages"].append(error_message)
        
        return state
    
    def _validate_results(self, state: AgentState) -> AgentState:
        """Validate that results match user intent"""
        
        if not state.get("current_products"):
            return state
        
        # Create validation prompt
        user_query = state["messages"][0].content if state["messages"] else ""
        products = state["current_products"][:5]  # Validate top 5
        
        validation_prompt = f"""User asked: {user_query}

Found {len(state['current_products'])} products. Here are the top 5:
{json.dumps(products, indent=2, default=str)}

Do these products match what the user is looking for? 
Rate the relevance (1-10) and explain if we should:
1. Show these results
2. Search again with different criteria
3. Ask for clarification

Response format: {{"relevance": 8, "action": "show", "reason": "..."}}
"""
        
        messages = [
            SystemMessage(content="You are validating search results for relevance."),
            HumanMessage(content=validation_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            validation = json.loads(response.content)
            
            if validation.get("relevance", 0) < 6:
                # Low relevance - need to search again or clarify
                if validation.get("action") == "clarify":
                    state["next_action"] = "respond"  # Ask for clarification
                else:
                    state["next_action"] = "search_again"
            else:
                # Good results - proceed to response
                state["next_action"] = "respond"
                
        except:
            # Default to showing results if validation fails
            state["next_action"] = "respond"
        
        return state
    
    def _generate_response(self, state: AgentState) -> AgentState:
        """Generate final response to user"""
        
        # Build context for response generation
        messages = [
            SystemMessage(content=self._create_system_prompt()),
            *state["messages"]
        ]
        
        # Add instruction for response format
        if state.get("current_products"):
            products = state["current_products"]
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
        
        messages.append(HumanMessage(content=response_prompt))
        
        response = self.llm.invoke(messages)
        state["final_answer"] = response.content
        
        # Add response to messages
        state["messages"].append(AIMessage(content=response.content))
        
        return state
    
    def _update_memory(self, state: AgentState) -> AgentState:
        """Update conversation memory and session data"""
        
        # Save conversation turn
        user_message = next((m for m in state["messages"] if isinstance(m, HumanMessage)), None)
        if user_message:
            self.memory.add_message(user_message.content, "user")
        
        if state.get("final_answer"):
            self.memory.add_message(state["final_answer"], "assistant")
        
        # Update session data
        session_data = {
            "last_active": datetime.now().isoformat(),
            "search_history": state.get("search_history", []),
            "viewed_products": state.get("current_products", [])[:10],  # Keep last 10
            "user_context": state.get("user_context", {})
        }
        
        self.session_manager.update_session(
            self.session_id,
            self.tenant_id,
            session_data
        )
        
        return state
    
    async def chat(self, message: str) -> str:
        """
        Main chat interface
        
        Args:
            message: User's message
            
        Returns:
            Agent's response
        """
        print(f"\n🤖 AGENT: Starting chat workflow for message: '{message}'")
        
        # Create initial state
        initial_state = AgentState(
            messages=[HumanMessage(content=message)],
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            user_context={},
            current_products=[],
            search_history=[],
            next_action=None,
            tool_params=None,
            final_answer=None
        )
        
        print(f"🔄 AGENT: Running LangGraph workflow...")
        
        # Run the graph with thread ID configuration and recursion limit
        config = {
            "configurable": {"thread_id": self.session_id},
            "recursion_limit": 50
        }
        final_state = await self.graph.ainvoke(initial_state, config)
        
        print(f"✅ AGENT: Workflow completed. Final answer exists: {bool(final_state.get('final_answer'))}")
        
        return final_state.get("final_answer", "I'm sorry, I couldn't process your request.")
    
    def reset_session(self):
        """Reset the conversation session"""
        self.session_id = str(uuid.uuid4())
        self.memory = ConversationMemory(self.session_id, self.tenant_id)
        self.session_manager.clear_session(self.session_id, self.tenant_id)