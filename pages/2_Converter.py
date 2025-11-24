"""
Converter Page - CV to PPT Conversion
Converts candidate CVs to PPT format based on tracker status
"""
import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import tempfile
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Import utility functions
try:
    from utils_v2.text_extraction import extract_resume_text, extract_jd_text
    from utils_v2.cv_info_extraction import extract_cv_info_for_ppt
    from utils_v2.ppt_operations import read_sample_ppt_structure, create_ppt_from_sample
    from utils_v2.tracker import update_cv_conversion_status
except ImportError as e:
    st.error(f"❌ Import Error: {str(e)}")
    st.stop()

# Initialize session state for Converter page
if "converter_api_key" not in st.session_state:
    st.session_state.converter_api_key = ""
if "converter_model_name" not in st.session_state:
    st.session_state.converter_model_name = ""
if "converter_base_url" not in st.session_state:
    st.session_state.converter_base_url = ""

# Page title
st.title("🔄 Document Converter - CV to PPT")

st.markdown("---")

# Sidebar for LLM settings (needed for CV information extraction) - Generalized Approach
with st.sidebar:
    st.subheader("LLM Settings")
    st.caption("💡 Required for extracting CV information. Works with any OpenAI-compatible API provider.")
    
    # API Key input
    st.session_state.converter_api_key = st.text_input(
        "API Key", 
        value=st.session_state.converter_api_key, 
        type="password",
        help="Enter your API key (e.g., Groq: gsk_..., OpenRouter: sk-or-..., OpenAI: sk-...)"
    )
    
    # Model Name input
    st.session_state.converter_model_name = st.text_input(
        "Model Name",
        value=st.session_state.converter_model_name,
        placeholder="e.g., llama-3.3-70b-versatile, gpt-4, openai/gpt-oss-20b:free",
        help="Enter the exact model name as required by your API provider"
    )
    
    # Base URL input (optional, with auto-detection)
    base_url_input = st.text_input(
        "Base URL (Optional)",
        value=st.session_state.converter_base_url if st.session_state.converter_base_url else "",
        placeholder="Auto-detected from API key if empty",
        help="Leave empty for auto-detection. Examples: https://api.groq.com/openai/v1, https://openrouter.ai/api/v1"
    )
    st.session_state.converter_base_url = base_url_input.strip() if base_url_input and base_url_input.strip() else None
    
    # Show detected base URL if auto-detection is used
    if not st.session_state.converter_base_url and st.session_state.converter_api_key:
        from utils_v2.client_helper import detect_base_url
        detected_url = detect_base_url(st.session_state.converter_api_key)
        st.caption(f"🔍 Auto-detected: `{detected_url}`")

st.markdown("---")

# File Upload Section
st.subheader("📁 File Uploads")

# Sample PPT upload
sample_ppt_file = st.file_uploader(
    "Upload Sample PPT Template",
    type=["pptx"],
    help="Upload the sample PPT template that will be used as the base for conversion"
)

# Tracker Excel upload
tracker_file = st.file_uploader(
    "Upload Tracker Excel File",
    type=["xlsx"],
    help="Upload the tracker Excel file containing candidate information"
)

st.markdown("---")

# Processing Section
if sample_ppt_file and tracker_file and st.session_state.converter_api_key:
    if st.button("🚀 Start Conversion", type="primary"):
        try:
            # Save uploaded files temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp_ppt:
                tmp_ppt.write(sample_ppt_file.getbuffer())
                sample_ppt_path = tmp_ppt.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_tracker:
                tmp_tracker.write(tracker_file.getbuffer())
                tmp_tracker_path = tmp_tracker.name
            
            # Read tracker Excel
            df = pd.read_excel(tmp_tracker_path)
            
            if df.empty:
                st.error("❌ Tracker file is empty!")
                st.stop()
            
            # Check required columns
            required_columns = ['R2_Status', 'CV_Conversion_Status', 'Candidate_Name', 'Position', 'Location', 'Shortlisted_CV_Path']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.error(f"❌ Tracker missing required columns: {', '.join(missing_columns)}")
                st.stop()
            
            # Filter candidates to process
            # R2_Status == "Selected" AND CV_Conversion_Status is empty
            df['R2_Status'] = df['R2_Status'].astype(str).str.strip()
            df['CV_Conversion_Status'] = df['CV_Conversion_Status'].astype(str).str.strip()
            
            # Filter: R2_Status == "Selected" AND (CV_Conversion_Status is empty or "Not Found" or "nan")
            candidates_to_process = df[
                (df['R2_Status'].str.lower() == 'selected') &
                (df['CV_Conversion_Status'].isin(['', 'Not Found', 'nan', 'None']) | df['CV_Conversion_Status'].isna())
            ].copy()
            
            if candidates_to_process.empty:
                st.info("ℹ️ No candidates found to process. All selected candidates are already converted or R2_Status is not 'Selected'.")
                st.stop()
            
            st.success(f"✅ Found {len(candidates_to_process)} candidate(s) to process")
            st.markdown("---")
            
            # Process each candidate
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            successful_conversions = []
            failed_conversions = []
            
            for idx, (row_idx, candidate) in enumerate(candidates_to_process.iterrows()):
                candidate_name = str(candidate.get('Candidate_Name', 'Unknown')).strip()
                position = str(candidate.get('Position', 'Not Found')).strip()
                location = str(candidate.get('Location', 'Not Found')).strip()
                cv_path = str(candidate.get('Shortlisted_CV_Path', '')).strip()
                email_id = str(candidate.get('Email_ID', '')).strip()
                contact_number = str(candidate.get('Contact_Number', '')).strip()
                
                status_text.text(f"Processing {idx + 1} of {len(candidates_to_process)}: {candidate_name}")
                progress_bar.progress((idx + 1) / len(candidates_to_process))
                
                try:
                    # Check if CV path exists
                    if not cv_path or cv_path in ['Not Found', '', 'nan', 'None']:
                        failed_conversions.append({
                            'candidate': candidate_name,
                            'reason': 'CV path not found in tracker'
                        })
                        continue
                    
                    if not os.path.exists(cv_path):
                        failed_conversions.append({
                            'candidate': candidate_name,
                            'reason': f'CV file not found at: {cv_path}'
                        })
                        continue
                    
                    # Read CV file
                    cv_extension = os.path.splitext(cv_path)[1].lower()
                    cv_text = ""
                    
                    # Extract text from CV based on file type
                    try:
                        if cv_extension == '.pdf':
                            from utils_v2.text_extraction import extract_pdf_text
                            with open(cv_path, 'rb') as cv_file:
                                cv_text = extract_pdf_text(cv_file)
                        elif cv_extension == '.docx':
                            from utils_v2.text_extraction import extract_docx_text
                            # extract_docx_text can handle file path directly
                            cv_text = extract_docx_text(cv_path)
                        elif cv_extension == '.doc':
                            from utils_v2.text_extraction import extract_doc_text
                            with open(cv_path, 'rb') as cv_file:
                                cv_text = extract_doc_text(cv_file)
                        elif cv_extension == '.txt':
                            with open(cv_path, 'r', encoding='utf-8', errors='ignore') as cv_file:
                                cv_text = cv_file.read()
                        else:
                            failed_conversions.append({
                                'candidate': candidate_name,
                                'reason': f'Unsupported CV file format: {cv_extension}'
                            })
                            continue
                    except Exception as extract_error:
                        failed_conversions.append({
                            'candidate': candidate_name,
                            'reason': f'Error extracting text from CV: {str(extract_error)}'
                        })
                        continue
                    
                    if not cv_text or not cv_text.strip():
                        failed_conversions.append({
                            'candidate': candidate_name,
                            'reason': f'Could not extract text from CV (file may be corrupted or empty). File: {os.path.basename(cv_path)}'
                        })
                        continue
                    
                    # Extract CV information using LLM
                    cv_info = extract_cv_info_for_ppt(cv_text, st.session_state.converter_api_key, st.session_state.converter_model_name, st.session_state.converter_base_url)
                    
                    if not cv_info:
                        failed_conversions.append({
                            'candidate': candidate_name,
                            'reason': 'Failed to extract CV information'
                        })
                        continue
                    
                    # Prepare candidate data for PPT
                    candidate_data = {
                        'candidate_name': candidate_name,
                        'position': position,
                        'location': location,
                        'area_of_expertise': cv_info.get('area_of_expertise', 'Not Found'),
                        'education': cv_info.get('education', 'Not Found'),
                        'profile_summary': cv_info.get('profile_summary', 'Not Found'),
                        'project1': cv_info.get('project1', {}),
                        'project2': cv_info.get('project2', {}),
                        'project3': cv_info.get('project3', {}),
                        'project4': cv_info.get('project4', {})
                    }
                    
                    # Determine output folder and filename
                    # Clean position name for folder
                    position_clean = re.sub(r'[^\w\s-]', '', position)
                    position_clean = position_clean.replace(' ', '_').strip('_')
                    if not position_clean or position_clean == 'Not_Found':
                        position_clean = "Not_Found"
                    
                    # Create Converted_CVs folder at the same level as Tracker folder
                    # CV path structure: {Client}/{Position}_Candidates/Shortlisted/{file}
                    # We need: {Client}/{Position}_Candidates/Converted_CVs_{Position}/
                    if cv_path and os.path.exists(cv_path):
                        # Get the directory containing the CV file
                        cv_dir = os.path.dirname(cv_path)
                        # Go up one level to get {Client}/{Position}_Candidates/
                        base_dir = os.path.dirname(cv_dir)
                        # Create Converted_CVs folder
                        converted_folder = os.path.join(base_dir, f"Converted_CVs_{position_clean}")
                    else:
                        # Fallback: create in current directory if CV path is invalid
                        converted_folder = f"Converted_CVs_{position_clean}"
                    
                    os.makedirs(converted_folder, exist_ok=True)
                    
                    # Generate output filename: Current_Date_Position_Candidate_Name.pptx
                    current_date = datetime.now().strftime('%Y%m%d')
                    candidate_name_clean = re.sub(r'[^\w\s-]', '', candidate_name)
                    candidate_name_clean = candidate_name_clean.replace(' ', '_').strip('_')
                    if not candidate_name_clean:
                        candidate_name_clean = "Unknown"
                    
                    output_filename = f"{current_date}_{position_clean}_{candidate_name_clean}.pptx"
                    output_path = os.path.join(converted_folder, output_filename)
                    
                    # Create PPT from sample
                    success = create_ppt_from_sample(sample_ppt_path, candidate_data, output_path)
                    
                    if success:
                        # Update tracker
                        update_success, update_message = update_cv_conversion_status(
                            tmp_tracker_path,
                            candidate_email=email_id if email_id not in ['Not Found', '', 'nan', 'None'] else None,
                            candidate_name=candidate_name if candidate_name not in ['Not Found', '', 'nan', 'None'] else None,
                            contact_number=contact_number if contact_number not in ['Not Found', '', 'nan', 'None'] else None,
                            converted_ppt_path=output_path
                        )
                        
                        if update_success:
                            successful_conversions.append({
                                'candidate': candidate_name,
                                'ppt_path': output_path
                            })
                        else:
                            successful_conversions.append({
                                'candidate': candidate_name,
                                'ppt_path': output_path,
                                'warning': f'PPT created but tracker update failed: {update_message}'
                            })
                    else:
                        failed_conversions.append({
                            'candidate': candidate_name,
                            'reason': 'Failed to create PPT'
                        })
                
                except Exception as e:
                    failed_conversions.append({
                        'candidate': candidate_name,
                        'reason': f'Error: {str(e)}'
                    })
                    continue
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Show results
            st.markdown("---")
            st.subheader("📊 Conversion Results")
            
            if successful_conversions:
                st.success(f"✅ Successfully converted {len(successful_conversions)} candidate(s)")
                with st.expander("View successful conversions"):
                    for conv in successful_conversions:
                        st.write(f"**{conv['candidate']}**")
                        st.caption(f"PPT saved at: {conv['ppt_path']}")
                        if 'warning' in conv:
                            st.warning(conv['warning'])
                        st.markdown("---")
            
            if failed_conversions:
                st.error(f"❌ Failed to convert {len(failed_conversions)} candidate(s)")
                with st.expander("View failed conversions"):
                    for conv in failed_conversions:
                        st.write(f"**{conv['candidate']}**")
                        st.caption(f"Reason: {conv['reason']}")
                        st.markdown("---")
            
            # Save updated tracker back to original location
            # Try to determine original tracker path from CV paths
            original_tracker_path = None
            if successful_conversions:
                # Get the first successful conversion's CV path to determine tracker location
                first_candidate = candidates_to_process.iloc[0]
                first_cv_path = str(first_candidate.get('Shortlisted_CV_Path', '')).strip()
                
                if first_cv_path and os.path.exists(first_cv_path):
                    # CV path: {Client}/{Position}_Candidates/Shortlisted/{file}
                    # Tracker path: {Client}/{Position}_Candidates/Tracker/Candidates_Tracker.xlsx
                    cv_dir = os.path.dirname(first_cv_path)  # Shortlisted folder
                    base_dir = os.path.dirname(cv_dir)  # Position_Candidates folder
                    tracker_dir = os.path.join(base_dir, "Tracker")
                    original_tracker_path = os.path.join(tracker_dir, "Candidates_Tracker.xlsx")
            
            # Copy updated tracker to original location if we can determine it
            if original_tracker_path and os.path.exists(os.path.dirname(original_tracker_path)):
                try:
                    import shutil
                    shutil.copy2(tmp_tracker_path, original_tracker_path)
                    st.success(f"✅ Tracker updated successfully at: {original_tracker_path}")
                except Exception as e:
                    st.warning(f"⚠️ Could not save tracker to original location: {str(e)}")
                    st.info("💡 **Note**: Please download the updated tracker file manually.")
                    # Provide download button for updated tracker
                    with open(tmp_tracker_path, 'rb') as f:
                        st.download_button(
                            label="📥 Download Updated Tracker",
                            data=f.read(),
                            file_name="Candidates_Tracker_Updated.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            else:
                st.info("💡 **Note**: Could not determine original tracker location. Please download the updated tracker file.")
                # Provide download button for updated tracker
                with open(tmp_tracker_path, 'rb') as f:
                    st.download_button(
                        label="📥 Download Updated Tracker",
                        data=f.read(),
                        file_name="Candidates_Tracker_Updated.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            # Clean up temp files
            try:
                os.unlink(sample_ppt_path)
                # Keep tracker temp file for download if original path not found
                if original_tracker_path and os.path.exists(original_tracker_path):
                    try:
                        os.unlink(tmp_tracker_path)
                    except:
                        pass
            except:
                pass
            
        except Exception as e:
            st.error(f"❌ Error during conversion: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

elif not st.session_state.converter_api_key:
    st.warning("⚠️ Please enter your API Key in the sidebar to proceed with conversion.")
elif not sample_ppt_file:
    st.info("ℹ️ Please upload a Sample PPT template file.")
elif not tracker_file:
    st.info("ℹ️ Please upload a Tracker Excel file.")

st.markdown("---")

# Instructions
with st.expander("📖 How to Use"):
    st.markdown("""
    ### Step-by-Step Instructions:
    
    1. **Configure LLM Settings** (Sidebar)
       - Select your LLM provider (Groq or OpenRouter)
       - Enter your API key
       - Select the model
    
    2. **Upload Sample PPT Template**
       - Upload the PPT template that will be used as the base
       - The template should have placeholders or identifiable sections for:
         - Candidate Name
         - Position
         - Location
         - Area of Expertise
         - Education
         - Profile Summary
         - Project 1
         - Project 2
    
    3. **Upload Tracker Excel File**
       - Upload the tracker Excel file containing candidate information
       - The tracker should have columns: R2_Status, CV_Conversion_Status, Candidate_Name, Position, Location, Shortlisted_CV_Path
    
    4. **Start Conversion**
       - Click "Start Conversion" button
       - The system will:
         - Filter candidates where R2_Status = "Selected" AND CV_Conversion_Status is empty
         - Extract information from each candidate's CV
         - Create PPT files in Converted_CVs_{Position} folder
         - Update tracker with conversion status
    
    ### Output:
    - Converted PPT files will be saved in: `{Client}/{Position}_Candidates/Converted_CVs_{Position}/`
    - Filename format: `{Date}_{Position}_{Candidate_Name}.pptx`
    - Tracker will be updated with CV_Conversion_Status = "Converted" and CV_Converted_Path
    """)
