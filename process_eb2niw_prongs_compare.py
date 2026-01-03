# === process_eb2niw_prongs_compare.py ===

import requests
import fitz  # PyMuPDF
import csv
import time
import re
from openai import OpenAI

# ---------------
# SETTINGS
# ---------------
model_name = "gpt-4o"
batch_size = 50
sleep_time = 10
start_line = 1  # Starting line number (1-indexed)
end_line = 100  # Ending line number (inclusive)

# Your petition details
my_case = {
    "Prong1": "Strong: Research directly improves U.S. healthcare outcomes using AI for early disease detection.",
    "Prong2": "4+ years leading projects at a top U.S. university hospital and multiple published papers.",
    "Prong3": "Immediate healthcare application; delay would risk public health improvements."
}


# ---------------
# READ PDF LINKS
# ---------------
try:
    with open("Master_file", "r") as file:
        all_links = [line.strip() for line in file if line.strip()]
except FileNotFoundError:
    print("Error: 'Master_file' not found. Please ensure the file exists.")
    all_links = []

pdf_links = all_links[start_line - 1:end_line]

# ---------------
# HELPER FUNCTIONS
# ---------------

def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            print(f"Failed to fetch {url}")
            return ""
        with open("temp.pdf", "wb") as f:
            f.write(response.content)
        doc = fitz.open("temp.pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"Error fetching PDF from {url}: {e}")
        return ""

def analyze_niw_case_and_compare(text, my_case_data):
    client = OpenAI()
    prompt = f"""
You are an immigration expert.
I will provide my case details and a USCIS decision document (Decision).

MY CASE:
Prong 1: {my_case_data['Prong1']}
Prong 2: {my_case_data['Prong2']}
Prong 3: {my_case_data['Prong3']}

DECISION DOCUMENT:
{text[:12000]}

TASK:
1. Determine if the Decision is an EB-2 NIW petition. Answer "NIW: Yes" or "NIW: No".
2. If Yes, compare MY CASE to the standards and reasoning applied in the Decision.
   - For each prong, analyze if my profile would satisfy the adjudicator's specific logic/standard in this case.
   - Assess if I am stronger, weaker, or similar to the petitioner in the decision (or the standard applied).
3. Provide a "Qualification Percentage" (0-100%) estimating my chance of approval if judged by THIS specific adjudicator/standard.

OUTPUT FORMAT (Strictly follow):
NIW: [Yes/No]
Prong 1 Analysis: [Comparison text]
Prong 2 Analysis: [Comparison text]
Prong 3 Analysis: [Comparison text]
Qualification Percentage: [Number]%
Final Verdict: [One sentence summary]
"""
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        summary = response.choices[0].message.content
        return summary
    except Exception as e:
        print(f"Error during API call: {e}")
        return "Error"

# ---------------
# PROCESS PDFs
# ---------------

output_rows = []

print(f"Starting processing of {len(pdf_links)} links...")

for idx, link in enumerate(pdf_links):
    print(f"Processing {start_line + idx}/{len(all_links)}: {link}")
    text = extract_text_from_url(link)
    if not text:
        continue

    summary = analyze_niw_case_and_compare(text, my_case)

    if summary == "Error":
        continue

    # Parse the response
    is_niw = False
    if "NIW: Yes" in summary:
        is_niw = True
    elif "NIW: No" in summary:
        # Skip non-NIW cases as requested
        print("  -> Not an NIW case. Skipping.")
        continue
    
    # Fallback check if "NIW: Yes" wasn't explicit but context implies it
    # But strictly following instructions, we skip if not explicit Yes or if it says No.

    if is_niw:
        try:
            p1_analysis = ""
            p2_analysis = ""
            p3_analysis = ""
            qual_percent = ""
            final_verdict = ""

            lines = summary.split('\n')
            current_section = None
            
            # Simple line-based parsing assuming format is followed
            # Using regex or simpler find logic might be more robust for multiline values
            
            # Helper to extract value after label
            def extract_val(marker, text_block):
                pattern = re.compile(rf"{marker}\s*(.*)", re.IGNORECASE)
                match = pattern.search(text_block)
                return match.group(1).strip() if match else ""

            # Let's try to parse the whole block with regex for better multiline support if needed
            # But line iteration is often safer for streaming tokens if format varies slightly.
            # Given the format instruction, let's try to extract sections.
            
            p1_match = re.search(r"Prong 1 Analysis:\s*(.*?)(?=Prong 2 Analysis:|$)", summary, re.DOTALL | re.IGNORECASE)
            p1_analysis = p1_match.group(1).strip() if p1_match else "Parse Error"

            p2_match = re.search(r"Prong 2 Analysis:\s*(.*?)(?=Prong 3 Analysis:|$)", summary, re.DOTALL | re.IGNORECASE)
            p2_analysis = p2_match.group(1).strip() if p2_match else "Parse Error"

            p3_match = re.search(r"Prong 3 Analysis:\s*(.*?)(?=Qualification Percentage:|$)", summary, re.DOTALL | re.IGNORECASE)
            p3_analysis = p3_match.group(1).strip() if p3_match else "Parse Error"

            qual_match = re.search(r"Qualification Percentage:\s*(\d+%?)", summary, re.IGNORECASE)
            qual_percent = qual_match.group(1).strip() if qual_match else "N/A"

            verdict_match = re.search(r"Final Verdict:\s*(.*)", summary, re.IGNORECASE)
            final_verdict = verdict_match.group(1).strip() if verdict_match else "N/A"

            print(f"  -> NIW Case. Qualification: {qual_percent}")
            output_rows.append([link, p1_analysis, p2_analysis, p3_analysis, qual_percent, final_verdict])

        except Exception as e:
            print(f"Error parsing summary: {e}")
            output_rows.append([link, "Parse Error", "Parse Error", "Parse Error", "Parse Error", "Parse Error"])

    if (idx + 1) % batch_size == 0 or (idx + 1) == len(pdf_links):
        print("Saving progress...")
        with open("summary_prongs_comparison.csv", "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["PDF Link", "Prong 1 Comparison", "Prong 2 Comparison", "Prong 3 Comparison", "Qualification Percentage", "Final Verdict"])
            writer.writerows(output_rows)
        print(f"Saved {len(output_rows)} NIW rows so far.")
        time.sleep(sleep_time)

print("Done! All NIW comparisons saved to summary_prongs_comparison.csv")
