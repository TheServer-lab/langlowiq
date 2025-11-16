import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, font
import os
import random
import time
import threading
import re

# --------------------------------------------------------
# Simple LangLowIQ interpreter
# --------------------------------------------------------
class LangLowIQ:
    def __init__(self, output_func=print):
        self.vars = {}
        self.functions = {}
        self.output = output_func

    def say(self, *msg): self.output(" ".join(msg))
    def yell(self, *msg): self.output(" ".join(msg).upper() + "!!!")
    def whisper(self, *msg): self.output(" ".join(msg).lower())
    def mathlikeanidiot(self, expr):
        try:
            self.output(f"{expr} = {eval(expr, {}, self.vars)}")
        except Exception as e:
            self.output(f"[math error] {e}")
    def uhmath(self, name, expr):
        try:
            self.vars[name] = eval(expr, {}, self.vars)
        except Exception as e:
            self.output(f"[uhmath error] {e}")

    def run_string(self, code):
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"): 
                continue
            words = line.split()
            cmd = words[0].lower()
            args = words[1:]

            try:
                if cmd == "say": self.say(*args)
                elif cmd == "yell": self.yell(*args)
                elif cmd == "whisper": self.whisper(*args)
                elif cmd == "let": self.vars[args[0]] = " ".join(args[2:])
                elif cmd == "set": self.vars[args[0]] = " ".join(args[2:])
                elif cmd == "mathlikeanidiot": self.mathlikeanidiot(" ".join(args))
                elif cmd == "uhmath": self.uhmath(args[0], " ".join(args[2:]))
                elif cmd == "now":
                    if len(args) > 1 and args[1] == "=": self.vars[args[0]] = " ".join(args[2:])
                elif cmd == "random":
                    if len(args) == 4 and args[2] == "to":
                        self.vars[args[0]] = random.randint(int(args[1]), int(args[3]))
                elif cmd == "wait": time.sleep(float(args[0]))
                elif cmd == "maybe":
                    if random.choice([True, False]): self.say(" ".join(args))
                elif cmd == "ragequit":
                    self.output("ragequitting... 😡"); break
                elif cmd == "repeat":
                    count = int(args[0])
                    sub_cmd = " ".join(args[1:])
                    for _ in range(count): self.run_string(sub_cmd)
                elif cmd == "if":
                    var, _, val = args[0], args[1], args[2]
                    if self.vars.get(var) == val:
                        self.run_string(" ".join(args[3:]))
                elif cmd == "else":
                    self.run_string(" ".join(args))
                elif cmd == "steal":
                    path = " ".join(args)
                    if os.path.isfile(path):
                        with open(path, "r", encoding="utf-8") as f: self.run_string(f.read())
                    else: self.output(f"[steal error] File not found: {path}")
                elif cmd == "shoutrandom":
                    options = " ".join(args).split(",")
                    self.yell(random.choice([opt.strip() for opt in options]))
                elif cmd == "oops":
                    self.output("Oops! Something went wrong. 🤯")
                elif cmd == "brainfreeze":
                    time.sleep(random.uniform(0.5, 2.0))
                elif cmd == "listvars":
                    for k,v in self.vars.items(): self.output(f"{k} = {v}")
                elif cmd == "trashmath":
                    self.output(f"{' '.join(args)} = {random.randint(0,100)} (probably wrong)")
                else:
                    self.output(f"[unknown command] {cmd} (line {i})")
            except Exception as e:
                self.output(f"[error on line {i}] {e}")

# --------------------------------------------------------
# GUI IDE for LangLowIQ
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
            "repeat", "if", "else", "steal", "shoutrandom", "oops",
            "brainfreeze", "listvars", "trashmath"
        ]
        self.keyword_pattern = re.compile(r"\b(" + "|".join(self.keywords) + r")\b")

        self.editor.tag_configure("keyword", foreground="#ffcc00", font=("Consolas", 12, "bold"))
        self.editor.tag_configure("string", foreground="#55ff55")
        comment_font = font.Font(family="Consolas", size=12, slant="italic")
        self.editor.tag_configure("comment", foreground="#888888", font=comment_font)

        # --- Output console ---
        self.console = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=10, font=("Consolas", 11), bg="#111", fg="#0f0")
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
        file = filedialog.asksaveasfilename(defaultextension=".langlowiq",
                                            filetypes=[("LangLowIQ Files", "*.langlowiq"), ("All Files", "*.*")])
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

            interpreter = LangLowIQ(output)
            interpreter.run_string(code)
            output("Done.\n")

        threading.Thread(target=run_thread, daemon=True).start()

    # ---------- Syntax highlighting ----------
    def on_edit(self, event=None):
        self.editor.after_idle(self.highlight_syntax)
        self.editor.edit_modified(False)

    def highlight_syntax(self, event=None):
        text = self.editor.get(1.0, tk.END)
        for tag in self.editor.tag_names(): self.editor.tag_remove(tag, "1.0", tk.END)

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
say Hello world
yell I love coding
whisper please be quiet
let x = 5
uhmath y = x + 3
mathlikeanidiot 5 * 2 + 1
now mood = happy
random number 1 to 10
wait 1.5
maybe surprise!
ragequit

# New silly commands
repeat 5 say Hello
if mood = happy say Yay!
else say Sad times...
steal c:\\downloads\\lib.langlowiq
shoutrandom I love pizza, Coding is hard, Coffee time
oops
brainfreeze
listvars
trashmath 2 + 2

Tip: It's okay to be dumb. LangLowIQ understands you.
"""
        messagebox.showinfo("LangLowIQ Syntax Help", help_text)

# --------------------------------------------------------
# Run the app
# --------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = LangLowIQIDE(root)
    root.mainloop()
