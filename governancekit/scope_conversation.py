"""Localized, guided project-scope interview."""

from __future__ import annotations

import json
import os
import re
import getpass
from dataclasses import dataclass
from pathlib import Path

from .agent_scope import ScopeProposal, propose_project_scope, supported_scope_agents
from .discover import run_discover
from .project_config import ProviderConfig, ProjectConfig, _config_from_existing, load_project_config

_MANDATORY_SOURCES = (
    "AGENTS.md",
    ".docs/software-overview.md",
    ".docs/limits.md",
    "docs/project-rules.md",
)
_BACKTICK_PATH_RE = re.compile(r"`((?:\.docs|docs)/[^`]+|AGENTS\.md)`")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_ROLES = ("primary", "fallback", "optional")
_LLM_PRESETS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash-lite", "GEMINI_API_KEY"),
    "openai": ("https://api.openai.com/v1", "gpt-5-mini", "OPENAI_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3-super-120b-a12b", "NVIDIA_API_KEY"),
}


@dataclass(frozen=True)
class ScopeConversation:
    project_name: str
    required_reading: list[str]
    missing_reading: list[str]
    domains: list[str]
    capabilities: list[str]
    capability_domains: dict[str, str]
    agents: list[str]
    selected_agent: str | None
    providers: list[ProviderConfig]
    scope_summary: str | None


def _project_locale(root: Path) -> str | None:
    """Infer only when the process locale is the neutral C locale."""
    portuguese = (" nao ", " para ", " uma ", " decisoes ", " aprovacoes ", " projeto ")
    spanish = (" para ", " una ", " decisiones ", " aprobaciones ", " proyecto ")
    english = (" the ", " and ", " project ", " decisions ", " approvals ")
    foundation = root / "docs/product-foundation.md"
    candidates = [foundation] if foundation.is_file() else sorted((root / "docs").glob("*.md"))
    text = " "
    for path in candidates:
        text += " " + path.read_text(encoding="utf-8", errors="replace").lower()[:20_000]
    scores = {
        "pt-BR": sum(text.count(token) for token in portuguese),
        "es": sum(text.count(token) for token in spanish),
        "en": sum(text.count(token) for token in english),
    }
    winner = max(scores, key=scores.get)
    return winner if scores[winner] and list(scores.values()).count(scores[winner]) == 1 else None


def resolve_locale(environ: dict[str, str] | None = None, root: Path | None = None) -> str:
    """Choose the operational language without relying on a model default."""
    environ = environ or os.environ
    explicit = environ.get("GOVERNANCEKIT_LOCALE", "").lower().replace("_", "-")
    if explicit.startswith("pt"):
        return "pt-BR"
    if explicit.startswith("es"):
        return "es"
    if explicit.startswith("en"):
        return "en"
    value = " ".join(environ.get(name, "") for name in ("LC_ALL", "LC_MESSAGES", "LANG"))
    value = value.lower().replace("_", "-")
    if "pt" in value:
        return "pt-BR"
    if "es" in value:
        return "es"
    if "en" in value:
        return "en"
    if root is not None:
        inferred = _project_locale(root)
        if inferred:
            return inferred
    language = environ.get("LANGUAGE", "").lower().replace("_", "-")
    if "pt" in language:
        return "pt-BR"
    if "es" in language:
        return "es"
    return "en"


def _clean_csv(value: str) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def _project_doc_references(text: str) -> list[str]:
    return [
        rel for rel in _BACKTICK_PATH_RE.findall(text)
        if rel.startswith("docs/") and rel.endswith(".md") and not any(marker in rel for marker in ("*", "<", ">"))
    ]


def _safe_source(root: Path, rel: str) -> Path | None:
    relative = Path(rel)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def load_required_reading(root: Path) -> tuple[list[str], list[str]]:
    """Follow project documentation only when every resolved path stays in root."""
    root = root.resolve()
    paths = ["docs/required-reading.md", *_MANDATORY_SOURCES]
    index = _safe_source(root, "docs/required-reading.md")
    if index and index.is_file():
        text = _COMMENT_RE.sub("", index.read_text(encoding="utf-8", errors="replace"))
        paths.extend(_BACKTICK_PATH_RE.findall(text))

    available: list[str] = []
    missing: list[str] = []
    pending = list(dict.fromkeys(paths))
    seen: set[str] = set()
    while pending:
        rel = pending.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        path = _safe_source(root, rel)
        if path is None:
            missing.append(f"{rel} (rejected: outside project root)")
        elif path.is_file():
            text = _COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
            available.append(rel)
            if rel.startswith("docs/"):
                pending.extend(_project_doc_references(text))
        else:
            missing.append(rel)
    return available, missing


def _ask(prompt: str, default: str = "", *, gap: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    if gap:
        print()
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


def _yes_no(prompt: str, default: bool = True, *, gap: bool = True) -> bool:
    default_label = "Y/n" if default else "y/N"
    answer = _ask(f"{prompt} [{default_label}]", gap=gap).lower()
    return default if not answer else answer in {"y", "yes", "s", "sim"}


def _message(locale: str, key: str) -> str:
    messages = {
        "pt-BR": {
            "title": "── Definir escopo do projeto ─────────────────────────────────────",
            "reading": "Fontes que o agente leu antes da entrevista:",
            "missing": "Fontes ausentes ou recusadas (complete/corrija antes de implementar):",
            "agents": "Agentes de escopo disponíveis: ",
            "llm_title": "── Acesso LLM para a análise ──────────────────────────────────────",
            "project_agent_title": "── Projeto e agente ───────────────────────────────────────────────",
            "project": "Nome do projeto",
            "agent": "Agente que analisará o projeto",
            "proposal": "── Proposta do agente ─────────────────────────────────────────────",
            "saved_defaults": "Há uma configuração salva ou pendente. Os valores entre colchetes serão mantidos se você pressionar Enter.",
            "domains_help": "Revise os domínios que serão salvos. Enter aceita a proposta mostrada; para alterá-la, informe a lista completa separada por vírgulas. Exemplo: projetos, missões, conversas.",
            "domains": "Domínios a salvar",
            "capabilities_help": "Agora confirme as capacidades de cada domínio. Enter aceita a proposta; uma lista separada por vírgulas substitui somente as capacidades deste domínio.",
            "capabilities": "Capacidades de '{domain}'",
            "providers_title": "── Provedores LLM ─────────────────────────────────────────────────",
            "providers_help": "Configure os provedores que o projeto poderá usar. A finalidade descreve o uso humano (por exemplo, geral ou raciocínio). O papel define o roteamento: primary é o padrão, fallback é usado se o primary falhar e optional não participa do padrão. Nenhum segredo será solicitado ou salvo.",
            "configure_providers": "Configurar provedores LLM agora",
            "provider_name": "Nome do provedor (Enter encerra a lista)",
            "provider_purpose": "Finalidade do provedor (exemplo: geral, raciocínio, rápido)",
            "provider_role": "Papel de roteamento (primary, fallback ou optional)",
            "provider_mode": "Como a credencial é referenciada (env, file-ref ou manual)",
            "provider_ref": "Referência da credencial (nome da variável ou caminho local, nunca o segredo)",
            "provider_url": "URL base compatível com OpenAI",
            "provider_model": "Nome do modelo",
            "llm_advice": "Sugestões: Gemini Flash-Lite costuma oferecer faixa grátis/baixo custo para uso básico a amplo; NVIDIA NIM/Nemotron é OpenAI-compatible e tem afinidade técnica ampla; OpenAI GPT-5 mini tende a ser barato e tecnicamente amplo. Preços, créditos e franquias variam: confirme no portal do provedor. Crie a chave no portal e, abaixo, escolha se ela já está no shell ou se deseja criar um arquivo local protegido para colá-la.",
            "another_provider": "Adicionar outro provedor",
            "invalid_role": "Papel inválido. Use primary, fallback ou optional.",
            "primary_taken": "Já existe um provider primary. Escolha fallback ou optional.",
            "invalid_mode": "Modo inválido. Use env, file-ref ou manual.",
            "missing_ref": "Esse modo exige uma referência de credencial; o segredo não deve ser digitado aqui.",
            "summary_help": "Descreva em uma frase a finalidade, os usuários e os limites do projeto. Enter aceita o resumo proposto.",
            "summary": "Resumo do escopo",
            "no_agents": "nenhum detectado",
            "choose_agent": "Escolha um dos agentes detectados.",
            "domain_required": "Ao menos um domínio é obrigatório.",
            "capability_required": "Ao menos uma capacidade observável é obrigatória.",
            "primary_domain": "Domínio primário da capacidade",
            "use_domain": "Use um dos domínios declarados.",
        },
        "es": {
            "title": "── Definir alcance del proyecto ───────────────────────────────────",
            "reading": "Fuentes que el agente leyó antes de la entrevista:", "missing": "Fuentes ausentes o rechazadas:", "agents": "Agentes disponibles: ", "project_agent_title": "── Proyecto y agente ──────────────────────────────────────────────", "project": "Nombre del proyecto", "agent": "Agente que analizará el proyecto", "proposal": "── Propuesta del agente ───────────────────────────────────────────",
            "saved_defaults": "Hay una configuración guardada o pendiente. Enter conserva los valores entre corchetes.", "llm_title": "── Acceso LLM para el análisis ───────────────────────────────────",
            "domains_help": "Revise los dominios. Enter acepta la propuesta; para cambiarla, escriba la lista completa separada por comas.", "domains": "Dominios a guardar", "capabilities_help": "Confirme las capacidades de cada dominio. Enter acepta la propuesta.", "capabilities": "Capacidades de '{domain}'", "providers_title": "── Proveedores LLM ───────────────────────────────────────────────", "providers_help": "La finalidad describe el uso. primary es predeterminado, fallback se usa si falla y optional no participa por defecto. No se solicitarán secretos.", "configure_providers": "Configurar proveedores LLM ahora", "provider_name": "Nombre del proveedor (Enter termina la lista)", "provider_purpose": "Finalidad (ejemplo: general, razonamiento, rápido)", "provider_role": "Rol (primary, fallback u optional)", "provider_mode": "Referencia de credencial (env, file-ref o manual)", "provider_ref": "Referencia de credencial, nunca el secreto", "provider_url": "URL base compatible con OpenAI", "provider_model": "Nombre del modelo", "another_provider": "Agregar otro proveedor", "invalid_role": "Rol inválido. Use primary, fallback u optional.", "primary_taken": "Ya existe un proveedor primary. Elija fallback u optional.", "invalid_mode": "Modo inválido. Use env, file-ref o manual.", "missing_ref": "Este modo requiere una referencia de credencial.", "summary_help": "Describa finalidad, usuarios y límites. Enter acepta el resumen.", "summary": "Resumen del alcance", "no_agents": "ninguno detectado", "choose_agent": "Elija un agente detectado.", "domain_required": "Se requiere un dominio.", "capability_required": "Se requiere una capacidad.", "primary_domain": "Dominio primario", "use_domain": "Use un dominio declarado.",
        },
        "en": {
            "title": "── Define project scope ───────────────────────────────────────────", "reading": "Sources the agent read before this interview:", "missing": "Missing or rejected sources (complete/fix before implementation):", "agents": "Available scope agents: ", "llm_title": "── LLM access for analysis ───────────────────────────────────────", "project_agent_title": "── Project and agent ──────────────────────────────────────────────", "project": "Project name", "agent": "Agent that will analyze the project", "proposal": "── Agent proposal ─────────────────────────────────────────────────",
            "saved_defaults": "A saved or pending configuration exists. Enter keeps the values in brackets.",
            "domains_help": "Review the domains to save. Enter accepts the proposal; to change it, enter the complete comma-separated list. Example: projects, missions, conversations.", "domains": "Domains to save", "capabilities_help": "Confirm each domain's capabilities. Enter accepts the proposal; a comma-separated list replaces only this domain's capabilities.", "capabilities": "Capabilities for '{domain}'", "providers_title": "── LLM providers ─────────────────────────────────────────────────", "providers_help": "Purpose describes human use (for example general or reasoning). Role controls routing: primary is default, fallback is used if primary fails, and optional is not used by default. No secret will be requested or stored.", "configure_providers": "Configure LLM providers now", "provider_name": "Provider name (Enter ends the list)", "provider_purpose": "Provider purpose (example: general, reasoning, fast)", "provider_role": "Routing role (primary, fallback, or optional)", "provider_mode": "Credential reference mode (env, file-ref, or manual)", "provider_ref": "Credential reference (environment variable or local path, never the secret)", "provider_url": "OpenAI-compatible base URL", "provider_model": "Model name", "another_provider": "Add another provider", "invalid_role": "Invalid role. Use primary, fallback, or optional.", "primary_taken": "A primary provider already exists. Choose fallback or optional.", "invalid_mode": "Invalid mode. Use env, file-ref, or manual.", "missing_ref": "This mode requires a credential reference; do not enter the secret.", "summary_help": "Describe the purpose, users, and boundaries in one sentence. Enter accepts the proposed summary.", "summary": "Scope summary", "no_agents": "none detected", "choose_agent": "Choose one of the detected agents.", "domain_required": "At least one domain is required.", "capability_required": "At least one observable capability is required.", "primary_domain": "Primary domain for the capability", "use_domain": "Use one of the declared domains.",
        },
    }
    return messages[locale][key]


def _pending_or_applied_config(root: Path) -> ProjectConfig | None:
    current = load_project_config(root)
    if current is not None:
        return current
    path = root / ".gk/config-session.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    plan = data.get("plan") if isinstance(data, dict) else None
    config = plan.get("config") if isinstance(plan, dict) else None
    return _config_from_existing(config) if isinstance(config, dict) else None


def _print_provider_help(locale: str) -> None:
    if locale == "pt-BR":
        print("Esta configuração define qual LLM pode analisar o escopo.")
        print("Você pode usar uma variável de ambiente, apontar um arquivo existente ou criar um arquivo local protegido.")
        print("Ao criar o arquivo, a chave pode ser colada com a entrada oculta; ela não aparece na tela nem na configuração.")
        print("Papéis de roteamento:")
        print("  primary  - escolha padrão para análise.")
        print("  fallback - usada se a primary falhar.")
        print("  optional - disponível, mas fora do caminho padrão.")
        return
    print("This configuration determines which LLM can analyze the project scope.")
    print("It is used only for this scope interview, not for development tasks or project implementation.")
    print("Use an environment variable, reference an existing file, or create a protected local credential file.")
    print("When creating the file, the API key can be pasted into hidden input; it is not shown or stored in configuration.")
    print("Routing roles:")
    print("  primary  - default choice for analysis.")
    print("  fallback - used when the primary fails.")
    print("  optional - available, but outside the default route.")


def _print_provider_catalog(locale: str) -> None:
    if locale == "pt-BR":
        print("\nProvedores pré-configurados, compatíveis com a API OpenAI:")
        print("  gemini - Google Gemini; URL, modelo e GEMINI_API_KEY sugeridos automaticamente.")
        print("  nvidia - NVIDIA NIM; URL, modelo Nemotron e NVIDIA_API_KEY sugeridos automaticamente.")
        print("  openai - OpenAI; URL, modelo e OPENAI_API_KEY sugeridos automaticamente.")
        print("  outro  - qualquer endpoint compatível; informe URL, modelo e a referência da credencial.")
        return
    if locale == "es":
        print("\nProveedores preconfigurados compatibles con la API OpenAI:")
        print("  gemini - Google Gemini; URL, modelo y GEMINI_API_KEY sugeridos automáticamente.")
        print("  nvidia - NVIDIA NIM; URL, modelo Nemotron y NVIDIA_API_KEY sugeridos automáticamente.")
        print("  openai - OpenAI; URL, modelo y OPENAI_API_KEY sugeridos automáticamente.")
        print("  otro   - cualquier endpoint compatible; indique URL, modelo y referencia de credencial.")
        return
    print("\nPreconfigured OpenAI-compatible providers:")
    print("  gemini - Google Gemini; suggests its URL, model, and GEMINI_API_KEY.")
    print("  nvidia - NVIDIA NIM; suggests its URL, Nemotron model, and NVIDIA_API_KEY.")
    print("  openai - OpenAI; suggests its URL, model, and OPENAI_API_KEY.")
    print("  other  - any compatible endpoint; provide its URL, model, and credential reference.")


def _saved_providers(existing: ProjectConfig | None) -> list[ProviderConfig]:
    """A manual placeholder means no API provider was configured."""
    if existing is None:
        return []
    return [provider for provider in existing.providers if provider.mode != "manual"]


def _write_credential_file(root: Path, provider_name: str, secret: str) -> str:
    """Store a pasted secret outside project configuration with owner-only permissions."""
    root = root.resolve()
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", provider_name).strip(".-") or "llm"
    directory = root / ".credentials" / "llm"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        directory.resolve().relative_to(root)
    except ValueError as exc:
        raise RuntimeError("credential directory escaped the project root") from exc
    directory.chmod(0o700)
    target = directory / f"{safe_name}.key"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(target, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(secret.strip() + "\n")
    target.chmod(0o600)
    return target.relative_to(root).as_posix()


def _credential_method(locale: str) -> str:
    if locale == "pt-BR":
        print("Como a chave de API será fornecida?")
        print("  env      - a chave já está em uma variável de ambiente.")
        print("  arquivo  - a chave já está em um arquivo local protegido.")
        print("  criar    - criar `.credentials/llm/<provedor>.key` e colar a chave com entrada oculta.")
        print("  ajuda    - explicar como obter uma chave no portal do provedor.")
        return _ask("Método da credencial (env, arquivo, criar ou ajuda)", "env", gap=False).lower()
    print("How will the API key be provided?")
    print("  env    - the key is already in an environment variable.")
    print("  file   - the key is already in a protected local file.")
    print("  create - create `.credentials/llm/<provider>.key` and paste the key into hidden input.")
    print("  help   - explain how to obtain a key from the provider portal.")
    return _ask("Credential method (env, file, create, or help)", "env", gap=False).lower()


def _print_credential_help(locale: str, provider_name: str) -> None:
    if locale == "pt-BR":
        print(f"  Para usar {provider_name}, crie uma conta no portal do provedor, gere uma API key e retorne a esta pergunta.")
        print("  Depois escolha `env` se a chave estiver exportada no shell, ou `criar` para guardá-la apenas neste checkout.")
        return
    print(f"  Create an account in the {provider_name} provider portal, generate an API key, then return to this prompt.")
    print("  Choose `env` when it is exported in the shell, or `create` to store it only in this checkout.")


def _collect_providers(root: Path, locale: str, existing: ProjectConfig | None) -> list[ProviderConfig]:
    print("\n" + _message(locale, "providers_title"))
    _print_provider_help(locale)
    _print_provider_catalog(locale)
    if locale == "pt-BR":
        print("\n" + _message(locale, "llm_advice"))
    saved = _saved_providers(existing)
    if saved:
        print("\nConfiguração LLM já salva:" if locale == "pt-BR" else "\nSaved LLM configuration:")
        for provider in saved:
            details = [provider.purpose or "general", provider.role or "primary"]
            if provider.model:
                details.append(provider.model)
            print(f"  - {provider.name}: {', '.join(details)}")
        if _yes_no("Manter esta configuração LLM" if locale == "pt-BR" else "Keep this LLM configuration", gap=False):
            return saved
    if not _yes_no(_message(locale, "configure_providers"), gap=False):
        return [ProviderConfig(name="manual", mode="manual")]
    providers: list[ProviderConfig] = []
    while True:
        name = _ask(_message(locale, "provider_name"), gap=False)
        if not name:
            break
        purpose = _ask(_message(locale, "provider_purpose"), "general", gap=False)
        preset = _LLM_PRESETS.get(name.lower())
        while True:
            role = _ask(_message(locale, "provider_role"), "primary" if not providers else "fallback", gap=False)
            if role in _ROLES and not (role == "primary" and any(item.role == "primary" for item in providers)):
                break
            print("  " + _message(locale, "primary_taken" if role == "primary" else "invalid_role"))
        while True:
            method = _credential_method(locale)
            aliases = {"arquivo": "file", "criar": "create", "ajuda": "help"}
            method = aliases.get(method, method)
            if method == "help":
                _print_credential_help(locale, name)
                continue
            if method in {"env", "file", "create"}:
                break
            print("  Escolha env, arquivo, criar ou ajuda." if locale == "pt-BR" else "  Choose env, file, create, or help.")
        if method == "create":
            prompt = "Cole a chave de API (a entrada não será exibida)" if locale == "pt-BR" else "Paste the API key (input is hidden)"
            secret = getpass.getpass(f"  {prompt}: ").strip()
            while not secret:
                print("  A chave não pode ficar vazia." if locale == "pt-BR" else "  The API key cannot be empty.")
                secret = getpass.getpass(f"  {prompt}: ").strip()
            mode = "file-ref"
            credential_ref = _write_credential_file(root, name, secret)
        else:
            mode = "env" if method == "env" else "file-ref"
            default_ref = preset[2] if mode == "env" and preset else ""
            credential_ref = ""
            while not credential_ref:
                label = "Nome da variável de ambiente" if mode == "env" and locale == "pt-BR" else _message(locale, "provider_ref")
                credential_ref = _ask(label, default_ref, gap=False)
                if not credential_ref:
                    print("  " + _message(locale, "missing_ref"))
        base_url = _ask(_message(locale, "provider_url"), preset[0] if preset else "", gap=False)
        while not base_url:
            print("  Informe a URL base para que este provedor possa ser usado." if locale == "pt-BR" else "  Enter a base URL so this provider can be used.")
            base_url = _ask(_message(locale, "provider_url"), gap=False)
        model = _ask(_message(locale, "provider_model"), preset[1] if preset else "", gap=False)
        while not model:
            print("  Informe o modelo para que este provedor possa ser usado." if locale == "pt-BR" else "  Enter a model so this provider can be used.")
            model = _ask(_message(locale, "provider_model"), gap=False)
        providers.append(ProviderConfig(name=name, purpose=purpose or None, base_url=base_url or None, model=model or None, mode=mode, credential_ref=credential_ref, validation="reference-required", role=role))
        if not _yes_no(_message(locale, "another_provider"), default=False, gap=False):
            break
    return providers or [ProviderConfig(name="manual", mode="manual")]


def run_scope_conversation(root: Path, *, locale: str | None = None) -> ScopeConversation:
    root = root.resolve()
    locale = locale or resolve_locale(root=root)
    sources, missing = load_required_reading(root)
    discovery = run_discover(root)
    existing = _pending_or_applied_config(root)
    available_agents = supported_scope_agents(discovery.agents)

    print("\n" + _message(locale, "title"))
    print(_message(locale, "reading"))
    for source in sources:
        print(f"  - {source}")
    if missing:
        print(_message(locale, "missing"))
        for source in missing:
            print(f"  - {source}")
    print("\n" + _message(locale, "project_agent_title"))
    project_name = _ask(_message(locale, "project"), existing.project_name if existing else root.name, gap=False)
    if locale == "pt-BR":
        print("\n" + _message(locale, "llm_title"))
    providers = _collect_providers(root, locale, existing)
    api_provider = next(
        (item for item in providers if item.role == "primary" and item.mode in {"env", "file-ref"} and item.base_url and item.model and item.credential_ref),
        None,
    )
    if api_provider:
        available_agents = ["llm-api", *available_agents]
    print(_message(locale, "agents") + (", ".join(available_agents) or _message(locale, "no_agents")))
    if not available_agents:
        raise RuntimeError("no supported scope agent is installed (codex, claude, gemini, or cursor)")
    selected_default = existing.selected_agent if existing and existing.selected_agent in available_agents else available_agents[0]
    selected_agent = _ask(_message(locale, "agent"), selected_default, gap=False)
    while selected_agent not in available_agents:
        print("  " + _message(locale, "choose_agent"))
        selected_agent = _ask(_message(locale, "agent"), selected_default, gap=False)
    proposal: ScopeProposal = propose_project_scope(root, selected_agent, sources, locale=locale, provider=api_provider)
    print("\n" + _message(locale, "proposal"))
    print(proposal.render(locale=locale))
    if existing:
        print(_message(locale, "saved_defaults"))

    print("\n" + _message(locale, "domains_help"))
    proposal_default = ", ".join(existing.domains) if existing else ", ".join(proposal.domain_names)
    domains = _clean_csv(_ask(_message(locale, "domains"), proposal_default, gap=False))
    while not domains:
        print("  " + _message(locale, "domain_required"))
        domains = _clean_csv(_ask(_message(locale, "domains"), proposal_default, gap=False))

    print("\n" + _message(locale, "capabilities_help"))
    capabilities: list[str] = []
    capability_domains: dict[str, str] = {}
    for domain in domains:
        default_capabilities = ", ".join(
            capability for capability in (existing.capabilities if existing else [])
            if existing and existing.capability_domains.get(capability) == domain
        ) or ", ".join(proposal.capabilities_for(domain))
        names = _clean_csv(_ask(_message(locale, "capabilities").format(domain=domain), default_capabilities, gap=False))
        for name in names:
            if name in capability_domains:
                continue
            capabilities.append(name)
            capability_domains[name] = domain
    while not capabilities:
        print("  " + _message(locale, "capability_required"))
        domain = _ask(_message(locale, "primary_domain"), domains[0], gap=False)
        if domain not in domains:
            print("  " + _message(locale, "use_domain"))
            continue
        for name in _clean_csv(_ask(_message(locale, "capabilities").format(domain=domain), gap=False)):
            if name not in capability_domains:
                capabilities.append(name)
                capability_domains[name] = domain

    print("\n" + _message(locale, "summary_help"))
    scope_summary = _ask(_message(locale, "summary"), existing.scope_summary if existing and existing.scope_summary else proposal.summary, gap=False) or None
    return ScopeConversation(project_name, sources, missing, domains, capabilities, capability_domains, available_agents, selected_agent, providers, scope_summary)
