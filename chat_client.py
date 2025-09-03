#!/usr/bin/env python3
"""
Interactive terminal chat client for the e-commerce chat server
Usage: python chat_client.py [--tenant-id YOUR_TENANT_ID]
"""

import json
import uuid
import argparse
import requests
from typing import Optional
from datetime import datetime
import sys

# ANSI color codes for better terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ChatClient:
    def __init__(self, base_url: str = "http://localhost:8000", tenant_id: Optional[str] = None):
        self.base_url = base_url
        self.tenant_id = tenant_id or "6b028cbb-512d-4538-a3b1-71bc40f49ed1"  # Default tenant
        self.session_id = str(uuid.uuid4())
        self.stream_endpoint = f"{base_url}/api/chat/stream"
        
    def print_header(self):
        """Print welcome header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
        print(f"🛍️  E-Commerce Chat Assistant - Terminal Client")
        print(f"{'='*60}{Colors.ENDC}")
        print(f"{Colors.YELLOW}📍 Server: {self.base_url}")
        print(f"🏪 Tenant ID: {self.tenant_id}")
        print(f"🔑 Session ID: {self.session_id}{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}\n")
        print(f"{Colors.GREEN}Type 'exit' or 'quit' to end the session")
        print(f"Type 'clear' to clear the screen")
        print(f"Type 'new' to start a new session{Colors.ENDC}\n")
        
    def send_message(self, message: str) -> bool:
        """Send message to server and display response"""
        try:
            # Prepare request
            payload = {
                "message": message,
                "session_id": self.session_id,
                "tenant_id": self.tenant_id
            }
            
            # Send request with streaming
            response = requests.post(
                self.stream_endpoint,
                json=payload,
                stream=True,
                headers={'Accept': 'text/event-stream'}
            )
            
            if response.status_code != 200:
                print(f"{Colors.RED}❌ Error: Server returned status {response.status_code}{Colors.ENDC}")
                return False
            
            # Print assistant response header
            print(f"\n{Colors.BLUE}{Colors.BOLD}🤖 Assistant:{Colors.ENDC}")
            
            # Process streaming response
            buffer = ""
            message_buffer = ""
            products_shown = False
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        try:
                            data = json.loads(line_str[6:])
                            
                            # Handle different response types
                            if data.get('type') == 'chat_response':
                                # Handle structured ChatServerResponse
                                response_data = data.get('data', {})
                                
                                # Show message if exists
                                if response_data.get('message'):
                                    print(f"{Colors.CYAN}{response_data['message']}{Colors.ENDC}")
                                
                                # Show products if exist
                                if response_data.get('products'):
                                    self.display_products(response_data['products'])
                                    products_shown = True
                                    
                            elif data.get('type') == 'product_cards':
                                # Legacy format support
                                self.display_products(data.get('data', {}).get('products', []))
                                products_shown = True
                                if data.get('data', {}).get('message'):
                                    print(f"\n{Colors.CYAN}{data['data']['message']}{Colors.ENDC}")
                                    
                            elif data.get('chunk'):
                                # Text streaming
                                chunk = data.get('chunk', '')
                                message_buffer += chunk
                                print(chunk, end='', flush=True)
                                
                            elif data.get('error'):
                                print(f"\n{Colors.RED}❌ Error: {data['error']}{Colors.ENDC}")
                                return False
                                
                            if data.get('done'):
                                break
                                
                        except json.JSONDecodeError:
                            continue
            
            # Print final message if we only got text chunks
            if message_buffer and not products_shown:
                # Message already printed via chunks
                pass
                
            print("\n")  # Add spacing after response
            return True
            
        except requests.exceptions.ConnectionError:
            print(f"{Colors.RED}❌ Error: Cannot connect to server at {self.base_url}")
            print(f"Make sure the server is running (python run_server.py){Colors.ENDC}")
            return False
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {str(e)}{Colors.ENDC}")
            return False
    
    def display_products(self, products: list):
        """Display product cards in a formatted way"""
        if not products:
            return
            
        print(f"\n{Colors.GREEN}{Colors.BOLD}📦 Products:{Colors.ENDC}")
        print(f"{Colors.GREEN}{'─'*50}{Colors.ENDC}")
        
        for i, product in enumerate(products, 1):
            # Product name and vendor
            print(f"{Colors.BOLD}{i}. {product.get('name', 'Unknown Product')}{Colors.ENDC}")
            print(f"   {Colors.YELLOW}by {product.get('vendor', 'Unknown Vendor')}{Colors.ENDC}")
            
            # Price
            price_min = product.get('price_min', 0)
            price_max = product.get('price_max', price_min)
            if price_min == price_max:
                print(f"   💰 ${price_min:.2f}")
            else:
                print(f"   💰 ${price_min:.2f} - ${price_max:.2f}")
            
            # Discount indicator
            if product.get('has_discount'):
                print(f"   {Colors.RED}🏷️  ON SALE!{Colors.ENDC}")
            
            if i < len(products):
                print(f"{Colors.GREEN}{'─'*50}{Colors.ENDC}")
        
        print()  # Extra line for spacing
    
    def clear_screen(self):
        """Clear the terminal screen"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        self.print_header()
    
    def new_session(self):
        """Start a new chat session"""
        self.session_id = str(uuid.uuid4())
        print(f"\n{Colors.GREEN}✨ Started new session: {self.session_id}{Colors.ENDC}\n")
    
    def run(self):
        """Main chat loop"""
        self.print_header()
        
        while True:
            try:
                # Get user input
                user_input = input(f"{Colors.BOLD}{Colors.GREEN}👤 You: {Colors.ENDC}").strip()
                
                # Handle special commands
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print(f"\n{Colors.CYAN}👋 Goodbye! Thanks for chatting!{Colors.ENDC}\n")
                    break
                elif user_input.lower() == 'clear':
                    self.clear_screen()
                    continue
                elif user_input.lower() == 'new':
                    self.new_session()
                    continue
                elif not user_input:
                    continue
                
                # Send message and get response
                self.send_message(user_input)
                
            except KeyboardInterrupt:
                print(f"\n\n{Colors.CYAN}👋 Session interrupted. Goodbye!{Colors.ENDC}\n")
                break
            except Exception as e:
                print(f"{Colors.RED}❌ Unexpected error: {str(e)}{Colors.ENDC}")
                continue


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Interactive chat client for e-commerce server')
    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='Server URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--tenant-id',
        default='6b028cbb-512d-4538-a3b1-71bc40f49ed1',
        help='Tenant ID for the store'
    )
    
    args = parser.parse_args()
    
    # Create and run client
    client = ChatClient(base_url=args.url, tenant_id=args.tenant_id)
    client.run()


if __name__ == "__main__":
    main()