"""The operator's mailbox: one address, one credential, endpoints derived from it.

`sending-email.md` tells an agent to *"read the project's own email documentation to
find which transport it uses"* — and until now no project had anywhere to write that
down. `SMTP_ACCOUNT` and `SMTP_DOMAIN` were retired on 2026-08-10 on the reading that
"the canonical contract names no transport, so nothing asks for this any more"; what
that removed was the MECHANISM, leaving the contract pointing at documentation the kit
gave nobody a way to produce. SIX targets in the park still carry an orphaned
`SMTP_ACCOUNT` from before the retirement, answered and then unowned — `CodexBridge`,
`CodexBridgeMobile`, `ledgerlab`, two under `ZeeCred/jk-structure`, and
`Characters/Contraponto`, which carries it with no `OPERATOR_NAME` beside it. The first
version of this docstring said "two", counted by hand from a `find` that stopped at
depth 3; a council counted the park properly. The number is the delivery's own
justification for reversing a documented decision, so getting it wrong by a factor of
three is not a rounding error.

Three decisions shape this module.

**One slot, not two.** `SMTP_ACCOUNT` plus `SMTP_DOMAIN` asked the operator for the same
fact twice: the domain is the part of the address after `@`. `OPERATOR_EMAIL` is the
single answer, and everything else is derived from it or overridden explicitly.

**Endpoints are derived, and the derivation is a table.** The same shape the LLM catalog
already uses: a small map of the providers this kit knows, a documented convention for
the rest, and an explicit override for anything else. A wrong guess is visible and
correctable; a missing mechanism is not.

**The secret is never stored, only pointed at.** `identity.json` separates `values`
(literals) from `refs` (PATHS to credential files) precisely for this, and that split
already exists — it is not invented here.
"""

from __future__ import annotations

import imaplib
import json
import smtplib
import ssl
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path

from .path_safety import safe_path

_IDENTITY_FILE = ".credentials/identity.json"
_TOKEN_REF = "SMTP_TOKEN"
_ADDRESS_VALUE = "OPERATOR_EMAIL"
# Answered under the retired name before 2026-08-10 and orphaned since. Read, never
# written: a target that has it keeps working without the operator answering again.
_LEGACY_ADDRESS_VALUES = ("SMTP_ACCOUNT",)

_DEFAULT_TOKEN_PATH = ".credentials/smtp.token"

# A hostname label: letters, digits and hyphens. Used for the address's domain and,
# with the same rule, for an override host — an override carrying a newline split the
# confirmation line an operator reads before a send that cannot be recalled.
_LABEL_OK = __import__("re").compile(r"[A-Za-z0-9\u00a1-\uffff](?:[A-Za-z0-9\u00a1-\uffff-]*[A-Za-z0-9\u00a1-\uffff])?")


@dataclass(frozen=True)
class Endpoints:
    """Where to send and where to read, plus where the operator gets a token."""

    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    app_password_url: str
    label: str
    derived: bool = False


# Providers this kit knows. Ports are the submission/implicit-TLS pair every one of them
# documents; `app_password_url` is where the operator generates an application password,
# because for all of these the account password either will not work or should not be
# used. Deliberately small and deliberately a table — a new provider is a line here, not
# a branch somewhere.
_PROVIDERS: dict[str, Endpoints] = {
    "gmail.com": Endpoints(
        "smtp.gmail.com", 587, "imap.gmail.com", 993,
        "https://myaccount.google.com/apppasswords", "Google",
    ),
    "googlemail.com": Endpoints(
        "smtp.gmail.com", 587, "imap.gmail.com", 993,
        "https://myaccount.google.com/apppasswords", "Google",
    ),
    "outlook.com": Endpoints(
        "smtp-mail.outlook.com", 587, "outlook.office365.com", 993,
        "https://account.live.com/proofs/AppPassword", "Microsoft",
    ),
    "hotmail.com": Endpoints(
        "smtp-mail.outlook.com", 587, "outlook.office365.com", 993,
        "https://account.live.com/proofs/AppPassword", "Microsoft",
    ),
    "live.com": Endpoints(
        "smtp-mail.outlook.com", 587, "outlook.office365.com", 993,
        "https://account.live.com/proofs/AppPassword", "Microsoft",
    ),
    "zoho.com": Endpoints(
        "smtp.zoho.com", 587, "imap.zoho.com", 993,
        "https://accounts.zoho.com/home#security/apppassword", "Zoho",
    ),
    "yahoo.com": Endpoints(
        "smtp.mail.yahoo.com", 587, "imap.mail.yahoo.com", 993,
        "https://login.yahoo.com/account/security", "Yahoo",
    ),
    "fastmail.com": Endpoints(
        "smtp.fastmail.com", 587, "imap.fastmail.com", 993,
        "https://app.fastmail.com/settings/security/apppasswords", "Fastmail",
    ),
}


def endpoints_for(address: str) -> Endpoints:
    """Resolve the transport for *address*, by table or by convention.

    A domain the table does not know falls back to `mail.<domain>` / `imap.<domain>`,
    which is what cPanel, Plesk and most self-hosted setups publish. The result is
    marked `derived` so every caller can say "guessed" instead of "known" — a guess
    announced as a guess is correctable; a guess announced as a fact is a bug report
    three weeks later.
    """
    candidate = address.strip()
    # Two rounds of this guard were too loose. `rpartition` let a bare word derive
    # endpoints for itself; `partition` then let `a@@b.com`, `a@b@c.com`,
    # `a@exam ple.com` and `<a@b.com>` through, producing hosts like `mail.b@c.com`
    # that fail much later, at connect time, naming something the operator never typed.
    # `setup` exists precisely to validate BEFORE the operator goes hunting for an app
    # password, so it is the wrong place to be permissive.
    local, _, domain = candidate.partition("@")
    domain = domain.lower()
    labels = domain.split(".")
    if (
        candidate.count("@") != 1
        or not local
        or len(labels) < 2
        or any(not label or not _LABEL_OK.fullmatch(label) for label in labels)
        or any(character.isspace() for character in candidate)
        or "<" in candidate or ">" in candidate or "," in candidate
    ):
        raise ValueError(f"not an email address: {address!r}")
    known = _PROVIDERS.get(domain)
    if known is not None:
        return known
    return Endpoints(
        f"mail.{domain}", 587, f"imap.{domain}", 993,
        f"https://{domain}", f"{domain} (convention)", derived=True,
    )


@dataclass
class Mailbox:
    address: str
    token_path: str
    endpoints: Endpoints
    overrides: dict[str, str] = field(default_factory=dict)

    def resolved(self) -> Endpoints:
        """Endpoints with any explicit override applied, after checking each one.

        The overrides come from a file, and a host carrying a newline SPLIT the
        confirmation line an operator reads before a send that cannot be recalled —
        the half naming the real destination scrolled away. An empty host, a negative
        port and port 999999 were all accepted without a word.
        """
        if not self.overrides:
            return self.endpoints
        base = self.endpoints
        return Endpoints(
            _checked_host(self.overrides.get("smtp_host"), base.smtp_host),
            _checked_port(self.overrides.get("smtp_port"), base.smtp_port),
            _checked_host(self.overrides.get("imap_host"), base.imap_host),
            _checked_port(self.overrides.get("imap_port"), base.imap_port),
            base.app_password_url,
            base.label,
            derived=base.derived,
        )


def _redacted(exc: BaseException, secret: str) -> str:
    """The server's own words, minus the credential that was on the wire.

    `MailboxError`'s docstring promises never to carry the secret, and the branch for
    `SMTPAuthenticationError` honours it by interpolating nothing. Two generic branches
    did interpolate `{exc}` — and those exceptions are raised at the moment the password
    is in flight, with text the SERVER chooses: `imaplib.IMAP4.error` from `login()` IS
    the server's response line, and `SMTPResponseException` carries `smtp_error`. A
    council measured the password reaching stderr through both, and stderr is where CI
    logs and agent transcripts live.

    The server's text is worth keeping — it is usually the only clue — so it is kept and
    the credential is removed from it, rather than the whole message being thrown away.
    """
    text = str(exc)
    if secret and secret in text:
        text = text.replace(secret, "<credential>")
    return text


def _checked_host(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    host = str(value).strip()
    labels = host.split(".")
    if not host or any(not label or not _LABEL_OK.fullmatch(label) for label in labels):
        raise MailboxError(f"SMTP_OVERRIDES host is not a hostname: {host!r}")
    return host


def _checked_port(value: object, fallback: int) -> int:
    if value is None:
        return fallback
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise MailboxError(f"SMTP_OVERRIDES port is not a number: {value!r}") from exc
    if not 1 <= port <= 65535:
        raise MailboxError(f"SMTP_OVERRIDES port is out of range: {port}")
    return port


class MailboxError(RuntimeError):
    """Raised with a message an operator can act on — never with the secret in it."""


def _identity(root: Path) -> dict:
    path = safe_path(root, root / _IDENTITY_FILE)
    if path.is_symlink():
        # The credential store may legitimately be a symlink, and the kit has an opt-in
        # for that elsewhere. This file is the INDEX, not the secret, and following a
        # link to it silently would decide where the whole mailbox comes from.
        raise MailboxError(
            f"{_IDENTITY_FILE} is a symlink; point `refs` at the credential instead"
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MailboxError(
            f"no mailbox configured: {_IDENTITY_FILE} does not exist. "
            "Run `governancekit mail setup <address>`."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MailboxError(f"{_IDENTITY_FILE} is unreadable: {exc}") from exc


def _legacy_operator_state(root: Path) -> str:
    """An `SMTP_ACCOUNT` answered before the 2026-08-10 retirement, in `.gk/operator.json`."""
    try:
        data = json.loads((root / ".gk/operator.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    for legacy in _LEGACY_ADDRESS_VALUES:
        value = metadata.get(legacy)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def load_mailbox(root: Path) -> Mailbox:
    """Read the operator's mailbox, without reading the secret.

    `identity.json` may not exist at all: a council measured the park and found SIX
    targets carrying the orphaned `SMTP_ACCOUNT` and NONE of them carrying that file.
    The fallback whose comment claimed to serve `CodexBridge` was unreachable on
    `CodexBridge`, because `_identity` raised first. The claim had no artefact behind
    it, which is the defect this whole epic is about, committed in the delivery that
    reverses a retirement for exactly that population.
    """
    try:
        data = _identity(root)
    except MailboxError:
        # No index yet — the legacy answer may still be the only thing this target has.
        data = {}
    values = data.get("values", {}) if isinstance(data.get("values"), dict) else {}
    refs = data.get("refs", {}) if isinstance(data.get("refs"), dict) else {}

    address = str(values.get(_ADDRESS_VALUE) or "").strip()
    if not address:
        for legacy in _LEGACY_ADDRESS_VALUES:
            address = str(values.get(legacy) or "").strip()
            if address:
                break
    if not address:
        # The park's orphans are in `.gk/operator.json`, not here: `_OPERATOR_PLACEHOLDERS`
        # routes there, and `SMTP_ACCOUNT` was answered under that mechanism before the
        # retirement. Six targets, counted by a council over the whole park.
        address = _legacy_operator_state(root)
    if not address:
        raise MailboxError(
            f"no address: set `values.{_ADDRESS_VALUE}` in {_IDENTITY_FILE}. "
            "Run `governancekit mail setup <address>`."
        )

    token_path = str(refs.get(_TOKEN_REF) or _DEFAULT_TOKEN_PATH).strip()
    overrides = {
        key: str(value)
        for key, value in (values.get("SMTP_OVERRIDES") or {}).items()
        if isinstance(value, (str, int))
    } if isinstance(values.get("SMTP_OVERRIDES"), dict) else {}

    return Mailbox(address, token_path, endpoints_for(address), overrides)


def read_token(root: Path, mailbox: Mailbox) -> str:
    """Read the application password. The only function in this module that sees it."""
    # Checked BEFORE `safe_path`, which raises `UnsafePathError` on a symlink and so
    # made this branch unreachable — a guard that reads as protection and never runs,
    # which is the shape `AC-4` is about. The CLI did not catch that exception either,
    # so the documented outcome was a traceback.
    candidate = root / mailbox.token_path
    if candidate.is_symlink():
        raise MailboxError(
            f"{mailbox.token_path} is a symlink; the kit refuses to follow one to a "
            "credential unless the project opted in"
        )
    path = safe_path(root, candidate)
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise MailboxError(
            f"no credential at {mailbox.token_path}. "
            f"Generate one at {mailbox.resolved().app_password_url} and save it there."
        ) from exc
    except OSError as exc:
        raise MailboxError(f"{mailbox.token_path} is unreadable: {exc}") from exc
    if not secret:
        raise MailboxError(f"{mailbox.token_path} is empty")
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        # The asymmetry a council measured: `identity.json` — which holds an address and
        # a PATH — is written 0600, and the one file that holds an actual credential got
        # whatever the umask gave it (0644 on most distributions). Warned rather than
        # refused: the operator is mid-task, and refusing to send would punish them for
        # a permission the kit told them nothing about.
        print(
            f"\nWarning: {mailbox.token_path} is mode {mode:04o} — readable beyond you."
            f"\n  chmod 600 {mailbox.token_path}"
        )
    return secret


def setup_instructions(address: str) -> list[str]:
    """What the operator must do, for THEIR provider, to produce a credential.

    Decided locally from the domain. Nothing is sent anywhere to work out which
    provider this is — the address never leaves the machine to answer a question the
    text after `@` already answers.
    """
    ends = endpoints_for(address)
    lines = [
        f"Mailbox: {address}",
        f"Provider: {ends.label}"
        + ("  (guessed from the domain — override if wrong)" if ends.derived else ""),
        "",
        f"  send: {ends.smtp_host}:{ends.smtp_port}   read: {ends.imap_host}:{ends.imap_port}",
        "",
        "1. Generate an application password (not your account password):",
        f"     {ends.app_password_url}",
    ]
    if ends.derived:
        lines.append(
            "     This domain is not one the kit knows. The URL above is your domain's "
            "site;\n     your provider's control panel is where the app password lives."
        )
    lines += [
        f"2. Save it, and nothing else, in {_DEFAULT_TOKEN_PATH}  (mode 600)",
        "3. Keep it out of git — `.credentials/` is ignored by the managed block.",
        "",
        "The kit stores the PATH to that file, never the credential itself.",
    ]
    return lines


def send_message(
    root: Path, *, to: list[str], subject: str, body: str, dry_run: bool = False
) -> str:
    """Send one message from the operator's mailbox.

    `dry_run` renders and validates everything except the connection, because
    `sending-email.md` says email cannot be recalled and an ambiguous recipient must be
    asked about rather than guessed.
    """
    mailbox = load_mailbox(root)
    recipients = [address.strip() for address in to if address.strip()]
    if not recipients:
        raise MailboxError("no recipient: refusing to send")

    message = EmailMessage()
    message["From"] = mailbox.address
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    ends = mailbox.resolved()
    if dry_run:
        # `endpoints_for` marks a derived host so "every caller can say guessed instead
        # of known" — and this caller, the last checkpoint before a send that cannot be
        # recalled, was the one that did not. `mail setup` said it; the confirmation
        # did not, which is the wrong way round.
        guess = "  (host GUESSED from the domain)" if ends.derived else ""
        return (
            f"would send to {', '.join(recipients)} via {ends.smtp_host}:{ends.smtp_port} "
            f"as {mailbox.address}{guess}"
        )

    secret = read_token(root, mailbox)
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(ends.smtp_host, ends.smtp_port, timeout=30) as server:
            server.starttls(context=context)
            server.login(mailbox.address, secret)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailboxError(
            f"{ends.label} refused the credential in {mailbox.token_path}. "
            f"Generate a new application password at {ends.app_password_url}."
        ) from exc
    except (OSError, smtplib.SMTPException) as exc:
        raise MailboxError(
            f"could not send through {ends.smtp_host}: {_redacted(exc, secret)}"
        ) from exc
    return f"sent to {', '.join(recipients)} as {mailbox.address}"


def _decoded(raw: object) -> str:
    if raw is None:
        return ""
    try:
        return str(make_header(decode_header(str(raw))))
    except (ValueError, UnicodeDecodeError):
        return str(raw)


def list_inbox(root: Path, *, limit: int = 10, mailbox_name: str = "INBOX") -> list[dict]:
    """Read the most recent headers. Headers only — this never downloads a body.

    Reviewing the inbox is a read of someone's correspondence, so the default is the
    narrowest thing that answers "what arrived": who, when, about what.
    """
    mailbox = load_mailbox(root)
    secret = read_token(root, mailbox)
    ends = mailbox.resolved()
    context = ssl.create_default_context()
    out: list[dict] = []
    try:
        # `IMAP4_SSL` defaults to `timeout=None`. Without this the command hung for
        # ever against a host that accepts the connection and never answers — while
        # `send_message`, two functions above, passes 30. Same policy, two
        # implementations, one file.
        with imaplib.IMAP4_SSL(
            ends.imap_host, ends.imap_port, ssl_context=context, timeout=30
        ) as imap:
            imap.login(mailbox.address, secret)
            imap.select(mailbox_name, readonly=True)
            status, data = imap.search(None, "ALL")
            if status != "OK":
                raise MailboxError(f"{ends.imap_host} refused the search: {status}")
            ids = data[0].split()[-max(1, limit):]
            for message_id in reversed(ids):
                status, fetched = imap.fetch(
                    message_id, "(BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT)])"
                )
                if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                    continue
                headers = {}
                for line in fetched[0][1].decode("utf-8", errors="replace").splitlines():
                    if ":" in line:
                        key, _, value = line.partition(":")
                        headers[key.strip().lower()] = value.strip()
                out.append({
                    "from": _decoded(headers.get("from")),
                    "date": _decoded(headers.get("date")),
                    "subject": _decoded(headers.get("subject")),
                })
    except imaplib.IMAP4.error as exc:
        raise MailboxError(
            f"{ends.label} refused the credential in {mailbox.token_path}: "
            f"{_redacted(exc, secret)}"
        ) from exc
    except OSError as exc:
        raise MailboxError(f"could not reach {ends.imap_host}: {exc}") from exc
    return out
