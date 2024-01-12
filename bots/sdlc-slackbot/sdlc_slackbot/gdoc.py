from __future__ import print_function

import os.path
import re
from logging import getLogger

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]

logger = getLogger(__name__)


def read_paragraph_element(element):
    """Returns the text in the given ParagraphElement.

    Args:
        element: a ParagraphElement from a Google Doc.
    """
    text_run = element.get("textRun")
    if not text_run:
        return ""
    return text_run.get("content")


def read_structural_elements(elements):
    """Recurses through a list of Structural Elements to read a document's text where text may be
    in nested elements.

    Args:
        elements: a list of Structural Elements.
    """
    text = ""
    for value in elements:
        if "paragraph" in value:
            elements = value.get("paragraph").get("elements")
            for elem in elements:
                text += read_paragraph_element(elem)
        elif "table" in value:
            # The text in table cells are in nested Structural Elements and tables may be
            # nested.
            table = value.get("table")
            for row in table.get("tableRows"):
                cells = row.get("tableCells")
                for cell in cells:
                    text += read_structural_elements(cell.get("content"))
        elif "tableOfContents" in value:
            # The text in the TOC is also in a Structural Element.
            toc = value.get("tableOfContents")
            text += read_structural_elements(toc.get("content"))
    return text


def gdoc_creds():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    creds_path = "./bots/sdlc-slackbot/sdlc_slackbot/"

    if os.path.exists(creds_path + "token.json"):
        creds = Credentials.from_authorized_user_file(creds_path + "token.json", SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_path + "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(creds_path + "token.json", "w") as token:
            token.write(creds.to_json())

    return creds


def gdoc_get(gdoc_url):
    # https://docs.google.com/document/d/<ID>/edit

    result = None
    logger.info(gdoc_url)
    if not gdoc_url.startswith("https://docs.google.com/document") and not gdoc_url.startswith(
        "docs.google.com/document"
    ):
        logger.error("Invalid google doc url")
        return result

    # This regex captures the ID after "/d/" and before an optional "/edit", "/" or the end of the string.
    pattern = r"/d/([^/]+)"
    match = re.search(pattern, gdoc_url)

    if match:
        document_id = match.group(1)
        logger.info(document_id)
    else:
        logger.error("No ID found in the URL")
        return result

    creds = gdoc_creds()
    try:
        service = build("docs", "v1", credentials=creds)

        # Retrieve the documents contents from the Docs service.
        document = service.documents().get(documentId=document_id).execute()

        logger.info("The title of the document is: {}".format(document.get("title")))

        doc_content = document.get("body").get("content")
        result = read_structural_elements(doc_content)

    except HttpError as err:
        logger.error(err)

    return result
