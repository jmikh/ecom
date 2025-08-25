#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.query_agent import QueryAgent
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_parser(mock=False):
    agent = QueryAgent(mock_mode=mock)
    
    test_queries = [
        "silver bracelets under $50",
        "rose gold items with good reviews",
        "bracelets between $30 and $40",
        "items with moon gray color option",
        "waterproof jewelry"
    ]
    
    print("=" * 80)
    print("TESTING GPT-4 QUERY PARSER")
    print("=" * 80)
    
    for query in test_queries[:1]:
        print(f"\n\nQUERY: '{query}'")
        print("-" * 40)
        
        filters, semantic_query = agent.parse_query(query)
        
        print(f"Filters: {filters}")
        print(f"Semantic: {semantic_query}")
        print()
    
    agent.close()

if __name__ == "__main__":
    test_parser(mock=False)