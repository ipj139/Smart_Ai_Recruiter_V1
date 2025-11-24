"""
Home Page - Project Information and Overview
"""
import streamlit as st

# Page title
st.title("🏠 Smart AI Recruiter - Home")

st.markdown("---")

# Project Overview
st.header("📋 Project Overview")
st.markdown("""
**Smart AI Recruiter** is an intelligent resume screening application that leverages 
Artificial Intelligence and Large Language Models (LLMs) to automate and enhance the 
recruitment process. The application analyzes candidate resumes against job descriptions 
to provide comprehensive evaluation reports and similarity scores.
""")

# Key Features
st.header("✨ Key Features")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **🤖 AI-Powered Analysis**
    - LLM-based resume evaluation
    - Detailed scoring and feedback
    - Multi-criteria assessment
    
    **📊 Similarity Scoring**
    - BERT-based semantic similarity
    - ATS (Applicant Tracking System) compatibility
    - Quantitative match scores
    """)

with col2:
    st.markdown("""
    **📝 Document Processing**
    - PDF, DOC, DOCX support
    - Automatic text extraction
    - Batch processing capability
    
    **📈 Candidate Tracking**
    - Excel-based tracker system
    - Duplicate detection
    - Status management
    """)

st.markdown("---")

# Technology Stack
st.header("🛠️ Technology Stack")
st.markdown("""
- **Frontend**: Streamlit (Python Web Framework)
- **LLM Providers**: Groq, OpenRouter
- **NLP Models**: 
  - Sentence Transformers (BERT-based embeddings)
  - Various LLM models (Llama, GPT, etc.)
- **Text Processing**: 
  - pdfminer, PyPDF (PDF extraction)
  - docx2txt (DOCX extraction)
  - olefile (Legacy DOC extraction)
- **Data Management**: 
  - Pandas (Excel operations)
  - Session state management
""")

st.markdown("---")

# How It Works
st.header("🔄 How It Works")
st.markdown("""
1. **Input Job Description**: Upload or paste the job description
2. **Extract Evaluation Criteria**: AI automatically extracts key evaluation points
3. **Upload Resume(s)**: Single or batch resume processing
4. **AI Analysis**: 
   - Calculate similarity score using BERT embeddings
   - Generate detailed evaluation report using LLM
   - Extract candidate information
5. **Review & Decision**: Review results and shortlist/reject candidates
6. **Track Candidates**: Automatically update Excel tracker with candidate details
""")

st.markdown("---")

# Pages Navigation
st.header("📑 Application Pages")
st.markdown("""
- **🏠 Home**: Project information and overview (current page)
- **🔍 Screener**: Main resume screening functionality
- **🔄 Converter**: Document conversion tools (coming soon)
""")

st.info("💡 **Tip**: Navigate to the **Screener** page to start analyzing resumes!")

st.markdown("---")

# Usage Instructions
st.header("📖 Quick Start Guide")
with st.expander("Click to view step-by-step instructions"):
    st.markdown("""
    ### Step 1: Configure Settings
    - Go to the **Screener** page
    - In the sidebar, select your LLM provider (Groq or OpenRouter)
    - Enter your API key
    - Select the model you want to use
    
    ### Step 2: Enter Client Information
    - Enter the client name (e.g., HSBC, Unilever)
    - Optionally enter vendor name and profile shared date
    
    ### Step 3: Provide Job Description
    - Choose between text input or document upload
    - Wait for evaluation criteria to be extracted automatically
    
    ### Step 4: Select Evaluation Criteria
    - Review the extracted evaluation points
    - Select which criteria to use for assessment
    - Set the minimum experience requirement
    
    ### Step 5: Upload Resume(s)
    - Choose between Single or Batch processing
    - Select Experiment or Production method
    - Upload resume file(s)
    
    ### Step 6: Analyze
    - Click the "Analyze" button
    - Review the similarity score and detailed report
    - Make shortlist/reject decisions
    
    ### Step 7: Track Candidates
    - Candidates are automatically saved to Excel tracker
    - CVs are organized in folder structure
    - Duplicate detection prevents re-processing
    """)

st.markdown("---")

# Footer
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Smart AI Recruiter v1.0 | Built with ❤️ using Streamlit</p>
</div>
""", unsafe_allow_html=True)

