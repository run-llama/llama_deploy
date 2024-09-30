from .agent_workflow import build_agentic_workflow
from .rag_workflow import build_rag_workflow


rag_w = build_rag_workflow()
agentic_w = build_agentic_workflow(rag_w)
