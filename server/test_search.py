import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.query_agent import QueryAgent
import json
from pprint import pprint

def test_queries():
    agent = QueryAgent()
    
    test_cases = [
        "silver bracelets under $50",
        "comfortable yoga accessories",
        "rose gold items with good reviews",
        "products that mention family",
        "waterproof jewelry",
        "bracelets between $30 and $40",
        "items with moon gray color option",
        "products about strength and love"
    ]
    
    print("=" * 80)
    print("PRODUCT SEARCH ASSISTANT - TEST SUITE")
    print("=" * 80)
    
    for query in test_cases:
        print(f"\n\nQUERY: '{query}'")
        print("-" * 40)
        
        try:
            explanation = agent.explain_search(query)
            print("\n📊 QUERY ANALYSIS:")
            print(explanation)
            
            results = agent.search(query, mode='hybrid')
            
            print(f"\n🔍 FOUND: {results['total_found']} products")
            
            if results['results']:
                print("\n📦 TOP 3 RESULTS:")
                for i, product in enumerate(results['results'][:3], 1):
                    print(f"\n  {i}. {product['name']}")
                    print(f"     Price: ${product['price']}")
                    print(f"     Rating: {product['rating']}/5")
                    print(f"     Options: {', '.join(product['options'][:3])}")
                    print(f"     Match: {product['match_reason']}")
                    if product.get('snippet'):
                        print(f"     Snippet: {product['snippet'][:100]}...")
        
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    agent.close()

if __name__ == "__main__":
    test_queries()