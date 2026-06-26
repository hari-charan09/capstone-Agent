"""
gmail_mcp_server.py
--------------------
MCP server (stdio transport) exposing three Gmail tools:
  • list_messages(max_results)
  • get_message(message_id)
  • get_headers(message_id)

Run as an MCP server:
    python mcp-server/gmail_mcp_server.py

Run the self-test (not as MCP):
    python mcp-server/gmail_mcp_server.py --self-test
or simply run the __main__ block directly in an IDE.
"""

from __future__ import annotations

import base64
import re
import sys
from email import message_from_bytes
from html.parser import HTMLParser
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from gmail_auth import get_gmail_service

# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------

app = Server("gmail-mcp-server")


# ---------------------------------------------------------------------------
# Tool: list_messages
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_messages",
            description="Return a list of recent Gmail messages with id and snippet.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to return (default 10).",
                        "default": 10,
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_message",
            description=(
                "Return a full email object for the given message ID. "
                "Includes sender, subject, body text, extracted links, "
                "and SPF/DKIM/DMARC authentication results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message ID.",
                    }
                },
                "required": ["message_id"],
            },
        ),
        types.Tool(
            name="get_headers",
            description="Return the raw header dictionary for a Gmail message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message ID.",
                    }
                },
                "required": ["message_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    service = get_gmail_service()

    if name == "list_messages":
        max_results = int(arguments.get("max_results", 10))
        result = _list_messages(service, max_results)
    elif name == "get_message":
        message_id = arguments["message_id"]
        result = _get_message(service, message_id)
    elif name == "get_headers":
        message_id = arguments["message_id"]
        result = _get_headers(service, message_id)
    else:
        raise ValueError(f"Unknown tool: {name}")

    import json
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ---------------------------------------------------------------------------
# Gmail helper functions (sync — fine for stdio MCP)
# ---------------------------------------------------------------------------

def _list_messages(service, max_results: int = 10) -> list[dict]:
    """Return [{id, snippet}, …] for the most recent messages."""
    response = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results)
        .execute()
    )
    messages = response.get("messages", [])
    result = []
    for msg in messages:
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata",
                 metadataHeaders=["Subject"])
            .execute()
        )
        result.append(
            {
                "id": msg["id"],
                "snippet": detail.get("snippet", ""),
            }
        )
    return result


def _get_message(service, message_id: str) -> dict:
    """
    Return a full email object:
    {
        "id": str,
        "sender": str,
        "subject": str,
        "body_text": str,
        "links": [str],
        "headers": {"spf": str, "dkim": str, "dmarc": str}
    }
    """
    raw_msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="raw")
        .execute()
    )

    raw_bytes = base64.urlsafe_b64decode(raw_msg["raw"] + "==")
    email_msg = message_from_bytes(raw_bytes)

    # --- Basic headers ---
    sender = email_msg.get("From", "")
    subject = email_msg.get("Subject", "")

    # --- Body text ---
    body_text = _extract_body_text(email_msg)

    # --- Links ---
    links = _extract_links(body_text)

    # --- Auth headers (SPF / DKIM / DMARC) ---
    auth_results_header = email_msg.get("Authentication-Results", "")
    spf = _extract_auth_result(auth_results_header, "spf")
    dkim = _extract_auth_result(auth_results_header, "dkim")
    dmarc = _extract_auth_result(auth_results_header, "dmarc")

    # Truncate body to 1500 chars — enough for phishing analysis, avoids bloat
    body_text = body_text[:1500]

    return {
        "id": message_id,
        "sender": sender,
        "subject": subject,
        "body_text": body_text,
        "links": links,
        "headers": {
            "spf": spf,
            "dkim": dkim,
            "dmarc": dmarc,
        },
    }


def _get_headers(service, message_id: str) -> dict:
    """Return a flat {name: value} dict of all raw headers."""
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    return {h["name"]: h["value"] for h in headers}


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML parser that collects visible text, skipping scripts/styles."""

    SKIP_TAGS = {"script", "style", "head", "meta", "link", "noscript"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        # Join fragments with single spaces; collapse runs of whitespace
        raw = " ".join(self._parts)
        return re.sub(r"[ \t]{2,}", " ", raw).strip()


def _strip_html(html: str) -> str:
    """Strip HTML tags and return clean visible text."""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        # Last-resort fallback: crude regex tag stripper
        return re.sub(r"<[^>]+>", " ", html).strip()


def _extract_body_text(email_msg) -> str:
    """
    Walk the MIME tree and return readable plain text.
    Priority: text/plain > HTML-stripped text/html > empty string.
    """
    plain_text: str | None = None
    html_text: str | None = None

    parts = list(email_msg.walk()) if email_msg.is_multipart() else [email_msg]
    for part in parts:
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        decoded = payload.decode(charset, errors="replace")

        if ctype == "text/plain" and plain_text is None:
            plain_text = decoded
        elif ctype == "text/html" and html_text is None:
            html_text = decoded

    if plain_text is not None:
        return plain_text
    if html_text is not None:
        return _strip_html(html_text)
    return ""


_URL_RE = re.compile(
    r"https?://[^\s\)\]\>\"\'<]+",
    re.IGNORECASE,
)


def _extract_links(text: str) -> list[str]:
    """Extract all http/https URLs from text."""
    return list(dict.fromkeys(_URL_RE.findall(text)))  # deduplicated, order-preserved


_AUTH_RESULT_RE = re.compile(
    r"(?:^|;)\s*(?P<proto>spf|dkim|dmarc)\s*=\s*(?P<result>\w+)",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_auth_result(auth_header: str, proto: str) -> str:
    """
    Parse an Authentication-Results header and return pass/fail/none/softfail/…
    for the requested protocol.  Returns 'none' if not found.
    """
    for m in _AUTH_RESULT_RE.finditer(auth_header):
        if m.group("proto").lower() == proto.lower():
            return m.group("result").lower()
    return "none"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _run_mcp_server():
    """Start the stdio MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def _self_test():
    """
    Quick self-test: authenticate, call list_messages(5), then get_message on
    each of those 5 IDs, and print results to the console.
    """
    import json

    print("=" * 60)
    print("Gmail MCP Server - Self-Test")
    print("=" * 60)

    print("\n[1] Authenticating ...")
    service = get_gmail_service()
    print("    [OK] Authenticated successfully.\n")

    print("[2] Calling list_messages(5) ...")
    messages = _list_messages(service, 5)
    print(f"    [OK] Got {len(messages)} message(s).\n")
    for m in messages:
        print(f"    ID: {m['id']}")
        print(f"    Snippet: {m['snippet'][:80]}...\n")

    print("[3] Calling get_message() on each ID ...\n")
    for i, m in enumerate(messages, start=1):
        print(f"  --- Message {i} ---")
        email_obj = _get_message(service, m["id"])
        # Truncate body_text for terminal readability; the full 1500-char value
        # is what get_message() actually returns to callers.
        display_obj = {
            **email_obj,
            "body_text": email_obj["body_text"][:200]
                         + ("..." if len(email_obj["body_text"]) > 200 else ""),
        }
        print(json.dumps(display_obj, indent=2, ensure_ascii=False))
        print()

    print("=" * 60)
    print("Self-test complete.")
    print("=" * 60)


if __name__ == "__main__":
    if "--self-test" in sys.argv or True:   # always self-test when run directly
        _self_test()
    else:
        import asyncio
        asyncio.run(_run_mcp_server())
