import ast
import os

file_path = r"c:\Users\DELL\Desktop\kriaos2\backend\whatsapp_monitor.py"
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    ast.parse(source)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax Error at line {e.lineno}: {e.msg}")
    print(f"Line content: {e.text}")
except Exception as e:
    print(f"Error: {e}")
