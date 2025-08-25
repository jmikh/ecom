#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.query_agent import QueryAgent
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_query(query, mock_mode=False):
    """Test a single query"""
    agent = QueryAgent(mock_mode=mock_mode)
    
    print(f"\n{'='*60}")
    print(f"QUERY: '{query}'")
    print(f"{'='*60}")
    
    try:
        # Get search results
        results = agent.search(query)
        
        print(f"\nResults found: {results['total_found']}")
        print(f"Search mode: {results['metadata']['mode']}")
        print(f"Parsed filters: {results['metadata']['parsed_filters']}")
        print(f"Semantic query: '{results['metadata']['semantic_query']}'")
        
        print(f"\n{'='*40}")
        print("TOP RESULTS:")
        print(f"{'='*40}")
        
        for i, result in enumerate(results['results'][:3], 1):
            print(f"\n{i}. {result['name']}")
            print(f"   Price: ${result['price']}")
            print(f"   Category: {result['category']}")
            print(f"   Options: {result.get('options', [])}")
            print(f"   Rating: {result['rating']}")
            print(f"   Match: {result.get('match_reason', '')}")
            if result.get('snippet'):
                snippet = result['snippet'][:100] + "..." if len(result['snippet']) > 100 else result['snippet']
                print(f"   Description: {snippet}")
        
        if not results['results']:
            print("No results found.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        agent.close()

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {sys.argv[0]} \"your search query\"")
        print(f"  python {sys.argv[0]} \"your search query\" --mock")
        print(f"  python {sys.argv[0]} --interactive")
        print(f"  python {sys.argv[0]} --examples")
        sys.exit(1)
    
    # Check for flags
    mock_mode = '--mock' in sys.argv
    if mock_mode:
        sys.argv.remove('--mock')
    
    if '--interactive' in sys.argv:
        # Interactive mode
        print("🔍 Interactive Search Mode")
        print("Type 'quit' to exit, 'mock' to toggle mock mode")
        print("Current mock mode:", "ON" if mock_mode else "OFF")
        
        while True:
            try:
                query = input("\nEnter search query: ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                elif query.lower() == 'mock':
                    mock_mode = not mock_mode
                    print(f"Mock mode: {'ON' if mock_mode else 'OFF'}")
                    continue
                elif not query:
                    continue
                
                test_query(query, mock_mode)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
    
    elif '--examples' in sys.argv:
        # Test with example queries
        examples = [
            "silver bracelets under $50",
            "statement bracelets",
            "gold jewelry with good reviews",
            "bracelets",
            "waterproof items",
            "comfortable silk items",
            "rose gold mother daughter bracelets"
        ]
        
        print(f"🧪 Testing {len(examples)} example queries")
        print(f"Mock mode: {'ON' if mock_mode else 'OFF'}")
        
        for query in examples:
            test_query(query, mock_mode)
            input("\nPress Enter for next query...")
    
    else:
        # Single query mode
        query = ' '.join(sys.argv[1:])
        test_query(query, mock_mode)

if __name__ == "__main__":
    # For debugging
    # sys.argv = ["test_agent.py", "show me colorful bracelets"]
    main()