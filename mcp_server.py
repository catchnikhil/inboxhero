# Roll Number: evernorth-aai-1177619
from tool_registry import ToolRegistry

class MCPServer:
    def __init__(self, registry: ToolRegistry, name="InboxHeroServer", version="1.0"):
        self.registry = registry
        self.name = name
        self.version = version

    def handle(self, request: dict) -> dict:
        if request.get("jsonrpc") != "2.0":
            return {"jsonrpc":"2.0","id":request.get("id"),
                    "error":{"code":-32600,"message":"Invalid JSON-RPC version"}}

        method = request.get("method")
        req_id = request.get("id")

        try:
            if method == "initialize":
                return {"jsonrpc":"2.0","id":req_id,
                        "result":{"server":self.name,"protocol_version":self.version}}

            elif method == "tools/list":
                return {"jsonrpc":"2.0","id":req_id,"result":self.registry.list_tools()}

            elif method == "tools/call":
                params = request.get("params",{})
                tool_name = params.get("name")
                args = params.get("arguments",{})
                result = self.registry.call_tool(tool_name,args)
                return {"jsonrpc":"2.0","id":req_id,"result":result}

            else:
                return {"jsonrpc":"2.0","id":req_id,
                        "error":{"code":-32601,"message":f"Unknown method: {method}"}}
        except Exception as e:
            return {"jsonrpc":"2.0","id":req_id,
                    "error":{"code":-32001,"message":str(e)}}
