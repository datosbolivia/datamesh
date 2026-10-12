import { spawn } from "node:child_process"
import fs from "node:fs"
import path from "node:path"

// \p{Emoji} also matches ASCII digits, '#' and '*' (they carry the Emoji property
// for VS16 use), which would forbid any .md containing a numeral. Extended_Pictographic
// narrows the match to actual emoji depictions.
const EMOJI_RE = /[\p{Extended_Pictographic}]/u
const DOC_FILE_RE = /\.(md|qmd|rst)$/i
const CODE_FILE_RE = /^(bindings\/python\/.*\.py|core-go\/.*\.go|bindings\/typescript\/src\/.*\.tsx?|bindings\/r\/.*\.[Rr])$/i
const IGNORED_DIR_RE = /(^|\/)(dist|build|node_modules|\.venv|__pycache__)\//

const FORBIDDEN_BASH: Array<{ re: RegExp; why: string }> = [
  { re: /git\s+push\s+.*?--force(-with-lease)?\b/i, why: "git push --force" },
  { re: /git\s+push.*?\s-f\b/i, why: "git push -f" },
  { re: /git\s+force-push/i, why: "git force-push" },
  { re: /chmod\s+(-R\s*)?777/i, why: "chmod 777 (world-writable permissions)" },
  { re: /rm\s+-rf\s+\/{1,2}/i, why: "rm -rf on filesystem root" },
]

const DEBOUNCE_MS = 10_000

const sh = (s: string): string => `'${s.replace(/'/g, "'\\''")}'`

export const GuardhooksPlugin = async (ctx: any) => {
  const root: string = ctx.worktree ?? ctx.directory ?? process.cwd()
  const graphDir = path.join(root, "graphify-out")
  const logFile = path.join(graphDir, "guardhook.log")
  fs.mkdirSync(graphDir, { recursive: true })

  const changed = new Set<string>()
  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false

  const rel = (p: string): string => path.relative(root, p).split(path.sep).join("/")

  const isCodeFile = (p: string): boolean => {
    const r = rel(p)
    return CODE_FILE_RE.test(r) && !IGNORED_DIR_RE.test(r)
  }

  const noteChange = (p: string): void => {
    if (!isCodeFile(p)) return
    changed.add(rel(p))
    if (!timer) timer = setTimeout(run, DEBOUNCE_MS)
  }

  const schedule = (): void => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(run, DEBOUNCE_MS)
  }

  async function run(): Promise<void> {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (running || changed.size === 0) return
    running = true
    const files = [...changed].sort()
    changed.clear()

    const langs = new Set<string>()
    let wantGraph = false
    for (const f of files) {
      wantGraph = true
      if (f.startsWith("bindings/python/")) langs.add("python")
      else if (f.startsWith("core-go/")) langs.add("go")
      else if (f.startsWith("bindings/typescript/")) langs.add("ts")
      else if (f.startsWith("bindings/r/")) langs.add("r")
    }

    const cmds: string[] = []
    cmds.push(`echo "== guardhooks $(date '+%F %T') files=[${files.join(", ")}] ==="`)
    if (wantGraph) {
      cmds.push(
        `command -v graphify >/dev/null 2>&1 && { echo "[guardhooks] graphify update ."; graphify update . >/dev/null 2>&1 || echo "[guardhooks] graphify update FAILED rc=$?"; }`
      )
    }
    if (langs.has("python")) {
      cmds.push(
        `echo "[guardhooks] python3 -m pytest -q bindings/python/tests"; python3 -m pytest -q bindings/python/tests || echo "[guardhooks] pytest FAILED rc=$?"`
      )
    }
    if (langs.has("go")) {
      cmds.push(
        `command -v go >/dev/null 2>&1 && { echo "[guardhooks] go test ./... (core-go)"; (cd core-go && go test ./...) || echo "[guardhooks] go test FAILED rc=$?"; } || echo "[guardhooks] skip go test (go toolchain not installed)"`
      )
    }
    if (langs.has("ts")) {
      cmds.push(
        `[ -x bindings/typescript/node_modules/.bin/tsc ] && { echo "[guardhooks] tsc --noEmit"; (cd bindings/typescript && ./node_modules/.bin/tsc --noEmit) || echo "[guardhooks] tsc FAILED rc=$?"; } || echo "[guardhooks] skip tsc (bindings/typescript deps not installed)"`
      )
    }

    const script = `LOG=${sh(logFile)}; { ${cmds.join("; ")}; } >> "$LOG" 2>&1`
    fs.appendFileSync(logFile, `[guardhooks] queued ${files.length} file(s): ${files.join(", ")}\n`)
    const child = spawn("bash", ["-c", script], { cwd: root })
    child.on("exit", () => {
      running = false
      if (changed.size > 0 && !timer) schedule()
    })
  }

  return {
    "tool.execute.before": async (input: any, output: any) => {
      const tool = input.tool
      const args = output.args ?? {}
      if (tool === "edit" || tool === "write") {
        const fp = String(args.filePath ?? "")
        if (fp === "LICENSE") {
          throw new Error("[guardhooks] editing LICENSE is forbidden")
        }
        const text = String(args.newString ?? args.content ?? "")
        if (DOC_FILE_RE.test(fp) && EMOJI_RE.test(text)) {
          throw new Error("[guardhooks] emojis are forbidden in documentation files (*.md, *.qmd)")
        }
      }
      if (tool === "bash") {
        const cmd = String(args.command ?? "")
        for (const rule of FORBIDDEN_BASH) {
          if (rule.re.test(cmd)) throw new Error(`[guardhooks] command blocked: ${rule.why}`)
        }
      }
    },

    "tool.execute.after": async (input: any) => {
      if (input.tool === "edit" || input.tool === "write") {
        const fp = String(input.args?.filePath ?? input.output?.args?.filePath ?? "")
        if (fp) noteChange(fp)
      }
    },

    event: async ({ event }: any) => {
      if (event.type === "file.edited") {
        const p = event.filePath ?? event.path ?? event.data?.path
        if (typeof p === "string") noteChange(p)
      }
      if (event.type === "session.idle" && changed.size > 0 && !running) {
        await run()
      }
    },
  }
}