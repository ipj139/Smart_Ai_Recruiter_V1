"""
LLM-powered extraction functions for job descriptions and resumes
"""
import streamlit as st
import re
import json
from datetime import datetime
from utils_v2.client_helper import get_llm_client


def extract_position_from_jd(job_description, api_key, model_name, base_url=None):
    """Extract position/job title from job description - fast check first, then LLM, then regex
    
    Args:
        job_description: Job description text
        api_key: API key for LLM provider
        model_name: Model name to use
        base_url: Optional base URL for API. If not provided, auto-detects from API key
    """
    if not job_description or not job_description.strip():
        return "Not Found"
    
    # Quick check: look at first non-empty line - often the job title is right there
    lines = [line.strip() for line in job_description.split('\n') if line.strip()]
    if lines:
        first_line = lines[0]
        if len(first_line) <= 60:  # Reasonable length for a title
            words = first_line.split()
            if 2 <= len(words) <= 5:  # Typical job title length
                job_keywords = ['Developer', 'Engineer', 'Analyst', 'Manager', 'Specialist', 'Consultant', 
                               'Lead', 'Architect', 'Scientist', 'Designer', 'Executive', 'Assistant', 
                               'Coordinator', 'Director', 'Administrator', 'Tester', 'Programmer']
                first_line_lower = first_line.lower()
                for keyword in job_keywords:
                    if keyword.lower() in first_line_lower:
                        # This looks like a job title - return it
                        return ' '.join(word.capitalize() for word in words)
    
    # Try LLM extraction if API key available
    if api_key:
        try:
            # Use unified client (works with any OpenAI-compatible API)
            client = get_llm_client(api_key, base_url)
            
            prompt = f"""Extract the job title from this job description. Return ONLY the job title (e.g., "Data Analyst", "Java Developer"). If not found, return "Not Found".

{job_description[:2500]}

Job Title:"""
            
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0.0,
            )
            
            response = chat_completion.choices[0].message.content.strip()
            position = response.split('\n')[0].strip().strip('"\'')
            
            if position and len(position) >= 2 and len(position) <= 50 and 'not found' not in position.lower():
                return position
        except:
            pass
    
    # Regex fallback - search for job title patterns in first 10 lines
    header_text = '\n'.join(lines[:10]) if len(lines) > 0 else job_description[:500]
    job_keywords = ['Developer', 'Engineer', 'Analyst', 'Manager', 'Specialist', 'Consultant', 
                   'Lead', 'Architect', 'Scientist', 'Designer', 'Executive', 'Assistant', 
                   'Coordinator', 'Director', 'Administrator', 'Tester', 'Programmer']
    
    for line in lines[:10]:
        if len(line) > 60:
            continue
        words = line.split()
        if 2 <= len(words) <= 5:
            line_lower = line.lower()
            for keyword in job_keywords:
                if keyword.lower() in line_lower:
                    return ' '.join(word.capitalize() for word in words)
    
    # Final regex pattern search
    pattern = r'\b([A-Za-z]+(?:\s+[A-Za-z]+){0,2}\s+(?:Developer|Engineer|Analyst|Manager|Specialist|Consultant|Lead|Architect|Scientist|Designer|Executive|Assistant|Coordinator|Director|Administrator|Tester|Programmer))\b'
    match = re.search(pattern, job_description[:500], re.IGNORECASE)
    if match:
        return ' '.join(word.capitalize() for word in match.group(1).split())
    
    return "Not Found"


def extract_candidate_details_llm(resume_text, api_key, model_name, base_url=None):
    """Extract candidate details using LLM
    
    Args:
        resume_text: Resume text
        api_key: API key for LLM provider
        model_name: Model name to use
        base_url: Optional base URL for API. If not provided, auto-detects from API key
    """
    if not resume_text:
        return None
    
    # Use unified client (works with any OpenAI-compatible API)
    client = get_llm_client(api_key, base_url)
    
    prompt = f"""
    You are a resume parser. Extract the following information from the resume text below and return ONLY a valid JSON object.

    Required JSON format:
    {{
        "Candidate_Name": "extract the full name",
        "Contact_Number": "extract phone number",
        "Email_ID": "extract email address", 
        "Total_Experience": "extract years of experience",
        "Location": "extract city/state/country"
    }}

    IMPORTANT RULES:
    1. Return ONLY the JSON object, no explanations or additional text
    2. If information is not found, use "Not Found" as the value
    3. For experience, format as "X years" (e.g., "3 years", "5 years")
    4. For email extraction, search thoroughly throughout the entire resume text:
       - Check header/contact section first
       - Look for email patterns like: user@domain.com
       - Also check for obfuscated emails like: user[at]domain[dot]com or user(at)domain(dot)com
       - Email can appear anywhere in the resume (header, footer, signature, contact section)
    5. For location, extract the most relevant location mentioned
    6. Ensure the JSON is valid and properly formatted

    Resume Text:
    {resume_text[:5000]}
    """
    
    try:
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

            # If the model returned an empty/blank response, fall back silently
            if not response or not response.strip():
                raise json.JSONDecodeError("empty response", response, 0)

            # Try to find JSON object in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx].strip()
                if not json_str:
                    raise json.JSONDecodeError("no json object found", json_str, 0)
                details = json.loads(json_str)
            else:
                # Fall back to parsing the whole response only if non-empty
                details = json.loads(response)
            
            # Validate required keys
            required_keys = ['Candidate_Name', 'Contact_Number', 'Email_ID', 'Total_Experience', 'Location']
            for key in required_keys:
                if key not in details:
                    details[key] = 'Not Found'
            
            # Add additional fields
            details['Resume_Screening_Status'] = 'Shortlisted'
            details['Screening_Date'] = datetime.now().strftime('%Y-%m-%d')
            
            return details
            
        except json.JSONDecodeError:
            # Quiet fallback: do not surface low-level JSON errors to the UI
            return extract_details_fallback(resume_text)
            
    except Exception as e:
        st.error(f"Error extracting candidate details: {str(e)}")
        return extract_details_fallback(resume_text)


def extract_details_fallback(resume_text):
    """Fallback extraction using regex patterns"""
    details = {
        'Candidate_Name': 'Not Found',
        'Contact_Number': 'Not Found', 
        'Email_ID': 'Not Found',
        'Total_Experience': 'Not Found',
        'Location': 'Not Found',
        'Resume_Screening_Status': 'Shortlisted',
        'Screening_Date': datetime.now().strftime('%Y-%m-%d')
    }
    
    # Extract Name (first few lines, capitalized words)
    lines = resume_text.split('\n')[:5]
    for line in lines:
        line = line.strip()
        if len(line) > 0:
            # Remove common titles
            clean_line = re.sub(r'\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Sir|Madam)\b', '', line, flags=re.IGNORECASE)
            clean_line = clean_line.strip()
            
            # Check if it looks like a name (2-3 words, title case, no numbers)
            words = clean_line.split()
            if 2 <= len(words) <= 3 and all(word.isalpha() and word[0].isupper() for word in words):
                details['Candidate_Name'] = clean_line
                break
    
    # Extract Email - improved pattern to catch more formats
    email_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Standard email
        r'\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email with spaces around @
        r'\b[A-Za-z0-9._%+-]+\[at\][A-Za-z0-9.-]+\[dot\][A-Z|a-z]{2,}\b',  # Obfuscated email [at] and [dot]
        r'\b[A-Za-z0-9._%+-]+\s*\(at\)\s*[A-Za-z0-9.-]+\s*\(dot\)\s*[A-Z|a-z]{2,}\b',  # Obfuscated (at) and (dot)
    ]
    
    # Search in the entire resume text (not just first few lines)
    for pattern in email_patterns:
        email_matches = re.finditer(pattern, resume_text, re.IGNORECASE)
        for match in email_matches:
            email = match.group()
            # Clean up email (remove spaces around @)
            email = re.sub(r'\s*@\s*', '@', email)
            # Replace [at] and [dot] patterns
            email = email.replace('[at]', '@').replace('[dot]', '.')
            email = email.replace('(at)', '@').replace('(dot)', '.')
            # Basic validation
            if '@' in email and '.' in email.split('@')[1] and len(email) > 5:
                details['Email_ID'] = email
                break
        if details['Email_ID'] != 'Not Found':
            break
    
    # Also try searching in first 30 lines more carefully (header section)
    if details['Email_ID'] == 'Not Found':
        header_lines = resume_text.split('\n')[:30]
        header_text = '\n'.join(header_lines)
        for pattern in email_patterns[:1]:  # Use standard pattern for header
            email_match = re.search(pattern, header_text, re.IGNORECASE)
            if email_match:
                email = email_match.group()
                email = re.sub(r'\s*@\s*', '@', email)
                if '@' in email and '.' in email.split('@')[1]:
                    details['Email_ID'] = email
                    break
    
    # Extract Phone Number - improved patterns
    phone_patterns = [
        r'\+?\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{6,10}\b',  # International format like +91-9686331380 or +1-123-456-7890
        r'\b\+?\d{1,3}[-.\s]?\d{10}\b',  # Format like +91-9876543210 or +1-9876543210
        r'\b\d{10}\b',  # 10 digits (Indian format)
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US format 123-456-7890
        r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',  # General international with parentheses
    ]
    
    # Search in entire resume, but prioritize header section
    for pattern in phone_patterns:
        # First try header section (first 30 lines)
        header_lines = resume_text.split('\n')[:30]
        header_text = '\n'.join(header_lines)
        phone_match = re.search(pattern, header_text)
        if phone_match:
            phone = phone_match.group().strip()
            # Clean up phone number (keep format but normalize)
            phone = re.sub(r'\s+', '-', phone)  # Replace spaces with dash
            details['Contact_Number'] = phone
            break
    
    # If not found in header, search entire resume
    if details['Contact_Number'] == 'Not Found':
        for pattern in phone_patterns:
            phone_match = re.search(pattern, resume_text)
            if phone_match:
                phone = phone_match.group().strip()
                phone = re.sub(r'\s+', '-', phone)  # Replace spaces with dash
                details['Contact_Number'] = phone
                break
    
    # Extract Experience
    experience_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
        r'(?:experience|exp)[:\s]*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)',
    ]
    
    for pattern in experience_patterns:
        exp_match = re.search(pattern, resume_text, re.IGNORECASE)
        if exp_match:
            details['Total_Experience'] = f"{exp_match.group(1)} years"
            break
    
    # Extract Location
    location_keywords = ['location', 'address', 'based in', 'residing in', 'from']
    lines = resume_text.split('\n')
    
    for line in lines:
        line_lower = line.lower()
        for keyword in location_keywords:
            if keyword in line_lower:
                location_text = line.strip()
                if ':' in location_text:
                    location_text = location_text.split(':')[1].strip()
                
                # Clean up location
                location_text = re.sub(r'[^\w\s,]', '', location_text)
                if len(location_text) > 2 and len(location_text) < 50:
                    details['Location'] = location_text
                    break
        
        if details['Location'] != 'Not Found':
            break
    
    return details


def extract_evaluation_points(job_desc, api_key, model_name, base_url=None):
    """Extract all possible evaluation points/criteria from job description
    
    Args:
        job_desc: Job description text
        api_key: API key for LLM provider
        model_name: Model name to use
        base_url: Optional base URL for API. If not provided, auto-detects from API key
    """
    if not job_desc or not job_desc.strip():
        return []
    
    if not api_key:
        return []
    
    try:
        # Use unified client (works with any OpenAI-compatible API)
        client = get_llm_client(api_key, base_url)
        
        prompt = f"""Extract all possible evaluation criteria/points from the following job description. 
List each evaluation point as a separate, concise criterion that can be used to assess a candidate's resume.

For example:
- Technical Skills: Python, SQL, Data Analysis
- Experience Level: 3+ years
- Education: Bachelor's degree in Computer Science
- Certifications: AWS, Azure
- Location: Remote or New York
- Domain Knowledge: Banking/Finance
- Tools: Git, Docker, Kubernetes

Job Description:
{job_desc[:3000]}

Return ONLY a numbered list of evaluation criteria (one per line), with no explanations or additional text.
Each criterion should be specific and measurable. Format as:
1. [Criterion 1]
2. [Criterion 2]
3. [Criterion 3]
...
"""
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            temperature=0.0,
        )
        
        response = chat_completion.choices[0].message.content.strip()
        
        # Parse the response into a list of evaluation points
        points = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove numbering (e.g., "1. ", "1)", "- ", "* ")
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            line = re.sub(r'^[-•*]\s*', '', line)
            line = line.strip()
            
            # Remove markdown formatting
            line = re.sub(r'\*\*|\*|_', '', line)
            
            if line and len(line) > 3:  # Minimum length check
                points.append(line)
        
        return points if points else []
        
    except Exception as e:
        st.error(f"Error extracting evaluation points: {str(e)}")
        return []

