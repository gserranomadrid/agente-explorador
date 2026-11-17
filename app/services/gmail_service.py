import os
from base64 import urlsafe_b64decode
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GmailService:

  def __init__(self):
    project_dir = Path(__file__).resolve().parents[2]
    self.token_path = str(project_dir / "token.json")
    self.creds_path = str(project_dir / "credentials.json")
    self.creds = None
    self.SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

  def authenticate(self):
    if os.path.exists(self.token_path):
      self.creds = Credentials.from_authorized_user_file(
          self.token_path, self.SCOPES
      )
    if not self.creds or not self.creds.valid:
      if self.creds and self.creds.expired and self.creds.refresh_token:
        self.creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(
            self.creds_path, self.SCOPES
        )
        self.creds = flow.run_local_server(port=0)
      with open(self.token_path, "w") as token:
        token.write(self.creds.to_json())
    return self.creds

  def get_user_profile(self):
    if self.creds is None:
      if not os.path.exists(self.token_path):
        raise RuntimeError("No existe token de Google. Inicia la autenticación.")
      self.creds = Credentials.from_authorized_user_file(
          self.token_path, self.SCOPES
      )

    if not self.creds.valid:
      if not self.creds.expired or not self.creds.refresh_token:
        raise RuntimeError("El token de Google no es válido. Vuelve a autenticarte.")
      self.creds.refresh(Request())
      with open(self.token_path, "w", encoding="utf-8") as token:
        token.write(self.creds.to_json())

    service = build("gmail", "v1", credentials=self.creds)
    return service.users().getProfile(userId="me").execute()

  def fetch_inbox_emails(self, max_results=56):
    creds = self.authenticate()
    service = build("gmail", "v1", credentials=creds)

    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results)
        .execute()
    )
    messages = results.get("messages", [])

    emails_data = []
    for msg in messages:
      txt = (
          service.users()
          .messages()
          .get(userId="me", id=msg["id"], format="full")
          .execute()
      )
      payload = txt.get("payload", {})
      headers = payload.get("headers", [])
      subject = next(
          (h["value"] for h in headers if h["name"].lower() == "subject"),
          "Sin Asunto",
      )
      sender = next(
          (h["value"] for h in headers if h["name"].lower() == "from"),
          "Desconocido",
      )

      def plain_text(part):
        body = part.get("body", {}).get("data")
        if part.get("mimeType") == "text/plain" and body:
          return self._decode_base64(body).decode("utf-8", errors="replace")
        return "".join(plain_text(child) for child in part.get("parts", []))

      def attachments(part):
        filename = part.get("filename")
        body = part.get("body", {})
        if filename:
          data = body.get("data")
          if not data and body.get("attachmentId"):
            attachment = (
                service.users()
                .messages()
                .attachments()
                .get(
                    userId="me",
                    messageId=txt["id"],
                    id=body["attachmentId"],
                )
                .execute()
            )
            data = attachment.get("data")
          if data:
            yield {
                "filename": filename,
                "mime_type": part.get("mimeType") or "application/octet-stream",
                "content": self._decode_base64(data),
            }
        for child in part.get("parts", []):
          yield from attachments(child)

      internal_date = txt.get("internalDate")
      received_at = (
          datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
          if internal_date
          else datetime.now(timezone.utc)
      )
      emails_data.append({
          "message_id": txt["id"],
          "thread_id": txt["threadId"],
          "subject": subject,
          "sender": sender,
          "received_at": received_at,
          "body_text": plain_text(payload),
          "attachments": list(attachments(payload)),
      })

    return emails_data

  @staticmethod
  def _decode_base64(data):
    return urlsafe_b64decode(data + "=" * (-len(data) % 4))