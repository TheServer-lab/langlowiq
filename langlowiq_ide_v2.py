# langlowiq_v2.py
# LangLowIQ v2 - Goofy on the outside, powerful on the inside.
# Run: python langlowiq_v2.py

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, font
import os, re, time, random, threading, urllib.request, zipfile, io, sys, traceback

# -------------------------
# Caveman-style error helper
# -------------------------
def caveman_error(line_no, short, detail=""):
    if detail:
        return f"[oops] brain hurt line {line_no}: {short} — {detail}"
    else:
        return f"[oops] brain hurt line {line_no}: {short}"

# -------------------------
# Exceptions
# -------------------------
class OopsException(Exception):
    def __init__(self, msg, line_no=None):
        self.msg = msg
        self.line_no = line_no
    def __str__(self):
        if self.line_no:
            return caveman_error(self.line_no, self.msg)
        return f"[oops] {self.msg}"

# -------------------------
# Interpreter Core
# -------------------------
class LangLowIQ:
    def __init__(self, output_func=print, base_path=None):
        self.output = output_func
        self.base_path = base_path or os.getcwd()
        self.libs_path = os.path.join(self.base_path, "libs")
        self.modules_path = os.path.join(self.base_path, "modules")
        os.makedirs(self.libs_path, exist_ok=True)
        os.makedirs(self.modules_path, exist_ok=True)

        # Global environment (top-level variables)
        self.globals = {}
        # Functions: name -> (argnames, node_children)
        self.functions = {}
        # Classes: name -> {methods: {name: (argnames, body)}}
        self.classes = {}

        # Module cache
        self.module_cache = {}

        # Eval helpers (available to safe eval)
        self.eval_helpers = {
            "smash": lambda a,b="": str(a)+str(b),
            "slice_": lambda s,a,b=None: str(s)[int(a): (None if b is None else int(b))],
            "uppercase": lambda s: str(s).upper(),
            "lowercase": lambda s: str(s).lower(),
            "randint": lambda a,b: random.randint(int(a), int(b)),
            "choice": lambda *a: random.choice(list(a)),
        }

        # Create built-in libs if missing
        self._ensure_builtin_libs()

    # -------------------------
    # Utility: interpolate $vars inside strings
    # -------------------------
    def interp_string(self, s, env):
        # Replace occurrences of $name with its value from env or globals
        def repl(m):
            name = m.group(1)
            val = env.get(name, self.globals.get(name, ""))
            return str(val)
        return re.sub(r'\$([A-Za-z_]\w*)', repl, s)

    # -------------------------
    # Path resolver for file IO
    # -------------------------
    def _resolve_path(self, token):
        tok = token.strip()
        if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
            tok = tok[1:-1]
        if os.path.isabs(tok):
            return tok
        return os.path.join(self.base_path, tok)

    # -------------------------
    # Builtin libs creation
    # -------------------------
    def _ensure_builtin_libs(self):
        # small dumb libs as requested
        dumbmath = os.path.join(self.libs_path, "dumbmath.langlowiq")
        if not os.path.exists(dumbmath):
            open(dumbmath, "w", encoding="utf-8").write("""# dumbmath
do_thing dumbadd a b:
    giveback a + b
do_thing dumbsub a b:
    giveback a - b
do_thing dumbmul a b:
    giveback a * b
do_thing dumbdiv a b:
    giveback a / b
""")
        stringstuff = os.path.join(self.libs_path, "stringstuff.langlowiq")
        if not os.path.exists(stringstuff):
            open(stringstuff, "w", encoding="utf-8").write("""# stringstuff
do_thing smash a b:
    giveback smash a b
do_thing uppercase s:
    giveback uppercase s
do_thing lowercase s:
    giveback lowercase s
do_thing slice s a b:
    giveback slice s a b
""")
        filestuff = os.path.join(self.libs_path, "filestuff.langlowiq")
        if not os.path.exists(filestuff):
            open(filestuff, "w", encoding="utf-8").write("""# filestuff
do_thing scribblef filename content:
    scribble filename with content
do_thing fetchf filename var:
    fetch filename into var
""")
        randomstuff = os.path.join(self.libs_path, "randomstuff.langlowiq")
        if not os.path.exists(randomstuff):
            open(randomstuff, "w", encoding="utf-8").write("""# randomstuff
do_thing randit a b:
    giveback randint a b
do_thing pickone a b c:
    giveback choice a b c
""")

    # -------------------------
    # Package manager: naive pull
    # -------------------------
    def stealfrominternet(self, url_or_name):
        # accepts: direct URL or just name -> tries example.com/langlibs/<name>
        targets = []
        if url_or_name.startswith("http://") or url_or_name.startswith("https://"):
            targets.append(url_or_name)
        else:
            targets.append(f"https://example.com/langlibs/{url_or_name}.langlowiq")
            targets.append(f"https://example.com/langlibs/{url_or_name}.zip")
        for t in targets:
            try:
                self.output(f"[stealfrominternet] trying {t}")
                data = urllib.request.urlopen(t, timeout=6).read()
                if t.endswith(".zip"):
                    z = zipfile.ZipFile(io.BytesIO(data))
                    z.extractall(self.libs_path)
                    self.output(f"[stealfrominternet] unpacked zip to libs/")
                    return True
                else:
                    with open(os.path.join(self.libs_path, os.path.basename(t)), "wb") as f:
                        f.write(data)
                    self.output(f"[stealfrominternet] saved to libs/")
                    return True
            except Exception as e:
                continue
        self.output(f"[stealfrominternet] no luck, put lib in libs/ manually")
        return False

    # -------------------------
    # Module loader: steal
    # -------------------------
    def steal(self, name):
        name = name.strip().strip('"').strip("'")
        # try modules first
        local_path = os.path.join(self.modules_path, name)
        if not local_path.endswith(".langlowiq"):
            local_path += ".langlowiq"
        if not os.path.exists(local_path):
            # try libs
            local_path = os.path.join(self.libs_path, name)
            if not local_path.endswith(".langlowiq"):
                local_path += ".langlowiq"
        if not os.path.exists(local_path):
            self.output(caveman_error(0, f"{name} not found to steal", "put it in modules/ or libs/"))
            return False
        if name in self.module_cache:
            return True
        try:
            code = open(local_path, "r", encoding="utf-8").read()
            self.module_cache[name] = True
            self.run_string(code)
            return True
        except Exception as e:
            self.output(caveman_error(0, f"failed steal {name}", str(e)))
            return False

    # -------------------------
    # File IO: scribble, scribblemore, fetch
    # -------------------------
    def scribble(self, filename_token, content_token, env):
        path = self._resolve_path(filename_token)
        content = content_token
        if isinstance(content_token, str):
            if (content_token.startswith('"') and content_token.endswith('"')) or (content_token.startswith("'") and content_token.endswith("'")):
                content = self.interp_string(content_token[1:-1], env)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(content))
            self.output(f"[scribble] wrote {path}")
        except Exception as e:
            self.output(caveman_error(0, "scribble fail", str(e)))

    def scribblemore(self, filename_token, content_token, env):
        path = self._resolve_path(filename_token)
        content = content_token
        if isinstance(content_token, str):
            if (content_token.startswith('"') and content_token.endswith('"')) or (content_token.startswith("'") and content_token.endswith("'")):
                content = self.interp_string(content_token[1:-1], env)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(str(content))
            self.output(f"[scribblemore] appended {path}")
        except Exception as e:
            self.output(caveman_error(0, "scribblemore fail", str(e)))

    def fetch(self, filename_token, into_var, env):
        path = self._resolve_path(filename_token)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            env[into_var] = data
            self.output(f"[fetch] {path} -> {into_var}")
        except Exception as e:
            env[into_var] = ""
            self.output(caveman_error(0, "fetch fail", str(e)))

    # -------------------------
    # Expression evaluator (best-effort safe-ish)
    # -------------------------
    def _safe_eval(self, expr, env):
        # Convert low-IQ names to eval-callable forms:
        # smash "a" "b" -> smash("a","b") ; slice x 1 4 -> slice_(x,1,4)
        e = expr.strip()

        # Replace $var inside expression tokens with env lookup placeholder: keep as identifier, we will supply locals
        token_pattern = re.compile(r'\b(smash|slice|uppercase|lowercase|randint|choice)\b\s+(".*?"|\'.*?\'|\w+)(?:\s+(".*?"|\'.*?\'|\w+))?')

        def repl(m):
            fn = m.group(1)
            a = m.group(2)
            b = m.group(3)
            if b is None:
                if fn == "slice":
                    return f"slice_({a})"
                return f"{fn}({a})"
            else:
                if fn == "slice":
                    return f"slice_({a},{b})"
                return f"{fn}({a},{b})"
        e2 = token_pattern.sub(repl, e)

        # Build locals map: helpers + env + globals
        locals_map = {}
        locals_map.update(self.eval_helpers)
        # Add env & globals (names that are valid identifiers)
        for k, v in {**self.globals, **env}.items():
            if isinstance(k, str) and re.match(r'^[A-Za-z_]\w*$', k):
                locals_map[k] = v

        try:
            return eval(e2, {}, locals_map)
        except Exception as ex:
            raise OopsException(f"can't eval `{expr}`", None)

    # -------------------------
    # Parser: lines -> nodes using indentation
    # Node: {'line':str, 'indent':int, 'children':[]}
    # -------------------------
    def _count_indent(self, raw):
        count = 0
        for ch in raw:
            if ch == ' ':
                count += 1
            elif ch == '\t':
                count += 4
            else:
                break
        return count

    def _parse(self, code):
        lines = code.splitlines()
        raw_lines = []
        for ln in lines:
            raw_lines.append((ln.rstrip("\n\r"), self._count_indent(ln)))
        # recursive builder
        def build(start_idx, parent_indent):
            nodes = []
            i = start_idx
            while i < len(raw_lines):
                raw, indent = raw_lines[i]
                stripped = raw.strip()
                if stripped == "":
                    i += 1
                    continue
                if parent_indent != -1 and indent <= parent_indent:
                    break
                node = {'line': stripped, 'indent': indent, 'children': []}
                i += 1
                # collect children if header (ends with ':')
                if stripped.endswith(":"):
                    child_nodes, newi = build(i, indent)
                    node['children'] = child_nodes
                    i = newi
                nodes.append(node)
            return nodes, i
        nodes, _ = build(0, -1)
        return nodes

    # -------------------------
    # Executor: run nodes with environment env (dict)
    # -------------------------
    def _run_nodes(self, nodes, env, top_level=False):
        i = 0
        n = len(nodes)
        while i < n:
            node = nodes[i]
            i += 1
            line = node['line']
            children = node.get('children', [])
            # skip comments
            if not line or line.startswith("#"):
                continue

            # oops block: throw
            if line.startswith("oops"):
                # syntax: oops or oops "message"
                rest = line[len("oops"):].strip()
                if rest:
                    msg = rest.strip()
                    if (msg.startswith('"') and msg.endswith('"')) or (msg.startswith("'") and msg.endswith("'")):
                        msg = self.interp_string(msg[1:-1], env)
                    raise OopsException(msg, self._get_line_no(node))
                else:
                    # if oops used as header with children: execute children and throw; or if alone - raise general
                    if children:
                        try:
                            self._run_nodes(children, env)
                            raise OopsException("oop happened", self._get_line_no(node))
                        except OopsException as oe:
                            raise oe
                    else:
                        raise OopsException("oop happened", self._get_line_no(node))

            # try/catch: 'try:' with sibling 'catch <var>:'
            if line == "try:":
                # find catch sibling if present (next node at same level)
                catch_node = None
                if i < n and nodes[i]['line'].startswith("catch "):
                    catch_node = nodes[i]
                    i += 1
                try:
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                except OopsException as oe:
                    if catch_node:
                        m = re.match(r'catch\s+(\w+)\s*:', catch_node['line'])
                        if m:
                            varname = m.group(1)
                            env[varname] = str(oe)
                            self._run_nodes(catch_node.get('children', []), env)
                            continue
                    raise

            # conditionals: maybeif / ormaybe / otherwise (top-level chain)
            if line.startswith("maybeif "):
                cond = line[len("maybeif "):].strip()
                if cond.endswith(":"):
                    cond = cond[:-1]
                condv = False
                try:
                    condv = bool(self._safe_eval(cond, env))
                except OopsException:
                    condv = False
                if condv:
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                    # skip following ormaybe/otherwise siblings
                    while i < n and nodes[i]['line'].startswith("ormaybe"):
                        # consume and ignore
                        i += 1
                        # skip their children too (already parsed)
                    if i < n and nodes[i]['line'].startswith("otherwise"):
                        i += 1
                        # skip its children
                    continue
                else:
                    # not true -> evaluate ormaybe(s) and otherwise by falling through
                    continue

            if line.startswith("ormaybe "):
                cond = line[len("ormaybe "):].strip()
                if cond.endswith(":"):
                    cond = cond[:-1]
                condv = False
                try:
                    condv = bool(self._safe_eval(cond, env))
                except OopsException:
                    condv = False
                if condv:
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                continue

            if line.startswith("otherwise"):
                rv = self._run_nodes(children, env)
                if rv is not None:
                    return rv
                continue

            # repeatuntil cond:
            if line.startswith("repeatuntil "):
                cond = line[len("repeatuntil "):].strip()
                if cond.endswith(":"):
                    cond = cond[:-1]
                loop_guard = 0
                while True:
                    try:
                        condv = bool(self._safe_eval(cond, env))
                    except OopsException:
                        condv = False
                    if condv:
                        break
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                    loop_guard += 1
                    if loop_guard > 1000000:
                        raise OopsException("infinite loop detected", self._get_line_no(node))
                continue

            # alias: keepdoing cond:
            if line.startswith("keepdoing "):
                # same as repeatuntil but inverted style
                cond = line[len("keepdoing "):].strip()
                if cond.endswith(":"):
                    cond = cond[:-1]
                loop_guard = 0
                while True:
                    try:
                        condv = bool(self._safe_eval(cond, env))
                    except OopsException:
                        condv = False
                    if not condv:
                        break
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                    loop_guard += 1
                    if loop_guard > 1000000:
                        raise OopsException("infinite loop detected", self._get_line_no(node))
                continue

            # loopforever:
            if line.startswith("loopforever"):
                loop_guard = 0
                while True:
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                    loop_guard += 1
                    if loop_guard > 1000000:
                        raise OopsException("infinite loop detected", self._get_line_no(node))
                # never reaches

            # dosomany var in <start> to <end>:
            if line.startswith("dosomany "):
                m = re.match(r'dosomany\s+(\w+)\s+in\s+(.+?)\s+to\s+(.+?):?$', line)
                if not m:
                    continue
                var = m.group(1)
                start_expr = m.group(2)
                end_expr = m.group(3)
                try:
                    startv = int(self._safe_eval(start_expr, env))
                    endv = int(self._safe_eval(end_expr, env))
                except OopsException:
                    startv, endv = 0, -1
                for v in range(startv, endv+1):
                    env[var] = v
                    rv = self._run_nodes(children, env)
                    if rv is not None:
                        return rv
                continue

            # do_thing function definition
            if line.startswith("do_thing "):
                head = line[len("do_thing "):].strip()
                if head.endswith(":"):
                    head = head[:-1]
                parts = head.split()
                fname = parts[0]
                fargs = parts[1:]
                self.functions[fname] = (fargs, children)
                continue

            # thingy class definition
            if line.startswith("thingy "):
                cname = line[len("thingy "):].strip()
                if cname.endswith(":"):
                    cname = cname[:-1]
                # children contain do_thing definitions for methods
                methods = {}
                for child in children:
                    if child['line'].startswith("do_thing "):
                        mh = child['line'][len("do_thing "):].strip()
                        if mh.endswith(":"):
                            mh = mh[:-1]
                        parts = mh.split()
                        mname = parts[0]
                        margs = parts[1:]
                        methods[mname] = (margs, child.get('children', []))
                self.classes[cname] = {"methods": methods}
                self.output(f"[thingy] defined class '{cname}' with methods: {list(methods.keys())}")
                continue

            # do_thing inside class handled above; skip catch
            if line.startswith("catch "):
                continue

            # Simple commands and assignments:
            tokens = line.split()
            cmd = tokens[0]

            # let/set/now with '=' (support new ...)
            if cmd in ("let", "set", "now"):
                if len(tokens) >= 4 and tokens[2] == "=":
                    lhs = tokens[1]
                    rhs = line.split("=",1)[1].strip()
                    # new instantiation
                    if rhs.startswith("new "):
                        parts = rhs.split()
                        cname = parts[1]
                        args_tokens = parts[2:]
                        args_vals = []
                        for tok in args_tokens:
                            try:
                                v = self._safe_eval(tok, env)
                            except OopsException:
                                if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
                                    v = self.interp_string(tok[1:-1], env)
                                else:
                                    v = env.get(tok, self.globals.get(tok, None))
                            args_vals.append(v)
                        inst = self._instantiate(cname, args_vals)
                        self._assign(lhs, inst, env)
                    else:
                        try:
                            val = self._safe_eval(rhs, env)
                        except OopsException:
                            tok = rhs.strip()
                            if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
                                val = self.interp_string(tok[1:-1], env)
                            else:
                                val = env.get(tok, self.globals.get(tok, tok))
                        self._assign(lhs, val, env)
                continue

            # giveback (return) - if executed inside function body we return value
            if cmd == "giveback":
                expr = line[len("giveback"):].strip()
                try:
                    val = self._safe_eval(expr, env)
                except OopsException:
                    tok = expr.strip()
                    if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
                        val = self.interp_string(tok[1:-1], env)
                    else:
                        val = env.get(tok, self.globals.get(tok, None))
                return val

            # uhmath name = expr (assign evaluated result)
            if cmd == "uhmath" and len(tokens) >= 4 and tokens[2] == "=":
                name = tokens[1]
                expr = line.split("=",1)[1].strip()
                try:
                    val = self._safe_eval(expr, env)
                except OopsException:
                    tok = expr.strip()
                    if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
                        val = self.interp_string(tok[1:-1], env)
                    else:
                        val = env.get(tok, self.globals.get(tok, None))
                self._assign(name, val, env)
                continue

            # mathlikeanidiot <expr>
            if cmd == "mathlikeanidiot":
                expr = line[len("mathlikeanidiot"):].strip()
                try:
                    val = self._safe_eval(expr, env)
                    self.output(f"{expr} = {val}")
                except OopsException as oe:
                    self.output(str(oe))
                continue

            # random var <low> to <high>
            if cmd == "random":
                # random var 1 to 10
                m = re.match(r'random\s+(\w+)\s+(\d+)\s+to\s+(\d+)', line)
                if m:
                    var = m.group(1)
                    low = int(m.group(2)); high = int(m.group(3))
                    env[var] = random.randint(low, high)
                continue

            # wait <seconds>
            if cmd == "wait":
                try:
                    t = float(tokens[1])
                    time.sleep(t)
                except:
                    pass
                continue

            # maybe (one-off)
            if cmd == "maybe":
                if random.choice([True, False]):
                    parts = [self._resolve_value_token(w, env) for w in tokens[1:]]
                    self._do_say(parts)
                continue

            # yo (call)
            if cmd == "yo":
                if len(tokens) >= 2:
                    fname = tokens[1]
                    arg_tokens = tokens[2:]
                    arg_vals = []
                    for tok in arg_tokens:
                        try:
                            v = self._safe_eval(tok, env)
                        except OopsException:
                            if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
                                v = self.interp_string(tok[1:-1], env)
                            else:
                                v = env.get(tok, self.globals.get(tok, None))
                        arg_vals.append(v)
                    try:
                        self._call(fname, arg_vals, env)
                    except OopsException as oe:
                        raise oe
                continue

            # say / yell / whisper
            if cmd in ("say","sayit"):
                parts = [self._resolve_value_token(w, env) for w in tokens[1:]]
                self._do_say(parts)
                continue
            if cmd == "yell":
                parts = [self._resolve_value_token(w, env) for w in tokens[1:]]
                self.output(" ".join(map(str, parts)).upper() + "!!!")
                continue
            if cmd == "whisper":
                parts = [self._resolve_value_token(w, env) for w in tokens[1:]]
                self.output(" ".join(map(str, parts)).lower())
                continue

            # steal module
            if cmd == "steal":
                if len(tokens) >= 2:
                    mname = tokens[1].strip('"').strip("'")
                    self.steal(mname)
                continue

            # stealfrominternet
            if cmd == "stealfrominternet":
                if len(tokens) >= 2:
                    url = tokens[1].strip('"').strip("'")
                    self.stealfrominternet(url)
                continue

            # scribble / scribblemore / fetch
            if cmd == "scribble":
                m = re.match(r'scribble\s+(".*?"|\'.*?\'|\S+)\s+with\s+(.+)', line)
                if m:
                    fname = m.group(1); content = m.group(2).strip()
                    self.scribble(fname, content, env)
                continue
            if cmd == "scribblemore":
                m = re.match(r'scribblemore\s+(".*?"|\'.*?\'|\S+)\s+with\s+(.+)', line)
                if m:
                    fname = m.group(1); content = m.group(2).strip()
                    self.scribblemore(fname, content, env)
                continue
            if cmd == "fetch":
                m = re.match(r'fetch\s+(".*?"|\'.*?\'|\S+)\s+into\s+(\w+)', line)
                if m:
                    fname = m.group(1); into = m.group(2)
                    self.fetch(fname, into, env)
                continue

            # giveback at top level - ignore or use as return
            if cmd == "giveback":
                expr = line[len("giveback"):].strip()
                try:
                    return self._safe_eval(expr, env)
                except OopsException:
                    return None

            # unknown => caveman message
            self.output(caveman_error(self._get_line_no(node), "me no know command", line))
        return None

    # -------------------------
    # Helpers: instantiate, call, assign, resolve token, etc.
    # -------------------------
    def _instantiate(self, class_name, values):
        if class_name not in self.classes:
            raise OopsException(f"{class_name} no exist", None)
        inst = {"__class__": class_name, "__props__": {}}
        methods = self.classes[class_name]["methods"]
        if "init" in methods:
            argnames, body = methods["init"]
            local_env = dict(self.globals)
            local_env["self"] = inst["__props__"]
            for i, a in enumerate(argnames[1:]):
                local_env[a] = values[i] if i < len(values) else None
            # execute body nodes
            self._run_nodes(body, local_env)
            # copy keys to props except 'self'
            for k,v in local_env.items():
                if k != "self":
                    inst["__props__"][k] = v
        else:
            # create arg0..argN props
            for i,v in enumerate(values):
                inst["__props__"][f"arg{i}"] = v
        return inst

    def _call(self, name, values, env):
        # method call: obj.method
        if "." in name:
            obj_name, method_name = name.split(".",1)
            obj = env.get(obj_name, self.globals.get(obj_name))
            if not (isinstance(obj, dict) and "__class__" in obj):
                raise OopsException(f"{obj_name} not object", None)
            cls = obj["__class__"]
            methods = self.classes.get(cls, {}).get("methods", {})
            if method_name not in methods:
                raise OopsException(f"{method_name} not in {cls}", None)
            argnames, body = methods[method_name]
            local_env = dict(self.globals)
            local_env["self"] = obj["__props__"]
            for i,a in enumerate(argnames[1:]):
                local_env[a] = values[i] if i < len(values) else None
            return self._run_nodes(body, local_env)
        # function call
        if name in self.functions:
            argnames, body = self.functions[name]
            local_env = dict(self.globals)
            for i,a in enumerate(argnames):
                local_env[a] = values[i] if i < len(values) else None
            return self._run_nodes(body, local_env)
        # check built-ins libs: functions implemented via eval_helpers wrappers (stringstuff etc.)
        # allow calling dumb lib functions by name via eval_helpers if present
        if name in self.eval_helpers:
            return self.eval_helpers[name](*values)
        raise OopsException(f"{name} not function", None)

    def _assign(self, lhs, val, env):
        # property assignment: obj.prop
        if "." in lhs:
            obj_name, prop = lhs.split(".",1)
            obj = env.get(obj_name, self.globals.get(obj_name))
            if isinstance(obj, dict) and "__class__" in obj:
                obj["__props__"][prop] = val
            else:
                env[lhs] = val
        else:
            env[lhs] = val

    def _resolve_value_token(self, tok, env):
        # token may be quoted string, literal number, or var name
        tok = tok.strip()
        if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
            return self.interp_string(tok[1:-1], env)
        # try number
        if re.match(r'^[+-]?\d+(\.\d+)?$', tok):
            if '.' in tok:
                return float(tok)
            return int(tok)
        # try eval
        try:
            return self._safe_eval(tok, env)
        except OopsException:
            return env.get(tok, self.globals.get(tok, tok))

    def _do_say(self, parts):
        # join with spaces, strings already interpolated
        self.output(" ".join(map(str, parts)))

    def _get_line_no(self, node):
        # Not tracking exact original line numbers; return 0 for now
        # Could be extended to store original line indexes in parser nodes
        return 0

    # -------------------------
    # Top-level: parse and run a code string
    # -------------------------
    def run_string(self, code):
        nodes = self._parse(code)
        try:
            self._run_nodes(nodes, self.globals, top_level=True)
        except OopsException as oe:
            # caveman-style output
            if oe.line_no:
                self.output(str(oe))
            else:
                # line unknown
                self.output(f"[oops] brain hurt: {oe.msg}")
        except Exception as e:
            # unhandled runtime error
            self.output(f"[oops] me crash: {e}")

# -------------------------
# Simple GUI IDE (tkinter)
# -------------------------
class LangLowIQIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("LangLowIQ IDE v2 🤓💩")
        self.filename = None

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

        # editor
        self.editor = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20, font=("Consolas",12), undo=True)
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.bind("<<Modified>>", self.on_edit)

        # keywords for highlighting
        self.keywords = [
            "do_thing","giveback","uhmath","repeatuntil","loopforever","keepdoing","dosomany",
            "maybeif","ormaybe","otherwise","ifso","elseso","oops","catch","try","steal",
            "stealfrominternet","thingy","new","yo","say","yell","whisper","scribble","scribblemore","fetch",
            "smash","slice","uppercase","lowercase","random","maybe","let","set","now"
        ]
        self.keyword_pattern = re.compile(r"\b(" + "|".join(self.keywords) + r")\b")
        self.editor.tag_configure("keyword", foreground="#ffcc00", font=("Consolas",12,"bold"))
        self.editor.tag_configure("string", foreground="#55ff55")
        comment_font = font.Font(family="Consolas", size=12, slant="italic")
        self.editor.tag_configure("comment", foreground="#888888", font=comment_font)

        # console
        self.console = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=10, font=("Consolas",11), bg="#111", fg="#0f0")
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.insert(tk.END, "Welcome to LangLowIQ v2 IDE 🤓💩\n")

    # file ops
    def new_file(self):
        self.editor.delete(1.0, tk.END)
        self.filename = None

    def open_file(self):
        f = filedialog.askopenfilename(filetypes=[("LangLowIQ Files","*.langlowiq"),("All Files","*.*")])
        if f:
            with open(f,"r",encoding="utf-8") as fh:
                self.editor.delete(1.0, tk.END)
                self.editor.insert(tk.END, fh.read())
            self.filename = f
            self.highlight()

    def save_file(self):
        if not self.filename:
            self.save_as()
        else:
            with open(self.filename,"w",encoding="utf-8") as fh:
                fh.write(self.editor.get(1.0, tk.END))

    def save_as(self):
        f = filedialog.asksaveasfilename(defaultextension=".langlowiq", filetypes=[("LangLowIQ Files","*.langlowiq"),("All Files","*.*")])
        if f:
            self.filename = f
            self.save_file()

    # run
    def run_code(self):
        code = self.editor.get(1.0, tk.END)
        self.console.delete(1.0, tk.END)
        self.console.insert(tk.END, "Running...\n")
        def runner():
            interpreter = LangLowIQ(output_func=self.console_write)
            interpreter.run_string(code)
            self.console_write("Done.")
        threading.Thread(target=runner, daemon=True).start()

    def console_write(self, msg):
        self.console.insert(tk.END, str(msg) + "\n")
        self.console.see(tk.END)

    # highlighting
    def on_edit(self, event=None):
        self.editor.after_idle(self.highlight)
        self.editor.edit_modified(False)

    def highlight(self):
        text = self.editor.get(1.0, tk.END)
        for tag in self.editor.tag_names():
            self.editor.tag_remove(tag, "1.0", tk.END)
        for m in self.keyword_pattern.finditer(text):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.editor.tag_add("keyword", start, end)
        for m in re.finditer(r'"[^"]*"|\'[^\']*\'', text):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.editor.tag_add("string", start, end)
        for m in re.finditer(r"#.*", text):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.editor.tag_add("comment", start, end)

    # help
    def show_help(self):
        help_text = """
LangLowIQ v2 - Goofy manual (indentation blocks + 'end')

# comments with #

say "hello $name"
do_thing add a b:
    giveback a + b
end

let x = 5
uhmath x = $x + 1

thingy Person:
    do_thing init self name age:
        self.name = name
        self.age = age
    end
    do_thing greet self:
        say I am $self.name and $self.age
    end
end

let p = new Person "Rick" 18
yo p.greet

repeatuntil x == 10:
    uhmath x = $x + 1
end

try:
    oops "bad stuff"
catch err:
    say "caught: $err"
end

scribble "file.txt" with "hello"
fetch "file.txt" into contentVar

steal stringstuff
stealfrominternet "coollib"
"""
        messagebox.showinfo("LangLowIQ v2 Help", help_text)

# -------------------------
# If run as script, open IDE
# -------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = LangLowIQIDE(root)
    root.mainloop()
