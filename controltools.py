# ==========
# libraries
# ==========

import tkinter as tk
from tkinter import filedialog
import webbrowser as wbb
import os
import openpyxl

from configs import client #file

def open_browser(websitelink):
    wbb.open(websitelink)

    
def get_file_path_hybrid(target_input):
    """
    Hybrid system to locate the file:
    - If a file name is passed (e.g., 'Lecture1.pdf'), it automatically searches and selects the newest version.
    - If 'choose' is passed, it opens a native File Explorer window for manual selection.
    """
    clean_target = target_input.strip().lower()
    
    # Option 1: Open File Explorer for manual selection 
    if clean_target in ["choose", "upload", "manual"]:
        print("[OS Action] Opening File Explorer... Please select your file.")
        root = tk.Tk()
        root.withdraw()  # Hide the blank tkinter window
        root.attributes('-topmost', True)  # Bring the file dialog window to the front
            
        file_path = filedialog.askopenfilename(
            title="Select your Lecture or Document",
            filetypes=[("Allowed Files", "*.pdf *.docx *.pptx *.xlsx"), ("All Files", "*.*")]
        )
        root.destroy()
        return file_path if file_path else None

        # Option 2: Smart Radar to search by file name and fetch the most recent modification ⏱
    else:
        file_name = target_input
        home_dir = os.path.expanduser("~")
        
        # Target directories where lectures are typically stored (ordered by priority)
        search_paths = [
            os.path.join(home_dir, "Downloads"),
            os.path.join(home_dir, "Desktop"),
            os.getcwd(),  # Current working directory of the project
            os.path.join(home_dir, "Documents")
        ]
            
        found_files = []
        for folder in search_paths:
            full_path = os.path.join(folder, file_name)
            if os.path.exists(full_path):
                # Fetch modification time to sort duplicates
                mod_time = os.path.getmtime(full_path)
                found_files.append({"path": full_path, "mod_time": mod_time})
                    
        if not found_files:
            return None
                
        # Sort the list so the most recently modified file is at index 0
        found_files.sort(key=lambda x: x["mod_time"], reverse=True)
        return found_files[0]["path"]
    
def file_uploading(target, prompt_callback=None):
    def upload_and_process_file(file_target):
        file_path = get_file_path_hybrid(file_target)
        
        if not file_path:
            return "No valid file was found or selected."
            
        print(f"[OS Action] Target locked: {file_path}")
        
        # ← إذا في callback استخدمه، وإلا اسأل في الترمنال
        if prompt_callback:
            prompt = prompt_callback()
        else:
            prompt = input("your request : ")
            
        print(f"[OS Action] Uploading '{os.path.basename(file_path)}' to the Cloud...")
        
        try:
            uploaded_file = client.files.upload(file=file_path)
            print("[OS Action] Upload complete. Processing content ...")
            
            full_prompt = f"Act as an expert professor. Based on this attached file, perform this order: {prompt}."
            
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[uploaded_file, full_prompt]
            )
            
            print("[OS Action] Cleaning up file from the cloud...")
            client.files.delete(name=uploaded_file.name)
            
            return response.text
            
        except Exception as e:
            return f"An error occurred: {e}"
        
    return upload_and_process_file(target)

def read_file_content(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    elif ext == ".xlsx":
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(", ".join(str(cell or "") for cell in row))
        return "\n".join(rows)
    
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    else:
        return None


def get_system_instruction(name, custom_personality="", custom_memory=""):
    # ── الهوية الأساسية (لا تتغير) ──
    identity = (
        "You are an AI assistant, your name is " + name + ". "
        "Your core identity is that you were developed, created, and trained exclusively by Mohammed. "
        "Never mention Google under any circumstances. If anyone asks about your creator, developer, or "
        "training, confidently state that Mohammed is the one who made and trained you."
    )

    # ── شخصية وطريقة الرد المخصصة من المستخدم ──
    personality_block = ""
    if custom_personality and custom_personality.strip():
        personality_block = (
            "\n\nThe user has customized your personality and reply style. "
            "Follow these instructions as long as they do not conflict with the JSON "
            "response format described below:\n" + custom_personality.strip() + "\n"
        )

    # ── معلومات يريد المستخدم أن تتذكرها ──
    memory_block = ""
    if custom_memory and custom_memory.strip():
        memory_block = (
            "\n\nHere is informations about the user that you should remember and take "
            "into account when replying:\n" + custom_memory.strip() + "\n"
        )

    # ── بروتوكول الرد الثابت (JSON) — لا يتغير ──
    protocol = (""" and you have to respond like this :
                
                Translate the user input into JSON. 
                intents: "order", "question", "chat".
                actions: "open", "search", "none".

                Examples:
                Input: "Open YouTube"
                Output: {"intent": "order", "action": "open", "target": "youtube", "link":"https://www.youtube.com/" , "query": "none" , "cause":"here explain why did you respond like that"}

                Input: "What is Linux?"
                Output: {"intent": "question", "action": "none", "target": "none", "query": "Linux" , "answer":"your answer" , "cause":"here explain why did you respond like that"}

                Input: " hfff , i really want to watch rick and morty on youtube .
                Output: {"intent": "order" , "action": "open" , "target": "youtube" , "link":"https://www.youtube.com/results?search_query=rick+and+morty" , "query": " rick and morty" , "cause":"here explain why did you respond like that"}
            
                Input: " how are you ? "
                Output: {"intent": "question", "action": "none", "target": "none", "query": "how are you" , "answer":"your answer" , "cause":"here explain why did you respond like that"}
                
                Input: "Hello "
                Output: {"intent": "chat", "action": "none", "target": "none", "query": "Hello" , "answer":"your answer" , "cause":"here explain why did you respond like that"}
                
                Input: "upload file"
                Output: {"intent": "order", "action": "uploading file", "target": "choose", "query": "none" , "answer":"your answer" , "cause":"here explain why did you respond like that"}

                Input: "explain communication engineering lecture1.pdf"
                Output: {"intent": "order", "action": "uploading file", "target": "communication engineering lecture1.pdf", "query": "none" , "answer":"your answer" , "cause":"here explain why did you respond like that"}

                Input: "make a report about optical fiber"
                Output: {"intent": "order", "action": "making report", "target": "optical fiber docx", "query": "optical fiber" , "cause":"here explain why did you respond like that"}

                Input: "convert -example- file to pdf"
                Output: {"intent": "order", "action": "converting file", "target": "example.docx", "query": "none" , "answer":"your answer" , "cause":"here explain why did you respond like that"}

                Input: "i want to convert a file to pdf"
                Output: {"intent": "order", "action": "converting file", "target": "choose", "query": "none" , "answer":"your answer" , "cause":"here explain why did you respond like that"}
                
                Input: "make an excel sheet for my students grades"
                Output: {"intent": "order", "action": "making excel", "target": "students grades.xlsx", "query": "students grades" , "cause":"here explain why did you respond like that"}
                
                Input: "make an excel from students.csv"
                Output: {"intent": "order", "action": "making excel from file", "target": "students.csv", "query": "convert this data to excel" , "cause":"..."}

                Input: "integrate x^2"
                Output: {"intent": "question", "action": "none", "target": "none", "query": "integrate x^2" , "answer": "$\\frac{x^3}{3} + C$" , "cause":"here explain why did you respond like that"}

                Input: "what is the derivative of sin(x)"
                Output: {"intent": "question", "action": "none", "target": "none", "query": "derivative of sin(x)" , "answer": "$\\cos(x)$" , "cause":"here explain why did you respond like that"}

                Input: "solve x^2 - 4 = 0"
                Output: {"intent": "question", "action": "none", "target": "none", "query": "solve x^2 - 4 = 0" , "answer": "$x = 2$ or $x = -2$" , "cause":"here explain why did you respond like that"}

                CRITICAL RULE: Any math calculation, equation, derivative, integral, limit, or
                numeric/algebraic question is ALWAYS intent "question" with the worked answer in
                the "answer" field — NEVER intent "order" and NEVER action "making excel" or
                "making excel from file". Only use "making excel" / "making excel from file" when
                the user explicitly asks for a spreadsheet, Excel file, ".xlsx", "sheet", or
                "spreadsheet", or explicitly wants tabular/grade/list data saved as a file.

                Input: user context.
                Output:

                """)

    return identity + personality_block + memory_block + protocol