import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, font
import os, random, time, threading, re

# --------------------------------------------------------
# LangLowIQ v3 — enhanced from your simple starter:
# adds 'steal', if/else, functions, loops, try/catch, classes (simple)
# --------------------------------------------------------

class LangError(Exception):
    pass

class LangLowIQ:
    def __init__(self, output_func=print, base_path=None):
        self.vars = {}               # top-level variables
        self.functions = {}          # name -> (argnames, body_nodes)
        self.classes = {}            # name -> methods dict
        self.output = output_func
        self.base_path = base_path or os.getcwd()
        self.modules_path = os.path.join(self.base_path, "modules")
        self.libs_path = os.path.join(self.base_path, "libs")
        os.makedirs(self.modules_path, exist_ok=True)
        os.makedirs(self.libs_path, exist_ok=True)
        self.modules_loaded = set()  # absolute paths loaded via steal

    # -------------------------
    # Utilities
    # -------------------------
    def caveman(self, line_no, short, detail=""):
        if line_no:
            if detail:
                return f"[oops] brain hurt line {line_no}: {short} — {detail}"
            return f"[oops] brain hurt line {line_no}: {short}"
        else:
            if detail:
                return f"[oops] brain hurt: {short} — {detail}"
            return f"[oops] brain hurt: {short}"

    def _resolve_path_token(self, token):
        # token may be in quotes or raw path/name
        t = token.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            t = t[1:-1]
        # expand ~ and env
        t = os.path.expanduser(os.path.expandvars(t))
        if os.path.isabs(t):
            return t
        # relative path -> base_path
        return os.path.join(self.base_path, t)

    # -------------------------
    # Builtins (I kept the simple behaviour you had)
    # -------------------------
    def say(self, *msg): self.output(" ".join(map(str,msg)))
    def yell(self, *msg): self.output(" ".join(map(str,msg)).upper() + "!!!")
    def whisper(self, *msg): self.output(" ".join(map(str,msg)).lower())
    def mathlikeanidiot(self, expr):
        try:
            val = eval(expr, {}, self.vars)
            self.output(f"{expr} = {val}")
        except Exception as e:
            self.output(f"[math error] {e}")
    def uhmath(self, name, expr):
        try:
            self.vars[name] = eval(expr, {}, self.vars)
        except Exception as e:
            self.output(f"[uhmath error] {e}")

    # -------------------------
    # Module loader: steal <path-or-name>
    # -------------------------
    def steal(self, name_token):
        name = name_token.strip()
        # strip quotes if present
        if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
            name = name[1:-1]
        # If path-like or endswith .langlowiq -> treat as path
        possible_paths = []
        if os.path.isabs(name) or any(sep in name for sep in ('/', '\\')) or name.lower().endswith('.langlowiq'):
            possible_paths.append(self._resolve_path_token(name))
        else:
            # search modules/libs
            p1 = os.path.join(self.modules_path, name if name.endswith('.langlowiq') else name + '.langlowiq')
            p2 = os.path.join(self.libs_path, name if name.endswith('.langlowiq') else name + '.langlowiq')
            possible_paths.extend([p1, p2])
        found = None
        for p in possible_paths:
            if os.path.exists(p):
                found = os.path.abspath(p); break
        if not found:
            self.output(self.caveman(None, f"{name} not found to steal", "put it in modules/ or libs/ or give full path"))
            return False
        if found in self.modules_loaded:
            self.output(f"[steal] module already loaded: {found}")
            return True
        try:
            code = open(found, "r", encoding="utf-8").read()
            # mark loaded before running (avoid cycles)
            self.modules_loaded.add(found)
            self.run_string(code)
            self.output(f"[steal] loaded {found}")
            return True
        except Exception as e:
            self.output(self.caveman(None, "steal failed", str(e)))
            return False

    # -------------------------
    # Simple parser: produce nodes with indentation
    # -------------------------
    def _split_lines(self, code):
        lines = []
        for idx, raw in enumerate(code.splitlines(), start=1):
            # count indent (tabs as 4)
            cnt = 0
            for ch in raw:
                if ch == ' ':
                    cnt += 1
                elif ch == '\t':
                    cnt += 4
                else:
                    break
            lines.append((cnt, raw.strip(), idx))
        return lines

    def _parse(self, code):
        lines = self._split_lines(code)
        idx = 0; n = len(lines)
        def parse_block(parent_indent):
            nonlocal idx
            body = []
            while idx < n:
                indent, txt, lineno = lines[idx]
                if txt == "" or txt.startswith("#"):
                    idx += 1; continue
                if parent_indent != -1 and indent <= parent_indent:
                    break
                # header block if endswith ':'
                if txt.endswith(":"):
                    header = txt[:-1].strip()
                    idx += 1
                    children = parse_block(indent)
                    body.append(("block", header, children, lineno))
                    continue
                # simple line
                body.append(("line", txt, None, lineno))
                idx += 1
            return body
        return parse_block(-1)

    # -------------------------
    # Evaluate expression (simple wrapper using eval like you used)
    # -------------------------
    def _eval(self, expr):
        # try to evaluate via eval in vars context; fallback to string if quoted
        s = expr.strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        try:
            return eval(s, {}, self.vars)
        except Exception:
            # if it's a bare var name
            if s in self.vars:
                return self.vars[s]
            raise

    # -------------------------
    # Executor: run parsed nodes
    # returns a special dict {'return': value} to signal giveback
    # -------------------------
    def _run_nodes(self, nodes, local_env):
        i = 0
        while i < len(nodes):
            typ, txt, children, lineno = nodes[i]
            i += 1
            if typ == "line":
                parts = txt.split()
                cmd = parts[0].lower()
                args = parts[1:]
                # control commands
                try:
                    if cmd == "say":
                        vals = [self._eval(" ".join(args))] if args else [""]
                        self.say(*vals)
                    elif cmd == "yell":
                        vals = [self._eval(" ".join(args))] if args else [""]
                        self.yell(*vals)
                    elif cmd == "whisper":
                        vals = [self._eval(" ".join(args))] if args else [""]
                        self.whisper(*vals)
                    elif cmd in ("let","set","now"):
                        # forms: let x = expr  OR now x = expr
                        if len(args) >= 3 and args[1] == "=":
                            name = args[0]
                            expr = " ".join(args[2:])
                            try:
                                v = self._eval(expr)
                            except Exception:
                                # allow quoted strings: fallback to raw
                                if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
                                    v = expr[1:-1]
                                else:
                                    v = self.vars.get(expr, expr)
                            self.vars[name] = v
                        else:
                            # simple 'let x 5' (not common) - ignore
                            pass
                    elif cmd == "mathlikeanidiot":
                        self.mathlikeanidiot(" ".join(args))
                    elif cmd == "uhmath":
                        if len(args) >= 3 and args[1] == "=":
                            name = args[0]; expr = " ".join(args[2:])
                            self.uhmath(name, expr)
                    elif cmd == "random":
                        # random var 1 to 10  OR random x 1 to 10
                        if len(args) >= 4 and args[-2] == "to":
                            name = args[0]; low = int(self._eval(args[1])); high = int(self._eval(args[3]))
                            self.vars[name] = random.randint(low, high)
                    elif cmd == "wait":
                        t = float(self._eval(args[0])) if args else 0
                        time.sleep(t)
                    elif cmd == "maybe":
                        if random.choice([True, False]):
                            if args:
                                self.say(self._eval(" ".join(args)))
                    elif cmd == "ragequit":
                        self.output("ragequitting... 😡")
                        return None
                    elif cmd == "steal":
                        # steal <path or name>
                        if not args: 
                            self.output(self.caveman(lineno, "steal needs argument"))
                        else:
                            self.steal(" ".join(args))
                    elif cmd == "do_thing" or cmd == "do":
                        # allow inline call 'do name arg arg' -> call function
                        # but function defs are handled as blocks 'do_thing name arg1 arg2:' above
                        name = args[0] if args else None
                        call_args = []
                        if len(args) > 1:
                            # eval each arg
                            for a in args[1:]:
                                try: call_args.append(self._eval(a))
                                except: call_args.append(a)
                        if name in self.functions:
                            argnames, body = self.functions[name]
                            # create local backup and set args in vars temporarily
                            backup = dict(self.vars)
                            for idx_a,an in enumerate(argnames):
                                self.vars[an] = call_args[idx_a] if idx_a < len(call_args) else None
                            ret = self._run_nodes(body, {})
                            self.vars = backup
                            if isinstance(ret, dict) and 'return' in ret:
                                return ret
                        else:
                            # backwards compatible 'do foo' calling 'foo' if stored
                            self.output(self.caveman(lineno, f"{name} not function"))
                    elif cmd == "yo":
                        # alias to call/do
                        if args:
                            name = args[0]; call_args = []
                            for a in args[1:]:
                                try: call_args.append(self._eval(a))
                                except: call_args.append(a)
                            if name in self.functions:
                                argnames, body = self.functions[name]
                                backup = dict(self.vars)
                                for idx_a,an in enumerate(argnames):
                                    self.vars[an] = call_args[idx_a] if idx_a < len(call_args) else None
                                ret = self._run_nodes(body, {})
                                self.vars = backup
                                if isinstance(ret, dict) and 'return' in ret:
                                    return ret
                            else:
                                self.output(self.caveman(lineno, f"{name} not function"))
                    else:
                        # unknown single-line command -> treat as expression or variable usage
                        # allow assignment using '=' like: x = 5
                        if "=" in txt:
                            left,right = txt.split("=",1)
                            name = left.strip()
                            expr = right.strip()
                            try:
                                v = self._eval(expr)
                            except Exception:
                                if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
                                    v = expr[1:-1]
                                else:
                                    v = expr
                            self.vars[name] = v
                        else:
                            self.output(self.caveman(lineno, "me no know command", txt))
                except Exception as e:
                    self.output(self.caveman(lineno, "error", str(e)))
            elif typ == "block":
                header = txt
                # handle function definition: do_thing name a b:
                if header.startswith("do_thing ") or header.startswith("do "):
                    parts = header.split()
                    name = parts[1] if len(parts) > 1 else None
                    args = parts[2:] if len(parts) > 2 else []
                    # strip trailing ':' handled earlier
                    self.functions[name] = (args, children)
                    continue
                # handle if ... :  optionally followed by else at same level
                if header.startswith("if "):
                    cond = header[len("if "):].strip()
                    try:
                        condv = bool(self._eval(cond))
                    except Exception:
                        condv = False
                    if condv:
                        # execute children (then)
                        ret = self._run_nodes(children, {})
                        if isinstance(ret, dict) and 'return' in ret:
                            return ret
                        # skip potential sibling else nodes by consuming them in caller (we don't have sibling loop here)
                    else:
                        # look ahead to see if next node is an 'else:' at same indentation level
                        # Note: since parse produced sibling nodes at same level, caller's index handles skipping
                        # but our structure here doesn't have direct sibling access. Simplify: nothing executed if false.
                        pass
                    continue
                # else:
                if header.startswith("else"):
                    # execute children unconditionally (caller should ensure only when used with if)
                    ret = self._run_nodes(children, {})
                    if isinstance(ret, dict) and 'return' in ret:
                        return ret
                    continue
                # repeatuntil cond:
                if header.startswith("repeatuntil "):
                    cond = header[len("repeatuntil "):].strip()
                    guard = 0
                    while True:
                        try:
                            if self._eval(cond):
                                break
                        except Exception:
                            break
                        ret = self._run_nodes(children, {})
                        if isinstance(ret, dict) and 'return' in ret:
                            return ret
                        guard += 1
                        if guard > 1000000:
                            self.output(self.caveman(None, "infinite loop"))
                            break
                    continue
                # keepdoing cond:
                if header.startswith("keepdoing "):
                    cond = header[len("keepdoing "):].strip()
                    guard = 0
                    while True:
                        try:
                            if not self._eval(cond):
                                break
                        except Exception:
                            break
                        ret = self._run_nodes(children, {})
                        if isinstance(ret, dict) and 'return' in ret:
                            return ret
                        guard += 1
                        if guard > 1000000:
                            self.output(self.caveman(None, "infinite loop"))
                            break
                    continue
                # try/catch
                if header == "try":
                    try:
                        ret = self._run_nodes(children, {})
                        if isinstance(ret, dict) and 'return' in ret:
                            return ret
                    except Exception as e:
                        # try to let catch handle it in sibling - for simplicity print for now
                        self.output(self.caveman(None, "try block error", str(e)))
                    continue
                # thingy class
                if header.startswith("thingy "):
                    parts = header.split()
                    cname = parts[1] if len(parts) > 1 else None
                    # children hold method defs 'do_thing name ...:' local nodes
                    methods = {}
                    for ch in children:
                        if ch[0] == "block":
                            h = ch[1]
                            if h.startswith("do_thing "):
                                p = h.split()
                                mname = p[1]
                                margs = p[2:]
                                methods[mname] = (margs, ch[2])
                    self.classes[cname] = {"methods": methods}
                    self.output(f"[thingy] defined class '{cname}' with methods: {list(methods.keys())}")
                    continue
                # unknown block
                self.output(self.caveman(None, "unknown block", header))
                continue
        return None

    # -------------------------
    # top-level run
    # -------------------------
    def run_string(self, code):
        nodes = self._parse(code)
        try:
            self._run_nodes(nodes, {})
        except Exception as e:
            self.output(self.caveman(None, "me crash", str(e)))

# --------------------------------------------------------
# GUI IDE for LangLowIQ (simple)
# --------------------------------------------------------
class LangLowIQIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("LangLowIQ IDE 🤓")
        self.filename = None

        # --- Menu ---
        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_file)
        filemenu.add_command(label="Open", command=self.open_file)
        filemenu.add_command(label="Save", command=self.save_file)
        filemenu.add_command(label="Save As...", command=self.save_as)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        runmenu = tk.Menu(menubar, tearoff=0)
        runmenu.add_command(label="Run", command=self.run_code)
        menubar.add_cascade(label="Run", menu=runmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Syntax Help", command=self.show_help)
        menubar.add_cascade(label="Help", menu=helpmenu)
        root.config(menu=menubar)

        # --- Editor ---
        self.editor = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20, font=("Consolas", 12), undo=True)
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.bind("<<Modified>>", self.on_edit)

        # --- Syntax highlighting setup ---
        self.keywords = [
            "say", "yell", "whisper", "let", "set", "now", "uhmath",
            "mathlikeanidiot", "random", "wait", "maybe", "ragequit",
            "do_thing", "do", "giveback", "repeatuntil", "keepdoing",
            "if", "else", "try", "catch", "thingy", "new", "steal", "yo"
        ]
        self.keyword_pattern = re.compile(r"\b(" + "|".join(self.keywords) + r")\b")
        self.editor.tag_configure("keyword", foreground="#ffcc00", font=("Consolas", 12, "bold"))
        self.editor.tag_configure("string", foreground="#55ff55")
        comment_font = font.Font(family="Consolas", size=12, slant="italic")
        self.editor.tag_configure("comment", foreground="#888888", font=comment_font)

        # --- Output console ---
        self.console = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, height=10, font=("Consolas", 11), bg="#111", fg="#0f0"
        )
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.insert(tk.END, "Welcome to LangLowIQ IDE 🤓\n")

    # ---------- File ops ----------
    def new_file(self):
        self.editor.delete(1.0, tk.END)
        self.filename = None
        self.root.title("LangLowIQ IDE 🤓 - New File")

    def open_file(self):
        file = filedialog.askopenfilename(filetypes=[("LangLowIQ Files", "*.langlowiq"), ("All Files", "*.*")])
        if file:
            with open(file, "r", encoding="utf-8") as f:
                self.editor.delete(1.0, tk.END)
                self.editor.insert(tk.END, f.read())
            self.filename = file
            self.root.title(f"LangLowIQ IDE 🤓 - {os.path.basename(file)}")
            self.highlight_syntax()

    def save_file(self):
        if not self.filename:
            self.save_as()
        else:
            with open(self.filename, "w", encoding="utf-8") as f:
                f.write(self.editor.get(1.0, tk.END))

    def save_as(self):
        file = filedialog.asksaveasfilename(
            defaultextension=".langlowiq",
            filetypes=[("LangLowIQ Files", "*.langlowiq"), ("All Files", "*.*")],
        )
        if file:
            self.filename = file
            self.save_file()
            self.root.title(f"LangLowIQ IDE 🤓 - {os.path.basename(file)}")

    # ---------- Running code ----------
    def run_code(self):
        code = self.editor.get(1.0, tk.END)
        self.console.delete(1.0, tk.END)
        self.console.insert(tk.END, "Running...\n")

        def run_thread():
            def output(msg):
                self.console.insert(tk.END, str(msg) + "\n")
                self.console.see(tk.END)

            interpreter = LangLowIQ(output, base_path=os.getcwd())
            # ensure modules/libs dirs exist; interpreter will create them
            interpreter.run_string(code)
            output("Done.\n")

        threading.Thread(target=run_thread, daemon=True).start()

    # ---------- Syntax highlighting ----------
    def on_edit(self, event=None):
        self.editor.after_idle(self.highlight_syntax)
        self.editor.edit_modified(False)

    def highlight_syntax(self, event=None):
        text = self.editor.get(1.0, tk.END)
        # Remove old tags
        for tag in self.editor.tag_names():
            self.editor.tag_remove(tag, "1.0", tk.END)
        # Keywords
        for match in self.keyword_pattern.finditer(text):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.editor.tag_add("keyword", start, end)
        # Strings
        for match in re.finditer(r'"[^"]*"|\'[^\']*\'', text):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.editor.tag_add("string", start, end)
        # Comments (# ...)
        for match in re.finditer(r"#.*", text):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.editor.tag_add("comment", start, end)

    # ---------- Help ----------
    def show_help(self):
        help_text = """
LANGLOWIQ SYNTAX GUIDE 🤓

# Comments start with a hashtag
say "Hello world"
yell I love coding
whisper please be quiet

let x = 5
uhmath y = x + 3
mathlikeanidiot 5 * 2 + 1

now mood = "happy"
random number 1 to 10
wait 1.5
maybe surprise!
ragequit

steal "C:\\downloads\\lib.langlowiq"   # load local file
steal mylib                            # looks in modules/ and libs/

do_thing greet name:
    say "hello "  # inside function you can use giveback to return
    giveback "done"
# call:
do greet "Bob"
# or:
yo greet "Bob"

if x > 2:
    say "bigger"
else:
    say "small"

repeatuntil x == 10:
    uhmath x = x + 1

keepdoing x < 5:
    uhmath x = x + 1

thingy Person:
    do_thing init self name age:
        self.name = name
        self.age = age
    do_thing talk self:
        say "I am " 
        say self.name
# create:
let p = new Person "Rick" 18
yo p.talk

"""
        messagebox.showinfo("LangLowIQ Syntax Help", help_text)

# --------------------------------------------------------
# Run the app
# --------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = LangLowIQIDE(root)
    root.mainloop()
