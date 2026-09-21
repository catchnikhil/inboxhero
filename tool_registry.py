# Roll Number: evernorth-aai-1177619

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, description, parameters, func):
        self.tools[name] = {
            "description": description,
            "parameters": parameters,
            "func": func
        }

    def list_tools(self):
        return [
            {"name": name, "description": meta["description"], "parameters": meta["parameters"]}
            for name, meta in self.tools.items()
        ]

    def call_tool(self, name, arguments):
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        return self.tools[name]["func"](**arguments)
