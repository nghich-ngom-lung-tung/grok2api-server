import sys
import os

def main():
    args = sys.argv[1:]
    
    # Handle version check
    if "--version" in args or "-v" in args:
        print("Grok CLI 1.0.5 (xAI Grok)")
        sys.exit(0)

    # Handle models probe from Grok Build IDE
    if "models" in args:
        print("""Default model: grok-4.5

Available models:
* grok-4.5 (default)
* grok-4.6
* grok-2.5-fast
* grok-3
* grok-code
* grok-imagine-image
""")
        sys.exit(0)
        
    # Check if called as an ACP Agent by Grok Build IDE
    is_agent_mode = any(arg in ["agent", "stdio", "--always-approve", "--permission-mode"] for arg in args)
    
    if is_agent_mode:
        from grok_acp_agent import run_acp_server
        # Parse selected model from cli args if present
        selected_model = "grok-4.5"
        if "--model" in args:
            try:
                idx = args.index("--model")
                if idx + 1 < len(args):
                    selected_model = args[idx + 1]
            except Exception:
                pass
        run_acp_server(default_model=selected_model)
        sys.exit(0)

    # Otherwise run standard user CLI (Chat, 4K Image, Vision, Interactive)
    from grok_cli import main as cli_main
    cli_main()

if __name__ == "__main__":
    main()
