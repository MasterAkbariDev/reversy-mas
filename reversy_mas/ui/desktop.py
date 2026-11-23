"""Simple native desktop interface for REVERSY MAS."""
import tkinter as tk
from tkinter import ttk

from ..agents import NAMES, create_agent
from ..environment import BLACK, WHITE, notation
from ..match import Match


class DesktopApp:
    def __init__(self, root):
        self.root = root
        root.title('REVERSY MAS')
        root.configure(bg='#f2f5f3')
        root.resizable(False, False)
        self.running = False
        self.timer = None
        self.mode = tk.StringVar(value='Play against AI')
        self.opponent = tk.StringVar(value='Strategic')
        self.status = tk.StringVar()
        self.score = tk.StringVar()
        self.detail = tk.StringVar(value='Choose a highlighted square to play.')

        outer = tk.Frame(root, bg='#f2f5f3', padx=20, pady=16)
        outer.pack()
        tk.Label(outer, text='REVERSY MAS', font=('Segoe UI', 20, 'bold'), bg='#f2f5f3', fg='#173a2b').grid(row=0, column=0, columnspan=2, sticky='w')
        tk.Label(outer, textvariable=self.score, font=('Segoe UI', 13, 'bold'), bg='#f2f5f3', fg='#173a2b').grid(row=1, column=0, sticky='w', pady=(4, 10))
        self.canvas = tk.Canvas(outer, width=448, height=448, bg='#287555', highlightthickness=0)
        self.canvas.grid(row=2, column=0, rowspan=2)
        self.canvas.bind('<Button-1>', self.play_square)
        panel = tk.Frame(outer, bg='#f2f5f3', width=270, padx=18)
        panel.grid(row=2, column=1, sticky='new')
        tk.Label(panel, text='GAME SETUP', font=('Segoe UI', 10, 'bold'), bg='#f2f5f3', fg='#517060').pack(anchor='w')
        tk.Label(panel, text='Mode', bg='#f2f5f3', font=('Segoe UI', 10)).pack(anchor='w', pady=(12, 3))
        ttk.Combobox(panel, textvariable=self.mode, values=('Play against AI', 'Team vs AI', 'AI vs AI'), state='readonly', width=24).pack(anchor='w')
        tk.Label(panel, text='Opponent', bg='#f2f5f3', font=('Segoe UI', 10)).pack(anchor='w', pady=(12, 3))
        ttk.Combobox(panel, textvariable=self.opponent, values=NAMES, state='readonly', width=24).pack(anchor='w')
        ttk.Button(panel, text='New game', command=self.new_game).pack(fill='x', pady=(16, 6))
        controls = tk.Frame(panel, bg='#f2f5f3')
        controls.pack(fill='x')
        ttk.Button(controls, text='Start / Pause', command=self.toggle).pack(side='left', expand=True, fill='x')
        ttk.Button(controls, text='Step', command=self.step).pack(side='left', expand=True, fill='x', padx=(5, 0))
        tk.Label(panel, textvariable=self.status, wraplength=220, justify='left', bg='#f2f5f3', fg='#173a2b', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(20, 6))
        ttk.Separator(panel).pack(fill='x', pady=5)
        tk.Label(panel, text='LATEST DECISION', font=('Segoe UI', 9, 'bold'), bg='#f2f5f3', fg='#517060').pack(anchor='w', pady=(8, 4))
        tk.Label(panel, textvariable=self.detail, wraplength=220, justify='left', bg='#f2f5f3', font=('Segoe UI', 10)).pack(anchor='w')
        self.new_game()

    def new_game(self):
        self.running = False
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        black = None if self.mode.get() == 'Play against AI' else create_agent('Coordinator Team' if self.mode.get() == 'Team vs AI' else 'Strategic', 2)
        self.match = Match(black, create_agent(self.opponent.get(), 2))
        self.detail.set('Choose a highlighted square to play.' if black is None else 'Press Start / Pause or Step to watch the agents.')
        self.draw()

    def draw(self):
        p = self.match.position
        self.canvas.delete('all')
        human = self.match.players[p.turn] is None
        for i, cell in enumerate(p.board):
            row, col = divmod(i, 8)
            x, y = col * 56, row * 56
            self.canvas.create_rectangle(x, y, x+56, y+56, fill='#287555', outline='#18563d')
            if cell:
                self.canvas.create_oval(x+6, y+6, x+50, y+50, fill='#1b2420' if cell == BLACK else '#f9faf7', outline='#102b20' if cell == BLACK else '#ced8d2', width=2)
            elif human and i in p.legal:
                self.canvas.create_oval(x+24, y+24, x+32, y+32, fill='#d1e7a9', outline='')
        self.score.set(f'Black  {p.scores[0]}     :     {p.scores[1]}  White')
        if p.finished:
            self.running = False
            self.status.set('Game over — ' + ('Draw' if p.winner == 0 else ('Black wins' if p.winner == BLACK else 'White wins')))
        else:
            color = 'Black' if p.turn == BLACK else 'White'
            self.status.set(f'{color} to move · {self.match.player_name(p.turn)}' + ('\nNo legal moves: press Step to pass.' if not p.legal else ''))

    def play_square(self, event):
        p = self.match.position
        square = (event.y // 56) * 8 + event.x // 56
        if not p.finished and self.match.players[p.turn] is None and square in p.legal:
            self.advance(square)
            if not self.match.position.finished:
                self.root.after(150, self.auto_reply)

    def auto_reply(self):
        p = self.match.position
        if not p.finished and (self.match.players[p.turn] is not None or not p.legal):
            self.advance()
            if not self.match.position.finished and self.match.players[self.match.position.turn] is not None:
                self.root.after(150, self.auto_reply)

    def advance(self, move=None):
        turn = self.match.advance(move)
        text = f'{turn.actor} played {notation(turn.outcome.move)}.'
        if turn.decision:
            text += '\n' + turn.decision.reason
            if turn.decision.exchanges:
                text += '\n\nTeam proposals: ' + ', '.join(f'{e.proposal.sender}: {notation(e.proposal.preferred.move)}' for e in turn.decision.exchanges if e.accepted)
        self.detail.set(text)
        self.draw()

    def step(self):
        p = self.match.position
        if not p.finished and (self.match.players[p.turn] is not None or not p.legal):
            self.advance()

    def toggle(self):
        self.running = not self.running
        if not self.running and self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.running:
            self.tick()

    def tick(self):
        self.timer = None
        if not self.running or self.match.position.finished:
            return
        p = self.match.position
        if self.match.players[p.turn] is None and p.legal:
            self.running = False
            return
        self.step()
        if self.running:
            self.timer = self.root.after(350, self.tick)


def main():
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

