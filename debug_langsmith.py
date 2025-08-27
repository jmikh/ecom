#!/usr/bin/env python3
"""
LangSmith Debugging Dashboard and Analysis Tools
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from langsmith import Client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import os
from dotenv import load_dotenv

load_dotenv()

console = Console()


class LangSmithDebugDashboard:
    """Interactive debugging dashboard for LangSmith traces"""
    
    def __init__(self):
        api_key = os.getenv("LANGSMITH_API_KEY")
        if not api_key:
            console.print("[red]❌ LANGSMITH_API_KEY not found in .env file[/red]")
            console.print("Please add your LangSmith API key to the .env file")
            exit(1)
        
        self.client = Client(api_key=api_key)
        self.project_name = os.getenv("LANGSMITH_PROJECT", "ecom-product-agent")
        
    def get_recent_runs(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent runs from LangSmith"""
        try:
            # Get runs from the last N hours
            start_time = datetime.now() - timedelta(hours=hours)
            
            runs = self.client.list_runs(
                project_name=self.project_name,
                start_time=start_time,
                limit=limit
            )
            
            return list(runs)
        except Exception as e:
            console.print(f"[red]Error fetching runs: {e}[/red]")
            return []
    
    def analyze_run(self, run_id: str) -> Dict[str, Any]:
        """Analyze a specific run for debugging"""
        try:
            run = self.client.read_run(run_id)
            
            analysis = {
                "id": str(run.id),
                "name": run.name,
                "start_time": run.start_time,
                "end_time": run.end_time,
                "duration": (run.end_time - run.start_time).total_seconds() if run.end_time else None,
                "status": run.status,
                "error": run.error,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "metadata": run.extra.get("metadata", {}),
                "tags": run.tags or [],
                "token_usage": run.extra.get("token_usage", {}),
                "cost": run.extra.get("cost", 0)
            }
            
            return analysis
        except Exception as e:
            console.print(f"[red]Error analyzing run: {e}[/red]")
            return {}
    
    def display_runs_table(self, runs: List[Dict[str, Any]]):
        """Display runs in a formatted table"""
        table = Table(title=f"Recent LangSmith Runs - {self.project_name}")
        
        table.add_column("Time", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Duration", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Tokens", style="blue")
        table.add_column("Error", style="red")
        
        for run in runs:
            time_str = run.start_time.strftime("%H:%M:%S") if run.start_time else "N/A"
            name = run.name or "Unknown"
            
            duration = "N/A"
            if run.end_time and run.start_time:
                duration = f"{(run.end_time - run.start_time).total_seconds():.2f}s"
            
            status = run.status or "running"
            
            tokens = "N/A"
            if hasattr(run, 'extra') and run.extra.get('token_usage'):
                total = run.extra['token_usage'].get('total_tokens', 0)
                tokens = str(total)
            
            error = "✓" if not run.error else "✗"
            
            table.add_row(time_str, name, duration, status, tokens, error)
        
        console.print(table)
    
    def analyze_conversation_flow(self, session_id: Optional[str] = None):
        """Analyze conversation flow patterns"""
        runs = self.get_recent_runs(hours=24, limit=100)
        
        # Filter by session if provided
        if session_id:
            runs = [r for r in runs if r.extra.get("metadata", {}).get("session_id") == session_id]
        
        if not runs:
            console.print("[yellow]No runs found for analysis[/yellow]")
            return
        
        # Analyze patterns
        tool_calls = {}
        llm_calls = 0
        total_tokens = 0
        errors = []
        
        for run in runs:
            if run.run_type == "tool":
                tool_name = run.name or "unknown"
                tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
            elif run.run_type == "llm":
                llm_calls += 1
                if hasattr(run, 'extra') and run.extra.get('token_usage'):
                    total_tokens += run.extra['token_usage'].get('total_tokens', 0)
            
            if run.error:
                errors.append({
                    "name": run.name,
                    "error": run.error,
                    "time": run.start_time
                })
        
        # Display analysis
        console.print("\n[bold cyan]📊 Conversation Flow Analysis[/bold cyan]")
        console.print(f"Total Runs: {len(runs)}")
        console.print(f"LLM Calls: {llm_calls}")
        console.print(f"Total Tokens: {total_tokens}")
        
        if tool_calls:
            console.print("\n[bold yellow]🔧 Tool Usage:[/bold yellow]")
            for tool, count in sorted(tool_calls.items(), key=lambda x: x[1], reverse=True):
                console.print(f"  • {tool}: {count} calls")
        
        if errors:
            console.print("\n[bold red]❌ Errors:[/bold red]")
            for error in errors[:5]:  # Show first 5 errors
                console.print(f"  • {error['name']}: {error['error'][:100]}")
    
    def debug_specific_run(self, run_id: str):
        """Deep dive into a specific run for debugging"""
        analysis = self.analyze_run(run_id)
        
        if not analysis:
            return
        
        # Create detailed debug panel
        console.print(Panel.fit(
            f"[bold cyan]Run Debug Analysis[/bold cyan]\n\n"
            f"[yellow]ID:[/yellow] {analysis['id']}\n"
            f"[yellow]Name:[/yellow] {analysis['name']}\n"
            f"[yellow]Duration:[/yellow] {analysis.get('duration', 'N/A')}s\n"
            f"[yellow]Status:[/yellow] {analysis['status']}\n"
            f"[yellow]Tags:[/yellow] {', '.join(analysis['tags'])}\n",
            title="Run Details"
        ))
        
        # Show inputs
        if analysis.get('inputs'):
            console.print("\n[bold green]📥 Inputs:[/bold green]")
            console.print(json.dumps(analysis['inputs'], indent=2)[:500])
        
        # Show outputs
        if analysis.get('outputs'):
            console.print("\n[bold blue]📤 Outputs:[/bold blue]")
            console.print(json.dumps(analysis['outputs'], indent=2)[:500])
        
        # Show metadata
        if analysis.get('metadata'):
            console.print("\n[bold magenta]📋 Metadata:[/bold magenta]")
            console.print(json.dumps(analysis['metadata'], indent=2))
        
        # Show errors
        if analysis.get('error'):
            console.print("\n[bold red]❌ Error:[/bold red]")
            console.print(analysis['error'])
    
    def monitor_live(self, refresh_seconds: int = 5):
        """Live monitoring dashboard"""
        console.print("[bold cyan]🔄 Starting live monitoring...[/bold cyan]")
        console.print(f"Project: {self.project_name}")
        console.print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Clear and refresh
                console.clear()
                console.print(f"[bold]LangSmith Live Monitor - {datetime.now().strftime('%H:%M:%S')}[/bold]\n")
                
                # Get recent runs
                runs = self.get_recent_runs(hours=1, limit=20)
                
                if runs:
                    self.display_runs_table(runs)
                    
                    # Show summary stats
                    active_runs = [r for r in runs if r.status == "running"]
                    failed_runs = [r for r in runs if r.error]
                    
                    console.print(f"\n[green]✓ Active: {len(active_runs)}[/green] | "
                                f"[red]✗ Failed: {len(failed_runs)}[/red] | "
                                f"[blue]Total: {len(runs)}[/blue]")
                else:
                    console.print("[yellow]No recent runs found[/yellow]")
                
                # Wait before refresh
                import time
                time.sleep(refresh_seconds)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped[/yellow]")
    
    def export_debug_report(self, output_file: str = "langsmith_debug_report.json"):
        """Export comprehensive debug report"""
        console.print(f"[cyan]Generating debug report...[/cyan]")
        
        runs = self.get_recent_runs(hours=24, limit=100)
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "project": self.project_name,
            "total_runs": len(runs),
            "runs_summary": [],
            "statistics": {
                "tool_usage": {},
                "error_rate": 0,
                "avg_duration": 0,
                "total_tokens": 0
            }
        }
        
        total_duration = 0
        error_count = 0
        
        for run in runs:
            summary = {
                "id": str(run.id),
                "name": run.name,
                "type": run.run_type,
                "start": run.start_time.isoformat() if run.start_time else None,
                "duration": None,
                "status": run.status,
                "error": run.error
            }
            
            if run.end_time and run.start_time:
                duration = (run.end_time - run.start_time).total_seconds()
                summary["duration"] = duration
                total_duration += duration
            
            if run.error:
                error_count += 1
            
            if run.run_type == "tool":
                tool_name = run.name or "unknown"
                report["statistics"]["tool_usage"][tool_name] = \
                    report["statistics"]["tool_usage"].get(tool_name, 0) + 1
            
            report["runs_summary"].append(summary)
        
        # Calculate statistics
        if runs:
            report["statistics"]["error_rate"] = error_count / len(runs)
            report["statistics"]["avg_duration"] = total_duration / len(runs) if runs else 0
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        console.print(f"[green]✓ Debug report saved to {output_file}[/green]")
        return report


def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LangSmith Debugging Dashboard")
    parser.add_argument("--monitor", action="store_true", help="Start live monitoring")
    parser.add_argument("--analyze", metavar="RUN_ID", help="Analyze specific run")
    parser.add_argument("--session", metavar="SESSION_ID", help="Analyze session flow")
    parser.add_argument("--export", action="store_true", help="Export debug report")
    parser.add_argument("--recent", type=int, default=10, help="Show N recent runs")
    
    args = parser.parse_args()
    
    dashboard = LangSmithDebugDashboard()
    
    console.print(Panel.fit(
        "[bold cyan]🔍 LangSmith Debug Dashboard[/bold cyan]\n"
        f"Project: [yellow]{dashboard.project_name}[/yellow]",
        title="Welcome"
    ))
    
    if args.monitor:
        dashboard.monitor_live()
    elif args.analyze:
        dashboard.debug_specific_run(args.analyze)
    elif args.session:
        dashboard.analyze_conversation_flow(args.session)
    elif args.export:
        dashboard.export_debug_report()
    else:
        # Default: show recent runs
        runs = dashboard.get_recent_runs(hours=24, limit=args.recent)
        if runs:
            dashboard.display_runs_table(runs)
            dashboard.analyze_conversation_flow()
        else:
            console.print("[yellow]No runs found. Make sure your agent is running with LangSmith enabled.[/yellow]")
            console.print("\nTo enable LangSmith:")
            console.print("1. Add LANGSMITH_API_KEY to your .env file")
            console.print("2. Set LANGSMITH_TRACING=true")
            console.print("3. Run your agent")
            console.print("\nThen try:")
            console.print("  python debug_langsmith.py --monitor")


if __name__ == "__main__":
    main()