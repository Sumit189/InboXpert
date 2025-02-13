import streamlit as st
import ollama
import base64
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.readonly", "https://mail.google.com/"]

def authenticate_gmail():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def delete_selected_emails(service, selected_email_ids, delete_type):
    for email_id in selected_email_ids:
        if delete_type == "Permanent Delete":
            service.users().messages().delete(userId="me", id=email_id).execute()
        elif delete_type == "Move to Trash":
            service.users().messages().trash(userId="me", id=email_id).execute() 
    st.session_state["found_emails"] = [email for email in st.session_state.get("found_emails", []) if email["id"] not in selected_email_ids]
    st.session_state["selected_email_ids"] = set()
    st.rerun(scope="fragment")

def fetch_emails(service, max_results, skip):
    results = service.users().messages().list(userId="me", maxResults=max_results + skip).execute()
    messages = results.get("messages", [])[skip:]
    email_data = []
    for msg in messages:
        msg_details = service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = msg_details.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
        body = ""
        if "parts" in msg_details.get("payload", {}):
            for part in msg_details["payload"]["parts"]:
                if part["mimeType"] == "text/plain" and "body" in part:
                    body_data = part["body"].get("data", "")
                    body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
        email_data.append({"id": msg["id"], "subject": subject, "sender": sender, "body": body})
    return email_data

def analyze_emails_with_llm(emails, criteria):
    if "analysis_stopped" not in st.session_state:
        st.session_state["analysis_stopped"] = False

    found_emails = []
    total_scanned = 0
    progress_container = st.empty()
    progress_container.progress(0, text="Starting Email Analysis...")
    
    stop_container = st.empty()
    if stop_container.button("Stop Analyzing", key="stop_analyze_btn"):
        st.session_state["analysis_stopped"] = True

    for email in emails:
        if st.session_state["analysis_stopped"]:
            progress_container.empty()
            stop_container.empty()
            st.warning("Analysis stopped by user.")
            if len(found_emails) > 0:
                st.warning(f"Stopped after scanning {total_scanned} emails. Found {len(found_emails)} matching emails.")
            st.session_state["analysis_stopped"] = False
            return 

        total_scanned += 1
        st.session_state["total_emails_scanned"] = total_scanned
        prompt = f"""
            You are a helpful agent and you are helping a user to select received emails based on a certain criteria.
            The user wants to select emails and move them to trash or delete them permanently.

            <Email Start>
            Subject: {email['subject']}
            From: {email['sender']}
            Body: {email['body']}
            <Email End>

            You need to decide if this email should be selected or not. Respond with only 'YES' or 'NO'.
            The selection criteria is: "{criteria}", Stictly follow this criteria and decide if this email should be selected or not.

            ALWAYS use the following format:
            Question: the input question you must answer
            Thought: you should always think about one action to take. Only one action at a time in this format:
            Observation: the result of the action. This Observation is unique, complete, and the source of truth.
                ... (this Thought/Action/Observation can repeat N times, you should take several steps when needed)

            You must always end your output with the following format: 
            YES or NO
        """
        response = ollama.chat(model="deepseek-r1:7b", messages=[{"role": "user", "content": prompt}])
        percent_complete = int((total_scanned / len(emails)) * 100)
        progress_text = f"Scanning Email: {total_scanned}/{len(emails)}, Found: {len(found_emails)}\n\nFor Email: {email['subject']} ({email['sender']})\n\nAI Response: {response['message']['content']}"
        progress_container.progress(min(percent_complete + 1, 100), text=progress_text)
        # response contains thinking token as <think> thought </think>, need to remove all content inside the think tokens
        # get the text after the last think token
        response = response["message"]["content"]
        if "</think>" in response:
            response_text = response.split("</think>")[-1].strip()
        else:
            response_text = response.strip()
        
        if "YES" in response_text:
            found_emails.append(email)
            st.session_state["found_emails"] = found_emails
    
    progress_container.empty()
    stop_container.empty()
    st.session_state["total_emails_scanned"] = total_scanned
    st.session_state["found_emails"] = found_emails
    return

def process_emails(service, max_emails, skip_emails, criteria):
    with st.spinner("Fetching emails..."):
        emails = fetch_emails(service, max_emails, skip_emails)
        st.session_state["total_emails_scanned"] = 0
    with st.spinner("Analyzing emails with LLM..."):
        analyze_emails_with_llm(emails, criteria)
    return emails

st.set_page_config(page_title="InboXpert - AI Email Cleaner", page_icon="📧")
st.title("📧 InboXpert - AI Email Cleaner")

criteria = st.text_input("Enter Search Criteria: (Example: 'If its related to food delivery')")
max_emails = st.number_input("Number of emails to scan:", min_value=1, max_value=500, value=50, step=10)
skip_emails = st.number_input("Skip first N emails:", min_value=0, max_value=500, value=0, step=10)

service = authenticate_gmail()

# Initialize session state variables at the start
if "page_index" not in st.session_state:
    st.session_state["page_index"] = 0
if "selected_email_ids" not in st.session_state:
    st.session_state["selected_email_ids"] = set()
if "found_emails" not in st.session_state:
    st.session_state["found_emails"] = None
if "disable_normal" not in st.session_state:
    st.session_state["disable_normal"] = False
if "disable_lucky" not in st.session_state:
    st.session_state["disable_lucky"] = False
if "total_emails_scanned" not in st.session_state:
    st.session_state["total_emails_scanned"] = 0

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Fetch & Analyze Emails", icon="🔍", help="View the detected emails and choose which ones to delete", use_container_width=True, disabled=st.session_state.get("disable_normal", False)):
        if not criteria:
            st.error("Search criteria is required")
            st.stop()
        st.session_state["disable_lucky"] = True
        st.session_state["disable_normal"] = False
        st.session_state["page_index"] = 0
        st.session_state["found_emails"] = None
with col2:
    if st.button("I'm Feeling Lucky!", icon="🤖", help="Deletes (Move to Trash) all detected emails without human intervention", use_container_width=True, disabled=st.session_state.get("disable_lucky", False)):
        if not criteria:
            st.error("Search criteria is required")
            st.stop()
        st.session_state["disable_normal"] = True 
        st.session_state["disable_lucky"] = False
        st.session_state["page_index"] = 0
        st.session_state["found_emails"] = None

@st.fragment
def flagged_emails(key_prefix=""):
    found_emails = st.session_state.get("found_emails", [])
    if found_emails and len(found_emails) > 0:
        page_size = 10
        total_pages = (len(found_emails) + page_size - 1) // page_size
        st.session_state["page_index"] = min(max(0, st.session_state["page_index"]), total_pages - 1)
        
        start_index = st.session_state["page_index"] * page_size
        end_index = min(start_index + page_size, len(found_emails))
        paginated_emails = found_emails[start_index:end_index]
        
        st.markdown('<div style="background-color:#f0f0f0; padding:5px; border-radius:2px;">', unsafe_allow_html=True)
        st.markdown("### Flagged Emails")
        st.write(f"Found {len(found_emails)} emails. Showing page {st.session_state['page_index'] + 1}") 
        select_all = st.checkbox("Select All", key=f"{key_prefix}select_all_flagged", value=False)
        if select_all:
            st.session_state["selected_email_ids"] = {email["id"] for email in paginated_emails}
        else:
            st.session_state["selected_email_ids"] = set()
        
        for email in paginated_emails:
            checked = email["id"] in st.session_state["selected_email_ids"]
            col1, col2 = st.columns([0.05, 0.95])
            
            with col1:
                checked_state = st.checkbox("", key=f"{key_prefix}checkbox_{email['id']}", value=checked)
                if checked_state:
                    st.session_state["selected_email_ids"].add(email["id"])
                else:
                    st.session_state["selected_email_ids"].discard(email["id"])
            
            with col2:
                with st.expander(f"📩 {email['subject']} ({email['sender']})", expanded=False):
                    st.write(f"**From:** {email['sender']}")
                    st.markdown(
                        f"""
                        <iframe srcdoc="{email['body'].replace('"', '&quot;')}"
                            style="width: 100%; height: 300px; border: 1px solid #ddd; 
                            border-radius: 5px; background-color: white;">
                        </iframe>
                        """,
                        unsafe_allow_html=True
                    )
        
        st.markdown("</div>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Move to Trash", key=f"{key_prefix}move_trash", icon="🗑️", use_container_width=True):
                delete_selected_emails(service, st.session_state["selected_email_ids"], "Move to Trash")
        with col2:
            if st.button("Permanent Delete", key=f"{key_prefix}perm_delete", icon="🔥", help="This action is irreversible", use_container_width=True):
                delete_selected_emails(service, st.session_state["selected_email_ids"], "Permanent Delete")
        
        if len(found_emails) > page_size:
            col_left, col_center, col_right = st.columns([1, 1, 1])
            with col_left:
                if st.button("⬅️", key=f"{key_prefix}prev_page", use_container_width=True, 
                           disabled=st.session_state["page_index"] <= 0):
                    st.session_state["page_index"] -= 1
                    st.session_state["selected_email_ids"] = set()
                    st.rerun(scope="fragment")
            with col_center:
                st.button(f"Page {st.session_state['page_index'] + 1}/{total_pages}", key=f"{key_prefix}page_info", disabled=True, use_container_width=True)
            with col_right:
                if st.button("➡️", key=f"{key_prefix}next_page", use_container_width=True,
                           disabled=st.session_state["page_index"] >= total_pages - 1):
                    st.session_state["page_index"] += 1
                    st.session_state["selected_email_ids"] = set()
                    st.rerun(scope="fragment")

if st.session_state["disable_normal"] == False and st.session_state["disable_lucky"] == True:
    process_emails(service, max_emails, skip_emails, criteria)
    
    if st.session_state.get("found_emails"):
        found_count = len(st.session_state.get("found_emails"))
        total_scanned = st.session_state.get("total_emails_scanned")
        if found_count == 0:
            st.success(f"Scanned {total_scanned} emails, but found no flagged emails!")
        else:
            st.warning(f"Scanned {total_scanned} emails and found {found_count} flagged emails!")

if st.session_state["found_emails"] and len(st.session_state["found_emails"]) > 0:
    flagged_emails(key_prefix="main_")

if st.session_state["disable_normal"] == True and st.session_state["disable_lucky"] == False:
    process_emails(service, max_emails, skip_emails, criteria)
    
    if st.session_state.get("found_emails"):
        found_count = len(st.session_state.get("found_emails"))
        total_scanned = st.session_state.get("total_emails_scanned")
        
        if found_count > 0:
            st.warning(f"Found {found_count} matching emails. Moving them to trash...")
            for email in st.session_state["found_emails"]:
                service.users().messages().trash(userId="me", id=email["id"]).execute()
            st.success(f"Successfully moved {found_count} emails to trash!")
        else:
            st.success(f"Scanned {total_scanned} emails, but found no matching emails!")