"""LangGraph-based orchestration package for CompEye Agent.

Replaces the CrewAI sequential chain + self-built coordinator loop with an
explicit ``StateGraph``:  collect -> analyze -> write -> verify, with a
conditional edge that routes to ``rewrite`` once when verification fails.
"""
