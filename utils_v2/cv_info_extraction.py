"""
CV Information Extraction using LLM
Extracts specific information from CV text for PPT conversion
"""
import streamlit as st
import json
import re
from utils_v2.client_helper import get_llm_client


def extract_cv_info_for_ppt(cv_text, api_key, model_name, base_url=None):
    """Extract CV information needed for PPT conversion using LLM
    
    Args:
        cv_text: Extracted text from CV
        api_key: API key for LLM provider
        model_name: Model name to use
        base_url: Optional base URL for API. If not provided, auto-detects from API key
    
    Returns:
        Dictionary with:
        - area_of_expertise: Technical skills (1-3 words each, comma-separated)
        - education: Education details
        - profile_summary: Profile summary
        - project1: Latest project details (title, duration, description, technologies)
        - project2: Second latest project details
    """
    if not cv_text or not cv_text.strip():
        return None
    
    if not api_key:
        return None
    
    try:
        # Use unified client (works with any OpenAI-compatible API)
        client = get_llm_client(api_key, base_url)
        
        # Use more CV text if available (increase from 8000 to 15000 to capture more context)
        cv_text_sample = cv_text[:15000] if len(cv_text) > 15000 else cv_text
        
        prompt = f"""You are an expert resume parser. Extract structured information from the resume text below and return ONLY a valid JSON object with NO additional text, explanations, or markdown formatting.

=== REQUIRED JSON FORMAT ===
{{
    "area_of_expertise": "comma-separated technical skills (1-3 words each)",
    "education": "Education details (degree, university, year)",
    "profile_summary": "Professional summary (2-4 sentences)",
    "project1": {{"title": "...", "duration": "...", "description": "...", "technologies": "..."}},
    "project2": {{"title": "...", "duration": "...", "description": "...", "technologies": "..."}},
    "project3": {{"title": "...", "duration": "...", "description": "...", "technologies": "..."}},
    "project4": {{"title": "...", "duration": "...", "description": "...", "technologies": "..."}}
}}

=== FIELD-SPECIFIC EXTRACTION RULES ===

1. AREA_OF_EXPERTISE:
   EXTRACT FROM: "Skills", "Technical Skills", "Expertise", "Technologies", "Competencies", "Technical Competencies" sections
   FORMAT: Comma-separated list (e.g., "Python, SQL, Data Analysis, Machine Learning, Tableau")
   RULES:
   - Extract programming languages, tools, frameworks, platforms only
   - Each skill: 1-3 words maximum
   - Include skills from both dedicated skills section AND skills mentioned in project descriptions
   - Exclude soft skills (communication, teamwork, leadership, etc.)
   EXAMPLE: "Python, SQL, Tableau, Machine Learning, Apache Spark, Power BI, Flask, React"

2. EDUCATION:
   EXTRACT FROM: "Education", "Qualification", "Academic Background", "Educational Background" sections
   FORMAT: Degree, University/Institution, Year (if available)
   RULES:
   - Extract ONLY the HIGHEST/MOST RECENT education (do not include multiple degrees)
   - Priority: Highest degree first (PhD > Master's > Bachelor's > Diploma)
   - If same level, choose most recent by year
   - Include: Degree name, University/College name, Graduation year
   - Format: "B.Tech in Computer Science, XYZ University, 2020" or "M.Tech in Data Science, ABC University, 2022"
   - DO NOT include multiple education entries - only the highest/most recent one
   EXAMPLE: "M.Tech in Data Science, ABC University, 2022" (if candidate has both B.Tech and M.Tech, return only M.Tech)

3. PROFILE_SUMMARY:
   EXTRACT FROM (in priority order):
   1. Dedicated sections: "Professional Summary", "Profile Summary", "Executive Summary", "About", "Overview", "Objective", "Career Objective", "Summary of Qualifications", "Professional Profile", "Career Profile"
   2. First paragraph of "Work Experience" or "Professional Experience" section
   3. Introduction paragraph at the beginning of resume
   4. If none found: Synthesize from work experience and skills (2-3 sentences)
   FORMAT: 2-4 sentences describing professional background, expertise, and career focus
   RULES:
   - MUST be 2-4 complete sentences
   - Describe: years of experience, key expertise areas, career focus/goals
   - DO NOT use "Not Found" - always synthesize if needed
   EXAMPLE: "Experienced Data Analyst with 5+ years of expertise in data visualization, statistical analysis, and business intelligence. Proficient in Python, SQL, and Tableau for transforming complex datasets into actionable insights. Strong background in predictive modeling and machine learning algorithms. Seeking to leverage analytical skills to drive data-driven decision making."

4. PROJECTS (Project1, Project2, Project3, Project4):
   EXTRACT FROM (in priority order):
   1. Dedicated "Projects" section (with project names and descriptions)
   2. "Work Experience" or "Professional Experience" sections (extract project-like technical work)
   3. "Key Projects", "Notable Projects", "Project Experience", "Technical Projects", "Recent Projects", "Project Highlights" sections
   SELECTION CRITERIA:
   - Extract up to 4 MOST RECENT projects (by date or order in resume)
   - Prioritize: Technical projects > Business projects > Academic projects
   - Project1 = MOST RECENT, Project2 = SECOND MOST RECENT, Project3 = THIRD, Project4 = FOURTH
   - If fewer than 4 projects exist, set remaining to "Not Found"
   
   FOR EACH PROJECT, EXTRACT:
   
   a) TITLE:
      - Use explicit project name/title if available in CV
      - If no explicit title, create descriptive title based on project description
      - EXCLUDE: Company name, organization name, client name, employer name
      - Format: Descriptive technical title (e.g., "E-commerce Platform Development", "Data Analytics Dashboard", "Real-time Chat Application")
      - DO NOT use generic titles like "Project 1" or "Software Development"
   
   b) DURATION:
      - Extract from project dates or associated work experience dates
      - Format: "Jan 2023 - Dec 2023" or "6 months" or "2023" or "2022-2023"
      - If no duration found, use "Not Found"
   
   c) DESCRIPTION (CRITICAL - MUST FOLLOW EXACT FORMAT):
      FORMAT REQUIREMENT: ALWAYS in bullet point format with each bullet on a new line
      - Each bullet point MUST start with "•" (bullet character)
      - Each bullet point MUST be separated by "\\n" (newline)
      - Format: "• Point 1\\n• Point 2\\n• Point 3"
      
      EXTRACTION RULES:
      - If CV has bullets (• or -): Extract EXACTLY as-is, preserve all bullets and formatting
      - If CV has paragraph: Split by sentences (., !, ?) and convert each sentence to a bullet point
      - If CV has mixed format: Convert all to bullets (one bullet per sentence or existing bullet)
      
      CONTENT RULES:
      - EXCLUDE: Company name, organization name, client name, employer name, location
      - INCLUDE: What was done, technologies used, key achievements, responsibilities, technical implementation, results/metrics
      - NO word limits - extract ALL relevant technical details
      - Preserve technical terminology, metrics, and achievements
      
      EXAMPLES:
      
      EXAMPLE 1 - CV has bullets (extract as-is):
      CV Text: "• Developed real-time analytics dashboard using Python and React
      • Implemented RESTful APIs using Flask and PostgreSQL
      • Reduced data processing time by 60% through optimization"
      Extract: "• Developed real-time analytics dashboard using Python and React\\n• Implemented RESTful APIs using Flask and PostgreSQL\\n• Reduced data processing time by 60% through optimization"
      
      EXAMPLE 2 - CV has paragraph (convert each sentence to bullet):
      CV Text: "Developed a comprehensive data analytics platform that processes over 1 million records daily. Implemented ETL pipelines using Python and Apache Spark, resulting in 60% reduction in data processing time. Created interactive dashboards with Tableau and Power BI for real-time business intelligence reporting."
      Extract: "• Developed a comprehensive data analytics platform that processes over 1 million records daily\\n• Implemented ETL pipelines using Python and Apache Spark, resulting in 60% reduction in data processing time\\n• Created interactive dashboards with Tableau and Power BI for real-time business intelligence reporting"
      
      EXAMPLE 3 - CV has mixed format (convert all to bullets):
      CV Text: "Built e-commerce platform. Key features: payment integration, inventory management, order tracking. Used React and Node.js."
      Extract: "• Built e-commerce platform\\n• Key features: payment integration, inventory management, order tracking\\n• Used React and Node.js"
      
      EXAMPLE 4 - CV has numbered list (convert to bullets):
      CV Text: "1. Designed database schema
      2. Developed API endpoints
      3. Implemented authentication"
      Extract: "• Designed database schema\\n• Developed API endpoints\\n• Implemented authentication"
   
   d) TECHNOLOGIES:
      - Extract from project description itself
      - If not in description, infer from technical details mentioned
      - Format: Comma-separated (e.g., "Python, React, Flask, PostgreSQL, Docker")
      - Include: Programming languages, frameworks, tools, platforms, databases mentioned

=== CRITICAL EXTRACTION RULES ===

1. PROFILE_SUMMARY:
   - ALWAYS extract or synthesize (never "Not Found")
   - If no dedicated section: Extract from work experience introduction
   - If still not found: Synthesize 2-3 sentences from work experience and skills
   - Must be 2-4 complete sentences

2. PROJECTS:
   - Extract up to 4 most recent projects
   - Description MUST be in bullet format with \\n separators
   - If CV has bullets: Extract exactly as-is
   - If CV has paragraph: Convert each sentence to a bullet
   - EXCLUDE all company/organization/client names from descriptions
   - Include ALL technical details (no truncation)

3. AREA_OF_EXPERTISE:
   - Extract from skills section AND project descriptions
   - Only technical skills (languages, tools, frameworks)
   - Exclude soft skills

4. EDUCATION:
   - Extract all education entries (can be multiple, separate by newline)
   - Include degree, university, year

=== OUTPUT FORMAT ===
- Return ONLY valid JSON object
- NO markdown code blocks (no ```json)
- NO explanations or additional text
- Properly escape: \\n for newlines, \\" for quotes
- Use "Not Found" ONLY if information truly does not exist (except profile_summary - always synthesize)

=== VALIDATION ===
Before returning, verify:
- JSON is valid and parseable
- All required fields present
- Project descriptions are in bullet format with \\n
- Profile summary is 2-4 sentences
- No company names in project descriptions

Resume Text:
{cv_text_sample}
"""
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            temperature=0.0,
        )
        
        response = chat_completion.choices[0].message.content.strip()
        
        # Try to parse JSON response
        try:
            # Clean response to extract JSON
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()
            
            # Find JSON object in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx].strip()
                if json_str:
                    info = json.loads(json_str)
                    
                    # Post-process and validate extracted information
                    info = _post_process_extracted_info(info, cv_text)
                    
                    # Validate required keys
                    required_keys = ['area_of_expertise', 'education', 'profile_summary', 'project1', 'project2', 'project3', 'project4']
                    for key in required_keys:
                        if key not in info:
                            if key.startswith('project'):
                                info[key] = {'title': 'Not Found', 'duration': 'Not Found', 'description': 'Not Found', 'technologies': 'Not Found'}
                            else:
                                info[key] = 'Not Found'
                    
                    # Validate project structure
                    for proj_key in ['project1', 'project2', 'project3', 'project4']:
                        if proj_key in info and isinstance(info[proj_key], dict):
                            for field in ['title', 'duration', 'description', 'technologies']:
                                if field not in info[proj_key]:
                                    info[proj_key][field] = 'Not Found'
                        else:
                            info[proj_key] = {'title': 'Not Found', 'duration': 'Not Found', 'description': 'Not Found', 'technologies': 'Not Found'}
                    
                    return info
            else:
                # Fallback: try parsing whole response
                info = json.loads(response)
                info = _post_process_extracted_info(info, cv_text)
                return info
                
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            try:
                # Try to fix unescaped newlines and quotes
                fixed_response = response.replace('\n', '\\n').replace('\r', '')
                # Try to extract JSON again
                start_idx = fixed_response.find('{')
                end_idx = fixed_response.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = fixed_response[start_idx:end_idx].strip()
                    info = json.loads(json_str)
                    info = _post_process_extracted_info(info, cv_text)
                    return info
            except:
                pass
            
            # Fallback extraction using regex patterns
            return extract_cv_info_fallback(cv_text)
            
    except Exception as e:
        st.error(f"Error extracting CV information: {str(e)}")
        return extract_cv_info_fallback(cv_text)


def _post_process_extracted_info(info, cv_text):
    """Post-process and validate extracted information
    
    Args:
        info: Dictionary with extracted CV information
        cv_text: Original CV text for fallback extraction
    
    Returns:
        Validated and improved info dictionary
    """
    if not info:
        return info
    
    # Normalize "Not Found" variations
    not_found_variations = ['Not Found', 'not found', 'NOT FOUND', 'N/A', 'n/a', 'NA', 'na', '', None]
    
    # Validate and improve profile_summary
    profile_summary = info.get('profile_summary', '')
    if not profile_summary or str(profile_summary).strip() in not_found_variations:
        # Try to extract summary from CV text using fallback
        summary = _extract_summary_fallback(cv_text)
        if summary:
            info['profile_summary'] = summary
        else:
            info['profile_summary'] = 'Not Found'
    else:
        # Clean up profile_summary
        profile_summary = str(profile_summary).strip()
        # Remove excessive whitespace
        profile_summary = re.sub(r'\s+', ' ', profile_summary)
        # Ensure it's not too short (at least 20 characters)
        if len(profile_summary) < 20:
            summary = _extract_summary_fallback(cv_text)
            if summary:
                info['profile_summary'] = summary
        else:
            info['profile_summary'] = profile_summary
    
    # Validate and improve projects
    for proj_key in ['project1', 'project2']:
        if proj_key in info and isinstance(info[proj_key], dict):
            proj = info[proj_key]
            title = str(proj.get('title', '')).strip()
            description = str(proj.get('description', '')).strip()
            
            # If project title is missing or "Not Found", try to extract
            if not title or title in not_found_variations:
                # Try to extract from description or CV text
                if description and description not in not_found_variations:
                    # Extract first few words as title
                    title_words = description.split()[:5]
                    proj['title'] = ' '.join(title_words)
                else:
                    proj['title'] = 'Not Found'
            else:
                proj['title'] = title
            
            # Validate description
            if not description or description in not_found_variations:
                proj['description'] = 'Not Found'
            else:
                # Clean up description
                description = re.sub(r'\s+', ' ', description)
                # Ensure bullet points are properly formatted
                if '•' not in description and '\n' in description:
                    # Convert newlines to bullet points if needed
                    lines = [line.strip() for line in description.split('\n') if line.strip()]
                    if len(lines) > 1:
                        proj['description'] = '\n'.join([f"• {line}" if not line.startswith('•') else line for line in lines])
                    else:
                        proj['description'] = description
                else:
                    proj['description'] = description
            
            # Validate duration
            duration = str(proj.get('duration', '')).strip()
            if not duration or duration in not_found_variations:
                proj['duration'] = 'Not Found'
            else:
                proj['duration'] = duration
            
            # Validate technologies
            technologies = str(proj.get('technologies', '')).strip()
            if not technologies or technologies in not_found_variations:
                proj['technologies'] = 'Not Found'
            else:
                proj['technologies'] = technologies
        else:
            info[proj_key] = {'title': 'Not Found', 'duration': 'Not Found', 'description': 'Not Found', 'technologies': 'Not Found'}
    
    # Validate area_of_expertise
    expertise = info.get('area_of_expertise', '')
    if not expertise or str(expertise).strip() in not_found_variations:
        expertise = _extract_skills_fallback(cv_text)
        if expertise:
            info['area_of_expertise'] = expertise
        else:
            info['area_of_expertise'] = 'Not Found'
    else:
        info['area_of_expertise'] = str(expertise).strip()
    
    # Validate education
    education = info.get('education', '')
    if not education or str(education).strip() in not_found_variations:
        education = _extract_education_fallback(cv_text)
        if education:
            info['education'] = education
        else:
            info['education'] = 'Not Found'
    else:
        info['education'] = str(education).strip()
    
    return info


def _extract_summary_fallback(cv_text):
    """Extract profile summary from CV text using pattern matching"""
    if not cv_text:
        return None
    
    # Look for summary section headers
    summary_keywords = [
        'professional summary', 'profile summary', 'executive summary', 
        'about', 'overview', 'objective', 'career objective', 
        'summary of qualifications', 'professional profile', 'career profile'
    ]
    
    lines = cv_text.split('\n')
    summary_lines = []
    in_summary = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        # Check if this line is a section header
        if any(keyword in line_lower for keyword in summary_keywords) and len(line) < 100:
            in_summary = True
            continue
        elif in_summary:
            if line.strip():
                # Stop if we hit another section (all caps or common section headers)
                if line.isupper() and len(line) < 50:
                    break
                if any(keyword in line_lower for keyword in ['experience', 'education', 'skills', 'projects', 'work history']):
                    break
                # Collect summary lines (reasonable length)
                if len(line.strip()) < 300:
                    summary_lines.append(line.strip())
                    if len(summary_lines) >= 4:  # Max 4 sentences
                        break
            else:
                # Empty line might indicate end of summary
                if summary_lines:
                    break
    
    if summary_lines:
        summary = ' '.join(summary_lines)
        # Clean up
        summary = re.sub(r'\s+', ' ', summary).strip()
        if len(summary) >= 20:
            return summary
    
    # Fallback: extract first paragraph of work experience
    experience_keywords = ['experience', 'work experience', 'professional experience', 'employment']
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in experience_keywords) and len(line) < 100:
            # Get next 2-3 non-empty lines
            summary_lines = []
            for j in range(i+1, min(i+4, len(lines))):
                if lines[j].strip() and len(lines[j].strip()) < 300:
                    summary_lines.append(lines[j].strip())
            if summary_lines:
                summary = ' '.join(summary_lines)
                summary = re.sub(r'\s+', ' ', summary).strip()
                if len(summary) >= 20:
                    return summary
    
    return None


def _extract_skills_fallback(cv_text):
    """Extract technical skills from CV text"""
    if not cv_text:
        return None
    
    skills_keywords = ['skills', 'technical skills', 'expertise', 'technologies', 'competencies', 'technical competencies']
    lines = cv_text.split('\n')
    skills_found = []
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in skills_keywords):
            # Extract skills from this line and next few lines
            for j in range(i, min(i+10, len(lines))):
                skill_line = lines[j]
                # Extract technical terms (capitalized words, common tech terms)
                tech_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+)?)\b'
                matches = re.findall(tech_pattern, skill_line)
                for match in matches:
                    # Filter out common non-tech words
                    if match.lower() not in ['the', 'and', 'with', 'from', 'this', 'that', 'for', 'are', 'was', 'were']:
                        if len(match.split()) <= 3 and len(match) > 2:
                            if match not in skills_found:
                                skills_found.append(match)
                if len(skills_found) >= 15:  # Limit to 15 skills
                    break
            break
    
    if skills_found:
        return ', '.join(skills_found[:15])
    return None


def _extract_education_fallback(cv_text):
    """Extract education from CV text"""
    if not cv_text:
        return None
    
    education_keywords = ['education', 'qualification', 'degree', 'university', 'college', 'bachelor', 'master', 'phd', 'academic']
    lines = cv_text.split('\n')
    education_lines = []
    in_education = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in education_keywords) and len(line) < 100:
            in_education = True
            education_lines.append(line.strip())
        elif in_education and line.strip():
            if len(line.strip()) < 150:
                education_lines.append(line.strip())
            else:
                break
            if len(education_lines) >= 5:
                break
    
    if education_lines:
        return ' | '.join(education_lines[:5])
    return None


def extract_cv_info_fallback(cv_text):
    """Fallback extraction using regex patterns if LLM fails"""
    info = {
        'area_of_expertise': 'Not Found',
        'education': 'Not Found',
        'profile_summary': 'Not Found',
        'project1': {'title': 'Not Found', 'duration': 'Not Found', 'description': 'Not Found', 'technologies': 'Not Found'},
        'project2': {'title': 'Not Found', 'duration': 'Not Found', 'description': 'Not Found', 'technologies': 'Not Found'}
    }
    
    # Extract Education (look for education section)
    education_keywords = ['education', 'qualification', 'degree', 'university', 'college', 'bachelor', 'master', 'phd']
    lines = cv_text.split('\n')
    education_lines = []
    in_education = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in education_keywords) and len(line) < 100:
            in_education = True
            education_lines.append(line.strip())
        elif in_education and line.strip():
            if len(line.strip()) < 150:  # Reasonable education line length
                education_lines.append(line.strip())
            else:
                break
    
    if education_lines:
        info['education'] = ' | '.join(education_lines[:5])  # Limit to 5 lines
    
    # Extract Profile Summary (look for summary/objective section)
    summary_keywords = ['summary', 'objective', 'profile', 'about', 'overview']
    summary_lines = []
    in_summary = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in summary_keywords) and len(line) < 100:
            in_summary = True
        elif in_summary and line.strip():
            if len(line.strip()) < 300:  # Reasonable summary line length
                summary_lines.append(line.strip())
            if len(summary_lines) >= 3:  # Limit to 3 lines
                break
    
    if summary_lines:
        info['profile_summary'] = ' '.join(summary_lines)
    
    # Extract Technical Skills (look for skills section)
    skills_keywords = ['skill', 'expertise', 'technology', 'proficient', 'competent']
    skills_found = []
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in skills_keywords):
            # Look for skills in this line and next few lines
            for j in range(i, min(i + 5, len(lines))):
                skill_line = lines[j]
                # Extract common technical terms (1-3 words)
                tech_pattern = r'\b([A-Z][a-z]*(?:\s+[A-Z][a-z]*)?(?:\s+[A-Z][a-z]*)?)\b'
                matches = re.findall(tech_pattern, skill_line)
                for match in matches:
                    if len(match.split()) <= 3 and len(match) > 2:
                        skills_found.append(match)
                if len(skills_found) >= 10:  # Limit to 10 skills
                    break
            break
    
    if skills_found:
        info['area_of_expertise'] = ', '.join(skills_found[:10])
    
    return info

