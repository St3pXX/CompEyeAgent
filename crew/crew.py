from crewai import Crew
from crew.agents.collector import collector
from crew.agents.analyzer import analyzer
from crew.agents.writer import writer
from crew.agents.verifier import verifier
from tasks.collect_task import collect_info_task
from tasks.analyze_task import analyze_task
from tasks.write_task import write_task
from tasks.verify_task import verify_task

analysis_crew = Crew(
    agents=[collector, analyzer, writer, verifier],
    tasks=[collect_info_task, analyze_task, write_task, verify_task],
    flow="sequential",
    verbose=True,
)