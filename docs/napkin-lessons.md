# Napkin Lessons

- 2026-08-02: Fechar uma melhoria de UX exige registrar o comportamento
  efetivamente publicado e deixar a próxima validação real explícita; testes não
  substituem observação em uma árvore grande de consumidor.

- 2026-08-02: A rejected LLM proposal is an operator-visible exception, not a
  generic open item. State the provider/model, the contract violated, and the
  safe next decision without making the operator infer whether writing proceeds.

- 2026-08-02: Discovery must make its bounded scope visible. Report direct
  project folders only and prune nested Git roots before file enumeration, so a
  parent project never silently classifies another project's source.

- 2026-08-02: Recursive discovery is observable work, not an instant prompt.
  Announce it before scanning and state a realistic duration, especially before
  a second LLM-backed analysis can begin.

- 2026-08-02: Print the runtime version before an interactive installer begins,
  so captured terminal output identifies the exact CLI behavior under review.

- 2026-08-02: A configured provider is not consent to invoke it. In an
  interactive adoption flow, name the provider/model and ask before sending
  project sources; if it fails, attribute the failure to that provider/model,
  not to an invisible “selected agent”.

- 2026-08-02: Um provider configurado pode enriquecer uma proposta normal, mas
  sua indisponibilidade não transforma instalação em falha. Preserve a descoberta
  determinística, registre a lacuna e mantenha a aceitação humana como gate.

- 2026-08-02: Drift de projeto é evidência nova, não autorização para reescrever
  decisões aceitas. No upgrade, mostre a diferença e deixe a atualização de
  documentação como ação explícita.

- 2026-08-02: A ajuda raiz deve ensinar o caminho normal antes de listar o
  poder da ferramenta. Marcar superfícies especializadas como avançadas preserva
  descoberta sem transformar a primeira execução em um manual interno.

- 2026-08-02: Uma instalação simples não deve esconder consentimento: proposta
  gerada pode ser a UX padrão, mas automação precisa de `--accept-generated` e
  documentos completos já aceitos permanecem intocados.

- 2026-08-02: A removal plan must treat provenance as deletion authority, not
  merely evidence. A matching installed-file hash can permit a backup-first
  deletion; modified, unknown, referenced, and symlink paths stay preserved.

- 2026-08-02: Semantic extraction needs a distinct operator acceptance flag even
  after plan review. A configured LLM may propose the split, but it cannot decide
  that project content is moved or that the kit remainder replaces the source.

- 2026-07-27: A tokenizer can count its own encoding precisely without predicting
  another model's billing tokens. Report tokenizer and estimate mode separately;
  never translate library precision into universal model precision.

- 2026-07-27: Optional sources must be selected after every mandatory source.
  Otherwise an optional file can consume budget and make a later mandatory contract
  fail even though omitting the optional source would produce a valid context.

- 2026-05-04: Keep the policy kit and runtime orchestrator conceptually separate; this project owns the runtime/tooling layer.
- 2026-05-04: Bootstrap the runtime project with ready context and limits before choosing CLI, MCP, or IDE implementation details.
- 2026-05-04: Start runtime work with a narrow `doctor` command so governance rules become executable before orchestration grows.
- 2026-06-29: Project-owned docs (`docs/required-reading.md`, `docs/project/`) must NOT sit in the installer's upgrade path list — otherwise `--upgrade`/`--docs-only` would clobber project-authored content. Fresh install seeds them via the wholesale `docs` copy; upgrade preserves them by omission.
- 2026-06-29: Default install gitignores `docs` wholesale, which would also hide the project-owned `docs/project/`. Git cannot re-include a child of an ignored dir, so a bare `docs` + `!docs/project/` fails. Fix: emit `docs/*` (non-opaque) + `!docs/project/`. Verified with `git check-ignore`.
- 2026-06-29: `configure` only fills *known* kit placeholders (the `_PLACEHOLDER_DESCRIPTIONS` set); scanning all files for any `[WORD]` token would wrongly match doctor's own `[FAIL]`/`[HINT]` samples in README.
- 2026-07-01: Kit now lives in `.docs/`; `docs/` is 100% the project's. This ends the confusion of the project folder nesting inside the kit folder and stops `--upgrade` from invading legacy projects that already used `docs/`. The installer maps source `docs/` → dest `.docs/` (`_dest_rel`) so it works even before the AI-Agents source repo is restructured (twin epic `WK-20260701-dotdocs-kit-layout`). `--upgrade` auto-migrates legacy layouts (backup in `.docs-migration-bak/`). Whether `.docs/` is git-tracked is a prompted choice persisted in `.governancekit`; secrets stay ignored regardless.
- 2026-07-02: Per-host identity is now enforced runtime, not just contract (`WK-20260702-per-host-identity-runtime`). New `governancekit/identity.py` persists `operator_name/host_id/instance_path/sibling_path/assigned_ports/branch_ownership` to a gitignored `.governancekit-identity.json` (per instance, never tracked, no secrets). `doctor` gained a MANDATORY `host identity` gate (`[FAIL]`/`ok:false` when missing/incomplete) plus an advisory `sibling branch` same-branch guard; `resume` shows active operator@host + branch and warns on sibling collision; `configure` collects the fields (interactive prompts + `--operator-name/--host-id/...` flags) and refuses to save while a required field is missing. Field names deliberately match the AI-Agents companion contract issue for cross-repo alignment.
- 2026-07-06: Distilled the security mutirão (~280 real vulns) into the kit as verifiable rules (`WK-20260706-security-standards-distill`). Two homes by nature: normative *rules* went to AI-Agents (`.docs/agents/security-standards.md` + PR self-check, wired from `security.md`/required-reading); *enforcement* stays here. Of the 8 standard sections, §1 (secrets) and §7 (supply chain) were already materialized — `doctor._check_tracked_secret_files` (reactive: no secret already tracked) and installer `KNOWN_TARBALL_SHA256` checksum (SEC-0256). Added `doctor._check_gitignore_secrets` as the *preventive* counterpart to tracked-secrets: probes `.env` and `.credentials/secret.token` with `git check-ignore -q` so a repo can't track a secret in the first place (non-git repo passes, like tracked-secrets). Gap still open: SEC-0257 release-gate is a no-op in AI-Agents `new-tag.sh` (no `scripts/run-checks.sh`); and §3/§4/§5 (loopback bind, per-action authz, CORS fail-closed) remain review-gated, not automated.
- 2026-07-20: `doctor` foi flagrado em uso real (AcheiVc) reprovando o que o kit distribui e varrendo o que o git ignora — 5 de 15 findings eram ruído (`.env.example` como segredo; `main.dart.js` do Flutter em `.dart_tool/` gitignored dentro de submódulo). Ruído num scan advisory não é neutro: treina o operador a ignorar a saída, e o sinal real (shell injection ×3, weak password hash) afunda junto. A lógica correta de excluir `.example` já existia no gêmeo (`run-checks.sh` §4) e os dois gates discordavam. Lição: rodar as ferramentas de governança contra um projeto REAL, não só contra fixtures — os falsos positivos só aparecem no ruído de um repo de verdade (build artifacts, submódulos, `.example`).
- 2026-07-20: Recomendei "esperar o épico do arnês" para não adicionar um quinto walker ao pacote (medo do §7). Ao implementar a correção pontual, o medo não se materializou: modifiquei `_iter_source_files` no lugar (submódulo) e o gitignore virou um helper de CONSULTA ao git (`check-ignore -z --stdin`), não um walker. `§7` é sobre mecanismo geral novo com zero adotantes — modificar uma função existente + um helper de query não é isso. Lição: a recomendação conservadora ("espera a abstração certa") pode ser cara sem necessidade; medir o custo real da correção pontual antes de adiá-la — às vezes ela é menor do que o medo do §7 sugere.
- 2026-08-04: WK-20260804-home-shadow — o gate que detecta "projeto não configurado" era lido de fora do projeto: `~/AGENTS.md` + `~/docs/limits.md` instalados no `$HOME` eram herdados por walk-up por todo diretório abaixo, e o fallback era o `limits.md` mais permissivo do parque. Falhava aberto exatamente no caso em que importava. Lição: uma trava textual que mora no arquivo que ela exige não é trava; a verificação de `--root` tinha de ser mecânica, no código que escreve.
- 2026-08-04: WK-20260804-readiness-files — a épica 002 escreveu o critério certo ("docs/ é 100% território do projeto") e a task 001 dela classificou `limits.md`/`software-overview.md` como kit-owned mesmo assim. Um alvo reagiu em 2 dias com um symlink `.docs/limits.md -> ../docs/limits.md`, e o instalador cresceu um ramo inteiro de detecção de symlink para conviver com a gambiarra. Lição: quando a implementação precisa de código novo para sobreviver a uma gambiarra do usuário, a gambiarra é o requisito e a classificação é que está errada.
- 2026-08-04: WK-20260804-readiness-gate — o `doctor` testava o flag com `if "limits_ready: yes" in content`, e o template que o próprio kit distribui explica o flag em prosa. Resultado: template intocado passava no gate, enquanto o instalador shell (regex ancorada) bloqueava o MESMO arquivo. O teste não pegava porque a fixture era um arquivo de uma linha, incapaz de exibir o bug. Lição: quando dois gates cobrem o mesmo contrato em linguagens diferentes, o teste do mais frouxo tem de usar o artefato REAL que o produto distribui como fixture — fixture sintética esconde exatamente a diferença que importa.
- 2026-08-04: WK-20260804-review-findings — antes de reescrever histórico, olhar se o checkout é worktree. Este era: `AI/GovernanceKit/.git` servia quatro worktrees, três com feature branch não mesclada. Um `filter-repo` teria invalidado os quatro de uma vez, e o custo só apareceu porque conferi `.git` (arquivo, não diretório) antes de rodar. Lição: `cat .git` custa um segundo e distingue clone de worktree — a diferença entre reescrever um repo e reescrever quatro.
- 2026-08-04: WK-20260804-concurrency-awareness — o contrato do §8c existia desde maio e dizia que o kit "can surface" o relógio de encerramento; ninguém tinha grepado para ver se surfaceava. Não surfaceava: zero linhas. Lição: um contrato que descreve o runtime no modo "pode" nunca vira teste, e ninguém percebe a ausência — quando o texto delega a um mecanismo, o mecanismo precisa de nome de arquivo e teste, não de verbo modal.

- 2026-08-06: WK-20260806-council-commit-gate — o `pre-commit` que este kit instala nunca reprovou nada pelo `doctor`, por dois defeitos somados: `cli.py` sem guarda `__main__` (o `python3 -m governancekit.cli` importava, não imprimia e saía 0) e o veredito lido por `python3 - <<'PY'`, onde o heredoc SUBSTITUI o pipe como stdin. Os dois sobreviveram porque `tests/test_hooks.py` só afirmava sobre o TEXTO do script. Próxima vez: teste de hook ou de script gerado tem que EXECUTAR, e ser verificado por mutação — desligue o mecanismo e confirme que o teste falha.
- 2026-08-06: WK-20260804-governancekit-contract-reassessment (crítica A1) — a correção de caminhos do AI-Agents está na fonte desde 04/08 e não chegou a projeto nenhum, porque o elo que falta é NOSSO: `DEFAULT_REF` em `install_agents.py:21` mais a tabela de checksums. O CodexBridge rodou upgrade hoje e recebeu o texto velho. Próxima vez: quando uma issue de outro repositório depende de uma constante deste, escrever isso NA issue e nomear o dono do elo — senão ela é dada como fechada na fonte enquanto o parque segue quebrado. O `--check`/dry-run já mordeu assim em 23/07: relatório e realidade discordando, com o relatório otimista.
- 2026-08-06: WK-20260804-governancekit-contract-reassessment (crítica G1) — a tentação era trocar a verificação de coerência por uma comparação de hashes, já que o `.gk/manifest.json` guarda sha256 por arquivo. Não serve: o `AGENTS.md` incoerente BATE com o hash dele — foi instalado fielmente e está errado. Drift pega arquivo adulterado; coerência pega contrato fiel e obsoleto. Próxima vez: antes de substituir uma verificação por outra mais barata, rodar a barata contra o caso que motivou a cara. (E o `_check_manifest_drift`, `doctor.py:566`, hoje só confere presença — guarda os hashes e nunca os compara.)
- 2026-08-06: WK-20260806-council-commit-gate — o gate novo disparou no session-close do AI/Agents e não podia ser satisfeito: o gatilho `not-validated` lê o ARQUIVO `handoff.md` inteiro, não as linhas ADICIONADAS pelo diff staged, e casou uma entrada de 27/07 — dez dias antes da entrega. Como está, qualquer entrada passada com o marcador faz TODO commit que toca `handoff.md` disparar o gate para sempre, e a única saída é o waiver. Um gate que não pode ser satisfeito pelo trabalho corrente ensina a waivar por reflexo. Próxima vez: gatilho que fala sobre "a entrega" lê o DIFF, nunca o arquivo — arquivo acumula histórico e o gate passa a julgar o passado. É a quarta forma do mesmo defeito de detecção neste kit (substring vs âncora, prosa que ensina o marcador, escopo arquivo vs diff): perguntar sempre "sobre QUAL texto este detector decide?".
- 2026-08-06: WK-20260806-council-commit-gate — segundo falso positivo do MESMO gatilho, no mesmo dia: a linha do meu handoff que DESCREVE o gatilho (`` `not validated:` ancorado ``) disparou o gate. A âncora que escrevi de manhã aceita espaço e aspa/crase opcionais antes do marcador, então uma menção entre crases no início da linha casa como declaração. É a mesma lição de 24/07 — documentação de um mecanismo de detecção não pode escrever o padrão detectável — reincidindo pela terceira vez, agora no arquivo que descreve o próprio detector. Próxima vez: a âncora tem que EXIGIR o contexto de declaração (início de item de lista seguido de texto), e o teste de regressão nasce com a frase que fala do marcador, escrita como um humano escreveria: entre crases.
- 2026-08-07: WK-20260807-not-validated-trigger-scope — as duas correções do gatilho eram de ESCOPO, e o contrato já dizia o escopo certo: `council.md` §4 fala em "the delivery's `Tests` section", e a implementação tinha largado as duas qualificações — o diff (não o arquivo) e a seção (não qualquer prosa). Achar o defeito foi reler o contrato que o código diz implementar. Próxima vez, num detector que erra: comparar o código com a frase do contrato palavra por palavra ANTES de inventar heurística nova — o `[MANDATORY]` costuma já conter a resposta, e o que se perdeu foi um qualificador, não um algoritmo.
- 2026-08-07: WK-20260807-not-validated-trigger-scope (council, rodada 1) — corrigi o falso positivo estreitando o escopo para a seção `Tests`, e o *sweep skeptic* mostrou que isso perdia TRÊS das quatro ocorrências reais nos dois `handoff.md`: entradas escritas como uma lista de bullets simples não têm subseção nenhuma. Troquei um alarme falso barulhento por uma omissão silenciosa, que é pior. Próxima vez: ao apertar um detector por causa de falso positivo, rodar o detector apertado contra TODAS as ocorrências reais do parque antes de aceitar a correção — o falso negativo não aparece em teste sintético, só no arquivo de verdade.
- 2026-08-07: WK-20260807-not-validated-trigger-scope (council, rodada 2) — o gate falhava ABERTO na configuração git do operador: `diff.external`, `GIT_EXTERNAL_DIFF` e um atributo `-diff` no `.gitattributes` fazem `git diff` devolver zero hunks, e zero hunks é indistinguível de um diff limpo. Um parser de diff que não passa `--no-ext-diff --no-textconv --text` está confiando na config de quem commita. Próxima vez: todo `git diff` lido por máquina leva os três flags — e o teste do detector configura `diff.external` no repo temporário, porque nenhuma fixture o faz sozinha.
- 2026-08-07: WK-20260807-not-validated-trigger-scope (council, rodada 2) — a minha segunda tentativa calculava intervalos de entrada (`entry_level`, `starts`, spans) e criou um modo de falha que a versão simples não tem: uma entrada escrita um nível fundo demais era absorvida pela anterior e o corpo dela caía FORA de todos os intervalos — nem reivindicação, nem prosa, inalcançável. A regra final — "o heading que encerra a linha, e mais nada" — classifica os mesmos quatro casos reais e não tem intervalo para errar. Próxima vez: quando a aritmética de estrutura não distingue `### EntryB` de `### Entregue`, ela não está comprando nada — está só criando superfície onde o silêncio pode se esconder.
