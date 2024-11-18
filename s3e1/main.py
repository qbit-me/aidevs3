# This is the main entry point for the s3e1 module.

from services import OpenAiService, list_files

service = OpenAiService()

def main():
    print("Hello from s3e1!")
    
    # Build report from .txt files in the 'files' directory
    report = build_report()
    print("Report from .txt files:\n", report)
    
    # Build knowledge from facts
    knowledge = build_knowledge()
    print("Combined knowledge from facts:\n", knowledge)
    
import os

def build_report() -> str:
    """Builds a report by combining content from .txt files in the 'files' directory."""
    files = list_files('files')
    report_content = []
    for file_name in files:
        if file_name.endswith('.txt'):
            with open(f'files/{file_name}', 'r') as file:
                content = file.read().strip()
                report_content.append(f"<{file_name}>{content}</{file_name}>")
    return "\n".join(report_content)

def build_knowledge() -> str:
    """Builds a knowledge base by combining facts from the 'files/facts' directory."""
    facts = list_files('files/facts')
    combined_facts = []
    for fact_file in facts:
        with open(f'files/facts/{fact_file}', 'r') as file:
            content = file.read().strip()
            if content != "entry deleted":
                combined_facts.append(content)
    return "\n".join(combined_facts)

def situate_chunk(
    report_file_name: str, 
    full_report: str, 
    facts: str
) -> str:
    """Situates a chunk of the report within the context of the full report and facts."""
    with open(f'files/{report_file_name}', 'r') as file:
        chunk_content = file.read().strip()

    prompt = (
        f"<document>\n{full_report}\n</document>\n\n"
        f"<facts>\n{facts}\n</facts>\n\n"
        f"<chunk>\n{chunk_content}\n</chunk>\n\n"
        "Please give a short succinct context to situate this chunk within the overall document "
        "for the purposes of improving search retrieval of the chunk. Answer only with the succinct "
        "context and nothing else."
    )
    return prompt

if __name__ == "__main__":
    main()
