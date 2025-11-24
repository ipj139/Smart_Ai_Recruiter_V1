"""
Analysis functions for resume evaluation and scoring
"""
import re
from sklearn.metrics.pairwise import cosine_similarity
from utils_v2.client_helper import get_llm_client

# Lazy load SentenceTransformer to avoid slow startup
_ats_model = None

def _get_ats_model():
    """Lazy load the SentenceTransformer model only when needed"""
    global _ats_model
    if _ats_model is None:
        from sentence_transformers import SentenceTransformer
        _ats_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
    return _ats_model

def calculate_similarity_bert(text1, text2):
    """Calculate cosine similarity between two texts using BERT embeddings"""
    # Lazy load model only when this function is called
    ats_model = _get_ats_model()
    # Encode the texts directly to embeddings
    embeddings1 = ats_model.encode([text1])
    embeddings2 = ats_model.encode([text2])
    
    # Calculate cosine similarity without adding an extra list layer
    similarity = cosine_similarity(embeddings1, embeddings2)[0][0]
    return similarity


def get_report(resume, job_desc, api_key, model_name, selected_points=None, temperature=0.0, base_url=None, **kwargs):
    """Generate detailed analysis report using LLM
    
    Args:
        resume: Resume text
        job_desc: Job description text
        api_key: API key for LLM provider
        model_name: Model name to use
        selected_points: Optional list of evaluation points
        temperature: Temperature for LLM (default: 0.0)
        base_url: Optional base URL for API. If not provided, auto-detects from API key
        **kwargs: Additional arguments (e.g., experience_requirement)
    """
    # Initialize unified client (works with any OpenAI-compatible API)
    client = get_llm_client(api_key, base_url)

    # Build evaluation points section for prompt
    evaluation_points_section = ""
    experience_requirement = kwargs.get('experience_requirement', None)
    
    if selected_points and len(selected_points) > 0:
        points_list = "\n".join([f"- {point}" for point in selected_points])
        
        experience_text = ""
        if experience_requirement:
            experience_text = f"""
    # MANDATORY Experience Requirement:
    You MUST evaluate the candidate's overall work experience against this requirement: "{experience_requirement}"
    Extract the candidate's total work experience (in years and months) from the resume and compare it against this requirement.
    Score this point: 5/5 if candidate meets or exceeds the requirement, 0/5 if below requirement, with detailed explanation.
    Add this as a separate evaluation point titled "Overall Work Experience Requirement: {experience_requirement}" with score and explanation.
    """
        
        evaluation_points_section = f"""
    # Specific Evaluation Criteria (ONLY evaluate these points):
    {experience_text}
    You MUST evaluate the candidate ONLY on the following selected evaluation criteria:
    {points_list}
    
    Important: Evaluate ONLY the criteria listed above (including experience requirement). Do not add any additional evaluation points.
    """
    else:
        experience_text = ""
        if experience_requirement:
            experience_text = f"""
    # MANDATORY Experience Requirement:
    You MUST evaluate the candidate's overall work experience against this requirement: "{experience_requirement}"
    Extract the candidate's total work experience (in years and months) from the resume and compare it against this requirement.
    Score this point: 5/5 if candidate meets or exceeds the requirement, 0/5 if below requirement, with detailed explanation.
    Add this as a separate evaluation point titled "Overall Work Experience Requirement: {experience_requirement}" with score and explanation.
    """
        
        evaluation_points_section = f"""
    {experience_text}
    - Analyze candidate's resume based on the possible points that can be extracted from job description,and give your evaluation on each point with the criteria below:
    - Consider all points like required skills, experience,etc that are needed for the job role.
    """

    # Change the prompt to get the results in your style
    prompt_template = f"""
    # Context:
    - You are an AI Resume Analyzer, you will be given Candidate's resume and Job Description of the role he is applying for.

    # Instruction:
    {evaluation_points_section}
    - Calculate the score to be given (out of 5) for every point based on evaluation at the beginning of each point with a detailed explanation.  
    - If the resume aligns with the job description point, mark it with ✅ and provide a detailed explanation.  
    - If the resume doesn't align with the job description point, mark it with ❌ and provide a reason for it.  
    - If a clear conclusion cannot be made, use a ⚠️ sign with a reason.  
    - Extract the name of candidate from resume and mention that resume analysis for {{{{name}}}} is as below. Note that only take the name and remove titles like Mr., Mrs., Dr., Sir, etc.
    - Also fetch total number of years of experience from resume and mention that the candidate has {{{{total_experience}}}} years of experience and consider this for evaluation.
    - Also fetch location from resume and mention that the candidate is located in {{{{location}}}}. Consider this for matching.
    - At the very beginning of your response, create a heading "Analysis Report" and immediately below it render three bullet points (each on a new line) in markdown:
      - "Candidate Name: {{{{name}}}}"
      - "Total Experience: {{{{total_experience}}}} years"
      - "Candidate Location: {{{{location}}}}"
    - Add a dedicated point titled "Location Match" in the Job Description Alignment list. This point MUST include: the candidate location you extracted, the JD location(s) you extracted, whether they match, and the final score strictly as 5/5 (match) or 0/5 (no match), with an explanation.
    - In Job Description alignment if you observe evaluation point has occure multiple times then just consder one time, avoid dulications of evaluation parameters. It is good to use combine effect of skillsets.
    - At the end of your analysis, provide a "Summary" section with a heading "Summary". This summary MUST be written as a single, continuous paragraph (NOT bullet points, NOT numbered list, NOT sub-points). Write it as one flowing paragraph that combines all key strengths, weaknesses, location match status, and overall assessment conclusion in a natural, continuous text format. Do not use bullet points (•), dashes (-), or numbered lists in the Summary section - only plain paragraph text.

    # Inputs:
    Candidate Resume: {{RESUME}}
    ---
    Job Description: {{JOB_DESC}}

    # Output:
    - Each any every point should be given a score (example: 3/5 ). 
    - Mention the scores and  relevant emoji at the beginning of each point and then explain the reason.
    - The Summary section at the end must be a single paragraph without any bullet points, sub-points, or list formatting.
    """

    # Safely inject only resume and job description without touching other literal placeholders like {{name}}
    prompt = prompt_template.replace("{RESUME}", resume).replace("{JOB_DESC}", job_desc)

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model_name,
        temperature=temperature,
    )
    return chat_completion.choices[0].message.content


def extract_scores(text):
    """Extract scores from report text (format: x/5)"""
    # Regular expression pattern to find scores in the format x/5, where x can be an integer or a float
    pattern = r'(\d+(?:\.\d+)?)/5'
    # Find all matches in the text
    matches = re.findall(pattern, text)
    # Convert matches to floats
    scores = [float(match) for match in matches]
    return scores


def extract_summary_from_report(report_text):
    """Extract the last evaluation point or summary from the report"""
    if not report_text or not report_text.strip():
        return ""
    
    # Split report into lines
    lines = report_text.split('\n')
    
    # Look for common summary/conclusion indicators
    summary_keywords = ['summary', 'overall assessment', 'conclusion', 'final assessment', 
                       'overall evaluation', 'candidate summary', 'recommendation', 
                       'overall fit', 'final verdict', 'overall', 'conclusion']
    
    # Reverse search from the end to find the last substantial point
    # Look for lines that might indicate the last evaluation point or summary
    last_substantial_section = []
    found_summary_marker = False
    
    # Search backwards from the end
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        
        line_lower = line.lower()
        
        # Check if this line contains summary keywords
        if any(keyword in line_lower for keyword in summary_keywords):
            found_summary_marker = True
            # Collect from this point onwards until we hit a blank line or start of section
            j = i
            while j < len(lines) and (j == i or lines[j].strip()):
                if lines[j].strip():
                    last_substantial_section.insert(0, lines[j].strip())
                j += 1
                if len(last_substantial_section) >= 10:  # Limit length
                    break
            break
        
        # Collect substantial lines (not just headings or very short lines)
        if len(line) > 20 and not line.startswith('#'):
            last_substantial_section.insert(0, line)
            if len(last_substantial_section) >= 5:
                break
    
    # If we found a summary section, return it
    if last_substantial_section and found_summary_marker:
        return '\n'.join(last_substantial_section[:10]).strip()
    
    # If no summary marker, get the last few substantial lines (likely the last point)
    if last_substantial_section:
        return '\n'.join(last_substantial_section[:5]).strip()
    
    # Fallback: return last non-empty lines
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    if len(non_empty_lines) >= 3:
        # Get last 3-5 lines
        return '\n'.join(non_empty_lines[-5:]).strip()
    
    if non_empty_lines:
        return non_empty_lines[-1]
    
    return ""


def extract_failed_points_explanations(report_text):
    """Extract explanations for all points that have ❌ (X) emoji in the report"""
    if not report_text or not report_text.strip():
        return ""
    
    # Split report into lines
    lines = report_text.split('\n')
    
    failed_points = []
    
    # Look for patterns like: "Point Name ❌" or "Point Name (Score) ❌" or lines containing ❌
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Check if line contains ❌ emoji
        if '❌' in line_stripped:
            # Extract point name (usually before the emoji)
            # Pattern: "Point Name ❌" or "Point Name (X/5) ❌" or "❌ Point Name"
            point_name = None
            explanation_parts = []
            
            # Try to extract point name from current line
            # Remove score patterns like "5/5" or "0/5"
            temp_line = re.sub(r'\d+/\d+', '', line_stripped)
            # Split by ❌ emoji
            parts = temp_line.split('❌', 1)
            
            if len(parts) > 0:
                point_name = parts[0].strip()
                # Clean up point name
                point_name = re.sub(r'^[✅❌⚠️]\s*', '', point_name)
                point_name = re.sub(r'^[-•*]\s*', '', point_name)
                point_name = re.sub(r'^\d+\.\s*', '', point_name)
                
                # If point name is empty or too short, try to get from previous line
                if not point_name or len(point_name) < 3:
                    if i > 0:
                        prev_line = lines[i-1].strip()
                        if prev_line and len(prev_line) > 0 and len(prev_line) < 150:
                            # Check if previous line doesn't contain emojis and might be a point name
                            if '✅' not in prev_line and '❌' not in prev_line and '⚠️' not in prev_line:
                                point_name = prev_line
                
                # If still no point name, extract from current line
                if not point_name:
                    point_name = temp_line.replace('❌', '').strip()
                    point_name = re.sub(r'^[✅❌⚠️]\s*', '', point_name)
                
                # Get explanation from same line (after ❌) or next lines
                if len(parts) > 1:
                    after_emoji = parts[1].strip()
                    if after_emoji:
                        explanation_parts.append(after_emoji)
                
                # Look ahead for explanation in next lines (up to 5 lines)
                for j in range(i + 1, min(i + 6, len(lines))):
                    next_line = lines[j].strip()
                    
                    # Stop if we hit another emoji (new point)
                    if '✅' in next_line or '❌' in next_line or '⚠️' in next_line:
                        break
                    
                    # Stop if we hit a heading or section marker
                    if next_line.startswith('#') or next_line.startswith('**') or len(next_line) < 3:
                        # If we already have explanation, stop
                        if explanation_parts:
                            break
                        continue
                    
                    # Collect explanation text
                    if next_line and not next_line.startswith('|'):  # Skip table separators
                        clean_line = re.sub(r'^[-•*]\s*', '', next_line)
                        clean_line = re.sub(r'^\d+\.\s*', '', clean_line)
                        if clean_line:
                            explanation_parts.append(clean_line)
                    
                    # If we have substantial explanation (3+ lines or long text), stop looking
                    if len(explanation_parts) >= 3 or sum(len(p) for p in explanation_parts) > 200:
                        break
            
            # Clean up point name one more time
            if point_name:
                point_name = point_name.strip()
                # Remove extra whitespace
                point_name = re.sub(r'\s+', ' ', point_name)
            
            # If we have both point name and explanation, add to list
            if point_name and explanation_parts:
                explanation_text = ' '.join(explanation_parts).strip()
                if explanation_text:
                    failed_points.append({
                        'point': point_name,
                        'explanation': explanation_text
                    })
            # If we only have point name but no explanation from next lines, try to get from same line
            elif point_name and not explanation_parts:
                # Check if there's text after ❌ in the same line
                parts = line_stripped.split('❌', 1)
                if len(parts) > 1:
                    after_emoji = parts[1].strip()
                    # Remove score if present
                    after_emoji = re.sub(r'\d+/\d+', '', after_emoji).strip()
                    if after_emoji and len(after_emoji) > 10:
                        failed_points.append({
                            'point': point_name,
                            'explanation': after_emoji
                        })
    
    # Format the output
    if failed_points:
        formatted_output = []
        formatted_output.append("Failed Points (❌) - Explanations:\n")
        for idx, item in enumerate(failed_points, 1):
            formatted_output.append(f"{idx}. {item['point']}")
            formatted_output.append(f"   Explanation: {item['explanation']}\n")
        return '\n'.join(formatted_output)
    
    return ""


def process_single_resume(resume_file, job_desc, api_key, model_name, base_url=None, selected_points=None, experience_requirement=None):
    """Process a single resume and return all analysis results"""
    from utils_v2.text_extraction import extract_resume_text
    from utils_v2.llm_functions import extract_position_from_jd, extract_candidate_details_llm
    
    # Extract resume text
    resume_text = extract_resume_text(resume_file)
    
    if not resume_text or not resume_text.strip():
        return {
            'error': 'Could not extract text from resume',
            'resume_file': resume_file.name if resume_file else 'Unknown',
            'candidate_name': 'Not Found',
            'position': 'Not Found',
            'similarity_score': 0.0,
            'average_score': 0.0,
            'report': '',
            'candidate_details': None
        }
    
    # Calculate similarity score
    ats_score = calculate_similarity_bert(resume_text, job_desc) if (resume_text.strip() and job_desc.strip()) else 0.0
    
    # Get analysis report
    report = ""
    if api_key:
        report = get_report(
            resume_text,
            job_desc,
            api_key,
            model_name,
            selected_points=selected_points,
            temperature=0.0,
            base_url=base_url,
            experience_requirement=experience_requirement,
        )
    
    # Calculate average score
    report_scores = extract_scores(report)
    avg_score = (sum(report_scores) / (5*len(report_scores))) if report_scores else 0.0
    
    # Extract position
    position = "Not Found"
    if job_desc and job_desc.strip() and api_key:
        try:
            position = extract_position_from_jd(job_desc, api_key, model_name, base_url)
        except:
            position = "Not Found"
    
    # Extract candidate details
    candidate_details = None
    candidate_name = "Not Found"
    if api_key:
        try:
            candidate_details = extract_candidate_details_llm(resume_text, api_key, model_name, base_url)
            if candidate_details:
                candidate_name = candidate_details.get('Candidate_Name', 'Not Found')
        except:
            candidate_details = None
    
    return {
        'resume_file': resume_file.name if resume_file else 'Unknown',
        'resume_text': resume_text,
        'resume_file_obj': resume_file,
        'candidate_name': candidate_name,
        'candidate_details': candidate_details,
        'position': position,
        'similarity_score': ats_score,
        'average_score': avg_score,
        'report': report,
        'report_scores': report_scores,
        'error': None
    }

