"""Native, audience-friendly desktop interface for REVERSY MAS."""
import math
import random
import time
import tkinter as tk
from tkinter import ttk

from ..agents import NAMES, create_agent
from ..environment import BLACK, WHITE, flips, notation
from ..match import Match

BG = '#050914'
PANEL = '#0c1526'
CARD = '#142338'
MUTED = '#899eb4'
TEXT = '#eaf7ff'
MINT = '#47e8f2'
GOLD = '#f7ca66'
CELL = 64
BOARD = CELL * 8


class ArenaButton(tk.Canvas):
    """A rounded native canvas button with hover and keyboard focus."""
    def __init__(self, parent, text, command, primary=False, variable=None):
        super().__init__(parent, width=110, height=44, bg=parent['bg'],
                         highlightthickness=0, bd=0, cursor='hand2', takefocus=True)
        self.text, self.variable, self.command, self.primary = text, variable, command, primary
        self.hover = False
        self.bind('<Configure>', lambda e: self.paint())
        self.bind('<Enter>', lambda e: self.set_hover(True))
        self.bind('<Leave>', lambda e: self.set_hover(False))
        self.bind('<Button-1>', lambda e: self.focus_set())
        self.bind('<ButtonRelease-1>', self.activate)
        self.bind('<Return>', self.activate)
        self.bind('<space>', self.activate)
        self.bind('<FocusIn>', lambda e: self.paint())
        self.bind('<FocusOut>', lambda e: self.paint())
        if variable is not None:
            variable.trace_add('write', lambda *args: self.paint())

    def set_hover(self, value):
        self.hover = value
        self.paint()

    def activate(self, event):
        if event.type == tk.EventType.ButtonRelease and not (0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()):
            return
        self.command()

    def paint(self):
        self.delete('all')
        w, h, r = self.winfo_width(), self.winfo_height(), 11
        fill = ('#8cfaff' if self.hover else '#47e8f2') if self.primary else ('#284462' if self.hover else '#172b42')
        edge = '#b2fbff' if self.focus_get() == self else ('#43aab9' if not self.primary else '#8effff')
        self.create_polygon(2+r, 2, w-2-r, 2, w-2, 2, w-2, 2+r,
                            w-2, h-2-r, w-2, h-2, w-2-r, h-2,
                            2+r, h-2, 2, h-2, 2, h-2-r, 2, 2+r, 2, 2,
                            smooth=True, splinesteps=24, fill=fill, outline=edge, width=1)
        self.create_text(w/2, h/2, text=self.variable.get() if self.variable else self.text,
                         fill='#06121c' if self.primary else TEXT,
                         font=('Segoe UI', 10, 'bold'))


class DesktopApp:
    def __init__(self, root):
        self.root = root
        root.title('REVERSY MAS  •  Strategy arena')
        root.configure(bg=BG)
        root.minsize(960, 740)
        self.running = False
        self.timer = None
        self.generation = 0
        self.animating = False
        self.last_move = None
        self.mode = tk.StringVar(value='Human vs AI')
        self.black_choice = tk.StringVar(value='Coordinator Team')
        self.white_choice = tk.StringVar(value='Strategic')
        self.speed = tk.StringVar(value='Normal')
        self.status = tk.StringVar()
        self.black_name = tk.StringVar()
        self.white_name = tk.StringVar()
        self.black_score = tk.StringVar(value='2')
        self.white_score = tk.StringVar(value='2')
        self.move_count = tk.StringVar(value='MOVE 00')
        self.detail_title = tk.StringVar(value='Ready to play')
        self.detail = tk.StringVar(value='Choose a highlighted square to make your move.')
        self.play_label = tk.StringVar(value='▶  Start')
        self.style = ttk.Style(root)
        self.style.theme_use('clam')
        self.style.configure('Arena.TCombobox', fieldbackground=CARD, background=CARD,
                             foreground=TEXT, arrowcolor=MINT, borderwidth=0,
                             padding=7, font=('Segoe UI', 10))
        self.style.map('Arena.TCombobox', fieldbackground=[('readonly', CARD)],
                       foreground=[('readonly', TEXT)])
        root.option_add('*TCombobox*Listbox.background', CARD)
        root.option_add('*TCombobox*Listbox.foreground', TEXT)
        root.option_add('*TCombobox*Listbox.selectBackground', '#356856')
        self.build()
        self.new_game()

    def label(self, parent, text='', size=10, color=TEXT, bold=False, bg=None, **kw):
        return tk.Label(parent, text=text, font=('Segoe UI', size, 'bold' if bold else 'normal'),
                        fg=color, bg=bg or parent['bg'], **kw)

    def button(self, parent, text=None, command=None, primary=False, variable=None):
        return ArenaButton(parent, text, command, primary, variable)

    def combo(self, parent, variable, values):
        return ttk.Combobox(parent, textvariable=variable, values=values,
                            state='readonly', style='Arena.TCombobox', width=20)

    def build(self):
        shell = tk.Frame(self.root, bg=BG, padx=24, pady=18)
        shell.pack(fill='both', expand=True)
        header = tk.Frame(shell, bg=BG)
        header.pack(fill='x', pady=(0, 14))
        self.label(header, 'REVERSY', 23, bold=True).pack(side='left')
        self.label(header, '  MAS', 23, color=MINT, bold=True).pack(side='left')
        self.label(header, '  /  MULTI-AGENT ARENA', 9, color=MUTED, bold=True).pack(side='left', anchor='s', pady=6)
        self.label(header, 'COMPETE  •  COOPERATE  •  ADAPT', 9, color=MUTED, bold=True).pack(side='right')
        content = tk.Frame(shell, bg=BG)
        content.pack(fill='both', expand=True)
        left = tk.Frame(content, bg=BG)
        left.pack(side='left', anchor='n')
        scores = tk.Frame(left, bg=PANEL, padx=16, pady=10)
        scores.pack(fill='x', pady=(0, 10))
        for side, name, score, color in [('BLACK / MAGENTA', self.black_name, self.black_score, '#ff7fbd'), ('WHITE / CYAN', self.white_name, self.white_score, '#47e8f2')]:
            block = tk.Frame(scores, bg=PANEL)
            block.pack(side='left', expand=True, fill='x')
            self.label(block, side, 9, color=color, bold=True).pack(anchor='w')
            self.label(block, size=11, bold=True, textvariable=name).pack(anchor='w')
            self.label(block, size=25, bold=True, textvariable=score).pack(anchor='w')
        self.label(scores, size=9, color=MUTED, bold=True, textvariable=self.move_count).pack(side='right', anchor='n')
        board_frame = tk.Frame(left, bg='#276979', padx=4, pady=4)
        board_frame.pack()
        self.canvas = tk.Canvas(board_frame, width=BOARD, height=BOARD, bg='#0a1220', highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.play_square)
        self.label(left, size=12, color=MINT, bold=True, textvariable=self.status).pack(anchor='w', pady=(12, 0))
        self.label(left, 'Dots show legal moves  •  Gold outline marks the last move', 9, color=MUTED).pack(anchor='w', pady=(3, 0))

        panel = tk.Frame(content, bg=PANEL, padx=20, pady=16, width=365)
        panel.pack(side='left', fill='both', expand=True, padx=(20, 0))
        panel.pack_propagate(False)
        self.label(panel, 'MATCH SETTINGS', 10, color=MINT, bold=True).pack(anchor='w')
        self.label(panel, 'Game mode', 9, color=MUTED).pack(anchor='w', pady=(10, 3))
        mode_box = self.combo(panel, self.mode, ('Human vs AI', 'Team vs AI', 'AI vs AI'))
        mode_box.pack(fill='x')
        mode_box.bind('<<ComboboxSelected>>', self.mode_changed)
        choices = tk.Frame(panel, bg=PANEL)
        choices.pack(fill='x', pady=(9, 0))
        for title, variable, attr in [('BLACK STRATEGY', self.black_choice, 'black_box'), ('WHITE STRATEGY', self.white_choice, 'white_box')]:
            col = tk.Frame(choices, bg=PANEL)
            col.pack(side='left', fill='x', expand=True, padx=(0, 6))
            self.label(col, title, 8, color=MUTED, bold=True).pack(anchor='w', pady=(0, 4))
            box = self.combo(col, variable, ('Random', *NAMES))
            box.configure(width=12)
            box.pack(fill='x')
            setattr(self, attr, box)
        self.label(panel, 'Settings apply when you start a new game.', 8, color=MUTED).pack(anchor='w', pady=(6, 0))
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill='x', pady=(12, 0))
        self.button(row, '↻  New game', self.new_game, primary=True).pack(side='left', fill='x', expand=True)
        self.button(row, command=self.toggle, variable=self.play_label).pack(side='left', fill='x', expand=True, padx=6)
        self.button(row, 'Step', self.step).pack(side='left')
        speedrow = tk.Frame(panel, bg=PANEL)
        speedrow.pack(fill='x', pady=(10, 0))
        self.label(speedrow, 'PLAYBACK SPEED', 8, color=MUTED, bold=True).pack(side='left')
        self.combo(speedrow, self.speed, ('Slow', 'Normal', 'Fast')).pack(side='right')
        self.label(panel, 'LATEST DECISION', 10, color=MINT, bold=True).pack(anchor='w', pady=(18, 6))
        card = tk.Frame(panel, bg=CARD, padx=12, pady=10)
        card.pack(fill='x')
        self.label(card, size=11, bold=True, textvariable=self.detail_title, anchor='w').pack(fill='x')
        self.label(card, size=9, color='#d2e5d9', textvariable=self.detail, justify='left', anchor='nw', wraplength=295).pack(fill='x', pady=(5, 0))
        self.label(panel, 'MOVE HISTORY', 10, color=MINT, bold=True).pack(anchor='w', pady=(16, 6))
        history_frame = tk.Frame(panel, bg=CARD)
        history_frame.pack(fill='both', expand=True)
        scroll = tk.Scrollbar(history_frame, bg=CARD)
        scroll.pack(side='right', fill='y')
        self.history = tk.Listbox(history_frame, bg=CARD, fg=TEXT, selectbackground='#356856',
                                  relief='flat', bd=0, highlightthickness=0, font=('Segoe UI', 10),
                                  activestyle='none', yscrollcommand=scroll.set, height=5)
        self.history.pack(fill='both', expand=True, padx=8, pady=7)
        scroll.config(command=self.history.yview)
        self.mode_changed()

    def mode_changed(self, event=None):
        enabled = self.mode.get() == 'AI vs AI'
        self.black_box.configure(state='readonly' if enabled else 'disabled')

    def resolve(self, choice):
        return random.choice(NAMES) if choice == 'Random' else choice

    def cancel_timer(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None

    def schedule(self, delay, callback):
        self.cancel_timer()
        generation = self.generation
        def run():
            self.timer = None
            if generation == self.generation:
                callback()
        self.timer = self.root.after(delay, run)

    def new_game(self):
        self.generation += 1
        self.cancel_timer()
        self.running = self.animating = False
        self.play_label.set('▶  Start')
        mode = self.mode.get()
        black = None if mode == 'Human vs AI' else create_agent('Coordinator Team' if mode == 'Team vs AI' else self.resolve(self.black_choice.get()), 2)
        white = create_agent(self.resolve(self.white_choice.get()), 2)
        self.match = Match(black, white)
        self.black_name.set(self.match.player_name(BLACK))
        self.white_name.set(self.match.player_name(WHITE))
        self.last_move = None
        self.history.delete(0, 'end')
        self.detail_title.set('Ready to play')
        self.detail.set('Choose a highlighted square.' if black is None else 'Press Start to watch, or Step for one move.')
        self.draw()

    def draw(self, board=None, highlight=None, flip_scale=1.0):
        p = self.match.position
        board = p.board if board is None else board
        self.canvas.delete('all')
        legal = p.legal if not self.animating and not p.finished else ()
        for i, cell in enumerate(board):
            row, col = divmod(i, 8)
            x, y = col * CELL, row * CELL
            self.canvas.create_rectangle(x, y, x+CELL, y+CELL, fill='#101b30' if (row+col)%2 else '#0d182a', outline='#1b3b4b')
            if i == (self.last_move if highlight is None else highlight):
                self.canvas.create_rectangle(x+3, y+3, x+CELL-3, y+CELL-3, outline=GOLD, width=3)
            if cell:
                cx, cy = x+CELL/2, y+CELL/2
                scale = getattr(self, '_scales', {}).get(i, 1.0)
                size = getattr(self, '_sizes', {}).get(i, 1.0)
                radius = 25 * size
                # Layered rings give the discs the original game's luminous, dimensional finish.
                colors = (('#5c0034', '#b80864', '#f32991', '#ff9bcf') if cell == BLACK
                          else ('#004653', '#008899', '#00e4ee', '#cbffff'))
                self.canvas.create_oval(cx-radius-3, cy-radius*scale-3, cx+radius+3, cy+radius*scale+3,
                                        fill='#35152d' if cell == BLACK else '#0c3c4a', outline='')
                self.canvas.create_oval(cx-radius, cy-radius*scale, cx+radius, cy+radius*scale,
                                        fill=colors[0], outline=colors[1], width=2)
                self.canvas.create_oval(cx-radius*.86, cy-radius*.88*scale, cx+radius*.76, cy+radius*.74*scale,
                                        fill=colors[1], outline='')
                self.canvas.create_oval(cx-radius*.72, cy-radius*.78*scale, cx+radius*.51, cy+radius*.48*scale,
                                        fill=colors[2], outline='')
                if scale > .35:
                    self.canvas.create_oval(cx-radius*.47, cy-radius*.55*scale, cx-radius*.09, cy-radius*.22*scale,
                                            fill=colors[3], outline='')
            elif i in legal:
                self.canvas.create_oval(x+25, y+25, x+39, y+39, outline='#31838c', width=2)
                self.canvas.create_oval(x+29, y+29, x+35, y+35, fill=MINT, outline='')
        self.black_score.set(str(p.scores[0]))
        self.white_score.set(str(p.scores[1]))
        self.move_count.set(f'MOVE {len(self.match.history):02d}')
        if p.finished:
            self.running = False
            self.play_label.set('▶  Start')
            self.status.set('GAME OVER  •  ' + ('Draw' if p.winner == 0 else ('Black wins' if p.winner == BLACK else 'White wins')))
        else:
            color = 'BLACK' if p.turn == BLACK else 'WHITE'
            self.status.set(f'{color} TO MOVE  •  {self.match.player_name(p.turn)}' + ('  •  PASS' if not p.legal else ''))

    def play_square(self, event):
        if self.animating or self.running:
            return
        p = self.match.position
        square = (event.y // CELL) * 8 + event.x // CELL
        if not p.finished and self.match.players[p.turn] is None and square in p.legal:
            self.advance(square, auto_human=True)

    def advance(self, move=None, auto_human=False):
        if self.animating or self.match.position.finished:
            return
        turn = self.match.advance(move)
        outcome = turn.outcome
        self.last_move = outcome.move
        self.history.insert('end', f'{len(self.match.history):02d}   {"Black" if outcome.before.turn == BLACK else "White"}  ·  {turn.actor}  →  {notation(outcome.move)}')
        self.history.see('end')
        self.detail_title.set(f'{turn.actor}  →  {notation(outcome.move)}')
        text = f'{outcome.flips} disc(s) flipped'
        if turn.decision:
            text += f'  ·  {turn.decision_seconds * 1000:.0f} ms\n{turn.decision.reason}'
            if turn.decision.exchanges:
                text += '\n\nTEAM PROPOSALS\n' + '\n'.join(f'{e.proposal.sender}: {notation(e.proposal.preferred.move)}' if e.accepted else f'{e.proposal.sender}: rejected' for e in turn.decision.exchanges)
            if turn.adaptations:
                text += '\n\nADAPTATION\n' + '; '.join(f'{a.feature}: {a.previous_weight:.1f} → {a.new_weight:.1f}' for a in turn.adaptations)
        self.detail.set(text)
        self.animating = True
        flipped = tuple(flips(outcome.before.board, outcome.before.turn, outcome.move)) if outcome.move is not None else ()
        # Match the original's bounce and staggered 0.42-second disc flips.
        started = time.perf_counter()
        duration = .42
        stagger = .035
        total = .18 + duration + max(0, len(flipped)-1) * stagger
        def frame():
            elapsed = time.perf_counter() - started
            if outcome.move is None or elapsed >= total:
                self.animating = False
                self._scales, self._sizes = {}, {}
                self.draw()
                if self.running:
                    self.schedule({'Slow': 1300, 'Normal': 650, 'Fast': 180}[self.speed.get()], self.tick)
                elif auto_human:
                    self.schedule(450, self.auto_reply)
                return
            board = list(outcome.before.board)
            # A quick overshoot and settle suggests the original placement bounce.
            t = min(1.0, elapsed / .28)
            bounce = 1 - (1-t)**3 + .15 * math.sin(math.pi*t) * (1-t)
            board[outcome.move] = outcome.before.turn
            self._sizes = {outcome.move: max(.08, bounce)}
            self._scales = {}
            for index, square in enumerate(flipped):
                progress = max(0.0, min(1.0, (elapsed - .18 - index*stagger) / duration))
                if progress >= .5:
                    board[square] = outcome.after.board[square]
                # Cosine creates the edge-on midpoint of a 3D rotation.
                self._scales[square] = max(.06, abs(math.cos(math.pi*progress)))
            self.draw(board, outcome.move)
            self.schedule(16, frame)
        frame()

    def auto_reply(self):
        p = self.match.position
        if not p.finished and (self.match.players[p.turn] is not None or not p.legal):
            self.advance(auto_human=True)

    def step(self):
        if self.running or self.animating:
            return
        p = self.match.position
        if not p.finished and (self.match.players[p.turn] is not None or not p.legal):
            self.advance()

    def toggle(self):
        if self.match.position.finished:
            return
        self.running = not self.running
        self.play_label.set('Ⅱ  Pause' if self.running else '▶  Start')
        if self.running and not self.animating:
            self.tick()
        elif not self.running and not self.animating:
            self.cancel_timer()

    def tick(self):
        if not self.running or self.match.position.finished or self.animating:
            return
        p = self.match.position
        if self.match.players[p.turn] is None and p.legal:
            self.running = False
            self.play_label.set('▶  Start')
            return
        self.advance()


def main():
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

