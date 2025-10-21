# email_handler.py
import os
import pickle
import base64
from email import message_from_bytes
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

CLIENT_SECRET_FILE = os.getenv("GMAIL_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE = "token.pkl"

def authenticate_gmail():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service


def save_credentials_from_code(auth_code, redirect_uri=None, client_secret_file=None):
    """
    Exchange a single-use OAuth `auth_code` (the `code=` parameter received
    at the redirect URI) for credentials and save them to TOKEN_FILE.

    Usage:
    1. Run the OAuth initiation (or open the consent URL) that redirects to
       the provided redirect_uri. The OAuth response will contain `?code=...`.
    2. Copy the `code` value and call this helper in a Python REPL or small
       script to persist credentials without running the interactive local
       server flow.

    Example:
        from email_handler import save_credentials_from_code
        save_credentials_from_code('4/0AY0e-g4...')

    If `client_secret_file` is provided it will be used, otherwise
    CLIENT_SECRET_FILE is used.
    """
    cli_file = client_secret_file or CLIENT_SECRET_FILE
    # Build a flow with the same client secrets and scopes
    flow = InstalledAppFlow.from_client_secrets_file(cli_file, SCOPES, redirect_uri=redirect_uri)

    # Exchange the code for credentials
    creds = flow.fetch_token(code=auth_code)

    # fetch_token returns a dict-like object; to get a Credentials object we
    # can use the flow.credentials attribute after fetch
    credentials = flow.credentials

    # Save to TOKEN_FILE
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(credentials, token)

    return credentials

def get_latest_email():
    try:
        service = authenticate_gmail()
        results = service.users().messages().list(userId='me', q="is:unread", maxResults=1).execute()
        messages = results.get('messages', [])
        if not messages:
            return "No new emails found."

        msg = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
        payload = msg['payload']
        parts = payload.get('parts', [])
        data = ""
        if parts:
            for part in parts:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        else:
            data = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        return data.strip()
    except Exception as e:
        print(f"[Email Error] {e}")
        return "Error reading email."
