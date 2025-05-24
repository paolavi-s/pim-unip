import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import hashlib
import os
import shutil
import csv
import json
from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ==================== CONFIGURAÇÕES ====================
ADMIN_PASSWORD = "admin123"
DB_PATH = "quiz.db"
BACKUP_PATH = "quiz_backup.db"
QUESTIONS_FILE = "Quiz_data.json"

# ==================== BANCO DE DADOS ====================
def criar_banco():
    precisa_recriar = False
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='respostas'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(respostas)")
            colunas = [linha[1] for linha in cursor.fetchall()]
            if "usuario" not in colunas:
                precisa_recriar = True
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resultado'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(resultado)")
            colunas = [linha[1] for linha in cursor.fetchall()]
            if "usuario" not in colunas:
                precisa_recriar = True
        conn.close()

    if precisa_recriar:
        if os.path.exists(BACKUP_PATH):
            os.remove(BACKUP_PATH)
        shutil.move(DB_PATH, BACKUP_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_completo TEXT,
            usuario TEXT UNIQUE,
            senha_hash TEXT,
            data_nascimento TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            pergunta TEXT,
            resposta_criptografada TEXT,
            correta BOOLEAN
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resultado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            total_perguntas INTEGER,
            pontuacao INTEGER
        )
    """)
    conn.commit()
    conn.close()

# ==================== FUNÇÕES AUXILIARES ====================
def hash_senha(senha):
    salt = "s@lt123"
    return hashlib.sha256((senha + salt).encode('utf-8')).hexdigest()

def autenticar_usuario(usuario, senha):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT senha_hash FROM usuarios WHERE usuario = ?", (usuario,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado and resultado[0] == hash_senha(senha)

def cadastrar_usuario(nome_completo, usuario, senha, nascimento):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nome_completo, usuario, senha_hash, data_nascimento) VALUES (?, ?, ?, ?)",
                       (nome_completo, usuario, hash_senha(senha), nascimento))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def salvar_resposta(usuario, pergunta, resposta, correta):
    resposta_hash = hashlib.sha256(resposta.encode('utf-8')).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO respostas (usuario, pergunta, resposta_criptografada, correta)
        VALUES (?, ?, ?, ?)
    """, (usuario, pergunta, resposta_hash, correta))
    conn.commit()
    conn.close()

def salvar_resultado(usuario, total, pontuacao):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO resultado (usuario, total_perguntas, pontuacao)
        VALUES (?, ?, ?)
    """, (usuario, total, pontuacao))
    conn.commit()
    conn.close()

def buscar_resultados():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT usuario, pergunta, correta FROM respostas")
    respostas = cursor.fetchall()
    cursor.execute("SELECT usuario, total_perguntas, pontuacao FROM resultado")
    resultados = cursor.fetchall()
    conn.close()
    return respostas, resultados

def exportar_para_csv():
    respostas, resultados = buscar_resultados()
    with open("respostas.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Usuario", "Pergunta", "Correta"])
        for row in respostas:
            writer.writerow(row)
    with open("resultados.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Usuario", "Total", "Acertos"])
        for row in resultados:
            writer.writerow(row)

# ==================== QUIZ ====================
def carregar_perguntas():
    if not os.path.exists(QUESTIONS_FILE):
        messagebox.showerror("Erro", f"Arquivo {QUESTIONS_FILE} não encontrado.")
        return []
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)

class QuizApp:
    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.root.title(f"Quiz - Usuário: {usuario}")
        self.perguntas = carregar_perguntas()
        self.pontuacao = 0
        self.total = len(self.perguntas)
        self.restantes = self.perguntas.copy()

        ttk.Label(root, text=f"Bem-vindo, {usuario}!", font=("Arial", 14)).pack(pady=5)
        self.label = ttk.Label(root, text="Escolha a pergunta para responder:", font=("Arial", 12))
        self.label.pack(pady=5)

        self.perguntas_frame = ttk.Frame(root)
        self.perguntas_frame.pack(pady=10)

        self.conteudo_frame = ttk.Frame(root)
        self.conteudo_frame.pack(pady=10)

        self.mostrar_perguntas()

    def mostrar_perguntas(self):

        for widget in self.perguntas_frame.winfo_children():
            widget.destroy()
        for widget in self.conteudo_frame.winfo_children():
            widget.destroy()

        if not self.restantes:
            salvar_resultado(self.usuario, self.total, self.pontuacao)
            messagebox.showinfo("Fim", f"Acertou {self.pontuacao} de {self.total}.")
            self.root.destroy()
            return

        for i, item in enumerate(self.restantes):
            ttk.Button(self.perguntas_frame, text=item["titulo"], width=40,
                       command=lambda idx=i: self.mostrar_explicacao(idx)).pack(pady=3)

    def mostrar_explicacao(self, idx):
        for widget in self.conteudo_frame.winfo_children():
            widget.destroy()

        self.indice_atual = idx
        item = self.restantes[idx]

        explicacao_text = item.get("explicacao", "Não há explicação disponível para este tópico.")
        ttk.Label(self.conteudo_frame, text=f"Tópico: {item['titulo']}", font=("Arial", 14, "bold")).pack(pady=5)
        ttk.Label(self.conteudo_frame, text=explicacao_text, font=("Arial", 11), wraplength=500, justify="left").pack(pady=10)

        ttk.Button(self.conteudo_frame, text="Responder Pergunta", command=self.mostrar_pergunta).pack(pady=5)

    def mostrar_pergunta(self):
        for widget in self.conteudo_frame.winfo_children():
            widget.destroy()

        item = self.restantes[self.indice_atual]

        ttk.Label(self.conteudo_frame, text=item["pergunta"], font=("Arial", 12), wraplength=500).pack(pady=10)
        for i, opcao in enumerate(item["opcoes"], start=1):
            ttk.Button(self.conteudo_frame, text=opcao, width=60,
                       command=lambda i=i, o=opcao: self.responder(item, i, o)).pack(pady=3)

    def responder(self, item, resposta_idx, resposta_texto):
        correta = resposta_idx == item["resposta"]
        salvar_resposta(self.usuario, item["pergunta"], resposta_texto, correta)
        if correta:
            self.pontuacao += 1
            messagebox.showinfo("Correto", "✅ Resposta correta!")
        else:
            certa = item["opcoes"][item["resposta"] - 1]
            messagebox.showwarning("Errado", f"❌ Errado. Correta: {certa}")

        self.restantes.pop(self.indice_atual)

        self.mostrar_perguntas()


# ==================== ADMIN ====================
class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Administrador - Resultados")

        abas = ttk.Notebook(root)
        abas.pack(expand=True, fill='both')

        self.frame_respostas = ttk.Frame(abas)
        self.frame_grafico = ttk.Frame(abas)
        abas.add(self.frame_respostas, text="Resultados")
        abas.add(self.frame_grafico, text="Gráfico de Acertos")

        respostas, resultados = buscar_resultados()

        ttk.Label(self.frame_respostas, text="Respostas dos usuários", font=("Arial", 14)).pack(pady=10)
        tree1 = ttk.Treeview(self.frame_respostas, columns=("usuario", "pergunta", "correta"), show='headings')
        for col in ["usuario", "pergunta", "correta"]:
            tree1.heading(col, text=col.capitalize())
        for row in respostas:
            tree1.insert("", tk.END, values=(row[0], row[1], "Sim" if row[2] else "Não"))
        tree1.pack(pady=10)

        ttk.Label(self.frame_respostas, text="Pontuação Final", font=("Arial", 14)).pack(pady=10)
        tree2 = ttk.Treeview(self.frame_respostas, columns=("usuario", "total", "pontos", "media"), show='headings')
        for col in ["usuario", "total", "pontos", "media"]:
            tree2.heading(col, text=col.capitalize())
        for row in resultados:
            media = f"{(row[2] / row[1]) * 100:.1f}%" if row[1] > 0 else "0%"
            tree2.insert("", tk.END, values=(row[0], row[1], row[2], media))
        tree2.pack(pady=10)

        ttk.Button(self.frame_respostas, text="Exportar CSV", command=exportar_para_csv).pack(pady=10)

        # Gráfico
        nomes = [r[0] for r in resultados]
        pontuacoes = [r[2] for r in resultados]
        fig = Figure(figsize=(5, 4))
        ax = fig.add_subplot(111)
        ax.bar(nomes, pontuacoes)
        ax.set_title("Desempenho dos Usuários")
        ax.set_ylabel("Pontos")
        ax.set_xlabel("Usuários")
        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

# ==================== INÍCIO COM LOGIN/CADASTRO ====================
def iniciar_interface():
    def autenticar():
        usuario = entry_usuario.get().strip()
        senha = entry_senha.get()
        if autenticar_usuario(usuario, senha):
            login_janela.destroy()
            app = tk.Tk()
            QuizApp(app, usuario)
            app.mainloop()
        else:
            messagebox.showerror("Erro", "Usuário ou senha inválidos.")

    def abrir_cadastro():
        def cadastrar():
            nome = entry_nome.get().strip()
            usuario = entry_usuario_cadastro.get().strip()
            senha = entry_senha_cadastro.get()
            nascimento = entry_nascimento.get()
            if cadastrar_usuario(nome, usuario, senha, nascimento):
                messagebox.showinfo("Sucesso", "Usuário cadastrado com sucesso!")
                cadastro_janela.destroy()
            else:
                messagebox.showerror("Erro", "Usuário já existe.")

        cadastro_janela = tk.Toplevel()
        cadastro_janela.title("Cadastro de Usuário")
        ttk.Label(cadastro_janela, text="Nome completo:").pack()
        entry_nome = ttk.Entry(cadastro_janela)
        entry_nome.pack()
        ttk.Label(cadastro_janela, text="Nome de usuário:").pack()
        entry_usuario_cadastro = ttk.Entry(cadastro_janela)
        entry_usuario_cadastro.pack()
        ttk.Label(cadastro_janela, text="Senha:").pack()
        entry_senha_cadastro = ttk.Entry(cadastro_janela, show="*")
        entry_senha_cadastro.pack()
        ttk.Label(cadastro_janela, text="Data de nascimento (DD/MM/AAAA):").pack()
        entry_nascimento = ttk.Entry(cadastro_janela)
        entry_nascimento.pack()
        ttk.Button(cadastro_janela, text="Cadastrar", command=cadastrar).pack(pady=5)

    def entrar_admin():
        if entry_admin_senha.get() == ADMIN_PASSWORD:
            login_janela.destroy()
            app = tk.Tk()
            AdminApp(app)
            app.mainloop()
        else:
            messagebox.showerror("Erro", "Senha incorreta.")

    login_janela = tk.Tk()
    login_janela.title("Login do Sistema de Quiz")
    login_janela.geometry("300x300")

    ttk.Label(login_janela, text="Usuário:").pack()
    entry_usuario = ttk.Entry(login_janela)
    entry_usuario.pack(pady=5)

    ttk.Label(login_janela, text="Senha:").pack()
    entry_senha = ttk.Entry(login_janela, show="*")
    entry_senha.pack(pady=5)

    ttk.Button(login_janela, text="Login", command=autenticar).pack(pady=5)
    ttk.Button(login_janela, text="Cadastrar", command=abrir_cadastro).pack(pady=5)

    ttk.Label(login_janela, text="Administrador:").pack(pady=10)
    entry_admin_senha = ttk.Entry(login_janela, show="*")
    entry_admin_senha.pack(pady=5)
    ttk.Button(login_janela, text="Entrar como Admin", command=entrar_admin).pack(pady=5)

    login_janela.mainloop()

# ==================== EXECUÇÃO ====================
if __name__ == "__main__":
    criar_banco()
    iniciar_interface()