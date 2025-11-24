"""
Excel tracker functions for candidate management
"""
import pandas as pd
import os
import re
from datetime import datetime


def check_candidate_status_in_tracker(candidate_details, folder_name, vendor_name=""):
    """Check if candidate exists in tracker and return current status
    
    Args:
        candidate_details: Dictionary with candidate information
        folder_name: Base folder name (e.g., "Client_Name/Position_Candidates" or absolute path)
        vendor_name: Name of the vendor (optional)
    
    Returns:
        tuple: (exists, current_status, duplicate_reason, profile_remark)
            - exists: True if candidate exists, False otherwise
            - current_status: Current status if exists (Shortlisted/Rejected/Duplicate Profile), None otherwise
            - duplicate_reason: Reason code if duplicate
            - profile_remark: Profile remark if exists
    """
    # Normalize folder path (handle both relative and absolute paths)
    folder_name = os.path.normpath(folder_name)
    tracker_folder = os.path.join(folder_name, "Tracker")
    excel_path = os.path.join(tracker_folder, "Candidates_Tracker.xlsx")
    
    if not os.path.exists(excel_path):
        return False, None, "", ""
    
    try:
        df = pd.read_excel(excel_path)
        if df.empty:
            return False, None, "", ""
    except:
        return False, None, "", ""
    
    email_id = candidate_details.get('Email_ID', '')
    candidate_name = candidate_details.get('Candidate_Name', '')
    contact_number = candidate_details.get('Contact_Number', '')
    vendor_name_norm = str(vendor_name).strip().lower() if vendor_name else ""
    
    # Normalize values for comparison
    email_id_norm = str(email_id).strip().lower() if email_id and str(email_id).strip().lower() not in ['not found', ''] else None
    candidate_name_norm = str(candidate_name).strip().lower() if candidate_name and str(candidate_name).strip().lower() not in ['not found', ''] else None
    contact_number_norm = str(contact_number).strip().lower() if contact_number and str(contact_number).strip().lower() not in ['not found', ''] else None
    
    if contact_number_norm:
        contact_number_norm = re.sub(r'[\s\-\(\)]', '', contact_number_norm)
    
    # Check by email first
    if email_id_norm and 'Email_ID' in df.columns:
        existing_emails = df['Email_ID'].astype(str).str.strip().str.lower()
        valid_emails = existing_emails[~existing_emails.isin(['not found', '', 'nan', 'none'])]
        if not valid_emails.empty and email_id_norm in valid_emails.values:
            matching_rows = df[df['Email_ID'].astype(str).str.strip().str.lower() == email_id_norm]
            if not matching_rows.empty:
                # Check ALL matching rows for same vendor first (Scenario 2.3: prevent same vendor duplicates)
                if 'Vendor_Name' in df.columns:
                    # Check if ANY matching row has the same vendor
                    same_vendor_found = False
                    same_vendor_row = None
                    for idx, row in matching_rows.iterrows():
                        existing_vendor = str(row['Vendor_Name']).strip().lower() if pd.notna(row['Vendor_Name']) else ""
                        if vendor_name_norm and existing_vendor and vendor_name_norm == existing_vendor:
                            same_vendor_found = True
                            same_vendor_row = row
                            break
                    
                    if same_vendor_found:
                        # Same vendor found - return same_vendor (block entry)
                        current_status = same_vendor_row.get('Resume_Screening_Status', 'Unknown')
                        profile_remark = same_vendor_row.get('Profile_Remark', '')
                        return True, current_status, "email_same_vendor", profile_remark
                
                # No same vendor found in any row - treat as different vendor (allow entry with "Duplicate Profile")
                # Use first row for status/remark (but we know it's different vendor)
                current_status = matching_rows.iloc[0].get('Resume_Screening_Status', 'Unknown')
                profile_remark = matching_rows.iloc[0].get('Profile_Remark', '')
                return True, current_status, "email_different_vendor", profile_remark
    
    # Check by name + phone (both required)
    if candidate_name_norm and contact_number_norm and 'Candidate_Name' in df.columns and 'Contact_Number' in df.columns:
        df_name_norm = df['Candidate_Name'].astype(str).str.strip().str.lower()
        df_contact_norm = df['Contact_Number'].astype(str).str.strip().str.lower()
        df_contact_norm = df_contact_norm.apply(lambda x: re.sub(r'[\s\-\(\)]', '', x) if x not in ['not found', '', 'nan', 'none'] else x)
        
        valid_rows = (~df_name_norm.isin(['not found', '', 'nan', 'none'])) & (~df_contact_norm.isin(['not found', '', 'nan', 'none']))
        
        if valid_rows.any():
            name_match = df_name_norm[valid_rows] == candidate_name_norm
            contact_match = df_contact_norm[valid_rows] == contact_number_norm
            combined_match = name_match & contact_match
            
            if combined_match.any():
                matching_indices = df[valid_rows][combined_match].index
                matching_rows = df.loc[matching_indices]
                
                # Check ALL matching rows for same vendor first (Scenario 2.3: prevent same vendor duplicates)
                if 'Vendor_Name' in df.columns:
                    # Check if ANY matching row has the same vendor
                    same_vendor_found = False
                    same_vendor_row = None
                    for idx, row in matching_rows.iterrows():
                        existing_vendor = str(row['Vendor_Name']).strip().lower() if pd.notna(row['Vendor_Name']) else ""
                        if vendor_name_norm and existing_vendor and vendor_name_norm == existing_vendor:
                            same_vendor_found = True
                            same_vendor_row = row
                            break
                    
                    if same_vendor_found:
                        # Same vendor found - return same_vendor (block entry)
                        current_status = same_vendor_row.get('Resume_Screening_Status', 'Unknown')
                        profile_remark = same_vendor_row.get('Profile_Remark', '')
                        return True, current_status, "name_and_phone_same_vendor", profile_remark
                
                # No same vendor found in any row - treat as different vendor (allow entry with "Duplicate Profile")
                # Use first row for status/remark (but we know it's different vendor)
                current_status = matching_rows.iloc[0].get('Resume_Screening_Status', 'Unknown')
                profile_remark = matching_rows.iloc[0].get('Profile_Remark', '')
                return True, current_status, "name_and_phone_different_vendor", profile_remark
    
    # Fallback: Check by name + vendor (when contact number is missing but name exists)
    # This is a fallback for cases where contact number is not available in CV
    # Only check for same vendor duplicates (to avoid false positives with common names)
    if candidate_name_norm and not contact_number_norm and vendor_name_norm and 'Candidate_Name' in df.columns and 'Vendor_Name' in df.columns:
        df_name_norm = df['Candidate_Name'].astype(str).str.strip().str.lower()
        valid_rows = ~df_name_norm.isin(['not found', '', 'nan', 'none'])
        
        if valid_rows.any():
            name_match = df_name_norm[valid_rows] == candidate_name_norm
            
            if name_match.any():
                matching_indices = df[valid_rows][name_match].index
                matching_rows = df.loc[matching_indices]
                
                # Check ALL matching rows for same vendor (only block same vendor + same name)
                same_vendor_found = False
                same_vendor_row = None
                for idx, row in matching_rows.iterrows():
                    existing_vendor = str(row['Vendor_Name']).strip().lower() if pd.notna(row['Vendor_Name']) else ""
                    if vendor_name_norm and existing_vendor and vendor_name_norm == existing_vendor:
                        same_vendor_found = True
                        same_vendor_row = row
                        break
                
                if same_vendor_found:
                    # Same vendor + same name found (even without contact number) - block entry
                    current_status = same_vendor_row.get('Resume_Screening_Status', 'Unknown')
                    profile_remark = same_vendor_row.get('Profile_Remark', '')
                    return True, current_status, "name_and_vendor_same_vendor", profile_remark
    
    return False, None, "", ""


def update_tracker_excel(candidate_details, tracker_type="shortlisted", folder_name="shortlisted_candidate", feedback="", similarity_score=0.0, average_score=0.0, cv_path="", vendor_name="", profile_shared_date=None, allow_status_change=False):
    """Update or create unified Tracker Excel file with candidate details
    
    NEW UNIFIED TRACKER APPROACH:
    - Single tracker file: Candidates_Tracker.xlsx
    - First come first serve: Once candidate is processed, status cannot be changed
    - Folder structure: Client_Name/Position_Candidates/Shortlisted/ (for CVs) and Tracker/ (for Excel)
    
    Args:
        candidate_details: Dictionary with candidate information
        tracker_type: "shortlisted" or "rejected"
        folder_name: Base folder name (e.g., "Client_Name/Position_Candidates" or absolute path)
        feedback: Resume screening feedback
        similarity_score: ATS similarity score
        average_score: Average score from LLM report
        cv_path: File path of the shortlisted CV (only for shortlisted candidates)
        vendor_name: Name of the vendor (optional)
        profile_shared_date: Date when profile was shared (optional, datetime.date object or string)
        allow_status_change: If True, allows admin override to change status (default: False)
    
    Returns:
        tuple: (excel_path, added, duplicate_reason, profile_remark, current_status)
            - excel_path: Path to tracker file
            - added: True if added successfully, False if prevented
            - duplicate_reason: Reason code ("already_exists", "duplicate_same_vendor", etc.)
            - profile_remark: "Unique Profile" or "Duplicate Profile"
            - current_status: Current status if candidate already exists, None otherwise
    """
    # Normalize folder path (handle both relative and absolute paths)
    folder_name = os.path.normpath(folder_name)
    
    # Create unified folder structure: Client_Name/Position_Candidates/Shortlisted/ and Tracker/
    shortlisted_folder = os.path.join(folder_name, "Shortlisted")
    os.makedirs(shortlisted_folder, exist_ok=True)
    
    tracker_folder = os.path.join(folder_name, "Tracker")
    os.makedirs(tracker_folder, exist_ok=True)
    
    # Single unified tracker file
    excel_filename = "Candidates_Tracker.xlsx"
    excel_path = os.path.join(tracker_folder, excel_filename)
    
    # FIRST COME FIRST SERVE LOGIC: Check if candidate already exists
    desired_status = "Shortlisted" if tracker_type.lower() == "shortlisted" else "Rejected"
    
    # Check if candidate exists in tracker
    exists, current_status, duplicate_reason, existing_profile_remark = check_candidate_status_in_tracker(
        candidate_details, folder_name, vendor_name
    )
    
    # Track if this is a different vendor duplicate (will be added with "Duplicate Profile")
    is_different_vendor_duplicate = False
    
    # If candidate exists, apply first-come-first-serve logic
    if exists:
        # If same vendor duplicate, prevent entry
        if duplicate_reason.endswith("_same_vendor"):
            return excel_path, False, duplicate_reason, existing_profile_remark, current_status
        
        # If different vendor duplicate, allow entry but mark as "Duplicate Profile"
        # This allows tracking same candidate from different vendors
        if duplicate_reason.endswith("_different_vendor"):
            # Different vendor - continue to add with "Duplicate Profile" status
            is_different_vendor_duplicate = True
            profile_remark = "Duplicate Profile"
            # Continue processing below to add the entry (don't return, fall through)
        elif not allow_status_change:
            # Same vendor but different status change attempt - prevent (first come first serve)
            return excel_path, False, "already_exists", existing_profile_remark, current_status
        else:
            # Admin override: Update existing record's status
            # Read existing tracker
            try:
                df = pd.read_excel(excel_path)
                # Find and update the existing row
                email_id = candidate_details.get('Email_ID', '')
                candidate_name = candidate_details.get('Candidate_Name', '')
                contact_number = candidate_details.get('Contact_Number', '')
                
                # Find matching row (same logic as check function)
                email_id_norm = str(email_id).strip().lower() if email_id and str(email_id).strip().lower() not in ['not found', ''] else None
                candidate_name_norm = str(candidate_name).strip().lower() if candidate_name and str(candidate_name).strip().lower() not in ['not found', ''] else None
                contact_number_norm = str(contact_number).strip().lower() if contact_number and str(contact_number).strip().lower() not in ['not found', ''] else None
                
                if contact_number_norm:
                    contact_number_norm = re.sub(r'[\s\-\(\)]', '', contact_number_norm)
                
                matching_idx = None
                if email_id_norm and 'Email_ID' in df.columns:
                    matching_rows = df[df['Email_ID'].astype(str).str.strip().str.lower() == email_id_norm]
                    if not matching_rows.empty:
                        matching_idx = matching_rows.index[0]
                elif candidate_name_norm and contact_number_norm and 'Candidate_Name' in df.columns and 'Contact_Number' in df.columns:
                    df_name_norm = df['Candidate_Name'].astype(str).str.strip().str.lower()
                    df_contact_norm = df['Contact_Number'].astype(str).str.strip().str.lower()
                    df_contact_norm = df_contact_norm.apply(lambda x: re.sub(r'[\s\-\(\)]', '', x) if x not in ['not found', '', 'nan', 'none'] else x)
                    valid_rows = (~df_name_norm.isin(['not found', '', 'nan', 'none'])) & (~df_contact_norm.isin(['not found', '', 'nan', 'none']))
                    if valid_rows.any():
                        name_match = df_name_norm[valid_rows] == candidate_name_norm
                        contact_match = df_contact_norm[valid_rows] == contact_number_norm
                        combined_match = name_match & contact_match
                        if combined_match.any():
                            matching_idx = df[valid_rows][combined_match].index[0]
                
                if matching_idx is not None:
                    # Update existing row
                    df.loc[matching_idx, 'Resume_Screening_Status'] = desired_status
                    df.loc[matching_idx, 'Screening_Date'] = datetime.now().strftime('%Y-%m-%d')
                    df.loc[matching_idx, 'Resume_Screening_Feedback'] = feedback
                    df.loc[matching_idx, 'Similarity_Score'] = similarity_score
                    df.loc[matching_idx, 'Average_Score'] = average_score
                    if tracker_type.lower() == "shortlisted" and cv_path:
                        df.loc[matching_idx, 'Shortlisted_CV_Path'] = cv_path
                    elif tracker_type.lower() == "rejected":
                        df.loc[matching_idx, 'Shortlisted_CV_Path'] = ''  # Clear CV path if rejecting
                    
                    df.to_excel(excel_path, index=False)
                    return excel_path, True, "status_updated", existing_profile_remark, desired_status
            except Exception:
                pass  # If update fails, fall through to add new logic
    
    # Candidate doesn't exist or is being added for first time (or different vendor duplicate)
    # Initialize profile_remark if not already set (from different vendor duplicate above)
    if not is_different_vendor_duplicate:
        profile_remark = "Unique Profile"
    
    # Read tracker to check for duplicates (skip if already identified as different vendor duplicate)
    if os.path.exists(excel_path):
        try:
            df = pd.read_excel(excel_path)
            # Rename old column name if exists
            if 'Date_Shortlisted' in df.columns:
                if 'Screening_Date' not in df.columns:
                    df['Screening_Date'] = df['Date_Shortlisted']
                df = df.drop(columns=['Date_Shortlisted'])
            if 'Profile_Remark' in df.columns and 'Resume_Screening_Status' in df.columns:
                try:
                    df.loc[df['Profile_Remark'].astype(str).str.strip().str.lower() == 'duplicate profile', 'Resume_Screening_Status'] = 'Duplicate Profile'
                except Exception:
                    pass
            
            # Define manual columns that users will fill (always empty by default)
            manual_columns = [
                'R1_Schedule_Date',
                'R1_Panel_Name',
                'R1_Feedback',
                'R1_Status',
                'R2_Schedule_Date',
                'R2_Panel_Name',
                'R2_Feedback',
                'R2_Status',
                'CV_Conversion_Status',
                'CV_Converted_Path'
            ]
            
            # Add manual columns to existing tracker if they don't exist (backward compatibility)
            for col in manual_columns:
                if col not in df.columns:
                    df[col] = ""
        except:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    
    # Check for duplicates (for same vendor blocking and different vendor marking) - only if not already identified as different vendor duplicate
    if not is_different_vendor_duplicate:
        email_id = candidate_details.get('Email_ID', '')
        candidate_name = candidate_details.get('Candidate_Name', '')
        contact_number = candidate_details.get('Contact_Number', '')
        vendor_name_norm = str(vendor_name).strip().lower() if vendor_name else ""
        
        if not df.empty:
            email_id_norm = str(email_id).strip().lower() if email_id and str(email_id).strip().lower() not in ['not found', ''] else None
            candidate_name_norm = str(candidate_name).strip().lower() if candidate_name and str(candidate_name).strip().lower() not in ['not found', ''] else None
            contact_number_norm = str(contact_number).strip().lower() if contact_number and str(contact_number).strip().lower() not in ['not found', ''] else None
            
            if contact_number_norm:
                contact_number_norm = re.sub(r'[\s\-\(\)]', '', contact_number_norm)
            
            # Check by email - check for same vendor duplicates first (BLOCK)
            if email_id_norm and 'Email_ID' in df.columns:
                existing_emails = df['Email_ID'].astype(str).str.strip().str.lower()
                valid_emails = existing_emails[~existing_emails.isin(['not found', '', 'nan', 'none'])]
                if not valid_emails.empty and email_id_norm in valid_emails.values:
                    matching_rows = df[df['Email_ID'].astype(str).str.strip().str.lower() == email_id_norm]
                    if not matching_rows.empty and 'Vendor_Name' in df.columns:
                        # Check ALL matching rows for same vendor (critical for batch processing)
                        for idx, row in matching_rows.iterrows():
                            existing_vendor = str(row['Vendor_Name']).strip().lower() if pd.notna(row['Vendor_Name']) else ""
                            if vendor_name_norm and existing_vendor and vendor_name_norm == existing_vendor:
                                # Same vendor duplicate found - BLOCK
                                current_status_inner = row.get('Resume_Screening_Status', 'Unknown')
                                return excel_path, False, "email_same_vendor", row.get('Profile_Remark', ''), current_status_inner
                        # No same vendor found - check for different vendor
                        existing_vendor = str(matching_rows.iloc[0]['Vendor_Name']).strip().lower() if pd.notna(matching_rows.iloc[0]['Vendor_Name']) else ""
                        if vendor_name_norm and existing_vendor and vendor_name_norm != existing_vendor:
                            profile_remark = "Duplicate Profile"
            
            # Check by name + phone - check for same vendor duplicates first (BLOCK)
            if profile_remark == "Unique Profile" and candidate_name_norm and contact_number_norm:
                if 'Candidate_Name' in df.columns and 'Contact_Number' in df.columns:
                    df_name_norm = df['Candidate_Name'].astype(str).str.strip().str.lower()
                    df_contact_norm = df['Contact_Number'].astype(str).str.strip().str.lower()
                    df_contact_norm = df_contact_norm.apply(lambda x: re.sub(r'[\s\-\(\)]', '', x) if x not in ['not found', '', 'nan', 'none'] else x)
                    valid_rows = (~df_name_norm.isin(['not found', '', 'nan', 'none'])) & (~df_contact_norm.isin(['not found', '', 'nan', 'none']))
                    if valid_rows.any():
                        name_match = df_name_norm[valid_rows] == candidate_name_norm
                        contact_match = df_contact_norm[valid_rows] == contact_number_norm
                        if (name_match & contact_match).any():
                            matching_rows = df[valid_rows][name_match & contact_match]
                            if 'Vendor_Name' in df.columns and not matching_rows.empty:
                                # Check ALL matching rows for same vendor (critical for batch processing)
                                for idx, row in matching_rows.iterrows():
                                    existing_vendor = str(row['Vendor_Name']).strip().lower() if pd.notna(row['Vendor_Name']) else ""
                                    if vendor_name_norm and existing_vendor and vendor_name_norm == existing_vendor:
                                        # Same vendor duplicate found - BLOCK
                                        current_status_inner = row.get('Resume_Screening_Status', 'Unknown')
                                        return excel_path, False, "name_and_phone_same_vendor", row.get('Profile_Remark', ''), current_status_inner
                                # No same vendor found - check for different vendor
                                existing_vendor = str(matching_rows.iloc[0]['Vendor_Name']).strip().lower() if pd.notna(matching_rows.iloc[0]['Vendor_Name']) else ""
                                if vendor_name_norm and existing_vendor and vendor_name_norm != existing_vendor:
                                    profile_remark = "Duplicate Profile"
            
            # Fallback: Check by name + vendor (when contact number is missing but name exists)
            # This is a fallback for cases where contact number is not available in CV
            # Only check for same vendor duplicates (to avoid false positives with common names)
            if profile_remark == "Unique Profile" and candidate_name_norm and not contact_number_norm and vendor_name_norm:
                if 'Candidate_Name' in df.columns and 'Vendor_Name' in df.columns:
                    df_name_norm = df['Candidate_Name'].astype(str).str.strip().str.lower()
                    valid_rows = ~df_name_norm.isin(['not found', '', 'nan', 'none'])
                    
                    if valid_rows.any():
                        name_match = df_name_norm[valid_rows] == candidate_name_norm
                        
                        if name_match.any():
                            matching_rows = df[valid_rows][name_match]
                            
                            # Check ALL matching rows for same vendor (only block same vendor + same name)
                            for idx, row in matching_rows.iterrows():
                                existing_vendor = str(row['Vendor_Name']).strip().lower() if pd.notna(row['Vendor_Name']) else ""
                                if vendor_name_norm and existing_vendor and vendor_name_norm == existing_vendor:
                                    # Same vendor + same name found (even without contact number) - BLOCK
                                    current_status_inner = row.get('Resume_Screening_Status', 'Unknown')
                                    return excel_path, False, "name_and_vendor_same_vendor", row.get('Profile_Remark', ''), current_status_inner
    
    # Add Vendor_Name, Profile_Shared_Date, and Profile_Remark as first columns
    candidate_details['Vendor_Name'] = vendor_name if vendor_name else ""
    
    # Format profile_shared_date (handle datetime.date object or string)
    if profile_shared_date:
        if isinstance(profile_shared_date, str):
            candidate_details['Profile_Shared_Date'] = profile_shared_date
        else:
            # Assume it's a datetime.date object
            candidate_details['Profile_Shared_Date'] = profile_shared_date.strftime('%Y-%m-%d')
    else:
        candidate_details['Profile_Shared_Date'] = ""
    
    candidate_details['Profile_Remark'] = profile_remark
    
    # Add additional columns to candidate_details
    candidate_details['Resume_Screening_Feedback'] = feedback
    candidate_details['Similarity_Score'] = similarity_score
    candidate_details['Average_Score'] = average_score
    
    # Add Shortlisted_CV_Path column only for shortlisted candidates
    if tracker_type.lower() == "shortlisted" and cv_path:
        candidate_details['Shortlisted_CV_Path'] = cv_path
    elif tracker_type.lower() == "shortlisted":
        candidate_details['Shortlisted_CV_Path'] = ''  # Empty if path not provided
    else:
        candidate_details['Shortlisted_CV_Path'] = ''  # Empty for rejected candidates
    
    # Update status based on tracker type, override if Duplicate Profile
    # For different vendor duplicates, always set status to "Duplicate Profile"
    if profile_remark == 'Duplicate Profile':
        candidate_details['Resume_Screening_Status'] = 'Duplicate Profile'
    else:
        candidate_details['Resume_Screening_Status'] = desired_status
    
    # Ensure Screening_Date exists (update timestamp)
    candidate_details['Screening_Date'] = datetime.now().strftime('%Y-%m-%d')
    
    # Ensure Position exists (if not already set)
    if 'Position' not in candidate_details:
        candidate_details['Position'] = 'Not Found'
    
    # Define manual columns that users will fill (always empty by default)
    manual_columns = [
        'R1_Schedule_Date',
        'R1_Panel_Name',
        'R1_Feedback',
        'R1_Status',
        'R2_Schedule_Date',
        'R2_Panel_Name',
        'R2_Feedback',
        'R2_Status',
        'CV_Conversion_Status',
        'CV_Converted_Path'
    ]
    
    # Initialize manual columns as empty strings in candidate_details
    for col in manual_columns:
        candidate_details[col] = ""
    
    # Add new candidate data
    new_row = pd.DataFrame([candidate_details])
    
    # Define the required first columns in order
    first_columns = ['Vendor_Name', 'Profile_Shared_Date', 'Profile_Remark']
    
    # Reorder columns: Vendor_Name, Profile_Shared_Date, Profile_Remark first, then Position after Email_ID, then rest
    if not df.empty:
        # Get existing columns
        existing_cols = list(df.columns)
        
        # Remove first_columns from existing_cols if they exist (we'll add them at the beginning)
        for col in first_columns:
            if col in existing_cols:
                existing_cols.remove(col)
        
        # Ensure new_row has all existing columns
        for col in existing_cols:
            if col not in new_row.columns:
                new_row[col] = candidate_details.get(col, '')
        
        # Reorder new_row columns to match existing order
        new_row = new_row[existing_cols]
        
        # Add any new columns from candidate_details that don't exist in df
        new_cols = [col for col in candidate_details.keys() if col not in existing_cols and col not in first_columns]
        if new_cols:
            for col in new_cols:
                df[col] = ''
                new_row[col] = candidate_details.get(col, '')
            existing_cols = existing_cols + new_cols
        
        # Ensure df has first_columns (add empty columns if missing)
        for col in first_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Reorder: first_columns first, then existing_cols
        final_cols = first_columns + [col for col in existing_cols if col not in first_columns]
        df = df[final_cols]
        new_row = new_row[[col for col in final_cols if col in new_row.columns]]
        
        # Ensure new_row has all columns in final_cols
        for col in final_cols:
            if col not in new_row.columns:
                new_row[col] = candidate_details.get(col, '')
        new_row = new_row[final_cols]
    else:
        # Empty dataframe - create columns in correct order
        # Start with first_columns
        all_cols = first_columns + [col for col in candidate_details.keys() if col not in first_columns]
        new_row = new_row[[col for col in all_cols if col in new_row.columns]]
        # Ensure all columns exist
        for col in all_cols:
            if col not in new_row.columns:
                new_row[col] = candidate_details.get(col, '')
            new_row = new_row[all_cols]
    
    df = pd.concat([df, new_row], ignore_index=True)
    
    # Final column ordering: ensure Vendor_Name, Profile_Shared_Date, Profile_Remark are first
    cols = list(df.columns)
    for i, col in enumerate(first_columns):
        if col in cols:
            cols.remove(col)
            cols.insert(i, col)
    
    # Ensure Position is after Email_ID (if both exist)
    if 'Email_ID' in cols and 'Position' in cols:
        email_idx = cols.index('Email_ID')
        pos_idx = cols.index('Position')
        if pos_idx != email_idx + 1:
            cols.remove('Position')
            cols.insert(email_idx + 1, 'Position')
    
    # Define manual columns that users will fill (always empty by default)
    manual_columns = [
        'R1_Schedule_Date',
        'R1_Panel_Name',
        'R1_Feedback',
        'R1_Status',
        'R2_Schedule_Date',
        'R2_Panel_Name',
        'R2_Feedback',
        'R2_Status',
        'CV_Conversion_Status',
        'CV_Converted_Path'
    ]
    
    # Ensure manual columns are at the end (in specified order)
    for col in manual_columns:
        if col in cols:
            cols.remove(col)
    # Append manual columns at the end
    cols.extend(manual_columns)
    
    # Apply column ordering to DataFrame
    df = df[cols]
    
    # Save to Excel
    df.to_excel(excel_path, index=False)
    
    return excel_path, True, "", profile_remark, None  # Return True to indicate successful addition


def update_cv_conversion_status(tracker_path, candidate_email=None, candidate_name=None, contact_number=None, converted_ppt_path=""):
    """Update CV_Conversion_Status and CV_Converted_Path for a candidate in tracker
    
    Args:
        tracker_path: Full path to the tracker Excel file
        candidate_email: Email ID of candidate (primary identifier)
        candidate_name: Name of candidate (fallback identifier)
        contact_number: Contact number (fallback identifier)
        converted_ppt_path: Full path to the converted PPT file
    
    Returns:
        tuple: (success, message)
            - success: True if updated successfully, False otherwise
            - message: Success or error message
    """
    try:
        if not os.path.exists(tracker_path):
            return False, f"Tracker file not found: {tracker_path}"
        
        df = pd.read_excel(tracker_path)
        if df.empty:
            return False, "Tracker is empty"
        
        # Normalize identifiers
        email_norm = str(candidate_email).strip().lower() if candidate_email and str(candidate_email).strip().lower() not in ['not found', '', 'nan', 'none'] else None
        name_norm = str(candidate_name).strip().lower() if candidate_name and str(candidate_name).strip().lower() not in ['not found', '', 'nan', 'none'] else None
        contact_norm = str(contact_number).strip().lower() if contact_number and str(contact_number).strip().lower() not in ['not found', '', 'nan', 'none'] else None
        
        if contact_norm:
            contact_norm = re.sub(r'[\s\-\(\)]', '', contact_norm)
        
        # Find matching row
        matching_idx = None
        
        # Try email first
        if email_norm and 'Email_ID' in df.columns:
            matching_rows = df[df['Email_ID'].astype(str).str.strip().str.lower() == email_norm]
            if not matching_rows.empty:
                matching_idx = matching_rows.index[0]
        
        # Try name + phone
        if matching_idx is None and name_norm and contact_norm:
            if 'Candidate_Name' in df.columns and 'Contact_Number' in df.columns:
                df_name_norm = df['Candidate_Name'].astype(str).str.strip().str.lower()
                df_contact_norm = df['Contact_Number'].astype(str).str.strip().str.lower()
                df_contact_norm = df_contact_norm.apply(lambda x: re.sub(r'[\s\-\(\)]', '', x) if x not in ['not found', '', 'nan', 'none'] else x)
                valid_rows = (~df_name_norm.isin(['not found', '', 'nan', 'none'])) & (~df_contact_norm.isin(['not found', '', 'nan', 'none']))
                if valid_rows.any():
                    name_match = df_name_norm[valid_rows] == name_norm
                    contact_match = df_contact_norm[valid_rows] == contact_norm
                    if (name_match & contact_match).any():
                        matching_idx = df[valid_rows][name_match & contact_match].index[0]
        
        if matching_idx is None:
            return False, "Candidate not found in tracker"
        
        # Ensure CV_Conversion_Status and CV_Converted_Path columns exist
        if 'CV_Conversion_Status' not in df.columns:
            df['CV_Conversion_Status'] = ''
        if 'CV_Converted_Path' not in df.columns:
            df['CV_Converted_Path'] = ''
        
        # Update CV_Conversion_Status and CV_Converted_Path
        df.loc[matching_idx, 'CV_Conversion_Status'] = 'Converted'
        if converted_ppt_path:
            df.loc[matching_idx, 'CV_Converted_Path'] = converted_ppt_path
        
        # Save updated tracker
        df.to_excel(tracker_path, index=False)
        
        candidate_display = candidate_name or candidate_email or "Candidate"
        return True, f"Successfully updated {candidate_display}"
        
    except Exception as e:
        return False, f"Error updating tracker: {str(e)}"

