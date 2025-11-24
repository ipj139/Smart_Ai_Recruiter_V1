"""
Screener Page - Main Resume Screening Functionality
This page contains all the resume screening logic from the original main.py
"""
import streamlit as st
import re
import os
import requests
from dotenv import load_dotenv

# Import utility functions with error handling
try:
    from utils_v2.text_extraction import extract_resume_text, extract_jd_text
    from utils_v2.llm_functions import (
        extract_position_from_jd,
        extract_candidate_details_llm,
        extract_evaluation_points
    )
    from utils_v2.analysis import (
        calculate_similarity_bert,
        get_report,
        extract_scores,
        extract_summary_from_report,
        extract_failed_points_explanations,
        process_single_resume
    )
    from utils_v2.tracker import (
        check_candidate_status_in_tracker,
        update_tracker_excel
    )
except ImportError as e:
    st.error(f"❌ Import Error: {str(e)}")
    st.stop()

# Load environment variables from .env
load_dotenv()

# Helper function for Production Method auto-decision
def apply_production_auto_decision(result, similarity_threshold, average_threshold):
    """Apply auto-decision logic for Production Method based on thresholds"""
    similarity_score = result.get('similarity_score', 0.0)
    average_score = result.get('average_score', 0.0)
    
    # Check if both thresholds are met
    if similarity_score >= similarity_threshold and average_score >= average_threshold:
        decision = "Shortlisted"
    else:
        decision = "Rejected"
    
    return decision

def execute_production_auto_decision(result, decision, selected_base_folder, vendor_name, profile_shared_date, admin_override):
    """Execute the auto-decision by shortlisting or rejecting the candidate"""
    try:
        position_val = result.get('position', 'Not Found')
        if not position_val or position_val == 'Not Found':
            job_desc = st.session_state.get('job_desc', '') or ''
            if job_desc and job_desc.strip() and st.session_state.api_key:
                try:
                    position_val = extract_position_from_jd(
                        job_desc,
                        st.session_state.api_key,
                        st.session_state.model_name,
                        st.session_state.base_url
                    )
                except:
                    position_val = 'Not Found'
        
        if not selected_base_folder or not selected_base_folder.strip():
            return False, "Base folder path required"
        
        # Validate that the base folder exists
        if not os.path.exists(selected_base_folder) or not os.path.isdir(selected_base_folder):
            return False, f"Base folder does not exist: {selected_base_folder}"
        
        position_clean = re.sub(r'[^\w\s-]', '', position_val)
        position_clean = position_clean.replace(' ', '_').strip('_')
        if not position_clean or position_clean == 'Not_Found':
            position_clean = "Not_Found"
        
        position_folder = f"{position_clean}_Candidates"
        # Use absolute path for base folder
        base_folder_abs = os.path.abspath(selected_base_folder)
        folder_name = os.path.join(base_folder_abs, position_folder)
        os.makedirs(folder_name, exist_ok=True)
        
        candidate_details = result.get('candidate_details')
        if not candidate_details:
            return False, "Could not extract candidate details"
        
        candidate_details['Position'] = position_val if position_val and position_val != 'Not Found' else 'Not Found'
        candidate_name = candidate_details.get('Candidate_Name', 'Unknown')
        
        # Check if candidate already exists
        exists, current_status, duplicate_reason, _ = check_candidate_status_in_tracker(
            candidate_details, folder_name, vendor_name
        )
        
        if exists:
            if duplicate_reason.endswith("_same_vendor"):
                return False, f"Already screened with status: {current_status}"
            elif duplicate_reason.endswith("_different_vendor"):
                # Different vendor - add as duplicate profile
                full_report = result.get('report', '')
                if decision == "Shortlisted":
                    feedback = extract_summary_from_report(full_report) if full_report else ''
                else:
                    feedback = extract_failed_points_explanations(full_report) if full_report else ''
                
                similarity_score_val = result.get('similarity_score', 0.0)
                average_score_val = result.get('average_score', 0.0)
                file_path = ""
                
                excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                    candidate_details,
                    tracker_type="rejected",
                    folder_name=folder_name,
                    feedback=feedback,
                    similarity_score=similarity_score_val,
                    average_score=average_score_val,
                    cv_path=file_path,
                    vendor_name=vendor_name,
                    profile_shared_date=profile_shared_date,
                    allow_status_change=admin_override
                )
                
                if added:
                    return True, "Added as Duplicate Profile"
                else:
                    return False, f"Could not add: {duplicate_reason_ret}"
            else:
                return False, f"Already screened with status: {current_status}"
        
        # New candidate - proceed with auto-decision
        full_report = result.get('report', '')
        if decision == "Shortlisted":
            feedback = extract_summary_from_report(full_report) if full_report else ''
        else:
            feedback = extract_failed_points_explanations(full_report) if full_report else ''
        
        similarity_score_val = result.get('similarity_score', 0.0)
        average_score_val = result.get('average_score', 0.0)
        file_path = ""
        
        # Save CV if shortlisted
        if decision == "Shortlisted":
            resume_file_obj = result.get('resume_file_obj')
            if resume_file_obj:
                candidate_name_clean = re.sub(r'[^\w\s-]', '', candidate_name)
                candidate_name_clean = candidate_name_clean.replace(' ', '_').strip('_')
                if not candidate_name_clean:
                    candidate_name_clean = "Unknown"
                
                file_extension = os.path.splitext(resume_file_obj.name)[1]
                new_filename = f"{position_clean}_{candidate_name_clean}{file_extension}"
                
                shortlisted_folder = os.path.join(folder_name, "Shortlisted")
                os.makedirs(shortlisted_folder, exist_ok=True)
                file_path = os.path.join(shortlisted_folder, new_filename)
                file_path = os.path.abspath(file_path)
                
                resume_file_obj.seek(0)
                with open(file_path, "wb") as f:
                    f.write(resume_file_obj.getbuffer())
        
        tracker_type = "shortlisted" if decision == "Shortlisted" else "rejected"
        excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
            candidate_details,
            tracker_type=tracker_type,
            folder_name=folder_name,
            feedback=feedback,
            similarity_score=similarity_score_val,
            average_score=average_score_val,
            cv_path=file_path,
            vendor_name=vendor_name,
            profile_shared_date=profile_shared_date,
            allow_status_change=admin_override
        )
        
        if added:
            return True, f"Successfully {decision.lower()}"
        else:
            return False, f"Could not add: {duplicate_reason_ret}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

# Session States to store values - Optimized batch initialization
_default_session_state = {
    "form_submitted": False,
    "resume": "",
    "job_desc": "",
    "api_key": "",
    "model_name": "",
    "base_url": "",
    "similarity_score": 0.0,
    "average_score": 0.0,
    "report": "",
    "report_scores": [],
    "evaluation_points": [],
    "selected_evaluation_points": [],
    "prev_jd_method": "",
    "processing_mode": "Single Resume Processing",
    "experiment_processing_mode": "Single Resume Processing",
    "production_processing_mode": "Single Resume Processing",
    "batch_results": [],
    "experiment_batch_results": [],
    "production_batch_results": [],
    "batch_processing_complete": False,
    "experiment_batch_processing_complete": False,
    "production_batch_processing_complete": False,
    "experiment_resume_file": None,
    "production_resume_file": None,
    "experiment_resume_files": None,
    "production_resume_files": None,
    "experiment_form_submitted": False,
    "production_form_submitted": False,
    "experience_requirement": "1 year and above",
    "analysis_method": "Experiment Method",
    "experiment_batch_button_states": {},
    "production_batch_button_states": {},
    "experiment_single_button_state": None,
    "production_single_button_state": None,
    "show_thanking_note_single": False,
    "show_thanking_note_batch": False,
    "production_similarity_threshold": 0.7,
    "production_average_threshold": 0.6,
    "production_auto_decisions": {},
}

# Initialize session state efficiently
for key, default_value in _default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# Initialize base_url if not present
if "base_url" not in st.session_state:
    st.session_state.base_url = ""

# Page title (for Screener page)
st.title("🔍 Screener - Resume Analysis")

# Inject global CSS for button color customization
st.markdown("""
<style>
    /* Green button for shortlisted state */
    button[data-testid="baseButton-primary"][aria-label*="shortlist"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
        color: white !important;
    }
    
    /* Red button for rejected state */
    button[data-testid="baseButton-primary"][aria-label*="reject"] {
        background-color: #dc3545 !important;
        border-color: #dc3545 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# <--------- Starting the Work Flow --------->

# Initialize selected_base_folder in session state if not present (replaces client_name)
if "selected_base_folder" not in st.session_state:
    st.session_state.selected_base_folder = ""

# Initialize vendor_name and profile_shared_date in session state
if "vendor_name" not in st.session_state:
    st.session_state.vendor_name = ""
if "profile_shared_date" not in st.session_state:
    st.session_state.profile_shared_date = None

# Sidebar controls for API key and model selection (Generalized Approach)
with st.sidebar:
    st.subheader("LLM Settings")
    st.caption("💡 Works with any OpenAI-compatible API provider")
    
    # API Key input
    st.session_state.api_key = st.text_input(
        "API Key", 
        value=st.session_state.api_key, 
        type="password",
        help="Enter your API key (e.g., Groq: gsk_..., OpenRouter: sk-or-..., OpenAI: sk-...)"
    )
    
    # Model Name input
    st.session_state.model_name = st.text_input(
        "Model Name",
        value=st.session_state.model_name,
        placeholder="e.g., llama-3.3-70b-versatile, gpt-4, openai/gpt-oss-20b:free",
        help="Enter the exact model name as required by your API provider"
    )
    
    # Base URL input (optional, with auto-detection)
    base_url_input = st.text_input(
        "Base URL (Optional)",
        value=st.session_state.base_url if st.session_state.base_url else "",
        placeholder="Auto-detected from API key if empty",
        help="Leave empty for auto-detection. Examples: https://api.groq.com/openai/v1, https://openrouter.ai/api/v1"
    )
    st.session_state.base_url = base_url_input.strip() if base_url_input and base_url_input.strip() else None
    
    # Show detected base URL if auto-detection is used
    if not st.session_state.base_url and st.session_state.api_key:
        from utils_v2.client_helper import detect_base_url
        detected_url = detect_base_url(st.session_state.api_key)
        st.caption(f"🔍 Auto-detected: `{detected_url}`")
    
    # Admin Override Option
    st.markdown("---")
    st.caption("⚙️ **Admin Settings**")
    st.session_state.admin_override = st.checkbox(
        "Allow Status Change Override", 
        value=st.session_state.get('admin_override', False),
        help="⚠️ Enable this to allow changing candidate status if already processed (for error correction). First come first serve is disabled when enabled."
    )

# Base Folder Selection Section (replaces Client Name Input)
st.subheader("Folder Selection")
st.caption("💡 Select an existing folder from your system. Subfolders (_Candidates, Shortlisted, Tracker, Converted_CVs) will be created within the selected folder.")

base_folder_input = st.text_input(
    "Enter Base Folder Path", 
    value=st.session_state.selected_base_folder, 
    placeholder="C:\\Users\\YourName\\Documents\\Recruitment or /home/user/documents/recruitment",
    help="Enter the full path to an existing folder. You can paste the path from Windows Explorer or File Manager."
)

# Validate and normalize folder path
if base_folder_input:
    folder_path = base_folder_input.strip()
    # Normalize the path (handles both Windows and Unix paths)
    folder_path = os.path.normpath(folder_path)
    
    # Check if folder exists
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Convert to absolute path
        folder_path = os.path.abspath(folder_path)
        st.session_state.selected_base_folder = folder_path
        st.success(f"✅ Selected folder: {folder_path}")
    else:
        st.error(f"⚠️ Folder does not exist: {folder_path}")
        st.info("💡 Please enter a valid folder path. You can copy the path from Windows Explorer (right-click folder → Properties → Location) or File Manager.")
        st.session_state.selected_base_folder = ""
else:
    st.session_state.selected_base_folder = ""

# Vendor Information Section
st.markdown("---")
st.subheader("Vendor Information")
st.caption("💡 Optional: If you cannot provide these details, the tracker will contain empty fields for these points.")

vendor_name_input = st.text_input("Enter Vendor Name (e.g., ABC Corp, XYZ Agency)", value=st.session_state.vendor_name, placeholder="Enter vendor name (optional)...")
if vendor_name_input:
    vendor_name_clean = vendor_name_input.strip()
    st.session_state.vendor_name = vendor_name_clean
else:
    st.session_state.vendor_name = ""

profile_shared_date_input = st.date_input("Select Profile Shared Date", value=st.session_state.profile_shared_date, help="Select the date when the profile was shared (optional)")
if profile_shared_date_input:
    st.session_state.profile_shared_date = profile_shared_date_input
else:
    st.session_state.profile_shared_date = None

# Initialize previous method tracking
if "prev_jd_method" not in st.session_state:
    st.session_state.prev_jd_method = None

# Initialize jd_input_method and jd_file variables (needed for Analyze button)
jd_input_method = None
jd_file = None

# Job Description Input Section
st.subheader("Job Description Input")

# Check if base folder is selected before allowing JD input
if not st.session_state.selected_base_folder or not st.session_state.selected_base_folder.strip():
    st.error("⚠️ **Please select a base folder first before providing Job Description.**")
    st.info("💡 Enter the full path to an existing folder in the 'Folder Selection' section above to proceed.")
    
    st.session_state.job_desc = ""
    st.session_state.evaluation_points = []
    st.session_state.selected_evaluation_points = []
    st.session_state.evaluation_points_confirmed = False
else:
    jd_input_method = st.radio("Choose input method:", ["Text Input", "Document Upload"], horizontal=True)
    
    # Detect if input method changed and clear all related data
    method_changed = st.session_state.prev_jd_method is not None and st.session_state.prev_jd_method != jd_input_method
    
    if method_changed:
        st.session_state.job_desc = ""
        st.session_state.evaluation_points = []
        st.session_state.selected_evaluation_points = []
        st.session_state.evaluation_points_confirmed = False
        st.session_state.last_jd_file_id = None
        st.session_state.last_jd_text_id = None
    
    st.session_state.prev_jd_method = jd_input_method

    jd_file = None
    if jd_input_method == "Text Input":
        if method_changed:
            st.session_state.job_desc = ""
        
        new_jd = st.text_area("Enter the Job Description of the role you are applying for:", placeholder="Job Description...", value=st.session_state.job_desc)
        if new_jd.strip():
            current_jd_id = hash(new_jd.strip())
            if st.session_state.get('last_jd_text_id') != current_jd_id:
                st.session_state.evaluation_points = []
                st.session_state.selected_evaluation_points = []
                st.session_state.evaluation_points_confirmed = False
                st.session_state.last_jd_text_id = current_jd_id
        st.session_state.job_desc = new_jd
    elif jd_input_method == "Document Upload":
        if method_changed:
            st.session_state.job_desc = ""
        
        jd_file = st.file_uploader(label="Upload Job Description (PDF, DOC, DOCX, or TXT)", type=["pdf","doc","docx","txt"])
        if jd_file:
            st.success(f"File uploaded: {jd_file.name}")
            current_file_id = f"{jd_file.name}_{jd_file.size}"
            if st.session_state.get('last_jd_file_id') != current_file_id:
                with st.spinner("🔄 Extracting Job Description from document..."):
                    extracted_jd = extract_jd_text(jd_file)
                    if extracted_jd and extracted_jd.strip():
                        st.session_state.evaluation_points = []
                        st.session_state.selected_evaluation_points = []
                        st.session_state.evaluation_points_confirmed = False
                        st.session_state.job_desc = extracted_jd
                        st.session_state.last_jd_file_id = current_file_id
                        st.success("✅ Job Description extracted successfully!")
                    else:
                        st.error("Could not extract text from the Job Description document.")

# Track if JD file/text was processed
if "last_jd_file_id" not in st.session_state:
    st.session_state.last_jd_file_id = None
if "last_jd_text_id" not in st.session_state:
    st.session_state.last_jd_text_id = None

# Evaluation Points Extraction and Selection Section
if st.session_state.selected_base_folder and st.session_state.selected_base_folder.strip() and st.session_state.job_desc and st.session_state.job_desc.strip():
    st.markdown("---")
    st.subheader("📋 Evaluation Criteria Selection")
    
    # Auto-extract evaluation points if not already extracted
    if not st.session_state.evaluation_points or len(st.session_state.evaluation_points) == 0:
        if st.session_state.api_key:
            with st.spinner("🔄 Extracting evaluation criteria from Job Description..."):
                extracted_points = extract_evaluation_points(
                    st.session_state.job_desc,
                    st.session_state.api_key,
                    st.session_state.model_name,
                    st.session_state.base_url
                )
                if extracted_points:
                    st.session_state.evaluation_points = extracted_points
                    st.session_state.selected_evaluation_points = extracted_points.copy()
                    st.session_state.evaluation_points_confirmed = False
                    st.success(f"✅ Extracted {len(extracted_points)} evaluation criteria!")
                    st.rerun()
                else:
                    st.warning("⚠️ Could not extract evaluation points. Please check your API key or try again.")
        else:
            st.error("⚠️ Please enter your API Key in the sidebar to extract evaluation points.")
            st.info("💡 Once API key is provided, evaluation points will be extracted automatically.")
    
    # Initialize confirmation status
    if "evaluation_points_confirmed" not in st.session_state:
        st.session_state.evaluation_points_confirmed = False
    
    # Experience Requirement Selection (Mandatory)
    st.write("**📊 Overall Work Experience Requirement** (Mandatory)")
    experience_options = [
        "1 year and above", "2 years and above", "3 years and above", "4 years and above",
        "5 years and above", "6 years and above", "7 years and above", "8 years and above",
        "9 years and above", "10 years and above", "15 years and above", "20 years and above"
    ]
    
    current_idx = 0
    if st.session_state.experience_requirement in experience_options:
        current_idx = experience_options.index(st.session_state.experience_requirement)
    
    st.session_state.experience_requirement = st.selectbox(
        "Select minimum work experience requirement:",
        options=experience_options,
        index=current_idx,
        help="This experience requirement will be used for candidate evaluation"
    )
    
    st.markdown("---")
    
    # Display evaluation points with selection checkboxes
    if st.session_state.evaluation_points and len(st.session_state.evaluation_points) > 0:
        if not st.session_state.evaluation_points_confirmed:
            st.write("**Select evaluation criteria to use for candidate assessment:**")
            st.caption("Check/uncheck the criteria you want to include in the analysis. At least one criterion must be selected.")
            
            if not st.session_state.selected_evaluation_points:
                st.session_state.selected_evaluation_points = st.session_state.evaluation_points.copy()
            
            selected_points = []
            cols = st.columns(2)
            
            for idx, point in enumerate(st.session_state.evaluation_points):
                col_idx = idx % 2
                with cols[col_idx]:
                    is_selected = point in st.session_state.selected_evaluation_points
                    if st.checkbox(point, value=is_selected, key=f"eval_point_{idx}"):
                        selected_points.append(point)
            
            st.session_state.selected_evaluation_points = selected_points
            
            if len(selected_points) > 0:
                st.info(f"📌 {len(selected_points)} evaluation criteria selected + Experience Requirement: {st.session_state.experience_requirement}")
                
                if st.button("✅ Confirm Selection and Proceed", type="primary"):
                    st.session_state.evaluation_points_confirmed = True
                    st.rerun()
            else:
                st.warning("⚠️ Please select at least one evaluation criterion to proceed.")
            
            if st.button("Reset to All", type="secondary"):
                st.session_state.selected_evaluation_points = st.session_state.evaluation_points.copy()
                st.rerun()
        
        else:
            st.success("✅ Evaluation criteria confirmed!")
            st.write("**Selected Evaluation Criteria for Analysis:**")
            st.caption("Please review the selected criteria below. You can go back to modify your selection.")
            
            with st.container():
                st.write(f"**Experience Requirement:** {st.session_state.experience_requirement} ⚠️ (Mandatory)")
                st.write("**Other Evaluation Criteria:**")
                for idx, point in enumerate(st.session_state.selected_evaluation_points, 1):
                    st.write(f"{idx}. {point}")
            
            if st.button("← Back to Modify Selection", type="secondary"):
                st.session_state.evaluation_points_confirmed = False
                st.rerun()

# Resume Upload Section
if (st.session_state.job_desc and st.session_state.job_desc.strip() and 
    st.session_state.get('evaluation_points_confirmed', False)):
    st.markdown("---")
    st.subheader("Resume Upload")
    
    # Analysis Method selection
    st.write("**Select Analysis Method:**")
    analysis_method_options = ["Experiment Method", "Production Method"]
    current_method_idx = 0 if st.session_state.analysis_method == "Experiment Method" else 1
    
    selected_method = st.radio(
        "",
        options=analysis_method_options,
        index=current_method_idx,
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.analysis_method = selected_method
    
    st.caption(f"📌 Currently using: **{selected_method}**")
    st.markdown("---")
    
    # EXPERIMENT METHOD SECTION
    if st.session_state.analysis_method == "Experiment Method":
        st.markdown("### 🧪 Experiment Method")
        
        experiment_mode = st.radio(
            "Select Processing Mode:",
            ["Single Resume Processing", "Batch Processing"],
            horizontal=True,
            index=0 if st.session_state.experiment_processing_mode == "Single Resume Processing" else 1,
            key="experiment_mode_radio"
        )
        
        if experiment_mode != st.session_state.experiment_processing_mode:
            st.session_state.experiment_batch_processing_complete = False
            st.session_state.experiment_batch_results = []
            st.session_state.experiment_form_submitted = False
        
        st.session_state.experiment_processing_mode = experiment_mode
        st.session_state.processing_mode = experiment_mode
        
        if st.session_state.experiment_processing_mode == "Single Resume Processing":
            resume_file = st.file_uploader(
                label="Upload your Resume/CV (PDF, DOC, or DOCX)", 
                type=["pdf","doc","docx"],
                key="experiment_single_upload"
            )
            st.session_state.experiment_resume_file = resume_file
            resume_files = None
            st.session_state.experiment_resume_files = None
        else:
            resume_files = st.file_uploader(
                label="Upload multiple Resumes/CVs (PDF, DOC, or DOCX)", 
                type=["pdf","doc","docx"],
                accept_multiple_files=True,
                key="experiment_batch_upload"
            )
            st.session_state.experiment_resume_files = resume_files
            resume_file = None
            st.session_state.experiment_resume_file = None
            if resume_files and len(resume_files) > 0:
                st.info(f"📁 {len(resume_files)} resume(s) selected for batch processing")
    
    # PRODUCTION METHOD SECTION
    else:
        st.markdown("### 💻 Production Method")
        
        # Threshold Inputs for Auto-Decision
        st.markdown("**⚙️ Auto-Decision Thresholds:**")
        threshold_col1, threshold_col2 = st.columns(2)
        with threshold_col1:
            st.session_state.production_similarity_threshold = st.number_input(
                "Similarity Score Threshold",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.production_similarity_threshold,
                step=0.01,
                help="Minimum similarity score required for auto-shortlisting (0.0 - 1.0)"
            )
        with threshold_col2:
            st.session_state.production_average_threshold = st.number_input(
                "Average Score Threshold",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.production_average_threshold,
                step=0.01,
                help="Minimum average score required for auto-shortlisting (0.0 - 1.0)"
            )
        st.caption("💡 Candidates meeting both thresholds will be auto-shortlisted, others will be auto-rejected.")
        st.markdown("---")
        
        production_mode = st.radio(
            "Select Processing Mode:",
            ["Single Resume Processing", "Batch Processing"],
            horizontal=True,
            index=0 if st.session_state.production_processing_mode == "Single Resume Processing" else 1,
            key="production_mode_radio"
        )
        
        if production_mode != st.session_state.production_processing_mode:
            st.session_state.production_batch_processing_complete = False
            st.session_state.production_batch_results = []
            st.session_state.production_form_submitted = False
        
        st.session_state.production_processing_mode = production_mode
        st.session_state.processing_mode = production_mode
        
        if st.session_state.production_processing_mode == "Single Resume Processing":
            resume_file = st.file_uploader(
                label="Upload your Resume/CV (PDF, DOC, or DOCX)", 
                type=["pdf","doc","docx"],
                key="production_single_upload"
            )
            st.session_state.production_resume_file = resume_file
            resume_files = None
            st.session_state.production_resume_files = None
        else:
            resume_files = st.file_uploader(
                label="Upload multiple Resumes/CVs (PDF, DOC, or DOCX)", 
                type=["pdf","doc","docx"],
                accept_multiple_files=True,
                key="production_batch_upload"
            )
            st.session_state.production_resume_files = resume_files
            resume_file = None
            st.session_state.production_resume_file = None
            if resume_files and len(resume_files) > 0:
                st.info(f"📁 {len(resume_files)} resume(s) selected for batch processing")
else:
    resume_file = None
    resume_files = None

# Analysis Button
if st.button("Analyze", type="primary"):
    if jd_input_method == "Document Upload" and jd_file:
        if not st.session_state.job_desc or not st.session_state.job_desc.strip():
            with st.spinner("🔄 Extracting Job Description from document..."):
                extracted_jd = extract_jd_text(jd_file)
            if extracted_jd and extracted_jd.strip():
                st.session_state.job_desc = extracted_jd
            else:
                st.error("Could not extract text from the Job Description document.")
            st.stop()
    elif jd_input_method == "Document Upload" and not jd_file:
        st.error("Please upload a Job Description document.")
        st.stop()

    # Get method-specific resume files and processing mode
    if st.session_state.analysis_method == "Experiment Method":
        current_resume_file = st.session_state.experiment_resume_file
        current_resume_files = st.session_state.experiment_resume_files
        current_processing_mode = st.session_state.experiment_processing_mode
        current_form_submitted_key = "experiment_form_submitted"
        current_batch_results_key = "experiment_batch_results"
        current_batch_complete_key = "experiment_batch_processing_complete"
    else:
        current_resume_file = st.session_state.production_resume_file
        current_resume_files = st.session_state.production_resume_files
        current_processing_mode = st.session_state.production_processing_mode
        current_form_submitted_key = "production_form_submitted"
        current_batch_results_key = "production_batch_results"
        current_batch_complete_key = "production_batch_processing_complete"

    # Handle Single Resume Processing
    if current_processing_mode == "Single Resume Processing":
        if st.session_state.job_desc and current_resume_file:
            with st.spinner("🔄 Extracting Information"):
                st.session_state.resume = extract_resume_text(current_resume_file)

            if not st.session_state.resume or not st.session_state.resume.strip():
                st.error("We couldn't extract text from your resume. Please upload a selectable-text PDF or a DOC/DOCX file.")
            else:
                selected_points = st.session_state.get('selected_evaluation_points', [])
                
                if st.session_state.evaluation_points and len(st.session_state.evaluation_points) > 0:
                    if len(selected_points) == 0:
                        st.warning("⚠️ Evaluation criteria extracted but none selected. Proceeding with all JD criteria (recommended: select specific criteria above).")
                        selected_points = None
                else:
                    selected_points = None
                
                st.session_state.similarity_score = 0.0
                st.session_state.average_score = 0.0
                st.session_state.report = ""
                st.session_state.report_scores = []
                st.session_state.extracted_position = "Not Found"
                st.session_state.selected_points_for_analysis = selected_points
                st.session_state[current_form_submitted_key] = True
                st.session_state.form_submitted = True
        else:
            st.warning("Please Upload both Resume and Job Description to analyze")

    # Handle Batch Processing
    elif current_processing_mode == "Batch Processing":
        if st.session_state.job_desc and current_resume_files and len(current_resume_files) > 0:
            st.session_state[current_batch_results_key] = []
            
            selected_points = st.session_state.get('selected_evaluation_points', [])
            
            if st.session_state.evaluation_points and len(st.session_state.evaluation_points) > 0:
                if len(selected_points) == 0:
                    selected_points = None
            else:
                selected_points = None
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, resume_file in enumerate(current_resume_files):
                status_text.text(f"Processing resume {idx + 1} of {len(current_resume_files)}: {resume_file.name}")
                progress_bar.progress((idx + 1) / len(current_resume_files))
                
                try:
                    result = process_single_resume(
                        resume_file,
                        st.session_state.job_desc,
                        st.session_state.api_key,
                        st.session_state.model_name,
                        st.session_state.base_url,
                        selected_points,
                        experience_requirement=st.session_state.get('experience_requirement', None)
                    )
                    st.session_state[current_batch_results_key].append(result)
                except Exception as e:
                    st.session_state[current_batch_results_key].append({
                        'resume_file': resume_file.name if resume_file else 'Unknown',
                        'error': f'Error processing: {str(e)}',
                        'candidate_name': 'Error',
                        'position': 'Error',
                        'similarity_score': 0.0,
                        'average_score': 0.0,
                        'report': '',
                        'candidate_details': None
                    })
            
            progress_bar.empty()
            status_text.empty()
            st.success(f"✅ Batch processing completed! Processed {len(current_resume_files)} resume(s).")
            
            # Apply auto-decision for Production Method
            if st.session_state.analysis_method == "Production Method":
                similarity_threshold = st.session_state.production_similarity_threshold
                average_threshold = st.session_state.production_average_threshold
                selected_base_folder = st.session_state.get('selected_base_folder', '').strip()
                vendor_name = st.session_state.get('vendor_name', '')
                profile_shared_date = st.session_state.get('profile_shared_date', None)
                admin_override = st.session_state.get('admin_override', False)
                
                if selected_base_folder:
                    # Validate folder exists
                    if os.path.exists(selected_base_folder) and os.path.isdir(selected_base_folder):
                        with st.spinner("🔄 Applying auto-decision based on thresholds..."):
                            for idx, result in enumerate(st.session_state[current_batch_results_key]):
                                if result.get('error'):
                                    continue
                                
                                decision = apply_production_auto_decision(result, similarity_threshold, average_threshold)
                                success, message = execute_production_auto_decision(
                                    result, decision, selected_base_folder, vendor_name, profile_shared_date, admin_override
                                )
                                result['auto_decision'] = decision
                                result['auto_decision_status'] = message
                        
                        # Set thanking note for batch processing
                        st.session_state.show_thanking_note_batch = True
                    else:
                        st.warning(f"⚠️ Base folder does not exist: {selected_base_folder}. Please select a valid folder.")
                else:
                    st.warning("⚠️ Base folder required for auto-decision. Please select a base folder.")
                    for result in st.session_state[current_batch_results_key]:
                        result['auto_decision'] = "Pending"
                        result['auto_decision_status'] = "Client name required"
            
            st.session_state[current_batch_complete_key] = True
            st.session_state.batch_processing_complete = True
            st.session_state.batch_results = st.session_state[current_batch_results_key]
        else:
            st.warning("Please upload at least one Resume and provide Job Description for batch processing.")

# Display Batch Processing Results Table
if st.session_state.analysis_method == "Experiment Method":
    current_batch_complete = st.session_state.get('experiment_batch_processing_complete', False)
    current_batch_results = st.session_state.get('experiment_batch_results', [])
    batch_results_key_prefix = "experiment"
else:
    current_batch_complete = st.session_state.get('production_batch_processing_complete', False)
    current_batch_results = st.session_state.get('production_batch_results', [])
    batch_results_key_prefix = "production"

if current_batch_complete and current_batch_results:
    st.markdown("---")
    st.subheader("📊 Batch Processing Results")
    
    if current_batch_results:
        # Production Method: Show summary table with Action column
        if st.session_state.analysis_method == "Production Method":
            header_cols = st.columns([2, 2, 2, 1.5, 1.5, 2, 2])
            header_cols[0].write("**Name**")
            header_cols[1].write("**Position**")
            header_cols[2].write("**Experience**")
            header_cols[3].write("**Location**")
            header_cols[4].write("**Similarity Score**")
            header_cols[5].write("**Average Score**")
            header_cols[6].write("**Action**")
            st.markdown("---")
            
            for idx, result in enumerate(current_batch_results):
                if result.get('error'):
                    st.warning(f"⚠️ {result.get('resume_file', 'Unknown')}: {result.get('error', 'Unknown error')}")
                    continue
                
                candidate_details = result.get('candidate_details', {})
                candidate_name = result.get('candidate_name', result.get('resume_file', 'Unknown'))
                position = result.get('position', 'Not Found')
                total_experience = candidate_details.get('Total_Experience', 'Not Found')
                location = candidate_details.get('Location', 'Not Found')
                similarity_score = f"{result.get('similarity_score', 0.0):.4f}"
                average_score = f"{result.get('average_score', 0.0):.4f}"
                auto_decision = result.get('auto_decision', 'Pending')
                
                row_cols = st.columns([2, 2, 2, 1.5, 1.5, 2, 2])
                
                with row_cols[0]:
                    st.write(candidate_name)
                with row_cols[1]:
                    st.write(position)
                with row_cols[2]:
                    st.write(total_experience)
                with row_cols[3]:
                    st.write(location)
                with row_cols[4]:
                    st.write(similarity_score)
                with row_cols[5]:
                    st.write(average_score)
                with row_cols[6]:
                    if auto_decision == "Shortlisted":
                        st.success(f"✅ {auto_decision}")
                    elif auto_decision == "Rejected":
                        st.error(f"❌ {auto_decision}")
                    else:
                        st.warning(f"⏳ {auto_decision}")
                    # Show status message if available
                    status_msg = result.get('auto_decision_status', '')
                    if status_msg:
                        st.caption(f"({status_msg})")
                
                st.markdown("---")
            
            # Show thanking note for Production Method batch processing
            if st.session_state.show_thanking_note_batch:
                st.markdown("---")
                st.info("💬 Your selection has been processed. Thank you for utilizing Smart AI Recruiter to enhance your talent acquisition.")
                st.session_state.show_thanking_note_batch = False
        
        # Experiment Method: Show table with manual buttons
        else:
            header_cols = st.columns([2, 2, 2, 1.5, 1.5, 2, 2])
            header_cols[0].write("**Name**")
            header_cols[1].write("**Position**")
            header_cols[2].write("**Experience**")
            header_cols[3].write("**Location**")
            header_cols[4].write("**Similarity Score**")
            header_cols[5].write("**Average Score**")
            header_cols[6].write("**Actions**")
            st.markdown("---")
            
            for idx, result in enumerate(current_batch_results):
                if result.get('error'):
                    st.warning(f"⚠️ {result.get('resume_file', 'Unknown')}: {result.get('error', 'Unknown error')}")
                    continue
                
                candidate_details = result.get('candidate_details', {})
                candidate_name = result.get('candidate_name', result.get('resume_file', 'Unknown'))
                position = result.get('position', 'Not Found')
                total_experience = candidate_details.get('Total_Experience', 'Not Found')
                location = candidate_details.get('Location', 'Not Found')
                similarity_score = f"{result.get('similarity_score', 0.0):.4f}"
                average_score = f"{result.get('average_score', 0.0):.4f}"
                
                row_cols = st.columns([2, 2, 2, 1.5, 1.5, 2, 2])
                
                with row_cols[0]:
                    st.write(candidate_name)
                with row_cols[1]:
                    st.write(position)
                with row_cols[2]:
                    st.write(total_experience)
                with row_cols[3]:
                    st.write(location)
                with row_cols[4]:
                    st.write(similarity_score)
                with row_cols[5]:
                    st.write(average_score)
                with row_cols[6]:
                    button_state_key = f"{batch_results_key_prefix}_batch_btn_{idx}"
                    if batch_results_key_prefix == "experiment":
                        button_state = st.session_state.experiment_batch_button_states.get(button_state_key, None)
                    else:
                        button_state = st.session_state.production_batch_button_states.get(button_state_key, None)
                    
                    shortlist_button_key = f"shortlist_{batch_results_key_prefix}_batch_{idx}"
                    reject_button_key = f"reject_{batch_results_key_prefix}_batch_{idx}"
                    shortlist_container_id = f"shortlist-btn-{batch_results_key_prefix}-{idx}"
                    reject_container_id = f"reject-btn-{batch_results_key_prefix}-{idx}"
                    
                    st.markdown(f"""
                    <style>
                    div#{shortlist_container_id} {{
                        width: 100% !important;
                        margin-bottom: 5px !important;
                    }}
                    div#{shortlist_container_id} button[data-testid="baseButton-primary"],
                    div#{shortlist_container_id} button[kind="primary"],
                    div#{shortlist_container_id} button[data-testid="baseButton-secondary"],
                    div#{shortlist_container_id} button[kind="secondary"] {{
                        background-color: #28a745 !important;
                        border-color: #28a745 !important;
                        color: white !important;
                        width: 100% !important;
                        min-height: 38px !important;
                        height: 38px !important;
                        padding: 0.5rem 1rem !important;
                    }}
                    div#{reject_container_id} {{
                        width: 100% !important;
                        margin-top: 5px !important;
                    }}
                    div#{reject_container_id} button[data-testid="baseButton-primary"],
                    div#{reject_container_id} button[kind="primary"],
                    div#{reject_container_id} button[data-testid="baseButton-secondary"],
                    div#{reject_container_id} button[kind="secondary"] {{
                        background-color: #dc3545 !important;
                        border-color: #dc3545 !important;
                        color: white !important;
                        width: 100% !important;
                        min-height: 38px !important;
                        height: 38px !important;
                        padding: 0.5rem 1rem !important;
                    }}
                    </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f'<div id="{shortlist_container_id}">', unsafe_allow_html=True)
                    if st.button(f"✅ Shortlist", key=shortlist_button_key, type="primary" if button_state == "shortlisted" else "secondary", use_container_width=True):
                        try:
                            position_val = result.get('position', 'Not Found')
                            if not position_val or position_val == 'Not Found':
                                job_desc = st.session_state.get('job_desc', '') or ''
                                if job_desc and job_desc.strip() and st.session_state.api_key:
                                    try:
                                        position_val = extract_position_from_jd(
                                            job_desc,
                                            st.session_state.api_key,
                                            st.session_state.model_name,
                                            st.session_state.base_url
                                        )
                                    except:
                                        position_val = 'Not Found'
                            
                            selected_base_folder = st.session_state.get('selected_base_folder', '').strip()
                            if not selected_base_folder:
                                st.error("⚠️ Please select a base folder before shortlisting candidates.")
                            elif not os.path.exists(selected_base_folder) or not os.path.isdir(selected_base_folder):
                                st.error(f"⚠️ Base folder does not exist: {selected_base_folder}. Please select a valid folder.")
                            else:
                                position_clean = re.sub(r'[^\w\s-]', '', position_val)
                                position_clean = position_clean.replace(' ', '_').strip('_')
                                if not position_clean or position_clean == 'Not_Found':
                                    position_clean = "Not_Found"
                                
                                position_folder = f"{position_clean}_Candidates"
                                base_folder_abs = os.path.abspath(selected_base_folder)
                                folder_name = os.path.join(base_folder_abs, position_folder)
                                os.makedirs(folder_name, exist_ok=True)
                                
                                candidate_details_val = result.get('candidate_details')
                                if candidate_details_val:
                                    candidate_details_val['Position'] = position_val if position_val and position_val != 'Not Found' else 'Not Found'
                                    
                                    vendor_name = st.session_state.get('vendor_name', '')
                                    exists, current_status, duplicate_reason, _ = check_candidate_status_in_tracker(
                                        candidate_details_val, folder_name, vendor_name
                                    )
                                    
                                    if exists:
                                        if duplicate_reason.endswith("_same_vendor"):
                                            st.warning(f"⚠️ **{candidate_name} already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                        elif duplicate_reason.endswith("_different_vendor"):
                                            full_report = result.get('report', '')
                                            feedback = extract_summary_from_report(full_report) if full_report else ''
                                            similarity_score_val = result.get('similarity_score', 0.0)
                                            average_score_val = result.get('average_score', 0.0)
                                            file_path = ""
                                            
                                            profile_shared_date = st.session_state.get('profile_shared_date', None)
                                            excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                                candidate_details_val,
                                                tracker_type="rejected",
                                                folder_name=folder_name,
                                                feedback=feedback,
                                                similarity_score=similarity_score_val,
                                                average_score=average_score_val,
                                                cv_path=file_path,
                                                vendor_name=vendor_name,
                                                profile_shared_date=profile_shared_date,
                                                allow_status_change=st.session_state.get('admin_override', False)
                                            )
                                            
                                            if added:
                                                st.success(f"✅ {candidate_name} added to tracker with 'Duplicate Profile' status (exists from different vendor).")
                                                if batch_results_key_prefix == "experiment":
                                                    st.session_state.experiment_batch_button_states[button_state_key] = "duplicate"
                                                    st.session_state.show_thanking_note_batch = True
                                                else:
                                                    st.session_state.production_batch_button_states[button_state_key] = "duplicate"
                                                st.rerun()
                                        else:
                                            st.warning(f"⚠️ **{candidate_name} already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                    else:
                                        full_report = result.get('report', '')
                                        feedback = extract_summary_from_report(full_report) if full_report else ''
                                        similarity_score_val = result.get('similarity_score', 0.0)
                                        average_score_val = result.get('average_score', 0.0)
                                        
                                        file_path = ""
                                        resume_file_obj = result.get('resume_file_obj')
                                        if resume_file_obj:
                                            candidate_name_clean = candidate_details_val.get('Candidate_Name', 'Unknown')
                                            candidate_name_clean = re.sub(r'[^\w\s-]', '', candidate_name_clean)
                                            candidate_name_clean = candidate_name_clean.replace(' ', '_').strip('_')
                                            if not candidate_name_clean:
                                                candidate_name_clean = "Unknown"
                                            
                                            file_extension = os.path.splitext(resume_file_obj.name)[1]
                                            new_filename = f"{position_clean}_{candidate_name_clean}{file_extension}"
                                            
                                            shortlisted_folder = os.path.join(folder_name, "Shortlisted")
                                            os.makedirs(shortlisted_folder, exist_ok=True)
                                            file_path = os.path.join(shortlisted_folder, new_filename)
                                            file_path = os.path.abspath(file_path)
                                            
                                            resume_file_obj.seek(0)
                                            with open(file_path, "wb") as f:
                                                f.write(resume_file_obj.getbuffer())
                                        
                                        profile_shared_date = st.session_state.get('profile_shared_date', None)
                                        excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                            candidate_details_val,
                                            tracker_type="shortlisted",
                                            folder_name=folder_name,
                                            feedback=feedback,
                                            similarity_score=similarity_score_val,
                                            average_score=average_score_val,
                                            cv_path=file_path,
                                            vendor_name=vendor_name,
                                            profile_shared_date=profile_shared_date,
                                            allow_status_change=st.session_state.get('admin_override', False)
                                        )
                                        
                                        if added:
                                            st.success(f"✅ {candidate_name} shortlisted successfully!")
                                            if batch_results_key_prefix == "experiment":
                                                st.session_state.experiment_batch_button_states[button_state_key] = "shortlisted"
                                                st.session_state.show_thanking_note_batch = True
                                            else:
                                                st.session_state.production_batch_button_states[button_state_key] = "shortlisted"
                                            st.rerun()
                                        else:
                                            if duplicate_reason_ret.endswith("_same_vendor"):
                                                st.warning(f"⚠️ **{candidate_name} already screened.** Current status: {status_ret}. Cannot change status.")
                                            else:
                                                st.warning(f"⚠️ **{candidate_name} already screened.** Duplicate entry prevented.")
                                else:
                                    st.warning(f"⚠️ Could not extract candidate details for {candidate_name}.")
                        except Exception as e:
                            st.error(f"Error shortlisting {candidate_name}: {str(e)}")
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown(f'<div id="{reject_container_id}">', unsafe_allow_html=True)
                if st.button(f"❌ Reject", key=reject_button_key, type="primary" if button_state == "rejected" else "secondary", use_container_width=True):
                    try:
                        position_val = result.get('position', 'Not Found')
                        if not position_val or position_val == 'Not Found':
                            job_desc = st.session_state.get('job_desc', '') or ''
                            if job_desc and job_desc.strip() and st.session_state.api_key:
                                try:
                                    position_val = extract_position_from_jd(
                                        job_desc,
                                        st.session_state.api_key,
                                        st.session_state.model_name,
                                        st.session_state.base_url
                                    )
                                except:
                                    position_val = 'Not Found'
                        
                        selected_base_folder = st.session_state.get('selected_base_folder', '').strip()
                        if not selected_base_folder:
                            st.error("⚠️ Please select a base folder before rejecting candidates.")
                        elif not os.path.exists(selected_base_folder) or not os.path.isdir(selected_base_folder):
                            st.error(f"⚠️ Base folder does not exist: {selected_base_folder}. Please select a valid folder.")
                        else:
                            position_clean = re.sub(r'[^\w\s-]', '', position_val)
                            position_clean = position_clean.replace(' ', '_').strip('_')
                            if not position_clean or position_clean == 'Not_Found':
                                position_clean = "Not_Found"
                            
                            position_folder = f"{position_clean}_Candidates"
                            base_folder_abs = os.path.abspath(selected_base_folder)
                            folder_name = os.path.join(base_folder_abs, position_folder)
                            os.makedirs(folder_name, exist_ok=True)
                            
                            candidate_details_val = result.get('candidate_details')
                            if candidate_details_val:
                                candidate_details_val['Position'] = position_val if position_val and position_val != 'Not Found' else 'Not Found'
                                
                                vendor_name = st.session_state.get('vendor_name', '')
                                exists, current_status, duplicate_reason, _ = check_candidate_status_in_tracker(
                                    candidate_details_val, folder_name, vendor_name
                                )
                                
                                if exists:
                                    if duplicate_reason.endswith("_same_vendor"):
                                        st.warning(f"⚠️ **{candidate_name} already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                    elif duplicate_reason.endswith("_different_vendor"):
                                        full_report = result.get('report', '')
                                        feedback = extract_failed_points_explanations(full_report) if full_report else ''
                                        similarity_score_val = result.get('similarity_score', 0.0)
                                        average_score_val = result.get('average_score', 0.0)
                                        file_path = ""
                                        
                                        profile_shared_date = st.session_state.get('profile_shared_date', None)
                                        excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                            candidate_details_val,
                                            tracker_type="rejected",
                                            folder_name=folder_name,
                                            feedback=feedback,
                                            similarity_score=similarity_score_val,
                                            average_score=average_score_val,
                                            cv_path=file_path,
                                            vendor_name=vendor_name,
                                            profile_shared_date=profile_shared_date,
                                            allow_status_change=st.session_state.get('admin_override', False)
                                        )
                                        
                                        if added:
                                            st.success(f"✅ {candidate_name} added to tracker with 'Duplicate Profile' status (exists from different vendor).")
                                            if batch_results_key_prefix == "experiment":
                                                st.session_state.experiment_batch_button_states[button_state_key] = "duplicate"
                                                st.session_state.show_thanking_note_batch = True
                                            else:
                                                st.session_state.production_batch_button_states[button_state_key] = "duplicate"
                                            st.rerun()
                                    else:
                                        st.warning(f"⚠️ **{candidate_name} already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                else:
                                    full_report = result.get('report', '')
                                    feedback = extract_failed_points_explanations(full_report) if full_report else ''
                                    similarity_score_val = result.get('similarity_score', 0.0)
                                    average_score_val = result.get('average_score', 0.0)
                                    
                                    profile_shared_date = st.session_state.get('profile_shared_date', None)
                                    excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                        candidate_details_val,
                                        tracker_type="rejected",
                                        folder_name=folder_name,
                                        feedback=feedback,
                                        similarity_score=similarity_score_val,
                                        average_score=average_score_val,
                                        vendor_name=vendor_name,
                                        profile_shared_date=profile_shared_date,
                                        allow_status_change=st.session_state.get('admin_override', False)
                                    )
                                    
                                    if added:
                                        st.success(f"✅ {candidate_name} rejected successfully!")
                                        if batch_results_key_prefix == "experiment":
                                            st.session_state.experiment_batch_button_states[button_state_key] = "rejected"
                                            st.session_state.show_thanking_note_batch = True
                                        else:
                                            st.session_state.production_batch_button_states[button_state_key] = "rejected"
                                        st.rerun()
                                    else:
                                        if duplicate_reason_ret.endswith("_same_vendor"):
                                            st.warning(f"⚠️ **{candidate_name} already screened.** Current status: {status_ret}. Cannot change status.")
                                        else:
                                            st.warning(f"⚠️ {candidate_name} already exists in tracker.")
                            else:
                                st.warning(f"⚠️ Could not extract candidate details for {candidate_name}.")
                    except Exception as e:
                        st.error(f"Error rejecting {candidate_name}: {str(e)}")
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("---")
        
        if st.session_state.show_thanking_note_batch:
            st.markdown("---")
            st.info("💬 Your selection has been processed. Thank you for utilizing Smart AI Recruiter to enhance your talent acquisition.")
            st.session_state.show_thanking_note_batch = False
    
    st.markdown("---")

# Single Resume Processing Display
if st.session_state.analysis_method == "Experiment Method":
    method_form_submitted = st.session_state.get('experiment_form_submitted', False)
    method_processing_mode = st.session_state.experiment_processing_mode
else:
    method_form_submitted = st.session_state.get('production_form_submitted', False)
    method_processing_mode = st.session_state.production_processing_mode

if (method_form_submitted or st.session_state.form_submitted) and method_processing_mode == "Single Resume Processing":
    scores_already_calculated = (
        'report' in st.session_state and 
        st.session_state.report and 
        st.session_state.report.strip() != "" and
        'similarity_score' in st.session_state and
        'average_score' in st.session_state
    )
    
    if not scores_already_calculated:
        with st.spinner("🔄 Generating Scores..."):
            safe_resume = st.session_state.resume or ""
            safe_job = st.session_state.job_desc or ""
            ats_score = calculate_similarity_bert(safe_resume, safe_job) if (safe_resume.strip() and safe_job.strip()) else 0.0
            
            st.session_state.similarity_score = ats_score

            if safe_resume.strip():
                if not st.session_state.api_key:
                    st.error("Please enter your API Key in the sidebar to generate the AI report.")
                    report = ""
                else:
                    selected_points = st.session_state.get('selected_points_for_analysis', None)
                    experience_requirement = st.session_state.get('experience_requirement', None)
                    report = get_report(
                        safe_resume,
                        safe_job,
                        st.session_state.api_key,
                        st.session_state.model_name,
                        selected_points=selected_points,
                        temperature=0.0,
                        base_url=st.session_state.base_url,
                        experience_requirement=experience_requirement,
                    )
            else:
                report = "Resume text could not be extracted; analysis is unavailable. Please re-upload as PDF (with selectable text), DOC, or DOCX."
            
            st.session_state.report = report

            report_scores = extract_scores(report)
            avg_score = (sum(report_scores) / (5*len(report_scores))) if report_scores else 0.0
            
            st.session_state.average_score = avg_score
            st.session_state.report_scores = report_scores
            
            job_desc = st.session_state.get('job_desc', '') or ''
            if job_desc and job_desc.strip() and st.session_state.api_key:
                try:
                    extracted_position = extract_position_from_jd(
                        job_desc,
                        st.session_state.api_key,
                        st.session_state.model_name,
                        st.session_state.base_url
                    )
                    st.session_state.extracted_position = extracted_position
                except:
                    st.session_state.extracted_position = "Not Found"
            elif job_desc and job_desc.strip():
                try:
                    extracted_position = extract_position_from_jd(
                        job_desc,
                        None,
                        None,
                        None
                    )
                    st.session_state.extracted_position = extracted_position
                except:
                    st.session_state.extracted_position = "Not Found"
            else:
                st.session_state.extracted_position = "Not Found"
        
        st.success("✅ Scores generated successfully!")
        
        # Apply auto-decision for Production Method Single Resume
        if st.session_state.analysis_method == "Production Method":
            similarity_threshold = st.session_state.production_similarity_threshold
            average_threshold = st.session_state.production_average_threshold
            selected_base_folder = st.session_state.get('selected_base_folder', '').strip()
            
            if selected_base_folder:
                # Validate folder exists
                if os.path.exists(selected_base_folder) and os.path.isdir(selected_base_folder):
                    # Create result dict for auto-decision
                    result_dict = {
                        'similarity_score': ats_score,
                        'average_score': avg_score,
                        'position': st.session_state.get('extracted_position', 'Not Found'),
                        'report': report,
                        'candidate_details': None,
                        'resume_file_obj': current_action_resume_file if 'current_action_resume_file' in locals() else st.session_state.production_resume_file
                    }
                    
                    # Extract candidate details if API key available
                    if st.session_state.api_key and st.session_state.resume:
                        try:
                            candidate_details = extract_candidate_details_llm(
                                st.session_state.resume,
                                st.session_state.api_key,
                                st.session_state.model_name,
                                st.session_state.base_url
                            )
                            if candidate_details:
                                result_dict['candidate_details'] = candidate_details
                                result_dict['candidate_name'] = candidate_details.get('Candidate_Name', 'Unknown')
                        except:
                            pass
                    
                    # Apply auto-decision
                    decision = apply_production_auto_decision(result_dict, similarity_threshold, average_threshold)
                    vendor_name = st.session_state.get('vendor_name', '')
                    profile_shared_date = st.session_state.get('profile_shared_date', None)
                    admin_override = st.session_state.get('admin_override', False)
                    
                    if result_dict.get('candidate_details'):
                        with st.spinner("🔄 Applying auto-decision..."):
                            success, message = execute_production_auto_decision(
                                result_dict, decision, selected_base_folder, vendor_name, profile_shared_date, admin_override
                            )
                        st.session_state.production_single_auto_decision = decision
                        st.session_state.production_single_auto_decision_status = message
                        if success:
                            if decision == "Shortlisted":
                                st.success(f"✅ Candidate auto-shortlisted! {message}")
                            else:
                                st.success(f"✅ Candidate auto-rejected! {message}")
                        else:
                            st.warning(f"⚠️ {message}")
                else:
                    st.warning("⚠️ Could not extract candidate details for auto-decision. Please check your API key.")
                    st.session_state.production_single_auto_decision = "Pending"
                    st.session_state.production_single_auto_decision_status = "Could not extract candidate details"
            else:
                st.warning("⚠️ Client name required for auto-decision. Please enter client name.")
                st.session_state.production_single_auto_decision = "Pending"
                st.session_state.production_single_auto_decision_status = "Client name required"
    else:
        ats_score = st.session_state.similarity_score
        avg_score = st.session_state.average_score
        report = st.session_state.get('report', '')
        if 'report_scores' in st.session_state:
            report_scores = st.session_state.report_scores
        else:
            report_scores = extract_scores(report) if report else []
            st.session_state.report_scores = report_scores
        
        if 'extracted_position' not in st.session_state:
            job_desc = st.session_state.get('job_desc', '') or ''
            if job_desc and job_desc.strip() and st.session_state.api_key:
                try:
                    extracted_position = extract_position_from_jd(
                        job_desc,
                        st.session_state.api_key,
                        st.session_state.model_name,
                        st.session_state.base_url
                    )
                    st.session_state.extracted_position = extracted_position
                except:
                    st.session_state.extracted_position = "Not Found"
            else:
                st.session_state.extracted_position = "Not Found"

    # Display scores
    col1, col2 = st.columns(2, border=True)
    with col1:
        st.write("Similarity Score:")
        st.subheader(str(ats_score))

    with col2:
        st.write("Total Average score according to our AI report:")
        st.subheader(str(avg_score))

    # Calculations detail expander
    with st.expander("Show calculation details"):
        st.markdown("""
        - **ATS Similarity (cosine similarity)**: cosine(embedding(resume), embedding(job_description))
        - **LLM point scores parsed**: values matching the pattern `x/5` in the report
        """)
        st.write({
            "ats_similarity": ats_score,
            "parsed_llm_scores": report_scores,
            "num_points": len(report_scores),
            "sum_scores": sum(report_scores) if report_scores else 0.0,
            "average_normalized": avg_score,
        })
        if report_scores:
            st.latex(r"\text{Average (0-1)} = \frac{\sum_i s_i}{5 \times n}")
        else:
            st.info("No x/5 scores were found in the AI report.")

    # Analysis Report
    with st.expander("📊 Analysis Report", expanded=False):
        st.markdown(f"""
                <div style='text-align: left; background-color: #ffffff; color: #111111; padding: 10px; border-radius: 10px; margin: 5px 0;'>
                    {report}
                </div>
                """, unsafe_allow_html=True)
        
        st.download_button(
            label="Download Report",
            data=report,
            file_name="report.txt",
            icon=":material/download:",
        )
    
    # Candidate Decision Section
    st.markdown("---")
    st.subheader("Candidate Decision")
    
    # Production Method: Show summary table
    if st.session_state.analysis_method == "Production Method":
        # Get candidate details for display
        candidate_name = "Unknown"
        position = st.session_state.get('extracted_position', 'Not Found')
        total_experience = "Not Found"
        location = "Not Found"
        
        if st.session_state.api_key and st.session_state.resume:
            try:
                candidate_details = extract_candidate_details_llm(
                    st.session_state.resume,
                    st.session_state.api_key,
                    st.session_state.model_name,
                    st.session_state.base_url
                )
                if candidate_details:
                    candidate_name = candidate_details.get('Candidate_Name', 'Unknown')
                    total_experience = candidate_details.get('Total_Experience', 'Not Found')
                    location = candidate_details.get('Location', 'Not Found')
            except:
                pass
        
        # Display summary table
        st.markdown("**📊 Candidate Summary:**")
        summary_cols = st.columns([2, 2, 2, 1.5, 1.5, 2, 2])
        summary_cols[0].write("**Name**")
        summary_cols[1].write("**Position**")
        summary_cols[2].write("**Experience**")
        summary_cols[3].write("**Location**")
        summary_cols[4].write("**Similarity Score**")
        summary_cols[5].write("**Average Score**")
        summary_cols[6].write("**Action**")
        st.markdown("---")
        
        row_cols = st.columns([2, 2, 2, 1.5, 1.5, 2, 2])
        with row_cols[0]:
            st.write(candidate_name)
        with row_cols[1]:
            st.write(position)
        with row_cols[2]:
            st.write(total_experience)
        with row_cols[3]:
            st.write(location)
        with row_cols[4]:
            st.write(f"{ats_score:.4f}")
        with row_cols[5]:
            st.write(f"{avg_score:.4f}")
        with row_cols[6]:
            auto_decision = st.session_state.get('production_single_auto_decision', 'Pending')
            if auto_decision == "Shortlisted":
                st.success(f"✅ {auto_decision}")
            elif auto_decision == "Rejected":
                st.error(f"❌ {auto_decision}")
            else:
                st.warning(f"⏳ {auto_decision}")
            status_msg = st.session_state.get('production_single_auto_decision_status', '')
            if status_msg:
                st.caption(f"({status_msg})")
    
    # Experiment Method: Show manual buttons
    else:
        col1, col2 = st.columns(2)
        
        if st.session_state.analysis_method == "Experiment Method":
            current_action_resume_file = st.session_state.experiment_resume_file
            single_button_state = st.session_state.get('experiment_single_button_state', None)
        else:
            current_action_resume_file = st.session_state.production_resume_file
            single_button_state = st.session_state.get('production_single_button_state', None)
        
        single_shortlist_container_id = f"single-shortlist-btn-{st.session_state.analysis_method.lower().replace(' ', '-')}"
        single_reject_container_id = f"single-reject-btn-{st.session_state.analysis_method.lower().replace(' ', '-')}"
        
        st.markdown(f"""
        <style>
        div#{single_shortlist_container_id} button[data-testid="baseButton-primary"],
        div#{single_shortlist_container_id} button[kind="primary"] {{
            background-color: #28a745 !important;
            border-color: #28a745 !important;
            color: white !important;
        }}
        div#{single_reject_container_id} button[data-testid="baseButton-primary"],
        div#{single_reject_container_id} button[kind="primary"] {{
            background-color: #dc3545 !important;
            border-color: #dc3545 !important;
            color: white !important;
        }}
        </style>
        """, unsafe_allow_html=True)
        
        with col1:
            st.markdown(f'<div id="{single_shortlist_container_id}">', unsafe_allow_html=True)
            if st.button("✅ Shortlist", type="primary" if single_button_state == "shortlisted" else "secondary", use_container_width=True):
                if not current_action_resume_file:
                    st.error("No resume file found")
                elif current_action_resume_file:
                    try:
                        position = st.session_state.get('extracted_position', 'Not Found')
                        
                        if not position or position == 'Not Found':
                            job_desc = st.session_state.get('job_desc', '') or ''
                            if job_desc and job_desc.strip() and st.session_state.api_key:
                                try:
                                    position = extract_position_from_jd(
                                        job_desc,
                                        st.session_state.api_key,
                                        st.session_state.model_name,
                                        st.session_state.base_url
                                    )
                                    st.session_state.extracted_position = position
                                except Exception as e:
                                    position = 'Not Found'
                                    st.session_state.extracted_position = position
                        
                        selected_base_folder = st.session_state.get('selected_base_folder', '').strip()
                        if not selected_base_folder:
                            st.error("⚠️ Please select a base folder before shortlisting candidates.")
                            st.stop()
                        elif not os.path.exists(selected_base_folder) or not os.path.isdir(selected_base_folder):
                            st.error(f"⚠️ Base folder does not exist: {selected_base_folder}. Please select a valid folder.")
                            st.stop()
                        
                        position_clean = re.sub(r'[^\w\s-]', '', position)
                        position_clean = position_clean.replace(' ', '_').strip('_')
                        if not position_clean or position_clean == 'Not_Found':
                            position_clean = "Not_Found"
                        
                        position_folder = f"{position_clean}_Candidates"
                        base_folder_abs = os.path.abspath(selected_base_folder)
                        folder_name = os.path.join(base_folder_abs, position_folder)
                        os.makedirs(folder_name, exist_ok=True)
                        
                        candidate_details = None
                        candidate_name = "Unknown"
                        file_extension = os.path.splitext(current_action_resume_file.name)[1]
                        
                        if st.session_state.api_key and st.session_state.resume:
                            with st.spinner("🔄 Extracting candidate details..."):
                                candidate_details = extract_candidate_details_llm(
                                    st.session_state.resume, 
                                    st.session_state.api_key, 
                                    st.session_state.model_name, 
                                    st.session_state.base_url
                                )
                                
                                if candidate_details:
                                    candidate_details['Position'] = position if position and position != 'Not Found' else 'Not Found'
                                    
                                    candidate_name = candidate_details.get('Candidate_Name', 'Unknown')
                                    candidate_name_clean = re.sub(r'[^\w\s-]', '', candidate_name)
                                    candidate_name_clean = candidate_name_clean.replace(' ', '_').strip('_')
                                    if not candidate_name_clean:
                                        candidate_name_clean = "Unknown"
                                    
                                    vendor_name = st.session_state.get('vendor_name', '')
                                    exists, current_status, duplicate_reason, _ = check_candidate_status_in_tracker(
                                        candidate_details, folder_name, vendor_name
                                    )
                                    
                                    if exists:
                                        if duplicate_reason.endswith("_same_vendor"):
                                            st.warning(f"⚠️ **Candidate already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                        elif duplicate_reason.endswith("_different_vendor"):
                                            file_path = ""
                                            
                                            full_report = st.session_state.get('report', '')
                                            feedback = extract_summary_from_report(full_report) if full_report else ''
                                            similarity_score = st.session_state.get('similarity_score', 0.0)
                                            average_score = st.session_state.get('average_score', 0.0)
                                            
                                            profile_shared_date = st.session_state.get('profile_shared_date', None)
                                            excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                                candidate_details, 
                                                tracker_type="rejected",
                                                folder_name=folder_name,
                                                feedback=feedback,
                                                similarity_score=similarity_score,
                                                average_score=average_score,
                                                cv_path=file_path,
                                                vendor_name=vendor_name,
                                                profile_shared_date=profile_shared_date,
                                                allow_status_change=st.session_state.get('admin_override', False)
                                            )
                                            
                                            if added:
                                                st.success("✅ Candidate added to tracker with 'Duplicate Profile' status (exists from different vendor).")
                                                if st.session_state.analysis_method == "Experiment Method":
                                                    st.session_state.experiment_single_button_state = "duplicate"
                                                else:
                                                    st.session_state.production_single_button_state = "duplicate"
                                                st.session_state.show_thanking_note_single = True
                                                st.rerun()
                                        else:
                                            st.warning(f"⚠️ **Candidate already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                    else:
                                        new_filename = f"{position_clean}_{candidate_name_clean}{file_extension}"
                                        
                                        shortlisted_folder = os.path.join(folder_name, "Shortlisted")
                                        os.makedirs(shortlisted_folder, exist_ok=True)
                                        file_path = os.path.join(shortlisted_folder, new_filename)
                                        file_path = os.path.abspath(file_path)
                                        
                                        current_action_resume_file.seek(0)
                                        with open(file_path, "wb") as f:
                                            f.write(current_action_resume_file.getbuffer())
                                        
                                        full_report = st.session_state.get('report', '')
                                        feedback = extract_summary_from_report(full_report) if full_report else ''
                                        similarity_score = st.session_state.get('similarity_score', 0.0)
                                        average_score = st.session_state.get('average_score', 0.0)
                                        
                                        profile_shared_date = st.session_state.get('profile_shared_date', None)
                                        excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                            candidate_details, 
                                            tracker_type="shortlisted",
                                            folder_name=folder_name,
                                            feedback=feedback,
                                            similarity_score=similarity_score,
                                            average_score=average_score,
                                            cv_path=file_path,
                                            vendor_name=vendor_name,
                                            profile_shared_date=profile_shared_date,
                                            allow_status_change=st.session_state.get('admin_override', False)
                                        )
                                        
                                        if added:
                                            st.success("✅ Candidate shortlisted successfully!")
                                            if st.session_state.analysis_method == "Experiment Method":
                                                st.session_state.experiment_single_button_state = "shortlisted"
                                            else:
                                                st.session_state.production_single_button_state = "shortlisted"
                                            st.session_state.show_thanking_note_single = True
                                            st.rerun()
                                        else:
                                            if duplicate_reason_ret.endswith("_same_vendor"):
                                                duplicate_msg = f"⚠️ **Candidate already screened.** Current status: {status_ret}. Cannot change status."
                                            elif duplicate_reason_ret == "already_exists":
                                                duplicate_msg = f"⚠️ **Candidate already screened.** Current status: {status_ret}. Cannot change status."
                                            else:
                                                duplicate_msg = f"⚠️ Candidate already exists in tracker. Duplicate entry prevented."
                                            
                                            st.warning(duplicate_msg)
                                            
                                        with st.expander("📋 Extracted Candidate Details", expanded=False):
                                            st.write(f"**Name:** {candidate_details.get('Candidate_Name', 'N/A')}")
                                            st.write(f"**Email:** {candidate_details.get('Email_ID', 'N/A')}")
                                            st.write(f"**Position:** {candidate_details.get('Position', 'Not Found')}")
                                            st.write(f"**Phone:** {candidate_details.get('Contact_Number', 'N/A')}")
                                            st.write(f"**Experience:** {candidate_details.get('Total_Experience', 'N/A')}")
                                            st.write(f"**Location:** {candidate_details.get('Location', 'N/A')}")
                                            st.write(f"**Status:** {candidate_details.get('Resume_Screening_Status', 'N/A')}")
                                            st.write(f"**Date:** {candidate_details.get('Screening_Date', 'N/A')}")
                                            st.write(f"**Similarity Score:** {similarity_score:.4f}")
                                            st.write(f"**Average Score:** {average_score:.4f}")
                                else:
                                    fallback_filename = current_action_resume_file.name
                                    shortlisted_folder = os.path.join(folder_name, "Shortlisted")
                                    os.makedirs(shortlisted_folder, exist_ok=True)
                                    fallback_path = os.path.join(shortlisted_folder, fallback_filename)
                                    current_action_resume_file.seek(0)
                                    with open(fallback_path, "wb") as f:
                                        f.write(current_action_resume_file.getbuffer())
                                    st.warning(f"⚠️ CV saved as: {fallback_filename} (Could not extract candidate details. Please check your API key.)")
                        else:
                            st.warning("API key required to extract candidate details for shortlisting.")
                    
                    except Exception as e:
                        st.error(f"Error saving file: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'<div id="{single_reject_container_id}">', unsafe_allow_html=True)
            if st.button("❌ Reject", type="primary" if single_button_state == "rejected" else "secondary", use_container_width=True):
                if not current_action_resume_file:
                    st.error("No resume file found")
                elif current_action_resume_file:
                    try:
                        position = st.session_state.get('extracted_position', 'Not Found')
                        
                        if not position or position == 'Not Found':
                            job_desc = st.session_state.get('job_desc', '') or ''
                            if job_desc and job_desc.strip() and st.session_state.api_key:
                                try:
                                    position = extract_position_from_jd(
                                        job_desc,
                                        st.session_state.api_key,
                                        st.session_state.model_name,
                                        st.session_state.base_url
                                    )
                                    st.session_state.extracted_position = position
                                except Exception as e:
                                    position = 'Not Found'
                        
                        selected_base_folder = st.session_state.get('selected_base_folder', '').strip()
                        if not selected_base_folder:
                            st.error("⚠️ Please select a base folder before rejecting candidates.")
                            st.stop()
                        elif not os.path.exists(selected_base_folder) or not os.path.isdir(selected_base_folder):
                            st.error(f"⚠️ Base folder does not exist: {selected_base_folder}. Please select a valid folder.")
                            st.stop()
                        
                        position_clean = re.sub(r'[^\w\s-]', '', position)
                        position_clean = position_clean.replace(' ', '_').strip('_')
                        if not position_clean or position_clean == 'Not_Found':
                            position_clean = "Not_Found"
                        
                        position_folder = f"{position_clean}_Candidates"
                        base_folder_abs = os.path.abspath(selected_base_folder)
                        folder_name = os.path.join(base_folder_abs, position_folder)
                        os.makedirs(folder_name, exist_ok=True)
                        
                        if st.session_state.api_key and st.session_state.resume:
                            with st.spinner("🔄 Extracting candidate details..."):
                                candidate_details = extract_candidate_details_llm(
                                    st.session_state.resume, 
                                    st.session_state.api_key, 
                                    st.session_state.model_name, 
                                    st.session_state.base_url
                                )
                                
                                if candidate_details:
                                    candidate_details['Position'] = position if position and position != 'Not Found' else 'Not Found'
                                    
                                    vendor_name = st.session_state.get('vendor_name', '')
                                    exists, current_status, duplicate_reason, _ = check_candidate_status_in_tracker(
                                        candidate_details, folder_name, vendor_name
                                    )
                                    
                                    if exists:
                                        if duplicate_reason.endswith("_same_vendor"):
                                            st.warning(f"⚠️ **Candidate already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                        elif duplicate_reason.endswith("_different_vendor"):
                                            file_path = ""
                                            
                                            full_report = st.session_state.get('report', '')
                                            feedback = extract_failed_points_explanations(full_report) if full_report else ''
                                            similarity_score = st.session_state.get('similarity_score', 0.0)
                                            average_score = st.session_state.get('average_score', 0.0)
                                            
                                            profile_shared_date = st.session_state.get('profile_shared_date', None)
                                            excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                                candidate_details, 
                                                tracker_type="rejected",
                                                folder_name=folder_name,
                                                feedback=feedback,
                                                similarity_score=similarity_score,
                                                average_score=average_score,
                                                cv_path=file_path,
                                                vendor_name=vendor_name,
                                                profile_shared_date=profile_shared_date,
                                                allow_status_change=st.session_state.get('admin_override', False)
                                            )
                                            
                                            if added:
                                                st.success("✅ Candidate added to tracker with 'Duplicate Profile' status (exists from different vendor).")
                                                if st.session_state.analysis_method == "Experiment Method":
                                                    st.session_state.experiment_single_button_state = "duplicate"
                                                else:
                                                    st.session_state.production_single_button_state = "duplicate"
                                                st.session_state.show_thanking_note_single = True
                                                st.rerun()
                                        else:
                                            st.warning(f"⚠️ **Candidate already screened.** Current status: **{current_status}**. Cannot change status (first come first serve).")
                                    else:
                                        full_report = st.session_state.get('report', '')
                                        feedback = extract_failed_points_explanations(full_report) if full_report else ''
                                        similarity_score = st.session_state.get('similarity_score', 0.0)
                                        average_score = st.session_state.get('average_score', 0.0)
                                        
                                        profile_shared_date = st.session_state.get('profile_shared_date', None)
                                        excel_path, added, duplicate_reason_ret, profile_remark, status_ret = update_tracker_excel(
                                            candidate_details, 
                                            tracker_type="rejected",
                                            folder_name=folder_name,
                                            feedback=feedback,
                                            similarity_score=similarity_score,
                                            average_score=average_score,
                                            vendor_name=vendor_name,
                                            profile_shared_date=profile_shared_date,
                                            allow_status_change=st.session_state.get('admin_override', False)
                                        )
                                        
                                        if added:
                                            st.success("✅ Candidate rejected successfully!")
                                            if st.session_state.analysis_method == "Experiment Method":
                                                st.session_state.experiment_single_button_state = "rejected"
                                            else:
                                                st.session_state.production_single_button_state = "rejected"
                                            st.session_state.show_thanking_note_single = True
                                            st.rerun()
                                        else:
                                            if duplicate_reason_ret.endswith("_same_vendor"):
                                                duplicate_msg = f"⚠️ **Candidate already screened.** Current status: {status_ret}. Cannot change status."
                                            elif duplicate_reason_ret == "already_exists":
                                                duplicate_msg = f"⚠️ **Candidate already screened.** Current status: {status_ret}. Cannot change status."
                                            else:
                                                duplicate_msg = f"⚠️ Candidate already exists in tracker. Duplicate entry prevented."
                                            
                                            st.warning(duplicate_msg)
                                else:
                                    st.warning("Could not extract candidate details. Please check your API key.")
                        else:
                            st.warning("API key required to extract candidate details for rejection tracking.")
                            
                    except Exception as e:
                        st.error(f"Error processing rejection: {str(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.show_thanking_note_single:
        st.markdown("---")
        st.info("💬 Your selection has been processed. Thank you for utilizing Smart AI Recruiter to enhance your talent acquisition.")
        st.session_state.show_thanking_note_single = False

# Add error handling wrapper (uncomment if needed for debugging)
# try:
#     # All page content above
#     pass
# except Exception as e:
#     st.error(f"❌ Error loading Screener page: {str(e)}")
#     st.exception(e)

