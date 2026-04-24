# clipress
Universal CLI output compressor for AI agents.

Ships lean. Gets smarter with every call.

## Description
A Python-based CLI proxy that intercepts bash command output before it reaches an AI agent's context window, compresses it using a hybrid classifier + registry system, and returns only the semantically meaningful portion of the output.

## Integration & Setup

### For Shell-Based Agents (Gemini CLI, Codex, Pi)
Must set `CLIPRESS_AGENT_MODE=true` before starting the agent to enable the shell wrapper.
```bash
export CLIPRESS_AGENT_MODE=true
# start your agent
gemini-cli
```

### For Claude Code
Uses `.claude/settings.json` PostToolUse hook automatically. No env setup required.

## Known Limitations & Architecture Notes

### Streaming Pass-Through
`clipress` is **not a streaming pass-through**. It requires the full stdout/stderr of a command before it can classify, analyze, and compress the output. For very long-running commands that yield output slowly, you will not see real-time output updates.

### Thread Safety
The compressor is **NOT thread‑safe**. Concurrent calls from an agent running multiple bash commands simultaneously may corrupt the learned registry (`learned.json`) or the in-memory hot cache. Agents should await command completion before executing the next command.

### Cursor / Copilot (Integrated Terminal)
Coverage is partial — it only intercepts direct bash commands run in the terminal, not internal file APIs or custom executions via their extensions.

## Core Philosophy
- **Minimal Core**: Intelligence lives in the workspace, not the package.
- **Adaptive**: Learns from the command outputs over time.
- **Consistent**: Output contracts define what the user always sees.
- **Extendible**: Users shape compression through YAML only.
